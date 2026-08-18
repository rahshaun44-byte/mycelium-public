import socket

def test_http_head(host, port, path, desc):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((host, port))
        request = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUser-Agent: Tester\r\nConnection: close\r\n\r\n"
        s.sendall(request.encode())
        data = s.recv(1024).decode(errors="replace")
        s.close()
        status_line = data.split("\r\n")[0] if data else "NO_RESPONSE"
        print(f"[PASS] {desc:<35} -> {status_line}")
    except Exception as e:
        print(f"[FAIL] {desc:<35} -> Error: {e}")

print("==================================================================")
print("  QUANTUM FLEX: COMPREHENSIVE ENDPOINT VERIFICATION               ")
print("==================================================================")

endpoints = [
    ("127.0.0.1", 9000, "/sse", "MCP SSE (Local)"),
    ("100.64.1.29", 9000, "/sse", "MCP SSE (Tailscale Mesh)"),
    ("127.0.0.1", 8000, "/", "AMARA Dashboard (Local)"),
    ("100.64.1.29", 8000, "/", "AMARA Dashboard (Tailscale)"),
    ("100.64.1.29", 8000, "/api/telemetry", "AMARA Telemetry API (Tailscale)"),
    ("100.64.1.29", 8080, "/status", "API Gateway (Tailscale)"),
    ("127.0.0.1", 8001, "/health", "Athena RAG Node (Local)"),
]

for host, port, path, desc in endpoints:
    test_http_head(host, port, path, desc)

print("==================================================================")
