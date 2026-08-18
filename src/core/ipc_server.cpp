#include "quantum-flex/ipc_server.hpp"
#include "quantum-flex/local_node.hpp"

#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>

#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "quantum-flex/crypto_shamir.hpp"

#include <openssl/crypto.h>

namespace {
    // Genesis/unlock shard payloads are recovered secret material with no
    // further use once consumed — cleanse them rather than leaving raw bytes
    // sitting in freed heap memory until something else happens to overwrite it.
    void cleanse_shards(std::vector<quantumflex::crypto::SecretShard>& shards) {
        for (auto& shard : shards) {
            if (!shard.payload.empty()) {
                OPENSSL_cleanse(shard.payload.data(), shard.payload.size());
            }
        }
    }

    // Shard payloads are raw bytes and may contain ',' or ':' — the delimiters
    // this wire format uses — so payloads are always hex-encoded in transit
    // (see tools/genesis_tool.cpp, the only current producer of INIT|/UNLOCK|
    // lines). Decode back to raw bytes before handing shards to LocalNode.
    auto hex_decode(const std::string& hex) -> std::string {
        std::string raw;
        raw.reserve(hex.length() / 2);
        for (std::size_t i = 0; i + 1 < hex.length(); i += 2) {
            raw.push_back(static_cast<char>(std::stoi(hex.substr(i, 2), nullptr, 16)));
        }
        return raw;
    }

    auto parse_shares(const std::string& stream, const std::string& prefix) -> std::vector<quantumflex::crypto::SecretShard> {
        const std::string shares_str = stream.substr(prefix.length());
        std::vector<quantumflex::crypto::SecretShard> shards;

        std::istringstream share_stream(shares_str);
        std::string share_token;

        while (std::getline(share_stream, share_token, ',')) {
            const size_t colon_pos = share_token.find(':');
            if (colon_pos != std::string::npos) {
                const uint8_t shard_id = static_cast<uint8_t>(std::stoi(share_token.substr(0, colon_pos)));
                const std::string data = hex_decode(share_token.substr(colon_pos + 1));
                shards.push_back(quantumflex::crypto::SecretShard{.id = shard_id, .payload = data});
            }
        }
        return shards;
    }

    void ssl_write_str(SSL* ssl, const std::string& msg) {
        static_cast<void>(SSL_write(ssl, msg.c_str(), msg.length()));
    }

    // NOLINTNEXTLINE(readability-function-cognitive-complexity)
    void handle_active_telemetry(const std::string& stream, SSL* ssl, quantumflex::node::LocalNode& node, quantumflex::security::EwmaLifSentinel& sentinel) {
        const std::string set_key_prefix = "SET_HARVESTER_KEY|";
        const std::string telemetry_prefix = "TELEMETRY|";
        const std::string replicate_prefix = "REPLICATE|";
        const std::string enroll_prefix = "ENROLL_PEER|";
        const std::string gossub_prefix = "GOSSUB|";
        
        if (stream.starts_with(set_key_prefix)) {
            const std::string hex_key = stream.substr(set_key_prefix.length());
            node.set_harvester_key(hex_key);
            sentinel.record_success();
            ssl_write_str(ssl, "ACK|HARVESTER_KEY_SET\n");
        } else if (stream.starts_with(telemetry_prefix)) {
            const std::string payload_block = stream.substr(telemetry_prefix.length());
            const std::size_t last_pipe = payload_block.rfind('|');
            if (last_pipe != std::string::npos) {
                const std::string base_payload = payload_block.substr(0, last_pipe);
                const std::string signature_hex = payload_block.substr(last_pipe + 1);
                
                const std::size_t first_pipe = base_payload.find('|');
                std::string t_id = "UNKNOWN";
                if (first_pipe != std::string::npos) {
                    t_id = base_payload.substr(0, first_pipe);
                }
                
                try {
                    static_cast<void>(node.append_evidence(t_id, base_payload, signature_hex));
                    node.replication().append_block({stream});
                    sentinel.record_success();
                    ssl_write_str(ssl, "ACK|EVIDENCE_ACCEPTED\n");
                } catch (const std::exception& e) {
                    sentinel.record_drop();
                    const std::string err = std::string("ERR|") + e.what() + "\n";
                    ssl_write_str(ssl, err);
                    std::cerr << "[!] " << e.what() << '\n';
                }
            } else {
                sentinel.record_drop();
                ssl_write_str(ssl, "ERR|MALFORMED_TELEMETRY\n");
            }
        } else if (stream.starts_with(replicate_prefix)) {
            if (node.replication().receive_replication(stream)) {
                sentinel.record_success();
                ssl_write_str(ssl, "ACK|REPLICATION_ACCEPTED\n");
            } else {
                sentinel.record_drop();
                ssl_write_str(ssl, "ERR|REPLICATION_REJECTED\n");
            }
        } else if (stream.starts_with(enroll_prefix)) {
            const size_t pos1 = stream.find('|');
            const size_t pos2 = stream.find('|', pos1 + 1);
            const size_t pos3 = stream.find('|', pos2 + 1);
            if (pos1 != std::string::npos && pos2 != std::string::npos && pos3 != std::string::npos) {
                const std::string node_id = stream.substr(pos1 + 1, pos2 - pos1 - 1);
                const std::string pubkey = stream.substr(pos2 + 1, pos3 - pos2 - 1);
                const std::string sig = stream.substr(pos3 + 1);
                if (node.replication().enroll_peer(node_id, pubkey, sig)) {
                    sentinel.record_success();
                    ssl_write_str(ssl, "ACK|ENROLL_ACCEPTED\n");
                } else {
                    sentinel.record_drop();
                    ssl_write_str(ssl, "ERR|ENROLL_REJECTED\n");
                }
            } else {
                sentinel.record_drop();
                ssl_write_str(ssl, "ERR|MALFORMED_ENROLL\n");
            }
        } else if (stream.starts_with(gossub_prefix)) {
            if (node.gossipsub().validate_and_process(stream)) {
                sentinel.record_success();
                ssl_write_str(ssl, "ACK|GOSSUB_ACCEPTED\n");
            } else {
                sentinel.record_drop();
                ssl_write_str(ssl, "ERR|GOSSUB_REJECTED\n");
            }
        } else {
            sentinel.record_drop();
            ssl_write_str(ssl, "ERR|UNKNOWN_COMMAND\n");
        }
    }
} // namespace

