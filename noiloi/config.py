"""Load noiloi configuration from a simple key=value file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONF_PATHS = (
    Path(os.environ.get("NOILOI_CONF", "")),
    Path("/home/cds/bin/noiloi.conf"),
    Path(__file__).resolve().parent.parent / "noiloi.conf",
)

# Matches dirtyhack/turn-on-lights.sh
COLOR_STEPS: list[tuple[int, str | None]] = [
    (6500, "fcc68d"),
    (6100, "ffa463"),
    (5700, "fa9248"),
    (5300, "ff8b38"),
    (4900, "fc791c"),
    (4500, "b85212"),
    (4100, "a34410"),
    (3700, "8c320e"),
    (3300, None),
]


@dataclass
class Config:
    latitude: float = 54.989342
    longitude: float = 73.368212
    timezone: str = "Asia/Omsk"
    cronicle_url: str = "http://localhost:3012"
    cronicle_api_key: str = ""
    cronicle_category: str = "general"
    cronicle_plugin: str = "shellplug"
    cronicle_target: str = "neon"
    cloud_threshold: int = 70
    offset_clear_min: int = 10
    offset_overcast_min: int = 40
    weather_lead_min: int = 50
    yeelight_ips: list[str] = field(default_factory=list)
    razer_host: str = "127.0.0.1"
    razer_port: int = 13000
    log_file: str = "/home/cds/tmp/noiloi.log"
    noiloi_bin: str = "/home/cds/bin/noiloi"
    step_interval_min: int = 15


def _parse_value(raw: str) -> str:
    return raw.strip().strip("'").strip('"')


def load_config(path: Path | None = None) -> Config:
    conf_path: Path | None = path
    if conf_path is None:
        for candidate in DEFAULT_CONF_PATHS:
            if candidate and candidate.is_file():
                conf_path = candidate
                break

    cfg = Config()
    if conf_path is None:
        cfg.yeelight_ips = ["192.168.9.122", "192.168.9.60", "192.168.9.105"]
        return cfg

    for line in conf_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = _parse_value(value)
        if key == "latitude":
            cfg.latitude = float(value)
        elif key == "longitude":
            cfg.longitude = float(value)
        elif key == "timezone":
            cfg.timezone = value
        elif key == "cronicle_url":
            cfg.cronicle_url = value.rstrip("/")
        elif key == "cronicle_api_key":
            cfg.cronicle_api_key = value
        elif key == "cronicle_category":
            cfg.cronicle_category = value
        elif key == "cronicle_plugin":
            cfg.cronicle_plugin = value
        elif key == "cronicle_target":
            cfg.cronicle_target = value
        elif key == "cloud_threshold":
            cfg.cloud_threshold = int(value)
        elif key == "offset_clear_min":
            cfg.offset_clear_min = int(value)
        elif key == "offset_overcast_min":
            cfg.offset_overcast_min = int(value)
        elif key == "weather_lead_min":
            cfg.weather_lead_min = int(value)
        elif key == "yeelight_ips":
            cfg.yeelight_ips = value.split()
        elif key == "razer_host":
            cfg.razer_host = value
        elif key == "razer_port":
            cfg.razer_port = int(value)
        elif key == "log_file":
            cfg.log_file = value
        elif key in ("noiloi_bin", "heliolamp_bin"):
            cfg.noiloi_bin = value
        elif key == "step_interval_min":
            cfg.step_interval_min = int(value)

    if not cfg.yeelight_ips:
        cfg.yeelight_ips = ["192.168.9.122", "192.168.9.60", "192.168.9.105"]
    return cfg
