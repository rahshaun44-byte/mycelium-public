#include "quantum-flex/verified_core.h"
#include "quantum-flex/wire_framing.hpp"

#include <openssl/crypto.h>

#include <array>
#include <chrono>
#include <cstring>
#include <arpa/inet.h>
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
        uint32_t seq_id,
        const uint8_t* payload,
        uint32_t length
    ) -> std::vector<uint8_t> {
        std::vector<uint8_t> frame(sizeof(QFXKHeader) + length);

        QFXKHeader header;
        header.magic[0] = 'Q';
        header.magic[1] = 'F';
        header.version = 1;
        header.msg_type = msg_type;
        header.sequence_id = htonl(seq_id);
        header.length = htonl(length);
        header.flags = htonl(0);

        std::memcpy(frame.data(), &header, sizeof(QFXKHeader));

        if (payload != nullptr && length > 0) {
            std::memcpy(frame.data() + sizeof(QFXKHeader), payload, length);
        }

        return frame;
    }

    // ── QuantumFlexReassemblyPool ───────────────────────────────────────────

    bool QuantumFlexReassemblyPool::ingest_stream(const std::string& session_id, const uint8_t* data, std::size_t len, std::vector<uint8_t>& out_payload, uint8_t& out_msg_type) {
        if (len == 0) return false;
        auto now = std::chrono::steady_clock::now();

        if (pool.find(session_id) == pool.end()) {
            if (pool.size() >= max_pool_size) {
                // DDoS protection: evict oldest
                auto oldest_it = pool.begin();
                for (auto it = pool.begin(); it != pool.end(); ++it) {
                    if (it->second.start_time < oldest_it->second.start_time) {
                        oldest_it = it;
                    }
                }
                pool.erase(oldest_it);
            }
            pool[session_id] = {now, 0, {}};
        }

        auto& state = pool[session_id];
        
        // Append data to buffer
        state.buffer.insert(state.buffer.end(), data, data + len);

        // Do we have a full header?
        if (state.buffer.size() < sizeof(QFXKHeader)) {
            return false; // Still waiting for header
        }

        QFXKHeader header;
        std::memcpy(&header, state.buffer.data(), sizeof(QFXKHeader));
        
        // Endianness conversion for header fields
        uint32_t seq = ntohl(header.sequence_id);
        uint32_t payload_length = ntohl(header.length);

        // Verified Core Invariant: Enforce anti-rollover sequence bound (Theorem 5)
        if (seq >= QF_WIRE_MAX_SEQ_ID) {
            pool.erase(session_id);
            return false; // Fail closed on sequence exhaustion
        }

        // The ML-KEM public-key request is intentionally empty. Legacy empty
        // frames remain invalid; validate the header before dispatching.
        const bool empty_allowed = header.msg_type == MSG_MLKEM768_PK || header.msg_type == MSG_KEM_REJECT;
        if (header.magic[0] != 'Q' || header.magic[1] != 'F' || header.version != 1 ||
            header.flags != 0 || (payload_length == 0 && !empty_allowed) || payload_length > MAX_PAYLOAD_SIZE) {
            pool.erase(session_id);
            return false; // Fail secure
        }

        state.target_length = sizeof(QFXKHeader) + payload_length;

        // Do we have the full payload?
        if (state.buffer.size() >= state.target_length) {
            out_msg_type = header.msg_type;
            out_payload.assign(state.buffer.begin() + sizeof(QFXKHeader), state.buffer.begin() + state.target_length);
            pool.erase(session_id);
            return true;
        }

        return false;
    }

    void QuantumFlexReassemblyPool::drop_session(const std::string& session_id) {
        pool.erase(session_id);
    }

    void QuantumFlexReassemblyPool::enforce_timeouts() {
        auto now = std::chrono::steady_clock::now();
        for (auto it = pool.begin(); it != pool.end(); ) {
            if (std::chrono::duration_cast<std::chrono::milliseconds>(now - it->second.start_time) > timeout_limit) {
                it = pool.erase(it);
            } else {
                ++it;
            }
        }
    }
} // namespace quantumflex::wire
