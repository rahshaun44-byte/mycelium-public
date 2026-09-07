#include "quantum-flex/wire_framing.hpp"

#include <cassert>
#include <iostream>
#include <vector>

int main() {
    using namespace quantumflex::wire;
    std::cout << "[TEST] ── Starting Wire Framing & Gatekeeper Reassembly Tests ──\n";

    // 1. Single Frame Serialization & Parse
    std::vector<uint8_t> payload = {0x01, 0x02, 0x03, 0x04, 0x05};
    auto frame = serialize_frame(MSG_KEM_ACK, 0, 1, payload.data(), payload.size());
    assert(frame.size() == FRAME_HEADER_SIZE + payload.size());

    auto header = parse_frame_header(frame.data(), frame.size());
    assert(header.has_value());
    assert(header->magic == QFXK_MAGIC);
    assert(header->msg_type == MSG_KEM_ACK);
    assert(header->seq_id == 0);
    assert(header->total_chunks == 1);
    assert(header->chunk_len == 5);
    std::cout << "[PASS] Invariant 1: Single frame header parse byte-accurate!\n";

    // 2. Large Multi-Chunk Fragmentation (Frodo-976 Ciphertext size: 15,776 bytes)
    std::vector<uint8_t> large_ct(15776);
    for (std::size_t i = 0; i < large_ct.size(); ++i) {
        large_ct[i] = static_cast<uint8_t>(i & 0xFF);
    }

    auto chunks = fragment_payload(MSG_KEM_CT, large_ct, MAX_CHUNK_PAYLOAD);
    std::cout << "[+] Fragmented " << large_ct.size() << " bytes into " << chunks.size() << " chunks (each <= 1416 B)\n";
    assert(chunks.size() == 12); // 15776 / 1400 = 11.26 -> 12 chunks

    // 3. Gatekeeper Reassembly (Out of Order Delivery)
    GatekeeperReassemblyManager mgr;
    ReassembledMessage out_msg;
    const std::string session_id = "session_test_001";

    // Feed even chunks first, then odd chunks
    for (std::size_t i = 0; i < chunks.size(); i += 2) {
        auto status = mgr.ingest_chunk(session_id, chunks[i].data(), chunks[i].size(), out_msg);
        assert(status == ReassemblyStatus::IN_PROGRESS);
    }
    for (std::size_t i = 1; i < chunks.size(); i += 2) {
        auto status = mgr.ingest_chunk(session_id, chunks[i].data(), chunks[i].size(), out_msg);
        if (i == chunks.size() - 1) {
            assert(status == ReassemblyStatus::COMPLETE);
        } else {
            assert(status == ReassemblyStatus::IN_PROGRESS);
        }
    }

    assert(out_msg.msg_type == MSG_KEM_CT);
    assert(out_msg.payload == large_ct);
    std::cout << "[PASS] Invariant 2: Multi-chunk out-of-order reassembly exact!\n";

    // 4. CRC32 Checksum Corruption Test
    auto bad_chunk = chunks[0];
    bad_chunk[FRAME_HEADER_SIZE + 5] ^= 0x55; // Tamper payload byte
    ReassembledMessage bad_msg;
    auto bad_status = mgr.ingest_chunk("session_test_bad", bad_chunk.data(), bad_chunk.size(), bad_msg);
    assert(bad_status == ReassemblyStatus::CHECKSUM_ERROR);
    std::cout << "[PASS] Invariant 3: Tampered chunk caught by CRC32 checksum!\n";

    // 5. Duplicate Replay Test (Idempotence)
    GatekeeperReassemblyManager replay_mgr;
    ReassembledMessage replay_msg;
    auto s1 = replay_mgr.ingest_chunk("session_replay", chunks[0].data(), chunks[0].size(), replay_msg);
    assert(s1 == ReassemblyStatus::IN_PROGRESS);
    auto s2 = replay_mgr.ingest_chunk("session_replay", chunks[0].data(), chunks[0].size(), replay_msg);
    assert(s2 == ReassemblyStatus::IN_PROGRESS);
    std::cout << "[PASS] Invariant 4: Duplicate frame ignored without state corruption!\n";

    std::cout << "\n[ALL 4 WIRE FRAMING INVARIANTS 100% VERIFIED]\n";
    return 0;
}
