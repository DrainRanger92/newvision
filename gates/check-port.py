#!/usr/bin/env python3
"""Check if a port is available for binding."""
import socket
import sys


def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            print(f"PASS: port {port} free")
            return True
        except OSError:
            print(f"FAIL: port {port} occupied")
            return False


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    sys.exit(0 if check_port(port) else 1)


if __name__ == "__main__":
    main()
