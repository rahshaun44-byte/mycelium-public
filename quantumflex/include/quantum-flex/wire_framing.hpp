#ifndef QUANTUM_FLEX_WIRE_FRAMING_HPP
#define QUANTUM_FLEX_WIRE_FRAMING_HPP

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace quantumflex::wire {

    // ── Protocol Constants ──────────────────────────────────────────────────
    constexpr uint32_t QFXK_MAGIC               = 0x5146584B; // ASCII "QFXK"
    constexpr std::size_t FRAME_HEADER_SIZE     = 16;
    constexpr std::size_t MAX_CHUNK_PAYLOAD     = 1400;       // Safe for 1500 MTU
    constexpr std::size_t MAX_CHUNKS_PER_MESSAGE = 64;         // Hard ceiling on frame count
    constexpr std::size_t MAX_REASSEMBLY_SESSIONS = 64;       // Bounded state ceiling
    constexpr uint32_t DEFAULT_TIMEOUT_MS       = 1200;       // Strict Gatekeeper SLA
    constexpr std::size_t MAX_MESSAGE_BYTES     = 32768;      // 32 KB max message cap

    // ── Message Types ───────────────────────────────────────────────────────
    constexpr uint8_t MSG_INIT       = 0x01; // Legacy control line encapsulation
    constexpr uint8_t MSG_KEM_PK     = 0x02; // Hybrid Public Key (15664 bytes)
    constexpr uint8_t MSG_KEM_CT     = 0x03; // Hybrid Ciphertext (15776 bytes)
    constexpr uint8_t MSG_KEM_ACK    = 0x04; // Successful session establishment
    // Distinct IDs prevent legacy Frodo clients interpreting ML-KEM bytes.
    constexpr uint8_t MSG_MLKEM768_PK = 0x12; // 1184-byte ek; empty request
    constexpr uint8_t MSG_MLKEM768_CT = 0x13; // 1088-byte ciphertext
    constexpr uint8_t MSG_MLKEM768_CONFIRM = 0x14; // 32-byte HMAC, never the secret
    constexpr uint8_t MSG_KEM_REJECT = 0x7F; // Constant-time fail-closed reject

    // ── Wire Frame Header (16 Bytes, Strictly Aligned) ──────────────────────
#pragma pack(push, 1) // Enforce strict 1-byte alignment
    struct QFXKHeader {
        uint8_t magic[2];
        uint8_t version;
        uint8_t msg_type;
        uint32_t sequence_id;
        uint32_t length;
        uint32_t flags;
    };
#pragma pack(pop)

    static_assert(sizeof(QFXKHeader) == 16, "QFXKHeader must be exactly 16 bytes");
    
    constexpr std::size_t MAX_PAYLOAD_SIZE = 16384; // 15792 (FrodoKEM-976-AES CT) + overhead. Represents maximum size of the payload field, NOT the entire frame.

    // Anti-rollover bound (same numeric value as QF_WIRE_MAX_SEQ_ID in mycelium's
    // verified_core C ABI). Owned here so the codec does not depend on that ABI.
    constexpr uint32_t MAX_SEQ_ID = 0xFFFFFFFEU;


    enum class QFXKAlgorithm : uint8_t {
        FRODOKEM_976_AES = 0x01,
        FRODOKEM_976_SHAKE = 0x02,
        EFRODOKEM_976 = 0x03
    };



    struct ReassembledMessage {
        uint8_t msg_type{0};
        std::vector<uint8_t> payload;
    };

    // ── Utility Functions ───────────────────────────────────────────────────
    [[nodiscard]] auto compute_crc32(const uint8_t* data, std::size_t len) -> uint32_t;

    [[nodiscard]] auto serialize_frame(
        uint8_t msg_type,
        uint32_t seq_id,
        const uint8_t* payload,
        uint32_t length
    ) -> std::vector<uint8_t>;

    // ── Stream Reassembly State ─────────────────────────────────────────────
    struct ReassemblyState {
        std::chrono::steady_clock::time_point start_time;
        uint32_t target_length;
        std::vector<uint8_t> buffer;
    };

    class QuantumFlexReassemblyPool {
    private:
        std::unordered_map<std::string, ReassemblyState> pool;
        const std::chrono::milliseconds timeout_limit{1200};
        const std::size_t max_pool_size{100}; // DDoS protection

    public:
        // Accumulates stream bytes. Returns true if the full frame is ready.
        bool ingest_stream(const std::string& session_id, const uint8_t* data, std::size_t len, std::vector<uint8_t>& out_payload, uint8_t& out_msg_type);
        
        void drop_session(const std::string& session_id);
        void enforce_timeouts();
    };
} // namespace quantumflex::wire

#endif // QUANTUM_FLEX_WIRE_FRAMING_HPP
