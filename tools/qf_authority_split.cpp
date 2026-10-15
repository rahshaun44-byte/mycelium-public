// Generates a fresh 32-byte engine authority secret and splits it 3-of-5 with the
// engine's own ShamirSecretSharing. Every 3-share subset is recovered and compared
// before anything is emitted, so a bad split can never reach custody.
//
// Output: exactly five lines "<id>:<64 hex>\n" on stdout, and only when stdout is
// a pipe or file, never a terminal. The secret itself is never written anywhere.
// The intended reader is tools/qf_authority_ceremony.py, which seals each share
// with gpg in memory. Buffer cleansing is best effort, not a complete memory proof.
#include "quantum-flex/crypto_shamir.hpp"

#include <openssl/crypto.h>
#include <openssl/rand.h>

#include <array>
#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <sys/resource.h>
#include <unistd.h>
#include <vector>

namespace {

constexpr std::size_t kSecretSize = 32;
constexpr std::uint8_t kTotal = 5;
constexpr std::uint8_t kThreshold = 3;

struct SecretString {
    std::string bytes;
    ~SecretString() {
        if (!bytes.empty()) {
            OPENSSL_cleanse(bytes.data(), bytes.size());
        }
    }
};

struct SecretShares {
    std::vector<quantumflex::crypto::SecretShard> shares;
    ~SecretShares() {
        for (auto& share : shares) {
            if (!share.payload.empty()) {
                OPENSSL_cleanse(share.payload.data(), share.payload.size());
            }
        }
    }
};

auto write_all(std::string_view text) -> bool {
    std::size_t written = 0;
    while (written < text.size()) {
        const auto count = write(STDOUT_FILENO, text.data() + written, text.size() - written);
        if (count < 0 && errno == EINTR) {
            continue;
        }
        if (count <= 0) {
            return false;
        }
        written += static_cast<std::size_t>(count);
    }
    return true;
}

auto fail(std::string_view code) -> int {
    // Fixed codes only, on stderr, so nothing secret can leave via an error path.
    if (write(STDERR_FILENO, code.data(), code.size()) < 0) {
        return 2;
    }
    return 2;
}

auto run() -> int {
    if (isatty(STDOUT_FILENO) != 0) {
        return fail("ERROR_STDOUT_IS_TERMINAL\n");
    }

    SecretString secret;
    secret.bytes.assign(kSecretSize, '\0');
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    if (RAND_bytes(reinterpret_cast<unsigned char*>(secret.bytes.data()), static_cast<int>(kSecretSize)) != 1) {
        return fail("ERROR_RNG\n");
    }

    SecretShares split;
    split.shares = quantumflex::crypto::ShamirSecretSharing::split_secret(secret.bytes, kTotal, kThreshold);
    if (split.shares.size() != kTotal) {
        return fail("ERROR_SPLIT\n");
    }
    for (std::size_t index = 0; index < split.shares.size(); ++index) {
        if (split.shares[index].id != index + 1 || split.shares[index].payload.size() != kSecretSize) {
            return fail("ERROR_SPLIT\n");
        }
    }

    // All C(5,3) = 10 subsets must recover the same secret.
    for (std::size_t a = 0; a < kTotal; ++a) {
        for (std::size_t b = a + 1; b < kTotal; ++b) {
            for (std::size_t c = b + 1; c < kTotal; ++c) {
                SecretShares subset;
                subset.shares = {split.shares[a], split.shares[b], split.shares[c]};
                SecretString recovered;
                recovered.bytes = quantumflex::crypto::ShamirSecretSharing::recover_secret(subset.shares, kThreshold);
                if (recovered.bytes.size() != kSecretSize ||
                    CRYPTO_memcmp(recovered.bytes.data(), secret.bytes.data(), kSecretSize) != 0) {
                    return fail("ERROR_SUBSET_VERIFY\n");
                }
            }
        }
    }

    constexpr std::string_view kHex = "0123456789abcdef";
    SecretString output;
    output.bytes.reserve(kTotal * (2 + kSecretSize * 2 + 1));
    for (const auto& share : split.shares) {
        output.bytes.push_back(static_cast<char>('0' + share.id));
        output.bytes.push_back(':');
        for (const char raw : share.payload) {
            const auto value = static_cast<unsigned char>(raw);
            output.bytes.push_back(kHex[value >> 4U]);
            output.bytes.push_back(kHex[value & 0x0FU]);
        }
        output.bytes.push_back('\n');
    }
    return write_all(output.bytes) ? 0 : fail("ERROR_WRITE\n");
}

} // namespace

auto main(int argc, char** /*argv*/) -> int {
    const struct rlimit no_core{0, 0};
    if (setrlimit(RLIMIT_CORE, &no_core) != 0) {
        return fail("ERROR_INTERNAL\n");
    }
    if (argc != 1) {
        return fail("ERROR_USAGE\n");
    }
    try {
        return run();
    } catch (...) {
        return fail("ERROR_INTERNAL\n");
    }
}
