"""Open-Meteo cloud cover forecast."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime

from .config import Config


@dataclass
class CloudForecast:
    url: str
    cloud_cover: int | None
    forecast_hour: str | None = None


def open_meteo_url(cfg: Config) -> str:
    params = urllib.parse.urlencode(
        {
            "latitude": cfg.latitude,
            "longitude": cfg.longitude,
            "hourly": "cloud_cover",
            "timezone": cfg.timezone,
            "forecast_days": 1,
        }
    )
    return f"https://api.open-meteo.com/v1/forecast?{params}"


def fetch_cloud_cover(cfg: Config, at: datetime) -> CloudForecast:
    """Return cloud cover for the hour containing ``at`` (None cover on failure)."""
    url = open_meteo_url(cfg)
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return CloudForecast(url=url, cloud_cover=None)

    times = data.get("hourly", {}).get("time") or []
    covers = data.get("hourly", {}).get("cloud_cover") or []
    if not times or not covers or len(times) != len(covers):
        return CloudForecast(url=url, cloud_cover=None)

    target = at.strftime("%Y-%m-%dT%H:00")
    for t, cover in zip(times, covers):
        if t == target:
            return CloudForecast(url=url, cloud_cover=int(cover), forecast_hour=t)

    hour_prefix = at.strftime("%Y-%m-%dT%H")
    for t, cover in zip(times, covers):
        if t.startswith(hour_prefix):
            return CloudForecast(url=url, cloud_cover=int(cover), forecast_hour=t)
    return CloudForecast(url=url, cloud_cover=None)


def start_offset_minutes(cfg: Config, cloud_cover: int | None) -> tuple[int, str]:
    """Return (offset_minutes, reason). Defaults to clear on unknown weather."""
    if cloud_cover is None:
        return cfg.offset_clear_min, "weather_unavailable"
    if cloud_cover >= cfg.cloud_threshold:
        return cfg.offset_overcast_min, f"overcast cloud_cover={cloud_cover}"
    return cfg.offset_clear_min, f"clear cloud_cover={cloud_cover}"