namespace quantumflex::ipc {

    IpcServer::IpcServer(int port, const std::string& cert_file, const std::string& key_file, const std::string& ca_file, node::LocalNode& target_node, std::string bind_address, security::LifConfig lif_config)
        : port_(port), cert_file_(cert_file), key_file_(key_file), ca_file_(ca_file), bind_address_(std::move(bind_address)), node_(target_node), sentinel_(std::make_unique<security::EwmaLifSentinel>(node_, lif_config)) {
        SSL_load_error_strings();
        OpenSSL_add_ssl_algorithms();
    }

    IpcServer::~IpcServer() {
        stop();
        if (ssl_ctx_) {
            SSL_CTX_free(ssl_ctx_);
        }
        EVP_cleanup();
    }

    void IpcServer::configure_ssl_context() {
        const SSL_METHOD* method = TLS_server_method();
        ssl_ctx_ = SSL_CTX_new(method);
        if (!ssl_ctx_) {
            ERR_print_errors_fp(stderr);
            throw std::runtime_error("IPC FATAL: Failed to create SSL context");
        }

        if (SSL_CTX_use_certificate_file(ssl_ctx_, cert_file_.c_str(), SSL_FILETYPE_PEM) <= 0) {
            ERR_print_errors_fp(stderr);
            throw std::runtime_error("IPC FATAL: Failed to load server certificate");
        }

        if (SSL_CTX_use_PrivateKey_file(ssl_ctx_, key_file_.c_str(), SSL_FILETYPE_PEM) <= 0) {
            ERR_print_errors_fp(stderr);
            throw std::runtime_error("IPC FATAL: Failed to load server private key");
        }

        if (SSL_CTX_load_verify_locations(ssl_ctx_, ca_file_.c_str(), nullptr) <= 0) {
            ERR_print_errors_fp(stderr);
            throw std::runtime_error("IPC FATAL: Failed to load CA certificate for verification");
        }

        // Enforce strict mTLS: Fail if the client doesn't present a CA-signed cert
        SSL_CTX_set_verify(ssl_ctx_, SSL_VERIFY_PEER | SSL_VERIFY_FAIL_IF_NO_PEER_CERT, nullptr);
    }

    void IpcServer::start() {
        configure_ssl_context();

        if (sentinel_) {
            sentinel_->start();
        }

        server_fd_ = socket(AF_INET, SOCK_STREAM, 0);
        if (server_fd_ == -1) {
            throw std::runtime_error("IPC FATAL: Failed to create AF_INET socket");
        }

        int opt = 1;
        if (setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) == -1) {
            throw std::runtime_error("IPC FATAL: setsockopt SO_REUSEADDR failed");
        }

        struct sockaddr_in addr{};
        addr.sin_family = AF_INET;
        if (inet_pton(AF_INET, bind_address_.c_str(), &addr.sin_addr) != 1) {
            throw std::runtime_error("IPC FATAL: Invalid bind address: " + bind_address_);
        }
        addr.sin_port = htons(port_);

        // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
        if (bind(server_fd_, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) == -1) {
            throw std::runtime_error("IPC FATAL: Failed to bind TCP socket to port " + std::to_string(port_));
        }

        constexpr int MAX_BACKLOG = 5;
        if (listen(server_fd_, MAX_BACKLOG) == -1) {
            throw std::runtime_error("IPC FATAL: Failed to listen on TCP socket");
        }
    }

    auto IpcServer::process_single_connection() -> bool {
        if (server_fd_ == -1) {
            return false;
        }

        struct sockaddr_in client_addr{};
        socklen_t client_len = sizeof(client_addr);
        // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
        const int client_fd = accept4(server_fd_, reinterpret_cast<struct sockaddr*>(&client_addr), &client_len, SOCK_CLOEXEC);
        
        if (client_fd == -1) {
            return false;
        }

        SSL* ssl = SSL_new(ssl_ctx_);
        SSL_set_fd(ssl, client_fd);

        if (SSL_accept(ssl) <= 0) {
            std::cerr << "[!] mTLS Handshake Failed. Rejecting connection.\n";
            ERR_print_errors_fp(stderr);
            if (sentinel_) {
                sentinel_->record_drop();
            }
            SSL_free(ssl);
            close(client_fd);
            return true; // Return true to keep the loop going for the next connection
        }

        // Read the telemetry payload
        constexpr std::size_t MAX_BUFFER_SIZE = 4096;
        std::vector<char> buffer(MAX_BUFFER_SIZE, '\0');
        const int bytes_read = SSL_read(ssl, buffer.data(), buffer.size() - 1);
        
        if (bytes_read <= 0) {
            if (sentinel_) {
                sentinel_->record_drop();
            }
            SSL_free(ssl);
            close(client_fd);
            return true;
        }

        std::string stream(buffer.data(), static_cast<std::size_t>(bytes_read));

        if (node_.get_state() == quantumflex::node::SystemState::UNINITIALIZED) {
            const std::string init_prefix = "INIT|";
            if (stream.starts_with(init_prefix)) {
                auto shards = parse_shares(stream, init_prefix);
                try {
                    node_.initialize_node(shards, 3);
                    if (sentinel_) {
                        sentinel_->record_success();
                    }
                    ssl_write_str(ssl, "ACK|GENESIS_SECURED\n");
                } catch (const std::exception& e) {
                    if (sentinel_) {
                        sentinel_->record_drop();
                    }
                    const std::string err = std::string("ERR|") + e.what() + "\n";
                    ssl_write_str(ssl, err);
                    std::cerr << "[!] " << e.what() << '\n';
                }
                cleanse_shards(shards);
            } else {
                if (sentinel_) {
                    sentinel_->record_drop();
                }
                ssl_write_str(ssl, "ERR|NODE_UNINITIALIZED_CALL_INIT\n");
            }
        } else if (node_.get_state() == quantumflex::node::SystemState::LOCKED) {
            const std::string unlock_prefix = "UNLOCK|";
            if (stream.starts_with(unlock_prefix)) {
                auto shards = parse_shares(stream, unlock_prefix);
                try {
                    node_.unlock_node(shards, 3);
                    if (sentinel_) {
                        sentinel_->record_success();
                    }
                    ssl_write_str(ssl, "ACK|NODE_UNLOCKED\n");
                } catch (const std::exception& e) {
                    if (sentinel_) {
                        sentinel_->record_drop();
                    }
                    const std::string err = std::string("ERR|") + e.what() + "\n";
                    ssl_write_str(ssl, err);
                    std::cerr << "[!] " << e.what() << '\n';
                    cleanse_shards(shards);
                    // NOLINTNEXTLINE(concurrency-mt-unsafe)
                    std::exit(1);
                }
                cleanse_shards(shards);
            } else {
                if (sentinel_) {
                    sentinel_->record_drop();
                }
                ssl_write_str(ssl, "ERR|NODE_LOCKED\n");
            }
        } else {
            handle_active_telemetry(stream, ssl, node_, *sentinel_);
        }

        // Cleanse the raw wire buffer — for INIT|/UNLOCK| it still holds the
        // hex-encoded shard text even after the decoded SecretShards above
        // have been cleansed.
        OPENSSL_cleanse(buffer.data(), buffer.size());
        if (!stream.empty()) {
            OPENSSL_cleanse(stream.data(), stream.size());
        }

        SSL_shutdown(ssl);
        SSL_free(ssl);
        close(client_fd);
        return true;
    }

    void IpcServer::stop() {
        if (sentinel_) {
            sentinel_->stop();
        }
        if (server_fd_ != -1) {
            close(server_fd_);
            server_fd_ = -1;
        }
    }

} // namespace quantumflex::ipc
