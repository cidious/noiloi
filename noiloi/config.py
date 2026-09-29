"""Load noiloi configuration from a simple key=value file."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

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


def _xdg_config_home() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME", "").strip()
    return Path(raw) if raw else Path.home() / ".config"


def _xdg_state_home() -> Path:
    raw = os.environ.get("XDG_STATE_HOME", "").strip()
    return Path(raw) if raw else Path.home() / ".local" / "state"


def default_conf_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    env = os.environ.get("NOILOI_CONF", "").strip()
    if env:
        paths.append(Path(env).expanduser())
    paths.append(_xdg_config_home() / "noiloi" / "noiloi.conf")
    paths.append(Path(__file__).resolve().parent.parent / "noiloi.conf")
    cwd_conf = Path.cwd() / "noiloi.conf"
    if cwd_conf.resolve() not in {p.resolve() for p in paths}:
        paths.append(cwd_conf)
    return tuple(paths)


def default_log_file() -> str:
    return str(_xdg_state_home() / "noiloi" / "noiloi.log")


def default_noiloi_bin() -> str:
    argv0 = Path(sys.argv[0]).expanduser()
    try:
        if argv0.exists():
            return str(argv0.resolve())
    except OSError:
        pass
    found = shutil.which("noiloi")
    return found or "noiloi"


def expand_path(value: str) -> str:
    return str(Path(value).expanduser()) if value else value


@dataclass
class Config:
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = "UTC"
    cronicle_url: str = "http://localhost:3012"
    cronicle_api_key: str = ""
    cronicle_category: str = "general"
    cronicle_plugin: str = "shellplug"
    cronicle_target: str = ""
    cloud_threshold: int = 70
    offset_clear_min: int = 10
    offset_overcast_min: int = 40
    weather_lead_min: int = 50
    yeelight_ips: list[str] = field(default_factory=list)
    razer_host: str = "127.0.0.1"
    razer_port: int = 13000
    log_file: str = ""
    noiloi_bin: str = ""
    step_interval_min: int = 15
    off_on_sleep: bool = True
    off_on_shutdown: bool = True
    off_razer: bool = True
    verbose_log: bool = False

    def require_location(self) -> None:
        if self.latitude is None or self.longitude is None:
            raise ValueError("latitude and longitude must be set in noiloi.conf")
        if not self.timezone:
            raise ValueError("timezone must be set in noiloi.conf")

    def require_cronicle(self) -> None:
        if not self.cronicle_api_key or self.cronicle_api_key == "REPLACE_ME":
            raise ValueError("cronicle_api_key must be set in noiloi.conf")
        if not self.cronicle_target:
            raise ValueError("cronicle_target must be set in noiloi.conf")

    def require_devices(self) -> None:
        if not self.yeelight_ips:
            raise ValueError("yeelight_ips must be set in noiloi.conf")


def _parse_value(raw: str) -> str:
    return raw.strip().strip("'").strip('"')


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config(path: Path | None = None) -> Config:
    conf_path: Path | None = path
    if conf_path is None:
        for candidate in default_conf_paths():
            if candidate and candidate.is_file():
                conf_path = candidate
                break

    cfg = Config()
    if conf_path is None:
        cfg.log_file = default_log_file()
        cfg.noiloi_bin = default_noiloi_bin()
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
            cfg.log_file = expand_path(value)
        elif key in ("noiloi_bin", "heliolamp_bin"):
            cfg.noiloi_bin = expand_path(value)
        elif key == "step_interval_min":
            cfg.step_interval_min = int(value)
        elif key == "off_on_sleep":
            cfg.off_on_sleep = _parse_bool(value)
        elif key == "off_on_shutdown":
            cfg.off_on_shutdown = _parse_bool(value)
        elif key == "off_razer":
            cfg.off_razer = _parse_bool(value)
        elif key == "verbose_log":
            cfg.verbose_log = _parse_bool(value)

    if not cfg.log_file:
        cfg.log_file = default_log_file()
    if not cfg.noiloi_bin:
        cfg.noiloi_bin = default_noiloi_bin()
    return cfg
