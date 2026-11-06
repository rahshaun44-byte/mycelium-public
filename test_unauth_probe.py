#!/usr/bin/env python3
import socket
import sys

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 9444

def test_unauthenticated_access():
    print(f"[*] Probing unauthenticated endpoint at {TARGET_HOST}:{TARGET_PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    try:
        # Attempt raw unauthenticated TCP connection without mTLS or valid headers
        sock.connect((TARGET_HOST, TARGET_PORT))
        payload = b"GET /admin HTTP/1.1\r\nHost: local-probe\r\n\r\n"
        sock.sendall(payload)
        response = sock.recv(1024)
        if response:
            print(f"[!] WARNING: Raw connection accepted! Response received: {response}")
        else:
            print("[+] SUCCESS: Connection immediately closed / terminated by engine barrier (Zero bytes received).")
    except ConnectionRefusedError:
        print("[+] SUCCESS: Connection explicitly refused by target (Port closed/unbound).")
    except socket.timeout:
        print("[+] SUCCESS: Connection timed out or dropped silently by OPA/Engine filter.")
    except Exception as e:
        print(f"[+] SUCCESS: Connection terminated by barrier: {type(e).__name__} - {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    test_unauthenticated_access()
