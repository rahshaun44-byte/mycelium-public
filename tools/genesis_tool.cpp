// Operator CLI for generating and recovering the Shamir-shared genesis/unlock
// secret consumed by LocalNode::initialize_node / LocalNode::unlock_node over
// the mTLS IPC socket (see src/core/ipc_server.cpp). Kept in C++ and linked
// directly against the engine's own ShamirSecretSharing so the GF(256) field
// arithmetic can never drift from what the engine actually expects.
//
// Shard payloads are raw bytes and may contain any byte value, including ','
// and ':' — the characters the IPC wire format uses as delimiters. This tool
// always hex-encodes shard payloads, both in shard files and in the INIT|/
// UNLOCK| lines it prints, so a shard can never corrupt the wire framing.

#include "quantum-flex/crypto_shamir.hpp"

#include <openssl/rand.h>

#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

auto to_hex(const std::string& raw) -> std::string {
    std::ostringstream out;
    for (unsigned char byte : raw) {
        out << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(byte);
    }
    return out.str();
}

auto from_hex(const std::string& hex) -> std::string {
    if (hex.length() % 2 != 0) {
        throw std::runtime_error("Malformed hex payload (odd length)");
    }
    std::string raw;
    raw.reserve(hex.length() / 2);
    for (std::size_t i = 0; i < hex.length(); i += 2) {
        raw.push_back(static_cast<char>(std::stoi(hex.substr(i, 2), nullptr, 16)));
    }
    return raw;
}

auto get_flag(int argc, char** argv, const std::string& name, const std::string& fallback) -> std::string {
    for (int i = 2; i < argc - 1; ++i) {
        if (name == argv[i]) {
            return argv[i + 1];
        }
    }
    return fallback;
}

auto build_shard_line(const std::vector<quantumflex::crypto::SecretShard>& shards) -> std::string {
    std::ostringstream out;
    for (std::size_t i = 0; i < shards.size(); ++i) {
        if (i > 0) {
            out << ",";
        }
        out << static_cast<int>(shards[i].id) << ":" << to_hex(shards[i].payload);
    }
    return out.str();
}

auto cmd_split(int argc, char** argv) -> int {
    const auto total = static_cast<uint8_t>(std::stoi(get_flag(argc, argv, "--total", "5")));
    const auto threshold = static_cast<uint8_t>(std::stoi(get_flag(argc, argv, "--threshold", "3")));
    const std::string out_dir = get_flag(argc, argv, "--out-dir", ".");

    constexpr std::size_t SECRET_LEN = 32;
    std::string secret(SECRET_LEN, '\0');
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    if (RAND_bytes(reinterpret_cast<unsigned char*>(secret.data()), static_cast<int>(SECRET_LEN)) != 1) {
        std::cerr << "[!] RNG failure generating genesis secret\n";
        return 1;
    }

    const auto shards = quantumflex::crypto::ShamirSecretSharing::split_secret(secret, total, threshold);

    std::cout << "[+] Generated genesis secret. total=" << static_cast<int>(total)
              << " threshold=" << static_cast<int>(threshold) << "\n";

    for (const auto& shard : shards) {
        const std::string path = out_dir + "/shard_" + std::to_string(shard.id) + ".txt";
        std::ofstream file(path, std::ios::trunc);
        if (!file.is_open()) {
            std::cerr << "[!] Failed to open " << path << " for writing\n";
            return 1;
        }
        file << static_cast<int>(shard.id) << ":" << to_hex(shard.payload) << "\n";
        std::cout << "    -> wrote " << path << "\n";
    }

    std::vector<quantumflex::crypto::SecretShard> preview(shards.begin(), shards.begin() + threshold);
    std::cout << "\n[*] Distribute the shard_*.txt files to separate custodians/locations.\n"
              << "[*] Any " << static_cast<int>(threshold) << " of the " << static_cast<int>(total)
              << " are sufficient to genesis or unlock the node — keep them apart from each other\n"
              << "[*] and apart from QF_DATA_DIR, so a compromise of the running engine's filesystem\n"
              << "[*] access alone can't also recover the secret.\n\n"
              << "[*] Example INIT line (first " << static_cast<int>(threshold) << " shards):\n"
              << "INIT|" << build_shard_line(preview) << "\n";

    return 0;
}

auto cmd_recover(int argc, char** argv) -> int {
    const auto threshold = static_cast<uint8_t>(std::stoi(get_flag(argc, argv, "--threshold", "3")));
    const std::string shard_files_csv = get_flag(argc, argv, "--shards", "");
    if (shard_files_csv.empty()) {
        std::cerr << "[!] --shards <file1,file2,...> is required\n";
        return 1;
    }

    std::vector<quantumflex::crypto::SecretShard> shards;
    std::istringstream files_stream(shard_files_csv);
    std::string file_path;
    while (std::getline(files_stream, file_path, ',')) {
        std::ifstream file(file_path);
        if (!file.is_open()) {
            std::cerr << "[!] Failed to open shard file: " << file_path << "\n";
            return 1;
        }
        std::string line;
        std::getline(file, line);
        const std::size_t colon_pos = line.find(':');
        if (colon_pos == std::string::npos) {
            std::cerr << "[!] Malformed shard file: " << file_path << "\n";
            return 1;
        }
        const auto id = static_cast<uint8_t>(std::stoi(line.substr(0, colon_pos)));
        const std::string payload = from_hex(line.substr(colon_pos + 1));
        shards.push_back(quantumflex::crypto::SecretShard{.id = id, .payload = payload});
    }

    if (shards.size() < threshold) {
        std::cerr << "[!] Only " << shards.size() << " shard(s) provided; threshold is "
                  << static_cast<int>(threshold) << "\n";
        return 1;
    }

    // Local dry-run reconstruction, purely for operator confidence before sending
    // the UNLOCK| line — the engine performs its own independent recovery.
    const std::string recovered = quantumflex::crypto::ShamirSecretSharing::recover_secret(shards, threshold);
    std::cout << "[+] Local reconstruction succeeded. Recovered secret (hex): " << to_hex(recovered) << "\n\n"
              << "[*] Send this line over the mTLS IPC socket:\n"
              << "UNLOCK|" << build_shard_line(shards) << "\n";

    return 0;
}

} // namespace

auto main(int argc, char** argv) -> int {
    if (argc < 2) {
        std::cerr << "Usage:\n"
                  << "  qf_genesis_tool split [--total N] [--threshold K] [--out-dir DIR]\n"
                  << "  qf_genesis_tool recover --shards f1,f2,f3 [--threshold K]\n";
        return 1;
    }

    const std::string subcommand = argv[1];
    try {
        if (subcommand == "split") {
            return cmd_split(argc, argv);
        }
        if (subcommand == "recover") {
            return cmd_recover(argc, argv);
        }
    } catch (const std::exception& e) {
        std::cerr << "[!] " << e.what() << "\n";
        return 1;
    }

    std::cerr << "[!] Unknown subcommand: " << subcommand << "\n";
    return 1;
}
