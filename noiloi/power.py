"""Install systemd --user hooks to turn lamps off on sleep/shutdown."""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .logutil import log

SLEEP_UNIT = "noiloi-sleep.service"
SHUTDOWN_UNIT = "noiloi-shutdown.service"


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

    subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        check=False,
        capture_output=True,
    )
    return actions


def log_setup_actions(cfg: Config, actions: list[str]) -> None:
    for action in actions:
        log(cfg, f"setup-power: {action}")
