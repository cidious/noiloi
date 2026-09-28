"""Yeelight and Razer device control over TCP."""

from __future__ import annotations

import json
import socket
from typing import Iterable

from .config import Config


def _yeelight_send(ip: str, method: str, params: list, timeout: float = 1.5) -> None:
    payload = json.dumps({"id": 1, "method": method, "params": params}) + "\r\n"
    with socket.create_connection((ip, 55443), timeout=timeout) as sock:
        sock.sendall(payload.encode("utf-8"))
        try:
            sock.settimeout(0.5)
            sock.recv(4096)
        except (TimeoutError, OSError):
            pass


def yeelight_reachable(ip: str, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((ip, 55443), timeout=timeout):
            return True
    except OSError:
        return False


def set_yeelight_ct(cfg: Config, temp: int, ips: Iterable[str] | None = None) -> list[str]:
    """Power on and set color temperature. Returns list of errors (empty if all ok)."""
    errors: list[str] = []
    targets = list(ips if ips is not None else cfg.yeelight_ips)
    for ip in targets:
        if not yeelight_reachable(ip):
            errors.append(f"{ip} not available")
            continue
        try:
            _yeelight_send(ip, "set_power", ["on", "smooth", 200])
            _yeelight_send(ip, "set_ct_abx", [temp, "smooth", 200])
        except OSError as exc:
            errors.append(f"{ip}: {exc}")
    return errors


def set_razer_color(cfg: Config, hex_color: str) -> None:
    color = hex_color.lstrip("#")
    with socket.create_connection((cfg.razer_host, cfg.razer_port), timeout=3) as sock:
        sock.sendall(color.encode("utf-8"))
        try:
            sock.settimeout(1.0)
            sock.recv(2048)
        except (TimeoutError, OSError):
            pass
