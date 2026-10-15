// Read-only compatibility check for the private engine's legacy ledger envelope.
// No recovered secret or share is printed, written to disk, or sent over IPC.
#include "quantum-flex/crypto_shamir.hpp"

#include <openssl/crypto.h>
#include <openssl/evp.h>

#include <array>
#include <cerrno>
#include <charconv>
#include <cstdint>
#include <fcntl.h>
#include <memory>
#include <string>
#include <string_view>
#include <sys/resource.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

namespace {

constexpr std::size_t kShareCount = 3;
constexpr std::size_t kSecretSize = 32;
constexpr std::size_t kShareLineSize = 67; // id, colon, 64 hex characters, LF.
constexpr std::size_t kShareInputSize = kShareCount * kShareLineSize;
constexpr std::size_t kMaxLedgerSize = 512;

class FileDescriptor {
public:
    explicit FileDescriptor(int descriptor) : descriptor_(descriptor) {}
    ~FileDescriptor() {
        if (descriptor_ >= 0) {
            close(descriptor_);
        }
    }
    FileDescriptor(const FileDescriptor&) = delete;
    auto operator=(const FileDescriptor&) -> FileDescriptor& = delete;
    [[nodiscard]] auto get() const -> int { return descriptor_; }
private:
    int descriptor_;
};

template <std::size_t Size>
struct SecretArray {
    std::array<unsigned char, Size> bytes{};
    ~SecretArray() { OPENSSL_cleanse(bytes.data(), bytes.size()); }
};

struct SecretString {
    std::string bytes;
    ~SecretString() {
        if (!bytes.empty()) {
            OPENSSL_cleanse(bytes.data(), bytes.size());
        }
    }
};

struct SecretShares {
    std::vector<quantumflex::crypto::SecretShard> shares{kShareCount};
    ~SecretShares() {
        for (auto& share : shares) {
            if (!share.payload.empty()) {
                OPENSSL_cleanse(share.payload.data(), share.payload.size());
            }
        }
    }
};

struct ReadResult {
    std::size_t size{0};
    bool eof{false};
    bool failed{false};
};

// The extra byte in each caller's buffer detects oversize data without an
// unbounded allocation or an unbounded read of attacker-controlled input.
auto bounded_read(int descriptor, unsigned char* buffer, std::size_t capacity) -> ReadResult {
    ReadResult result;
    while (result.size < capacity) {
        const auto count = read(descriptor, buffer + result.size, capacity - result.size);
        if (count < 0) {
            if (errno == EINTR) {
                continue;
            }
            result.failed = true;
            break;
        }
        if (count == 0) {
            result.eof = true;
            break;
        }
        result.size += static_cast<std::size_t>(count);
    }
    return result;
}

auto hex_value(unsigned char value) -> int {
    if (value >= '0' && value <= '9') {
        return value - '0';
    }
    if (value >= 'a' && value <= 'f') {
        return value - 'a' + 10;
    }
    if (value >= 'A' && value <= 'F') {
        return value - 'A' + 10;
    }
    return -1;
}

auto lowercase_digest(std::string_view value) -> bool {
    if (value.size() != kSecretSize * 2) {
        return false;
    }
    for (const unsigned char character : value) {
        if (!((character >= '0' && character <= '9') ||
              (character >= 'a' && character <= 'f'))) {
            return false;
        }
    }
    return true;
}

auto timestamp_valid(std::string_view value) -> bool {
    if (value.empty() || value.size() > 20 || (value.size() > 1 && value[0] == '0')) {
        return false;
    }
    for (const unsigned char character : value) {
        if (character < '0' || character > '9') {
            return false;
        }
    }
    std::uint64_t timestamp{0};
    const auto result = std::from_chars(value.data(), value.data() + value.size(), timestamp);
    return result.ec == std::errc{} && result.ptr == value.data() + value.size();
}

struct Ledger {
    std::string payload;
    std::array<unsigned char, kSecretSize> signature{};
};

auto parse_ledger(std::string_view bytes, Ledger& ledger) -> bool {
    std::array<std::string_view, 4> lines{};
    std::size_t position = 0;
    for (auto& line : lines) {
        const auto end = bytes.find('\n', position);
        if (end == std::string_view::npos) {
            return false;
        }
        line = bytes.substr(position, end - position);
        position = end + 1;
    }
    if (position != bytes.size() || !lines[0].starts_with("STATE_ROOT|") ||
        !lines[1].starts_with("TIMESTAMP|") ||
        !lines[2].starts_with("LEDGER_SIGNATURE|") || lines[3] != "STATUS|ACTIVE") {
        return false;
    }
    const auto root = lines[0].substr(std::string_view("STATE_ROOT|").size());
    const auto timestamp = lines[1].substr(std::string_view("TIMESTAMP|").size());
    const auto signature = lines[2].substr(std::string_view("LEDGER_SIGNATURE|").size());
    if (!lowercase_digest(root) || !timestamp_valid(timestamp) || !lowercase_digest(signature)) {
        return false;
    }
    for (std::size_t index = 0; index < kSecretSize; ++index) {
        const auto high = hex_value(static_cast<unsigned char>(signature[index * 2]));
        const auto low = hex_value(static_cast<unsigned char>(signature[index * 2 + 1]));
        ledger.signature[index] = static_cast<unsigned char>((high << 4) | low);
    }
    ledger.payload = std::string(lines[0]) + "\n" + std::string(lines[1]) + "\n";
    return true;
}

auto parse_shares(const SecretArray<kShareInputSize + 1>& input, SecretShares& output) -> bool {
    std::array<bool, 6> seen{};
    for (std::size_t index = 0; index < kShareCount; ++index) {
        const auto* line = input.bytes.data() + index * kShareLineSize;
        if (line[0] < '1' || line[0] > '5' || line[1] != ':' || line[66] != '\n') {
            return false;
        }
        const auto id = static_cast<unsigned char>(line[0] - '0');
        if (seen[id]) {
            return false;
        }
        seen[id] = true;
        auto& share = output.shares[index];
        share.id = id;
        share.payload.resize(kSecretSize);
        for (std::size_t byte = 0; byte < kSecretSize; ++byte) {
            const auto high = hex_value(line[2 + byte * 2]);
            const auto low = hex_value(line[3 + byte * 2]);
            if (high < 0 || low < 0) {
                return false;
            }
            share.payload[byte] = static_cast<char>((high << 4) | low);
        }
    }
    return true;
}

struct Verdict {
    int code;
    std::string_view text;
};

auto check(const char* ledger_path) -> Verdict {
    const FileDescriptor descriptor(open(ledger_path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK));
    if (descriptor.get() < 0) {
        return {2, "ERROR_LEDGER_IO\n"};
    }
    struct stat metadata{};
    if (fstat(descriptor.get(), &metadata) != 0 || !S_ISREG(metadata.st_mode)) {
        return {2, "ERROR_LEDGER_IO\n"};
    }
    if (metadata.st_size <= 0 || metadata.st_size > static_cast<off_t>(kMaxLedgerSize)) {
        return {2, "ERROR_LEDGER\n"};
    }
    std::array<unsigned char, kMaxLedgerSize + 1> ledger_input{};
    const auto ledger_read = bounded_read(descriptor.get(), ledger_input.data(), ledger_input.size());
    if (ledger_read.failed) {
        return {2, "ERROR_LEDGER_IO\n"};
    }
    Ledger ledger;
    if (!ledger_read.eof || ledger_read.size > kMaxLedgerSize ||
        !parse_ledger(std::string_view(reinterpret_cast<const char*>(ledger_input.data()),
                                      ledger_read.size), ledger)) {
        return {2, "ERROR_LEDGER\n"};
    }

    SecretArray<kShareInputSize + 1> input;
    const auto share_read = bounded_read(STDIN_FILENO, input.bytes.data(), input.bytes.size());
    SecretShares shards;
    if (share_read.failed || !share_read.eof || share_read.size != kShareInputSize ||
        !parse_shares(input, shards)) {
        return {2, "ERROR_SHARES\n"};
    }
    SecretString recovered;
    recovered.bytes = quantumflex::crypto::ShamirSecretSharing::recover_secret(shards.shares, kShareCount);
    if (recovered.bytes.size() != kSecretSize) {
        return {2, "ERROR_INTERNAL\n"};
    }
    const std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> digest_context(
        EVP_MD_CTX_new(), &EVP_MD_CTX_free);
    SecretArray<kSecretSize> digest;
    unsigned int digest_size = 0;
    // Two updates hash the exact same bytes as payload + raw recovered salt,
    // without creating another copy of the recovered salt in a combined string.
    if (!digest_context || EVP_DigestInit_ex(digest_context.get(), EVP_sha256(), nullptr) != 1 ||
        EVP_DigestUpdate(digest_context.get(), ledger.payload.data(), ledger.payload.size()) != 1 ||
        EVP_DigestUpdate(digest_context.get(), recovered.bytes.data(), recovered.bytes.size()) != 1 ||
        EVP_DigestFinal_ex(digest_context.get(), digest.bytes.data(), &digest_size) != 1 ||
        digest_size != kSecretSize) {
        return {2, "ERROR_INTERNAL\n"};
    }
    const bool matches = CRYPTO_memcmp(digest.bytes.data(), ledger.signature.data(), kSecretSize) == 0;
    return matches ? Verdict{0, "MATCH\n"} : Verdict{1, "MISMATCH\n"};
}

auto report(Verdict verdict) -> int {
    std::size_t written = 0;
    while (written < verdict.text.size()) {
        const auto count = write(STDOUT_FILENO, verdict.text.data() + written, verdict.text.size() - written);
        if (count < 0 && errno == EINTR) {
            continue;
        }
        if (count <= 0) {
            return 2;
        }
        written += static_cast<std::size_t>(count);
    }
    return verdict.code;
}

} // namespace

auto main(int argc, char** argv) -> int {
    // This affects only this checker process and its children; no system setting
    // is changed. Buffer cleansing is best effort, not a complete memory proof.
    const struct rlimit no_core{0, 0};
    if (setrlimit(RLIMIT_CORE, &no_core) != 0) {
        return report({2, "ERROR_INTERNAL\n"});
    }
    if (argc != 3 || std::string_view(argv[1]) != "--ledger" || argv[2][0] == '\0') {
        return report({2, "ERROR_USAGE\n"});
    }
    try {
        return report(check(argv[2]));
    } catch (...) {
        // Exception messages can contain sensitive data. Only fixed codes leave
        // this process, including on allocation and cryptographic failures.
        return report({2, "ERROR_INTERNAL\n"});
    }
}
