"""Sunset calculation via astral."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sunset

from .config import Config


def round_to_minute(dt: datetime) -> datetime:
    if dt.second >= 30:
        dt = dt + timedelta(seconds=60 - dt.second)
    else:
        dt = dt - timedelta(seconds=dt.second)
    return dt.replace(microsecond=0)


def today_sunset(cfg: Config, on: date | None = None) -> datetime:
    if cfg.latitude is None or cfg.longitude is None:
        raise ValueError("latitude and longitude must be set in noiloi.conf")
    tz = ZoneInfo(cfg.timezone)
    day = on or datetime.now(tz).date()
    loc = LocationInfo("local", "", cfg.timezone, cfg.latitude, cfg.longitude)
    when = sunset(loc.observer, date=day, tzinfo=tz)
    return round_to_minute(when)


def cronicle_timing(dt: datetime) -> dict:
    """Build a one-shot Cronicle timing object for an aware datetime."""
    return {
        "years": [dt.year],
        "months": [dt.month],
        "days": [dt.day],
        "hours": [dt.hour],
        "minutes": [dt.minute],
    }
