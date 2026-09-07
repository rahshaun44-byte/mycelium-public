#include <iostream>
#include <fstream>
#include <vector>
#include <cstring>
#include <unistd.h>
#include <fcntl.h>
#include <arpa/inet.h>
#include <systemd/sd-journal.h>
#include <openssl/ssl.h>
#include <openssl/err.h>
#include <cerrno>

const char* CA_CERT     = "/etc/quantum-flex/root-ca.crt";
const char* CLIENT_CERT = "/etc/quantum-flex/endpoint.crt";
const char* CLIENT_KEY  = "/etc/quantum-flex/endpoint.key";
const char* ATHENA_HOST = "127.0.0.1";
const int   ATHENA_PORT = 9443;

SSL_CTX* create_mtls_context() {
    SSL_library_init();
    OpenSSL_add_all_algorithms();
    SSL_load_error_strings();

    const SSL_METHOD *method = TLS_client_method();
    SSL_CTX *ctx = SSL_CTX_new(method);
    if (!ctx) {
        ERR_print_errors_fp(stderr);
        return nullptr;
    }

    if (SSL_CTX_use_certificate_file(ctx, CLIENT_CERT, SSL_FILETYPE_PEM) <= 0) {
        ERR_print_errors_fp(stderr);
        SSL_CTX_free(ctx);
        return nullptr;
    }

    if (SSL_CTX_use_PrivateKey_file(ctx, CLIENT_KEY, SSL_FILETYPE_PEM) <= 0) {
        ERR_print_errors_fp(stderr);
        SSL_CTX_free(ctx);
        return nullptr;
    }

    if (!SSL_CTX_load_verify_locations(ctx, CA_CERT, nullptr)) {
        ERR_print_errors_fp(stderr);
        SSL_CTX_free(ctx);
        return nullptr;
    }

    SSL_CTX_set_verify(ctx, SSL_VERIFY_PEER, nullptr);
    return ctx;
}

bool push_to_athena(const std::string& payload) {
    SSL_CTX *ctx = create_mtls_context();
    if (!ctx) {
        std::cerr << "[SENTINEL] Failed to create mTLS context\n";
        return false;
    }

    int sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0) {
        std::cerr << "[SENTINEL] socket() failed: " << strerror(errno) << std::endl;
        SSL_CTX_free(ctx);
        return false;
    }

    struct sockaddr_in serv_addr{};
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(ATHENA_PORT);
    inet_pton(AF_INET, ATHENA_HOST, &serv_addr.sin_addr);

    if (connect(sockfd, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) < 0) {
        std::cerr << "[SENTINEL] connect() failed to " << ATHENA_HOST << ":" << ATHENA_PORT
                  << " — " << strerror(errno) << std::endl;
        close(sockfd);
        SSL_CTX_free(ctx);
        return false;
    }

    SSL *ssl = SSL_new(ctx);
    SSL_set_fd(ssl, sockfd);

    if (SSL_connect(ssl) <= 0) {
        std::cerr << "[SENTINEL] SSL_connect failed\n";
        ERR_print_errors_fp(stderr);
        SSL_free(ssl);
        close(sockfd);
        SSL_CTX_free(ctx);
        return false;
    }

    SSL_write(ssl, payload.c_str(), payload.length());
    std::cout << "[SENTINEL] Transmitted " << payload.length() << " bytes to Athena.\n";

    SSL_shutdown(ssl);
    SSL_free(ssl);
    close(sockfd);
    SSL_CTX_free(ctx);
    return true;
}

int main() {
    sd_journal *j;
    int r = sd_journal_open(&j, SD_JOURNAL_LOCAL_ONLY);
    if (r < 0) {
        std::cerr << "Failed to open journal: " << strerror(-r) << "\n";
        return 1;
    }

    sd_journal_add_match(j, "_SYSTEMD_UNIT=sshd.service", 0);
    sd_journal_seek_tail(j);
    sd_journal_previous(j);

    std::cout << "[SENTINEL] Monitoring sshd.service -> Pushing to Athena ("
              << ATHENA_HOST << ":" << ATHENA_PORT << ")...\n";

    while (true) {
        r = sd_journal_next(j);
        if (r < 0) break;
        if (r == 0) {
            sd_journal_wait(j, (uint64_t)-1);
            continue;
        }

        const void *data;
        size_t length;
        if (sd_journal_get_data(j, "MESSAGE", &data, &length) >= 0) {
            std::string log_entry((const char*)data, length);
            std::cout << "\n[LIF SPIKE DETECTED] " << log_entry << std::endl << std::flush;
            push_to_athena(log_entry);
        }
    }

    sd_journal_close(j);
    return 0;
}
