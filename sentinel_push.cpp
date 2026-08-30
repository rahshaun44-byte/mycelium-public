#define UNICODE
#define _UNICODE
#include <windows.h>
#include <winevt.h>
#include <iostream>
#include <string>
#include <vector>
#include <chrono>
#include <libpq-fe.h>

#pragma comment(lib, "wevtapi.lib")
#pragma comment(lib, "libpq.lib")

static HANDLE g_hStopEvent = NULL;

BOOL WINAPI ConsoleHandler(DWORD signal) {
    if (signal == CTRL_C_EVENT || signal == CTRL_CLOSE_EVENT || signal == CTRL_SHUTDOWN_EVENT) {
        std::wcout << L"\n[SENTINEL] Shutdown signal received. Exiting...\n";
        if (g_hStopEvent) {
            SetEvent(g_hStopEvent);
        }
        return TRUE;
    }
    return FALSE;
}

class SentinelEngine {
public:
    SentinelEngine() {
        std::wcout << L"=================================================================\n";
        std::wcout << L"  QUANTUM FLEX // WINDOWS NATIVE SENTINEL ENGINE (C++20)\n";
        std::wcout << L"  Zero-Trust Telemetry Core | Target: Windows Event Log API\n";
        std::wcout << L"=================================================================\n";

        // Read connection credentials dynamically from environment
        const char* env_conninfo = std::getenv("QUANTUM_PG_CONNINFO");
        std::string conninfo_str;

        if (env_conninfo && strlen(env_conninfo) > 0) {
            conninfo_str = env_conninfo;
        } else {
            const char* db_host = std::getenv("DB_HOST") ? std::getenv("DB_HOST") : "127.0.0.1";
            const char* db_port = std::getenv("DB_PORT") ? std::getenv("DB_PORT") : "5432";
            const char* db_name = std::getenv("DB_NAME") ? std::getenv("DB_NAME") : "quantum_flex";
            const char* db_user = std::getenv("QUANTUM_SENTINEL_USER") ? std::getenv("QUANTUM_SENTINEL_USER") : "quantum_sentinel";
            const char* db_pass = std::getenv("QUANTUM_SENTINEL_PASSWORD") ? std::getenv("QUANTUM_SENTINEL_PASSWORD") : "";

            conninfo_str = "host=" + std::string(db_host) +
                           " port=" + std::string(db_port) +
                           " dbname=" + std::string(db_name) +
                           " user=" + std::string(db_user) +
                           " password=" + std::string(db_pass) +
                           " connect_timeout=5";
        }

        std::wcout << L"[SENTINEL] Connecting to PostgreSQL persistence layer...\n";
        
        conn = PQconnectdb(conninfo_str.c_str());
        if (PQstatus(conn) != CONNECTION_OK) {
            std::cerr << "[DB ERROR] Connection failed: " << PQerrorMessage(conn) << "\n";
            PQfinish(conn);
            conn = nullptr;
        } else {
            std::wcout << L"[SENTINEL] Database connection established. Role: quantum_sentinel (Append-Only).\n";
        }
    }

    ~SentinelEngine() {
        if (conn) {
            PQfinish(conn);
            conn = nullptr;
        }
        std::wcout << L"[SENTINEL] Engine shut down safely.\n";
    }

