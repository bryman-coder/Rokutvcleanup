#!/usr/bin/env python3
"""Serve a small, password-protected browser remote for a local Roku."""

from __future__ import annotations

import argparse
import ipaddress
import json
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from roku_remote import KEYS, RokuRemote, discover_roku_devices

WEB_DIR = Path(__file__).parent / "web"
ALLOWED_KEYS = set(KEYS.values())


class RokuWebServer(ThreadingHTTPServer):
    daemon_threads = True
    remote: RokuRemote | None = None
    access_code: str


class RokuWebHandler(BaseHTTPRequestHandler):
    server: RokuWebServer
    server_version = "RokuRemote"

    def log_message(self, format: str, *args: object) -> None:
        # Keep access codes and request details out of the terminal log.
        return

    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = f"Bearer {self.server.access_code}"
        if secrets.compare_digest(self.headers.get("Authorization", ""), expected):
            return True
        self._json({"error": "Enter the access code shown in the terminal."}, 401)
        return False

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 16_384:
                raise ValueError("Request body is too large.")
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object.")
            return data
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must be a small JSON object.") from exc

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            try:
                body = (WEB_DIR / "index.html").read_bytes()
            except OSError:
                self.send_error(500, "The web interface file is missing.")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if not self.path.startswith("/api/"):
            self.send_error(404)
            return
        if not self._authorized():
            return
        try:
            if self.path == "/api/devices":
                devices = discover_roku_devices()
                self._json({"devices": [{"ip": ip, "id": device_id} for ip, device_id in devices]})
            elif self.path == "/api/status":
                remote = self.server.remote
                if remote is None:
                    self._json({"connected": False})
                else:
                    info = dict(remote.device_info())
                    name = info.get("User Device Name") or info.get("Model Name") or "Roku"
                    support = remote.tv_control_support()
                    self._json({
                        "connected": True,
                        "ip": remote.ip,
                        "name": name,
                        "info": info,
                        "tv_control": support,
                    })
            elif self.path == "/api/apps":
                remote = self.server.remote
                if remote is None:
                    self._json({"error": "Connect to a Roku first."}, 409)
                else:
                    self._json({"apps": [{"id": app_id, "name": name} for app_id, name in remote.apps()]})
            else:
                self.send_error(404)
        except (OSError, RuntimeError, ValueError) as exc:
            self._json({"error": str(exc)}, 502)

    def do_POST(self) -> None:
        if not self.path.startswith("/api/"):
            self.send_error(404)
            return
        if not self._authorized():
            return
        try:
            data = self._read_json()
            if self.path == "/api/connect":
                target = ipaddress.ip_address(str(data.get("ip", "")))
                if target.version != 4 or not (target.is_private or target.is_link_local):
                    self._json({"error": "Enter the Roku's local IPv4 address."}, 400)
                    return
                remote = RokuRemote(str(target))
                # Verify that this address is a reachable Roku before selecting it.
                info = dict(remote.device_info())
                self.server.remote = remote
                name = info.get("User Device Name") or info.get("Model Name") or "Roku"
                self._json({"connected": True, "ip": remote.ip, "name": name})
            elif self.path == "/api/key":
                remote = self.server.remote
                key = data.get("key")
                if remote is None:
                    self._json({"error": "Connect to a Roku first."}, 409)
                elif key not in ALLOWED_KEYS:
                    self._json({"error": "That button is not supported."}, 400)
                else:
                    remote.press(key)
                    self._json({"sent": key})
            elif self.path == "/api/launch":
                remote = self.server.remote
                app_id = str(data.get("id", ""))
                if remote is None:
                    self._json({"error": "Connect to a Roku first."}, 409)
                else:
                    remote.launch(app_id)
                    self._json({"launched": app_id})
            else:
                self.send_error(404)
        except (OSError, RuntimeError, ValueError) as exc:
            self._json({"error": str(exc)}, 502)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a browser-based Roku remote.")
    parser.add_argument("--port", type=int, default=8765, help="Web app port (default: 8765)")
    parser.add_argument(
        "--lan",
        action="store_true",
        help="Allow other devices on your home network to connect (requires the access code)",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be from 1 to 65535")

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    access_code = secrets.token_urlsafe(18)
    server = RokuWebServer((host, args.port), RokuWebHandler)
    server.access_code = access_code
    print(f"Roku Remote is running at http://{'localhost' if not args.lan else '<computer-ip>'}:{args.port}")
    if args.lan:
        print("For phone access, open the address above using this computer's local IP on the same Wi-Fi.")
        print("Temporary access code:", access_code)
        print("Use this only on a trusted home network. Stop with Ctrl+C when finished.")
    else:
        print("This mode is available only on this computer. Use --lan for phone access.")
        print("Temporary access code:", access_code)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRoku Remote stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
