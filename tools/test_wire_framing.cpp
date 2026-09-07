#include "quantum-flex/wire_framing.hpp"
#include <iostream>
#include <cassert>
#include <vector>
#include <string>

using namespace quantumflex::wire;

int main() {
    std::vector<uint8_t> payload = {0x11, 0x22, 0x33, 0x44};
    
    // Test serialization
    auto frame = serialize_frame(MSG_KEM_ACK, 1234, payload.data(), payload.size());
    assert(frame.size() == sizeof(QFXKHeader) + payload.size());
    
    // Test stream ingestion
    QuantumFlexReassemblyPool pool;
    std::vector<uint8_t> out_payload;
    uint8_t out_msg_type = 0;
    
    bool complete = pool.ingest_stream("test_session", frame.data(), frame.size(), out_payload, out_msg_type);
    
    assert(complete == true);
    assert(out_msg_type == MSG_KEM_ACK);
    assert(out_payload == payload);
    
    // Test fragmentation/stream accumulation
    auto frame2 = serialize_frame(MSG_KEM_PK, 5678, payload.data(), payload.size());
    QuantumFlexReassemblyPool pool2;
    std::vector<uint8_t> out2;
    uint8_t type2 = 0;
    
    // Feed partial frame (first 10 bytes)
    bool p1 = pool2.ingest_stream("test_session2", frame2.data(), 10, out2, type2);
    assert(p1 == false);
    
    // Feed rest
    bool p2 = pool2.ingest_stream("test_session2", frame2.data() + 10, frame2.size() - 10, out2, type2);
    assert(p2 == true);
    assert(type2 == MSG_KEM_PK);
    assert(out2 == payload);

    std::cout << "[PASS] Wire framing tests completed successfully." << std::endl;
    return 0;
}
