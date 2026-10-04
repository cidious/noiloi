"""CLI: noiloi daily | weather | step | setup-daily."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import COLOR_STEPS, Config, load_config
from .cronicle import Cronicle, CronicleError
from .devices import razer_reachable, set_razer_color, set_yeelight_ct, yeelight_off, yeelight_reachable
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


def _current_step_index(start: datetime, now: datetime, step_interval_min: int) -> int | None:
    """Return the currently active step index once the ramp has started."""
    if now < start:
        return None
    interval_min = max(1, step_interval_min)
    elapsed = now - start
    idx = int(elapsed.total_seconds() // (interval_min * 60))
    return min(idx, len(COLOR_STEPS) - 1)


def _apply_lighting_step(cfg: Config, temp: int, razer: str | None) -> tuple[list[str], str | None]:
    """Apply a color step to the configured devices and capture any errors."""
    cfg.require_devices()
    yeelight_errors = set_yeelight_ct(cfg, temp)
    razer_error: str | None = None
    if razer:
        try:
            set_razer_color(cfg, razer)
        except OSError as exc:
            razer_error = str(exc)
    return yeelight_errors, razer_error


def _systemctl_user_state(unit: str) -> tuple[str, str, str | None]:
    try:
        enabled = subprocess.run(
            ["systemctl", "--user", "is-enabled", unit],
            check=False,
            capture_output=True,
            text=True,
        )
        active = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return "unknown", "unknown", str(exc)

    enabled_state = (enabled.stdout or enabled.stderr).strip() or f"rc={enabled.returncode}"
    active_state = (active.stdout or active.stderr).strip() or f"rc={active.returncode}"
    return enabled_state, active_state, None


def _unit_file_exists(unit: str) -> bool:
    return (Path.home() / ".config" / "systemd" / "user" / unit).is_file()


def _status_title(text: str) -> None:
    print(text)


def _status_section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def cmd_status(cfg: Config) -> int:
    issues = 0
    _status_title("Noiloi status")

    _status_section("Config")
    location_ok = cfg.latitude is not None and cfg.longitude is not None and bool(cfg.timezone)
    print(f"timezone: {cfg.timezone or 'missing'}")
    print(
        "location: "
        + (
            f"{cfg.latitude}, {cfg.longitude}"
            if cfg.latitude is not None and cfg.longitude is not None
            else "missing"
        )
    )
    print(f"cronicle: {cfg.cronicle_url} target={cfg.cronicle_target or 'missing'} category={cfg.cronicle_category}")
    print(f"yeelight_ips: {len(cfg.yeelight_ips)} configured")
    print(f"razer: {cfg.razer_host}:{cfg.razer_port}")
    print(f"noiloi_bin: {cfg.noiloi_bin}")
    print(f"run_on_startup: {int(cfg.run_on_startup)}")
    if not location_ok:
        issues += 1
        print("config issue: latitude/longitude/timezone incomplete")
    if not cfg.cronicle_target:
        issues += 1
        print("config issue: cronicle_target missing")
    if not cfg.yeelight_ips:
        issues += 1
        print("config issue: yeelight_ips missing")

    _status_section("Cronicle")
    if not cfg.cronicle_api_key or cfg.cronicle_api_key == "REPLACE_ME":
        issues += 1
        print("cronicle: not configured (missing API key)")
    else:
        try:
            api = Cronicle(cfg)
            schedule = api.get_schedule(limit=2000)
        except CronicleError as exc:
            issues += 1
            print(f"cronicle: error: {exc}")
        else:
            noiloi_daily = [row for row in schedule if str(row.get("title", "")).startswith("noiloi-daily")]
            legacy_daily = [row for row in schedule if str(row.get("title", "")).startswith("heliolamp-daily")]
            print(f"daily events: {len(noiloi_daily)} noiloi, {len(legacy_daily)} legacy")
            for row in noiloi_daily[:3]:
                print(f"  - {row.get('title')} (id={row.get('id')})")
            if len(noiloi_daily) == 0:
                issues += 1
                print("  issue: no daily event found")
            if legacy_daily:
                print(f"  legacy daily events: {len(legacy_daily)}")

            if location_ok:
                try:
                    day_key = datetime.now(ZoneInfo(cfg.timezone)).strftime("%Y%m%d")
                except Exception:
                    day_key = None
                    issues += 1
                    print("today events: unable to determine local day")
                if day_key:
                    today_weather = [
                        row
                        for row in schedule
                        if str(row.get("title", "")).startswith((f"noiloi-weather-{day_key}", f"heliolamp-weather-{day_key}"))
                    ]
                    today_steps = [
                        row
                        for row in schedule
                        if str(row.get("title", "")).startswith((f"noiloi-step-{day_key}-", f"heliolamp-step-{day_key}-"))
                    ]
                    print(f"today weather events: {len(today_weather)}")
                    for row in today_weather[:3]:
                        print(f"  - {row.get('title')} (id={row.get('id')})")
                    print(f"today step events: {len(today_steps)}")
                    for row in today_steps[:5]:
                        print(f"  - {row.get('title')} (id={row.get('id')})")

            legacy = [row for row in schedule if str(row.get("title", "")).startswith("heliolamp-")]
            if legacy:
                print(f"legacy heliolamp events: {len(legacy)}")
            else:
                print("legacy heliolamp events: none")

    _status_section("Systemd")
    for unit in ("noiloi-sleep.service", "noiloi-shutdown.service"):
        enabled, active, err = _systemctl_user_state(unit)
        if err:
            issues += 1
            print(f"{unit}: unavailable ({err})")
            continue
        print(f"{unit}: enabled={enabled} active={active}")
        expected = cfg.off_on_sleep if unit == "noiloi-sleep.service" else cfg.off_on_shutdown
        if expected and enabled != "enabled":
            issues += 1
            print(f"  issue: expected enabled because {unit} is configured on")
        if not expected and enabled == "enabled":
            issues += 1
            print(f"  issue: unit is enabled but config disables it")
    startup_service = "noiloi-startup.service"
    startup_timer = "noiloi-startup.timer"
    startup_service_exists = _unit_file_exists(startup_service)
    print(f"{startup_service}: file={'yes' if startup_service_exists else 'no'}")
    if cfg.run_on_startup and not startup_service_exists:
        issues += 1
        print("  issue: startup service file missing")
    if not cfg.run_on_startup and startup_service_exists:
        issues += 1
        print("  issue: startup service file present but config disables startup catch-up")
    enabled, active, err = _systemctl_user_state(startup_timer)
    if err:
        issues += 1
        print(f"{startup_timer}: unavailable ({err})")
    else:
        print(f"{startup_timer}: enabled={enabled} active={active}")
        if cfg.run_on_startup and (enabled != "enabled" or active != "active"):
            issues += 1
            print("  issue: startup timer is not enabled and active")
        if not cfg.run_on_startup and (enabled == "enabled" or active == "active"):
            issues += 1
            print("  issue: startup timer still active even though config disables it")

    _status_section("Devices")
    if cfg.yeelight_ips:
        for ip in cfg.yeelight_ips:
            ok = yeelight_reachable(ip)
            print(f"yeelight {ip}: {'reachable' if ok else 'unreachable'}")
            if not ok:
                issues += 1
    else:
        print("yeelight: not configured")
    razer_ok = razer_reachable(cfg.razer_host, cfg.razer_port)
    print(f"razer {cfg.razer_host}:{cfg.razer_port}: {'reachable' if razer_ok else 'unreachable'}")
    if not razer_ok:
        issues += 1

    return 0 if issues == 0 else 1


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

    active_idx = _current_step_index(start, now, cfg.step_interval_min)
    if active_idx is not None:
        ct, razer = COLOR_STEPS[active_idx]
        current, total = active_idx + 1, len(COLOR_STEPS)
        log(
            cfg,
            f"weather: applying current step {current}/{total} ct={ct} razer={razer or '-'}",
        )
        errors, razer_error = _apply_lighting_step(cfg, ct, razer)
        for err in errors:
            log(cfg, f"weather: yeelight {err}")
        if razer_error:
            log(cfg, f"weather: razer error: {razer_error}")

    start_idx = 0 if active_idx is None else active_idx + 1
    for idx, (ct, razer) in enumerate(COLOR_STEPS[start_idx:], start=start_idx):
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
    errors, razer_error = _apply_lighting_step(cfg, temp, razer)
    for err in errors:
        log(cfg, f"step: yeelight {err}")
    if razer_error:
        log(cfg, f"step: razer error: {razer_error}")

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
    log(cfg, f"setup-power: run_on_startup={int(cfg.run_on_startup)}")
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
    sub.add_parser("status", help="Show current configuration, schedule, device, and hook status")
    sub.add_parser(
        "setup-power",
        help="Install/remove systemd --user hooks for sleep/shutdown and login catch-up",
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
        if args.command == "status":
            return cmd_status(cfg)
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
