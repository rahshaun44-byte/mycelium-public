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
    constexpr uint8_t MSG_KEM_REJECT = 0x7F; // Constant-time fail-closed reject

    // ── Wire Frame Header (16 Bytes, Big-Endian) ────────────────────────────
    struct FrameHeader {
        uint32_t magic{0};
        uint8_t  msg_type{0};
        uint8_t  flags{0};
        uint16_t seq_id{0};
        uint16_t total_chunks{0};
        uint16_t chunk_len{0};
        uint32_t checksum{0}; // IEEE 802.3 CRC32
    };

    enum class ReassemblyStatus {
        IN_PROGRESS,
        COMPLETE,
        CHECKSUM_ERROR,
        PROTOCOL_ERROR,
        CAPACITY_EXCEEDED,
        TIMEOUT_PURGED
    };

    struct ReassembledMessage {
        uint8_t msg_type{0};
        std::vector<uint8_t> payload;
    };

    // ── Utility Functions ───────────────────────────────────────────────────
    [[nodiscard]] auto compute_crc32(const uint8_t* data, std::size_t len) -> uint32_t;

    [[nodiscard]] auto serialize_frame(
        uint8_t msg_type,
        uint16_t seq_id,
        uint16_t total_chunks,
        const uint8_t* payload,
        uint16_t chunk_len
    ) -> std::vector<uint8_t>;

    [[nodiscard]] auto parse_frame_header(
        const uint8_t* data,
        std::size_t len
    ) -> std::optional<FrameHeader>;

    [[nodiscard]] auto fragment_payload(
        uint8_t msg_type,
        const std::vector<uint8_t>& payload,
        std::size_t chunk_size = MAX_CHUNK_PAYLOAD
    ) -> std::vector<std::vector<uint8_t>>;

    // ── Gatekeeper Reassembly Manager (Fail-Closed & Bounded RAM) ───────────
    class GatekeeperReassemblyManager {
    public:
        explicit GatekeeperReassemblyManager(
            std::size_t max_sessions = MAX_REASSEMBLY_SESSIONS,
            uint32_t timeout_ms = DEFAULT_TIMEOUT_MS
        );
        ~GatekeeperReassemblyManager();

        GatekeeperReassemblyManager(const GatekeeperReassemblyManager&) = delete;
        auto operator=(const GatekeeperReassemblyManager&) -> GatekeeperReassemblyManager& = delete;
        GatekeeperReassemblyManager(GatekeeperReassemblyManager&&) = delete;
        auto operator=(GatekeeperReassemblyManager&&) -> GatekeeperReassemblyManager& = delete;

        auto ingest_chunk(
            const std::string& session_id,
            const uint8_t* frame_data,
            std::size_t frame_len,
            ReassembledMessage& out_msg
        ) -> ReassemblyStatus;

        void sweep_expired_sessions(std::vector<std::string>& out_purged_sessions);

        void drop_session(const std::string& session_id);

        [[nodiscard]] auto active_session_count() const -> std::size_t;
        [[nodiscard]] auto evicted_session_count() const -> std::size_t;

    private:
        struct SessionContext {
            uint8_t msg_type{0};
            uint16_t total_chunks{0};
            std::size_t received_count{0};
            std::size_t total_bytes{0};
            std::vector<bool> received_mask;
            std::vector<std::vector<uint8_t>> chunks;
            std::chrono::steady_clock::time_point created_at;

            ~SessionContext();
        };

        std::size_t max_sessions_;
        std::size_t evicted_count_{0};
        uint32_t timeout_ms_;
        std::unordered_map<std::string, SessionContext> sessions_;
    };

} // namespace quantumflex::wire

#endif // QUANTUM_FLEX_WIRE_FRAMING_HPP
