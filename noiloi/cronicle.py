"""Minimal Cronicle REST client."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .config import Config


class CronicleError(RuntimeError):
    pass


class Cronicle:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        if not cfg.cronicle_api_key or cfg.cronicle_api_key == "REPLACE_ME":
            raise CronicleError("cronicle_api_key is not set in noiloi.conf")

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.cfg.cronicle_url}{path}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST" if payload is not None else "GET",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.cfg.cronicle_api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise CronicleError(f"HTTP {exc.code} for {path}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise CronicleError(f"request failed for {path}: {exc}") from exc

        if body.get("code", 0) != 0:
            raise CronicleError(f"Cronicle error for {path}: {body}")
        return body

    def get_schedule(self, limit: int = 1000) -> list[dict[str, Any]]:
        body = self._request(
            "/api/app/get_schedule/v1",
            {"offset": 0, "limit": limit},
        )
        return list(body.get("rows") or [])

    def create_event(self, event: dict[str, Any]) -> str:
        body = self._request("/api/app/create_event/v1", event)
        event_id = body.get("id")
        if not event_id:
            raise CronicleError(f"create_event returned no id: {body}")
        return str(event_id)

    def delete_event(self, event_id: str) -> None:
        self._request("/api/app/delete_event/v1", {"id": event_id})

    def find_by_title_prefix(self, prefix: str) -> list[dict[str, Any]]:
        return [row for row in self.get_schedule() if str(row.get("title", "")).startswith(prefix)]

    def delete_by_title_prefix(self, prefix: str) -> int:
        deleted = 0
        for row in self.find_by_title_prefix(prefix):
            event_id = row.get("id")
            if event_id:
                self.delete_event(str(event_id))
                deleted += 1
        return deleted

    def shell_event(
        self,
        *,
        title: str,
        script: str,
        timing: dict[str, Any] | None,
        enabled: int = 1,
        timeout: int = 120,
        notes: str = "",
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "title": title,
            "enabled": enabled,
            "category": self.cfg.cronicle_category,
            "plugin": self.cfg.cronicle_plugin,
            "target": self.cfg.cronicle_target,
            "timezone": self.cfg.timezone,
            "catch_up": 0,
            "max_children": 1,
            "timeout": timeout,
            "retries": 0,
            "detached": 0,
            "multiplex": 0,
            "notes": notes,
            "params": {
                "script": script,
                "annotate": 1,
                "json": 0,
            },
        }
        if timing is not None:
            event["timing"] = timing
        return event
