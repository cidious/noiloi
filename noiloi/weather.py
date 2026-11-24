"""Cloud cover forecast: MET Norway primary, Open-Meteo fallback."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import Config

_USER_AGENT = "noiloi/1.0 (https://github.com/cidious/noiloi; personal lighting automation)"


@dataclass
class CloudForecast:
    url: str
    cloud_cover: int | None
    forecast_hour: str | None = None
    provider: str = ""
    error: str | None = None


def _http_get_json(url: str, *, headers: dict[str, str] | None = None) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def metno_url(cfg: Config) -> str:
    params = urllib.parse.urlencode(
        {
            "lat": cfg.latitude,
            "lon": cfg.longitude,
        }
    )
    return f"https://api.met.no/weatherapi/locationforecast/2.0/compact?{params}"


def open_meteo_url(cfg: Config) -> str:
    params = urllib.parse.urlencode(
        {
            "latitude": cfg.latitude,
            "longitude": cfg.longitude,
            "hourly": "cloud_cover",
            "timezone": cfg.timezone,
            "forecast_days": 2,
        }
    )
    return f"https://api.open-meteo.com/v1/forecast?{params}"


def _fetch_metno(cfg: Config, at: datetime) -> CloudForecast:
    url = metno_url(cfg)
    try:
        data = _http_get_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return CloudForecast(url=url, cloud_cover=None, provider="metno", error=str(exc))

    series = (data.get("properties") or {}).get("timeseries") or []
    if not series:
        return CloudForecast(url=url, cloud_cover=None, provider="metno", error="empty timeseries")

    target = at.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    best: tuple[int, datetime, int] | None = None  # (abs_seconds, time, cover)
    for row in series:
        raw_time = row.get("time")
        if not raw_time:
            continue
        try:
            when = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        except ValueError:
            continue
        details = ((row.get("data") or {}).get("instant") or {}).get("details") or {}
        cover = details.get("cloud_area_fraction")
        if cover is None:
            continue
        delta = abs(int((when - target).total_seconds()))
        if best is None or delta < best[0]:
            best = (delta, when, int(round(float(cover))))

    if best is None:
        return CloudForecast(url=url, cloud_cover=None, provider="metno", error="no cloud_area_fraction")
    # Reject matches more than 90 minutes away
    if best[0] > 90 * 60:
        return CloudForecast(url=url, cloud_cover=None, provider="metno", error="no nearby hour")
    local = best[1].astimezone(ZoneInfo(cfg.timezone))
    return CloudForecast(
        url=url,
        cloud_cover=best[2],
        forecast_hour=local.strftime("%Y-%m-%dT%H:%M"),
        provider="metno",
    )


def _fetch_openmeteo(cfg: Config, at: datetime) -> CloudForecast:
    url = open_meteo_url(cfg)
    try:
        data = _http_get_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return CloudForecast(url=url, cloud_cover=None, provider="openmeteo", error=str(exc))

    times = data.get("hourly", {}).get("time") or []
    covers = data.get("hourly", {}).get("cloud_cover") or []
    if not times or not covers or len(times) != len(covers):
        return CloudForecast(url=url, cloud_cover=None, provider="openmeteo", error="empty hourly")

    target = at.strftime("%Y-%m-%dT%H:00")
    for t, cover in zip(times, covers):
        if t == target:
            return CloudForecast(
                url=url,
                cloud_cover=int(cover),
                forecast_hour=t,
                provider="openmeteo",
            )

    hour_prefix = at.strftime("%Y-%m-%dT%H")
    for t, cover in zip(times, covers):
        if t.startswith(hour_prefix):
            return CloudForecast(
                url=url,
                cloud_cover=int(cover),
                forecast_hour=t,
                provider="openmeteo",
            )
    return CloudForecast(url=url, cloud_cover=None, provider="openmeteo", error="hour not found")


def fetch_cloud_cover(cfg: Config, at: datetime) -> CloudForecast:
    """Return cloud cover %% near sunset hour.

    Providers: ``metno`` (default), ``openmeteo``, or ``auto`` (metno then openmeteo).
    """
    provider = (cfg.weather_provider or "metno").strip().lower()
    if provider == "openmeteo":
        return _fetch_openmeteo(cfg, at)
    if provider == "metno":
        return _fetch_metno(cfg, at)

    # auto
    primary = _fetch_metno(cfg, at)
    if primary.cloud_cover is not None:
        return primary
    fallback = _fetch_openmeteo(cfg, at)
    if fallback.cloud_cover is not None:
        fallback.error = f"metno failed ({primary.error}); used openmeteo"
        return fallback
    return CloudForecast(
        url=primary.url,
        cloud_cover=None,
        provider="auto",
        error=f"metno={primary.error}; openmeteo={fallback.error}",
    )


def start_offset_minutes(cfg: Config, cloud_cover: int | None) -> tuple[int, str]:
    """Return (offset_minutes, reason). Defaults to clear on unknown weather."""
    if cloud_cover is None:
        return cfg.offset_clear_min, "weather_unavailable"
    if cloud_cover >= cfg.cloud_threshold:
        return cfg.offset_overcast_min, f"overcast cloud_cover={cloud_cover}"
    return cfg.offset_clear_min, f"clear cloud_cover={cloud_cover}"
