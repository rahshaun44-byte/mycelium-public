#include "quantum-flex/wire_framing.hpp"

#include <openssl/crypto.h>

#include <array>
#include <chrono>
#include <cstring>
#include <stdexcept>

namespace quantumflex::wire {

    // ── IEEE 802.3 CRC32 Implementation ─────────────────────────────────────
    namespace {
        constexpr auto generate_crc32_table() -> std::array<uint32_t, 256> {
            std::array<uint32_t, 256> table{};
            for (uint32_t i = 0; i < 256; ++i) {
                uint32_t crc = i;
                for (int j = 0; j < 8; ++j) {
                    crc = (crc & 1) ? (crc >> 1) ^ 0xEDB88320U : (crc >> 1);
                }
                table[i] = crc;
            }
            return table;
        }

        constexpr auto CRC32_TABLE = generate_crc32_table();
    } // namespace

    auto compute_crc32(const uint8_t* data, std::size_t len) -> uint32_t {
        uint32_t crc = 0xFFFFFFFFU;
        for (std::size_t i = 0; i < len; ++i) {
            crc = (crc >> 8) ^ CRC32_TABLE[(crc ^ data[i]) & 0xFFU];
        }
        return crc ^ 0xFFFFFFFFU;
    }

    // ── Frame Serialization & Parsing ───────────────────────────────────────

    auto serialize_frame(
        uint8_t msg_type,
        uint16_t seq_id,
        uint16_t total_chunks,
        const uint8_t* payload,
        uint16_t chunk_len
    ) -> std::vector<uint8_t> {
        std::vector<uint8_t> frame(FRAME_HEADER_SIZE + chunk_len);

        // Magic (0x5146584B)
        frame[0] = static_cast<uint8_t>((QFXK_MAGIC >> 24) & 0xFF);
        frame[1] = static_cast<uint8_t>((QFXK_MAGIC >> 16) & 0xFF);
        frame[2] = static_cast<uint8_t>((QFXK_MAGIC >> 8) & 0xFF);
        frame[3] = static_cast<uint8_t>(QFXK_MAGIC & 0xFF);

        frame[4] = msg_type;
        frame[5] = 0x00; // Flags

        // seq_id
        frame[6] = static_cast<uint8_t>((seq_id >> 8) & 0xFF);
        frame[7] = static_cast<uint8_t>(seq_id & 0xFF);

        // total_chunks
        frame[8] = static_cast<uint8_t>((total_chunks >> 8) & 0xFF);
        frame[9] = static_cast<uint8_t>(total_chunks & 0xFF);

        // chunk_len
        frame[10] = static_cast<uint8_t>((chunk_len >> 8) & 0xFF);
        frame[11] = static_cast<uint8_t>(chunk_len & 0xFF);

        // Checksum of payload
        uint32_t csum = (payload != nullptr && chunk_len > 0) ? compute_crc32(payload, chunk_len) : 0;
        frame[12] = static_cast<uint8_t>((csum >> 24) & 0xFF);
        frame[13] = static_cast<uint8_t>((csum >> 16) & 0xFF);
        frame[14] = static_cast<uint8_t>((csum >> 8) & 0xFF);
        frame[15] = static_cast<uint8_t>(csum & 0xFF);

        if (payload != nullptr && chunk_len > 0) {
            std::memcpy(frame.data() + FRAME_HEADER_SIZE, payload, chunk_len);
        }

        return frame;
    }

    auto parse_frame_header(
        const uint8_t* data,
        std::size_t len
    ) -> std::optional<FrameHeader> {
        if (data == nullptr || len < FRAME_HEADER_SIZE) {
            return std::nullopt;
        }

        FrameHeader h;
        h.magic = (static_cast<uint32_t>(data[0]) << 24) |
                  (static_cast<uint32_t>(data[1]) << 16) |
                  (static_cast<uint32_t>(data[2]) << 8)  |
                  static_cast<uint32_t>(data[3]);

        if (h.magic != QFXK_MAGIC) {
            return std::nullopt;
        }

        h.msg_type     = data[4];
        h.flags        = data[5];
        h.seq_id       = static_cast<uint16_t>((static_cast<uint16_t>(data[6]) << 8) | data[7]);
        h.total_chunks = static_cast<uint16_t>((static_cast<uint16_t>(data[8]) << 8) | data[9]);
        h.chunk_len    = static_cast<uint16_t>((static_cast<uint16_t>(data[10]) << 8) | data[11]);
        h.checksum     = (static_cast<uint32_t>(data[12]) << 24) |
                         (static_cast<uint32_t>(data[13]) << 16) |
                         (static_cast<uint32_t>(data[14]) << 8)  |
                         static_cast<uint32_t>(data[15]);

        return h;
    }

    auto fragment_payload(
        uint8_t msg_type,
        const std::vector<uint8_t>& payload,
        std::size_t chunk_size
    ) -> std::vector<std::vector<uint8_t>> {
        if (chunk_size == 0 || chunk_size > MAX_CHUNK_PAYLOAD) {
            chunk_size = MAX_CHUNK_PAYLOAD;
        }

        if (payload.empty()) {
            return {serialize_frame(msg_type, 0, 1, nullptr, 0)};
        }

        const std::size_t total_chunks = (payload.size() + chunk_size - 1) / chunk_size;
        std::vector<std::vector<uint8_t>> frames;
        frames.reserve(total_chunks);

        for (std::size_t i = 0; i < total_chunks; ++i) {
            const std::size_t offset = i * chunk_size;
            const std::size_t len = std::min(chunk_size, payload.size() - offset);
            frames.push_back(serialize_frame(
                msg_type,
                static_cast<uint16_t>(i),
                static_cast<uint16_t>(total_chunks),
                payload.data() + offset,
                static_cast<uint16_t>(len)
            ));
        }

        return frames;
    }

