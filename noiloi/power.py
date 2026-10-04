"""Install systemd --user hooks to turn lamps off on sleep/shutdown."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .logutil import log

SLEEP_UNIT = "noiloi-sleep.service"
SHUTDOWN_UNIT = "noiloi-shutdown.service"
STARTUP_SERVICE = "noiloi-startup.service"
STARTUP_TIMER = "noiloi-startup.timer"


def _user_unit_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def _unit_text(cfg: Config, *, before: str, wanted_by: str, description: str) -> str:
    bin_path = cfg.noiloi_bin
    return (
        "[Unit]\n"
        f"Description={description}\n"
        f"Before={before}\n"
        "DefaultDependencies=no\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={bin_path} off\n"
        "TimeoutStartSec=15\n"
        "\n"
        "[Install]\n"
        f"WantedBy={wanted_by}\n"
    )


def _startup_service_text(cfg: Config) -> str:
    bin_path = cfg.noiloi_bin
    return (
        "[Unit]\n"
        "Description=Run noiloi daily after login\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={bin_path} daily\n"
        "TimeoutStartSec=180\n"
    )


def _startup_timer_text() -> str:
    return (
        "[Unit]\n"
        "Description=Run noiloi daily shortly after session start\n"
        "\n"
        "[Timer]\n"
        "OnStartupSec=90s\n"
        f"Unit={STARTUP_SERVICE}\n"
        "AccuracySec=1s\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def setup_power_hooks(cfg: Config) -> list[str]:
    """Write/enable or remove systemd user units. Returns human-readable actions."""
    import subprocess

    unit_dir = _user_unit_dir()
    unit_dir.mkdir(parents=True, exist_ok=True)
    actions: list[str] = []

    plans = [
        (
            SLEEP_UNIT,
            cfg.off_on_sleep,
            _unit_text(
                cfg,
                before="sleep.target",
                wanted_by="sleep.target",
                description="Turn off noiloi lamps before system sleep",
            ),
        ),
        (
            SHUTDOWN_UNIT,
            cfg.off_on_shutdown,
            _unit_text(
                cfg,
                before="shutdown.target",
                wanted_by="exit.target",
                description="Turn off noiloi lamps before session exit/shutdown",
            ),
        ),
    ]

    for name, enabled, body in plans:
        path = unit_dir / name
        if enabled:
            path.write_text(body, encoding="utf-8")
            actions.append(f"wrote {path}")
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                check=False,
                capture_output=True,
            )
            result = subprocess.run(
                ["systemctl", "--user", "enable", "--now", name],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                actions.append(f"enabled {name}")
            else:
                actions.append(
                    f"enable {name} failed: {(result.stderr or result.stdout).strip()}"
                )
        else:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", name],
                check=False,
                capture_output=True,
            )
            if path.exists():
                path.unlink()
                actions.append(f"removed {path}")
            else:
                actions.append(f"{name} already disabled")

    startup_service_path = unit_dir / STARTUP_SERVICE
    startup_timer_path = unit_dir / STARTUP_TIMER
    if cfg.run_on_startup:
        startup_service_path.write_text(_startup_service_text(cfg), encoding="utf-8")
        actions.append(f"wrote {startup_service_path}")
        startup_timer_path.write_text(_startup_timer_text(), encoding="utf-8")
        actions.append(f"wrote {startup_timer_path}")
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=False,
            capture_output=True,
        )
        result = subprocess.run(
            ["systemctl", "--user", "enable", "--now", STARTUP_TIMER],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            actions.append(f"enabled {STARTUP_TIMER}")
        else:
            actions.append(
                f"enable {STARTUP_TIMER} failed: {(result.stderr or result.stdout).strip()}"
            )
    else:
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", STARTUP_TIMER],
            check=False,
            capture_output=True,
        )
        if startup_timer_path.exists():
            startup_timer_path.unlink()
            actions.append(f"removed {startup_timer_path}")
        else:
            actions.append(f"{STARTUP_TIMER} already disabled")
        if startup_service_path.exists():
            startup_service_path.unlink()
            actions.append(f"removed {startup_service_path}")
        else:
            actions.append(f"{STARTUP_SERVICE} already disabled")

    subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        check=False,
        capture_output=True,
    )
    return actions


def log_setup_actions(cfg: Config, actions: list[str]) -> None:
    for action in actions:
        log(cfg, f"setup-power: {action}")
