"""CLI: noiloi daily | weather | step | setup-daily."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import COLOR_STEPS, Config, load_config
from .cronicle import Cronicle, CronicleError
from .devices import set_razer_color, set_yeelight_ct, yeelight_off
from .logutil import log
from .power import log_setup_actions, setup_power_hooks
from .sun import cronicle_timing, today_sunset
from .weather import fetch_cloud_cover, start_offset_minutes


def _day_prefix(day: datetime) -> str:
    return day.strftime("%Y%m%d")


def _step_position(temp: int) -> tuple[int, int] | None:
    """Return 1-based (current, total) for a known Kelvin step, else None."""
    total = len(COLOR_STEPS)
    for idx, (ct, _) in enumerate(COLOR_STEPS):
        if ct == temp:
            return idx + 1, total
    return None


def cmd_daily(cfg: Config) -> int:
    cfg.require_location()
    cfg.require_cronicle()
    tz = ZoneInfo(cfg.timezone)
    now = datetime.now(tz)
    sunset = today_sunset(cfg, on=now.date())
    weather_at = sunset - timedelta(minutes=cfg.weather_lead_min)
    day = _day_prefix(sunset)
    lead = sunset - weather_at

    log(cfg, f"daily: sunset={sunset.isoformat()} weather_at={weather_at.isoformat()}")
    if cfg.verbose_log:
        log(
            cfg,
            f"daily: sunset−weather_at={lead} "
            f"({int(lead.total_seconds() // 60)}m, weather_lead_min={cfg.weather_lead_min})",
        )

    api = Cronicle(cfg)
    past = api.delete_past_oneshots(now.date())
    if past:
        log(cfg, f"daily: removed {past} past one-shot event(s)")

    if weather_at <= now:
        log(cfg, "daily: weather time already passed; running weather scheduling immediately")
        return cmd_weather(cfg, for_date=now.date(), self_delete=False)

    removed = api.delete_by_title_prefix(f"noiloi-weather-{day}")
    removed += api.delete_by_title_prefix(f"noiloi-step-{day}-")
    removed += api.delete_by_title_prefix(f"heliolamp-weather-{day}")
    removed += api.delete_by_title_prefix(f"heliolamp-step-{day}-")
    if removed:
        log(cfg, f"daily: removed {removed} stale event(s) for {day}")

    title = f"noiloi-weather-{day}"
    script = f"#!/bin/sh\nexec {cfg.noiloi_bin} weather\n"
    event = api.shell_event(
        title=title,
        script=script,
        timing=cronicle_timing(weather_at),
        timeout=180,
        notes=f"Fetch cloud cover and schedule color steps; sunset {sunset.isoformat()}",
    )
    event_id = api.create_event(event)
    log(cfg, f"daily: created {title} id={event_id} at {weather_at.strftime('%H:%M')}")
    return 0


def cmd_weather(cfg: Config, for_date=None, *, self_delete: bool = True) -> int:
    cfg.require_location()
    cfg.require_cronicle()
    tz = ZoneInfo(cfg.timezone)
    now = datetime.now(tz)
    day_date = for_date or now.date()
    sunset = today_sunset(cfg, on=day_date)
    day = _day_prefix(sunset)

    forecast = fetch_cloud_cover(cfg, sunset)
    offset, reason = start_offset_minutes(cfg, forecast.cloud_cover)
    start = sunset - timedelta(minutes=offset)
    log(
        cfg,
        f"weather: sunset={sunset.isoformat()} cloud={forecast.cloud_cover} "
        f"offset=-{offset}m ({reason}) start={start.isoformat()}",
    )
    if cfg.verbose_log:
        log(cfg, f"weather: url={forecast.url}")
        hour = forecast.forecast_hour or sunset.strftime("%Y-%m-%dT%H:00")
        cover = "unavailable" if forecast.cloud_cover is None else f"{forecast.cloud_cover}%"
        log(cfg, f"weather: forecast before sunset hour={hour} cloud_cover={cover}")
        log(
            cfg,
            f"weather: first step offset=-{offset}m "
            f"(threshold={cfg.cloud_threshold}%, clear={cfg.offset_clear_min}m, "
            f"overcast={cfg.offset_overcast_min}m) reason={reason}",
        )

    api = Cronicle(cfg)
    removed = api.delete_by_title_prefix(f"noiloi-step-{day}-")
    removed += api.delete_by_title_prefix(f"heliolamp-step-{day}-")
    if removed:
        log(cfg, f"weather: removed {removed} stale step event(s)")

    for idx, (ct, razer) in enumerate(COLOR_STEPS):
        when = start + timedelta(minutes=idx * cfg.step_interval_min)
        if when < now - timedelta(minutes=1):
            log(cfg, f"weather: skip past step {idx} at {when.isoformat()}")
            continue
        title = f"noiloi-step-{day}-{idx:02d}"
        if razer:
            script = f"#!/bin/sh\nexec {cfg.noiloi_bin} step {ct} {razer}\n"
        else:
            script = f"#!/bin/sh\nexec {cfg.noiloi_bin} step {ct}\n"
        event = api.shell_event(
            title=title,
            script=script,
            timing=cronicle_timing(when),
            timeout=60,
            notes=f"CT={ct} razer={razer or '-'}",
        )
        event_id = api.create_event(event)
        log(cfg, f"weather: created {title} id={event_id} at {when.strftime('%H:%M')} ct={ct}")

    if self_delete:
        _self_delete(
            api,
            cfg,
            label="weather",
            allowed_prefixes=("noiloi-weather-", "heliolamp-weather-"),
        )
    return 0


def cmd_step(cfg: Config, temp: int, razer: str | None) -> int:
    cfg.require_devices()
    pos = _step_position(temp)
    if cfg.verbose_log and pos is not None:
        current, total = pos
        log(
            cfg,
            f"step: {current}/{total} ct={temp} razer={razer or '-'}",
        )
    else:
        log(cfg, f"step: ct={temp} razer={razer or '-'}")
    errors = set_yeelight_ct(cfg, temp)
    for err in errors:
        log(cfg, f"step: yeelight {err}")
    if razer:
        try:
            set_razer_color(cfg, razer)
        except OSError as exc:
            log(cfg, f"step: razer error: {exc}")

    try:
        api = Cronicle(cfg)
        _self_delete(
            api,
            cfg,
            label="step",
            allowed_prefixes=("noiloi-step-", "heliolamp-step-"),
        )
    except CronicleError as exc:
        log(cfg, f"step: self-delete skipped: {exc}")
    return 0


def cmd_off(cfg: Config) -> int:
    cfg.require_devices()
    log(cfg, "off: powering down lamps")
    errors = yeelight_off(cfg)
    for err in errors:
        log(cfg, f"off: yeelight {err}")
    if cfg.off_razer:
        try:
            set_razer_color(cfg, "000000")
        except OSError as exc:
            log(cfg, f"off: razer error: {exc}")
    return 0 if not errors else 1


def cmd_setup_power(cfg: Config) -> int:
    actions = setup_power_hooks(cfg)
    log_setup_actions(cfg, actions)
    log(
        cfg,
        f"setup-power: off_on_sleep={int(cfg.off_on_sleep)} "
        f"off_on_shutdown={int(cfg.off_on_shutdown)} bin={cfg.noiloi_bin}",
    )
    return 0


def cmd_setup_daily(cfg: Config) -> int:
    """Create or replace the permanent noon noiloi-daily Cronicle event."""
    cfg.require_cronicle()
    api = Cronicle(cfg)
    for prefix in ("noiloi-daily", "heliolamp-daily"):
        for row in api.find_by_title_prefix(prefix):
            api.delete_event(str(row["id"]))
            log(cfg, f"setup-daily: removed old event id={row['id']} title={row.get('title')}")

    script = f"#!/bin/sh\nexec {cfg.noiloi_bin} daily\n"
    event = api.shell_event(
        title="noiloi-daily",
        script=script,
        timing={"hours": [12], "minutes": [0]},
        timeout=180,
        notes="Plan sunset weather fetch and color-step Cronicle events",
    )
    event_id = api.create_event(event)
    log(cfg, f"setup-daily: created noiloi-daily id={event_id} at 12:00 {cfg.timezone}")
    return 0


def _self_delete(
    api: Cronicle,
    cfg: Config,
    label: str,
    allowed_prefixes: tuple[str, ...] = (),
) -> None:
    event_id = os.environ.get("JOB_EVENT")
    if not event_id:
        log(cfg, f"{label}: JOB_EVENT unset; skip self-delete")
        return
    title = os.environ.get("JOB_TITLE", "")
    if allowed_prefixes and not any(title.startswith(p) for p in allowed_prefixes):
        log(cfg, f"{label}: JOB_TITLE={title!r} not in {allowed_prefixes}; skip self-delete")
        return
    api.delete_event(event_id)
    log(cfg, f"{label}: deleted Cronicle event id={event_id} title={title!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="noiloi",
        description='Sunset lighting scheduler ("night light" in a London accent)',
    )
    parser.add_argument(
        "--conf",
        default=None,
        help="Path to noiloi.conf (default: NOILOI_CONF, ~/.config/noiloi/noiloi.conf, or ./noiloi.conf)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("daily", help="Schedule today's weather one-shot from sunset")
    sub.add_parser("weather", help="Fetch cloud cover and schedule color steps")
    step = sub.add_parser("step", help="Apply one Yeelight/Razer color step")
    step.add_argument("temp", type=int, help="Yeelight color temperature Kelvin")
    step.add_argument("razer", nargs="?", default=None, help="Optional Razer hex color")
    sub.add_parser("off", help="Turn off Yeelight lamps (and optionally Razer)")
    sub.add_parser(
        "setup-power",
        help="Install/remove systemd --user hooks for sleep/shutdown lamp off",
    )
    sub.add_parser("setup-daily", help="Create permanent Cronicle noiloi-daily event")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(None if args.conf is None else Path(args.conf))

    try:
        if args.command == "daily":
            return cmd_daily(cfg)
        if args.command == "weather":
            return cmd_weather(cfg)
        if args.command == "step":
            return cmd_step(cfg, args.temp, args.razer)
        if args.command == "off":
            return cmd_off(cfg)
        if args.command == "setup-power":
            return cmd_setup_power(cfg)
        if args.command == "setup-daily":
            return cmd_setup_daily(cfg)
    except CronicleError as exc:
        log(cfg, f"error: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 — top-level CLI boundary
        log(cfg, f"error: {exc}")
        return 1

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
