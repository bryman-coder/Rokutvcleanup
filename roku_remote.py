#!/usr/bin/env python3
"""A small terminal remote for a Roku on your local network."""

from __future__ import annotations

import argparse
import ipaddress
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


KEYS = {
    "home": "Home",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "select": "Select",
    "back": "Back",
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

    def device_info(self) -> list[tuple[str, str]]:
        root = ET.fromstring(self.request("query/device-info"))
        return [
            (child.tag.replace("-", " ").title(), (child.text or "").strip())
            for child in root
            if (child.text or "").strip()
        ]

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
    ip = args.ip or input("Roku IP address: ").strip()

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
            elif action in {"q", "quit", "exit"}:
                return 0
            else:
                print("Choose 1–5 or q.")
        except (RuntimeError, ET.ParseError, ValueError) as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