    void persist_event(const std::string& xml_payload) {
        auto now = std::chrono::system_clock::now();
        auto usec = std::chrono::duration_cast<std::chrono::microseconds>(now.time_since_epoch()).count();
        std::string timestamp_str = std::to_string(usec);
        std::string node_id = "yoga-win11-master";

        std::wcout << L"\n[TELEMETRY CAPTURED] Node: " << node_id.c_str() 
                   << L" | Timestamp: " << timestamp_str.c_str() << L"\n";
        std::cout << "Payload Preview: " << xml_payload.substr(0, 180) << "...\n";

        if (conn && PQstatus(conn) == CONNECTION_OK) {
            const char* paramValues[3] = { node_id.c_str(), timestamp_str.c_str(), xml_payload.c_str() };
            int paramLengths[3] = { (int)node_id.length(), (int)timestamp_str.length(), (int)xml_payload.length() };
            int paramFormats[3] = { 0, 0, 0 }; // Text format

            const char* query = "INSERT INTO quantum_telemetry_channel (node_id, timestamp, payload) VALUES ($1, $2::BIGINT, $3);";
            PGresult* res = PQexecParams(conn, query, 3, NULL, paramValues, paramLengths, paramFormats, 0);

            if (PQresultStatus(res) != PGRES_COMMAND_OK) {
                std::cerr << "[DB ERROR] Insertion failed: " << PQerrorMessage(conn) << "\n";
            } else {
                std::wcout << L"[PERSISTENCE] Telemetry row successfully committed to quantum_telemetry_channel.\n" << std::flush;
            }
            PQclear(res);
        } else {
            std::wcerr << L"[WARN] Database connection not ready. Payload bypassed storage.\n" << std::flush;
        }
    }

    static DWORD WINAPI SubscriptionCallback(
        EVT_SUBSCRIBE_NOTIFY_ACTION action,
        PVOID pContext,
        EVT_HANDLE hEvent
    ) {
        if (action == EvtSubscribeActionDeliver) {
            SentinelEngine* engine = static_cast<SentinelEngine*>(pContext);
            DWORD bufferSize = 0;
            DWORD bufferUsed = 0;
            DWORD propertyCount = 0;

            EvtRender(NULL, hEvent, EvtRenderEventXml, bufferSize, NULL, &bufferUsed, &propertyCount);
            if (GetLastError() == ERROR_INSUFFICIENT_BUFFER) {
                bufferSize = bufferUsed;
                std::vector<wchar_t> buffer(bufferSize / sizeof(wchar_t) + 1);
                if (EvtRender(NULL, hEvent, EvtRenderEventXml, bufferSize, buffer.data(), &bufferUsed, &propertyCount)) {
                    int size_needed = WideCharToMultiByte(CP_UTF8, 0, buffer.data(), -1, NULL, 0, NULL, NULL);
                    std::string utf8_xml(size_needed, 0);
                    WideCharToMultiByte(CP_UTF8, 0, buffer.data(), -1, &utf8_xml[0], size_needed, NULL, NULL);

                    if (engine) {
                        engine->persist_event(utf8_xml);
                    }
                }
            }
        }
        return ERROR_SUCCESS;
    }

    void start_monitoring() {
        std::wcout << L"[SENTINEL] Subscribing to Windows Event Log (Channel: Application, XPath: *)...\n";

        EVT_HANDLE hSub = EvtSubscribe(
            NULL,
            NULL,
            L"Application",
            L"*",
            NULL,
            this,
            (EVT_SUBSCRIBE_CALLBACK)SubscriptionCallback,
            EvtSubscribeToFutureEvents
        );

        if (!hSub) {
            DWORD err = GetLastError();
            std::wcerr << L"[CRITICAL ERROR] EvtSubscribe failed. Error Code: " << err << L"\n";
            return;
        }

        std::wcout << L"[SENTINEL] Pipeline active. Intercepting live OS telemetry stream.\n" << std::flush;

        // Block on stop event until signaled
        WaitForSingleObject(g_hStopEvent, INFINITE);

        EvtClose(hSub);
        std::wcout << L"[SENTINEL] Subscription closed.\n" << std::flush;
    }

private:
    PGconn* conn = nullptr;
};

int wmain() {
    g_hStopEvent = CreateEvent(NULL, TRUE, FALSE, NULL);
    SetConsoleCtrlHandler(ConsoleHandler, TRUE);

    try {
        SentinelEngine engine;
        engine.start_monitoring();
    } catch (const std::exception& e) {
        std::cerr << "[FATAL EXCEPTION] " << e.what() << "\n";
        CloseHandle(g_hStopEvent);
        return 1;
    }

    CloseHandle(g_hStopEvent);
    return 0;
}