    // ── GatekeeperReassemblyManager ─────────────────────────────────────────

    GatekeeperReassemblyManager::SessionContext::~SessionContext() {
        for (auto& chunk : chunks) {
            if (!chunk.empty()) {
                OPENSSL_cleanse(chunk.data(), chunk.size());
            }
        }
    }

    GatekeeperReassemblyManager::GatekeeperReassemblyManager(
        std::size_t max_sessions,
        uint32_t timeout_ms
    ) : max_sessions_(max_sessions), timeout_ms_(timeout_ms) {}

    GatekeeperReassemblyManager::~GatekeeperReassemblyManager() = default;

    auto GatekeeperReassemblyManager::ingest_chunk(
        const std::string& session_id,
        const uint8_t* frame_data,
        std::size_t frame_len,
        ReassembledMessage& out_msg
    ) -> ReassemblyStatus {
        if (frame_data == nullptr || frame_len < FRAME_HEADER_SIZE) {
            return ReassemblyStatus::PROTOCOL_ERROR;
        }

        auto header_opt = parse_frame_header(frame_data, frame_len);
        if (!header_opt.has_value()) {
            return ReassemblyStatus::PROTOCOL_ERROR;
        }

        const FrameHeader& h = header_opt.value();
        if (frame_len < FRAME_HEADER_SIZE + h.chunk_len) {
            return ReassemblyStatus::PROTOCOL_ERROR;
        }

        const uint8_t* payload_ptr = frame_data + FRAME_HEADER_SIZE;
        uint32_t computed_csum = compute_crc32(payload_ptr, h.chunk_len);
        if (computed_csum != h.checksum) {
            return ReassemblyStatus::CHECKSUM_ERROR;
        }

        if (h.total_chunks == 0 || h.total_chunks > MAX_CHUNKS_PER_MESSAGE || 
            h.seq_id >= h.total_chunks || h.chunk_len > MAX_CHUNK_PAYLOAD) {
            return ReassemblyStatus::PROTOCOL_ERROR;
        }

        auto now = std::chrono::steady_clock::now();

        // Check if session exists
        auto it = sessions_.find(session_id);
        if (it == sessions_.end()) {
            if (sessions_.size() >= max_sessions_) {
                std::vector<std::string> purged;
                sweep_expired_sessions(purged);
                if (sessions_.size() >= max_sessions_) {
                    // Evict the oldest session to prevent state exhaustion starvation
                    auto oldest_it = sessions_.begin();
                    for (auto sit = sessions_.begin(); sit != sessions_.end(); ++sit) {
                        if (sit->second.created_at < oldest_it->second.created_at) {
                            oldest_it = sit;
                        }
                    }
                    sessions_.erase(oldest_it);
                    evicted_count_++;
                }
            }

            SessionContext ctx;
            ctx.msg_type = h.msg_type;
            ctx.total_chunks = h.total_chunks;
            ctx.received_count = 0;
            ctx.total_bytes = 0;
            ctx.received_mask.assign(h.total_chunks, false);
            ctx.chunks.resize(h.total_chunks);
            ctx.created_at = now;

            it = sessions_.emplace(session_id, std::move(ctx)).first;
        }

        SessionContext& ctx = it->second;

        // Check timeout
        auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(now - ctx.created_at).count();
        if (elapsed_ms > timeout_ms_) {
            sessions_.erase(it);
            return ReassemblyStatus::TIMEOUT_PURGED;
        }

        // Validate consistency across chunks
        if (ctx.msg_type != h.msg_type || ctx.total_chunks != h.total_chunks) {
            sessions_.erase(it);
            return ReassemblyStatus::PROTOCOL_ERROR;
        }

        // Idempotent duplicate check
        if (ctx.received_mask[h.seq_id]) {
            return ReassemblyStatus::IN_PROGRESS; // Already received
        }

        ctx.chunks[h.seq_id].assign(payload_ptr, payload_ptr + h.chunk_len);
        ctx.received_mask[h.seq_id] = true;
        ctx.received_count++;
        ctx.total_bytes += h.chunk_len;

        if (ctx.total_bytes > MAX_MESSAGE_BYTES) {
            sessions_.erase(it);
            return ReassemblyStatus::PROTOCOL_ERROR; // Overflow guard
        }

        // Check for complete assembly
        if (ctx.received_count == ctx.total_chunks) {
            out_msg.msg_type = ctx.msg_type;
            out_msg.payload.reserve(ctx.total_bytes);
            for (const auto& chunk : ctx.chunks) {
                out_msg.payload.insert(out_msg.payload.end(), chunk.begin(), chunk.end());
            }

            sessions_.erase(it);
            return ReassemblyStatus::COMPLETE;
        }

        return ReassemblyStatus::IN_PROGRESS;
    }

    void GatekeeperReassemblyManager::sweep_expired_sessions(std::vector<std::string>& out_purged_sessions) {
        auto now = std::chrono::steady_clock::now();
        for (auto it = sessions_.begin(); it != sessions_.end();) {
            auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(now - it->second.created_at).count();
            if (elapsed_ms > timeout_ms_) {
                out_purged_sessions.push_back(it->first);
                it = sessions_.erase(it);
            } else {
                ++it;
            }
        }
    }

    void GatekeeperReassemblyManager::drop_session(const std::string& session_id) {
        sessions_.erase(session_id);
    }

    auto GatekeeperReassemblyManager::active_session_count() const -> std::size_t {
        return sessions_.size();
    }

    auto GatekeeperReassemblyManager::evicted_session_count() const -> std::size_t {
        return evicted_count_;
    }

} // namespace quantumflex::wire
