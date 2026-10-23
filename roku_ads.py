"""Persistent Roku ad-filter list and sinkhole export helpers."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


CONFIG_PATH = Path.home() / ".roku-remote" / "ad-blocking.json"
MAX_DOMAINS = 500
LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_domains(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_DOMAINS:
        raise ValueError(f"Provide a list of up to {MAX_DOMAINS} domains.")
    domains: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError("Each blocked domain must be text.")
        raw = item.strip().rstrip(".")
        if not raw:
            continue
        try:
            domain = raw.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ValueError(f"Invalid domain: {raw}") from exc
        labels = domain.split(".")
        if len(domain) > 253 or len(labels) < 2 or not all(
            LABEL_PATTERN.fullmatch(label) for label in labels
        ):
            raise ValueError(f"Invalid domain: {raw}")
        domains.add(domain)
    return sorted(domains)


def validate_sinkhole_ip(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Enter an IPv4 sinkhole address.")
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError as exc:
        raise ValueError("Enter a valid IPv4 sinkhole address, such as 0.0.0.0.") from exc
    if address.version != 4 or address.is_multicast or address == ipaddress.IPv4Address("255.255.255.255"):
        raise ValueError("Use a valid unicast IPv4 sinkhole address.")
    return str(address)


def load_config() -> dict[str, Any]:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"sinkhole_ip": "0.0.0.0", "domains": []}
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read the ad-blocking list: {exc}") from exc
    if not isinstance(config, dict):
        raise RuntimeError("The saved ad-blocking list has an invalid format.")
    return {
        "sinkhole_ip": validate_sinkhole_ip(config.get("sinkhole_ip", "0.0.0.0")),
        "domains": normalize_domains(config.get("domains", [])),
    }


def save_config(sinkhole_ip: Any, domains: Any) -> dict[str, Any]:
    config = {
        "sinkhole_ip": validate_sinkhole_ip(sinkhole_ip),
        "domains": normalize_domains(domains),
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=CONFIG_PATH.parent, delete=False
        ) as temporary:
            json.dump(config, temporary, indent=2)
            temporary.write("\n")
            temporary_path = temporary.name
        os.replace(temporary_path, CONFIG_PATH)
    except OSError as exc:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
        raise RuntimeError(f"Could not save the ad-blocking list: {exc}") from exc
    return config
