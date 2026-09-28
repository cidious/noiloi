"""Simple file logger."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Config


def log(cfg: Config, message: str) -> None:
    tz = ZoneInfo(cfg.timezone)
    stamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %z")
    line = f"{stamp} {message}\n"
    path = Path(cfg.log_file)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        print(f"{line.rstrip()} (log write failed: {exc})", flush=True)
        return
    print(line, end="", flush=True)
