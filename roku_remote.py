#!/usr/bin/env python3
"""A small terminal remote for a Roku on your local network."""

from __future__ import annotations

import argparse
import ipaddress
import re
import socket
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlparse


KEYS = {
    "home": "Home",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "select": "Select",
    "back": "Back",
    "backspace": "Backspace",
    "enter": "Enter",
    "play/pause": "Play",
    "rewind": "Rev",
    "fast forward": "Fwd",
    "replay": "InstantReplay",
    "info": "Info",
    "volume up": "VolumeUp",
    "volume down": "VolumeDown",
    "mute": "VolumeMute",
    "power off": "PowerOff",
    "channel up": "ChannelUp",
    "channel down": "ChannelDown",
    "hdmi 1": "InputHDMI1",
    "hdmi 2": "InputHDMI2",
    "hdmi 3": "InputHDMI3",
    "hdmi 4": "InputHDMI4",
    "tv tuner": "InputTuner",
    "av input": "InputAV1",
}

SSDP_ADDRESS = ("239.255.255.250", 1900)
SSDP_REQUEST = (
    "M-SEARCH * HTTP/1.1\r\n"
    "HOST: 239.255.255.250:1900\r\n"
    'MAN: "ssdp:discover"\r\n'
    "ST: roku:ecp\r\n"
    "MX: 2\r\n\r\n"
).encode("ascii")


def parse_ssdp_response(data: bytes) -> tuple[str, str] | None:
    """Extract the Roku IP and device ID from one SSDP response."""
    headers = {}
    for line in data.decode("utf-8", errors="replace").splitlines():
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
    host = urlparse(headers.get("location", "")).hostname
    if not host:
        return None
    try:
        ip = str(ipaddress.ip_address(host))
    except ValueError:
        return None
    usn = headers.get("usn", "")
    match = re.search(r"uuid:roku:ecp:([^:]+)", usn, re.IGNORECASE)
    return ip, match.group(1) if match else "Roku device"


def discover_roku_devices(timeout: float = 5.0) -> list[tuple[str, str]]:
    """Return (IP, device ID) pairs found through Roku's local SSDP discovery."""
    found: dict[str, str] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(0.25)
        sock.sendto(SSDP_REQUEST, SSDP_ADDRESS)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            device = parse_ssdp_response(data)
            if device:
                found[device[0]] = device[1]
    return sorted(found.items())


class RokuRemote:
    def __init__(self, ip: str, timeout: float = 3.0) -> None:
        self.ip = str(ipaddress.ip_address(ip))
        self.base_url = f"http://{self.ip}:8060"
        self.timeout = timeout

    def request(self, endpoint: str, method: str = "GET") -> bytes:
        request = urllib.request.Request(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            data=b"" if method == "POST" else None,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Roku returned HTTP {exc.code} for {endpoint}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(
                f"Could not reach {self.ip}. Check the IP, Wi-Fi, and Roku's "
                "'Control by mobile apps' setting."
            ) from exc

    def press(self, key: str) -> None:
        self.request(f"keypress/{key}", method="POST")

    def type_text(self, text: str) -> None:
        """Type text into a currently focused Roku on-screen keyboard."""
        if not text or len(text) > 160 or not text.isprintable():
            raise ValueError("Enter 1–160 printable characters.")
        for character in text:
            encoded = quote(character, safe="")
            self.request(f"keypress/Lit_{encoded}", method="POST")

    def device_info(self) -> list[tuple[str, str]]:
        root = ET.fromstring(self.request("query/device-info"))
        return [
            (child.tag.replace("-", " ").title(), (child.text or "").strip())
            for child in root
            if (child.text or "").strip()
        ]

    def tv_control_support(self) -> dict[str, str | None]:
        """Report the Roku OS flags for TV control over HDMI-CEC, when present."""
        root = ET.fromstring(self.request("query/device-info"))
        info = {child.tag: (child.text or "").strip() for child in root}
        return {
            "power": info.get("supports-tv-power-control"),
            "volume": info.get("supports-audio-volume-control"),
        }

    def apps(self) -> list[tuple[str, str]]:
        root = ET.fromstring(self.request("query/apps"))
        return [
            (app.attrib.get("id", ""), (app.text or "").strip())
            for app in root.findall("app")
        ]

    def launch(self, app_id: str) -> None:
        if not app_id.isdecimal():
            raise ValueError("The app ID must contain digits only.")
        self.request(f"launch/{app_id}", method="POST")


def show_menu() -> None:
    print("\n=== Roku Remote ===")
    print("1. Navigation and playback")
    print("2. Volume, power, and TV inputs (if supported)")
    print("3. Show installed apps")
    print("4. Launch an installed app")
    print("5. Show device information")
    print("6. Check TV power and volume support")
    print("q. Quit")


def choose_key(remote: RokuRemote, choices: dict[str, str]) -> None:
    labels = list(choices)
    for number, label in enumerate(labels, start=1):
        print(f"{number}. {label.title()}")
    choice = input("Choose a button (Enter to go back): ").strip()
    if not choice:
        return
    if not choice.isdecimal() or not 1 <= int(choice) <= len(labels):
        print("Please enter one of the listed numbers.")
        return
    label = labels[int(choice) - 1]
    remote.press(choices[label])
    print(f"Sent {label.title()}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Control a Roku from your terminal.")
    parser.add_argument("--ip", help="Roku's local IP address")
    args = parser.parse_args()
    ip = args.ip
    if not ip:
        print("Searching for Roku devices on your local network...")
        try:
            devices = discover_roku_devices()
        except OSError as exc:
            print(f"Discovery could not run: {exc}")
            devices = []
        if len(devices) == 1:
            ip, device_id = devices[0]
            print(f"Found {device_id} at {ip}.")
        elif len(devices) > 1:
            for number, (device_ip, device_id) in enumerate(devices, start=1):
                print(f"{number}. {device_id} — {device_ip}")
            choice = input("Choose a Roku (or enter its IP): ").strip()
            if choice.isdecimal() and 1 <= int(choice) <= len(devices):
                ip = devices[int(choice) - 1][0]
            else:
                ip = choice
        if not ip:
            ip = input("No Roku found. Enter its IP address: ").strip()

    try:
        remote = RokuRemote(ip)
    except ValueError:
        print("Enter a valid IP address, such as 192.168.1.50.", file=sys.stderr)
        return 2

    print(f"Connected target: {remote.ip} (local network)")
    while True:
        show_menu()
        action = input("Select an option: ").strip().lower()
        try:
            if action == "1":
                choose_key(
                    remote,
                    {key: KEYS[key] for key in (
                        "home", "up", "down", "left", "right", "select", "back",
                        "play/pause", "rewind", "fast forward", "replay", "info",
                    )},
                )
            elif action == "2":
                choose_key(
                    remote,
                    {key: KEYS[key] for key in (
                        "volume up", "volume down", "mute", "power off",
                        "channel up", "channel down", "hdmi 1", "hdmi 2",
                        "hdmi 3", "hdmi 4", "tv tuner", "av input",
                    )},
                )
            elif action == "3":
                apps = remote.apps()
                if not apps:
                    print("No apps were returned by the Roku.")
                else:
                    for app_id, title in apps:
                        print(f"{app_id:>8}  {title}")
            elif action == "4":
                apps = remote.apps()
                for app_id, title in apps:
                    print(f"{app_id:>8}  {title}")
                app_id = input("Enter the app ID to launch (Enter to cancel): ").strip()
                if app_id:
                    remote.launch(app_id)
                    print("Launch command sent.")
            elif action == "5":
                for label, value in remote.device_info():
                    print(f"{label}: {value}")
            elif action == "6":
                support = remote.tv_control_support()
                for name, value in support.items():
                    label = "TV power" if name == "power" else "TV volume"
                    status = {"true": "enabled", "false": "not enabled"}.get(
                        (value or "").lower(), "not reported by this Roku"
                    )
                    print(f"{label}: {status}")
                print("For a Roku stick, TV control needs HDMI-CEC enabled on both devices.")
                print("On Roku, check Settings > System > Control other devices (CEC).")
                print("On the RCA TV, enable HDMI-CEC in its HDMI/device settings.")
                print("If the physical remote uses IR, this network app cannot send that IR signal.")
            elif action in {"q", "quit", "exit"}:
                return 0
            else:
                print("Choose 1–6 or q.")
        except (RuntimeError, ET.ParseError, ValueError) as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
