from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json

from .config import Settings
from .metrics import health, recent_growth, wci


USAGE_KEYS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")


def _iso(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _usage(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    return {key: max(0, int(value.get(key, 0) or 0)) for key in USAGE_KEYS}


@dataclass
class ThreadState:
    path: Path
    thread_id: str
    started_at: str | None = None
    last_activity: str | None = None
    title: str | None = None
    model: str | None = None
    effort: str | None = None
    context_window: int | None = None
    usage: dict[str, int] = field(default_factory=lambda: {key: 0 for key in USAGE_KEYS})
    calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_ids: set[str] = field(default_factory=set)
    user_messages: int = 0
    compactions: int = 0
    invalid_lines: int = 0
    event_count: int = 0
    rate_limits: dict[str, Any] | None = None

    def ingest(self, event: dict[str, Any]) -> None:
        self.event_count += 1
        timestamp = _iso(event.get("timestamp"))
        self.started_at = self.started_at or timestamp
        self.last_activity = timestamp or self.last_activity
        kind = event.get("type")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ptype = payload.get("type")
        if kind == "session_meta":
            self.thread_id = str(payload.get("session_id") or payload.get("id") or self.thread_id)
            self.started_at = _iso(payload.get("timestamp")) or self.started_at
            window = payload.get("context_window")
            self.context_window = int(window) if isinstance(window, (int, float)) else self.context_window
        elif kind == "turn_context":
            self.model = payload.get("model") or self.model
            self.effort = payload.get("effort") or self.effort
        elif kind == "compacted" or (kind == "event_msg" and ptype == "context_compacted"):
            self.compactions += 1
        elif kind == "event_msg" and ptype == "user_message":
            self.user_messages += 1
            message = payload.get("message")
            if self.title is None and isinstance(message, str):
                cleaned = " ".join(message.split())
                self.title = cleaned[:72] + ("…" if len(cleaned) > 72 else "")
        elif kind == "response_item" and ptype in {"function_call", "custom_tool_call", "local_shell_call", "web_search_call"}:
            call_id = str(payload.get("call_id") or payload.get("id") or f"event-{self.event_count}")
            self.tool_call_ids.add(call_id)
        elif kind == "event_msg" and ptype == "token_count":
            info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
            total = _usage(info.get("total_token_usage"))
            last = _usage(info.get("last_token_usage"))
            if total:
                self.usage = total
            if last:
                point = {
                    **last,
                    "timestamp": timestamp,
                    "cumulative_input_tokens": (total or self.usage)["input_tokens"],
                    "cumulative_cached_input_tokens": (total or self.usage)["cached_input_tokens"],
                    "cumulative_output_tokens": (total or self.usage)["output_tokens"],
                    "tool_calls": len(self.tool_call_ids),
                }
                if not self.calls or point != self.calls[-1]:
                    self.calls.append(point)
            window = info.get("model_context_window")
            self.context_window = int(window) if isinstance(window, (int, float)) and window > 0 else self.context_window
            if isinstance(payload.get("rate_limits"), dict):
                self.rate_limits = {**payload["rate_limits"], "observed_at": timestamp}

    def as_dict(self, settings: Settings, include_evolution: bool = False) -> dict[str, Any]:
        latest = self.calls[-1] if self.calls else None
        pressure = None
        if latest and self.context_window:
            pressure = round(latest["input_tokens"] / self.context_window * 100, 2)
        growth = recent_growth(self.calls, settings.weights)
        result = {
            "id": self.thread_id,
            "started_at": self.started_at,
            "last_activity": self.last_activity,
            "title": self.title or f"Thread {self.thread_id[:8]}",
            "model": self.model,
            "reasoning_effort": self.effort,
            "usage": {**self.usage, "uncached_input_tokens": max(0, self.usage["input_tokens"] - self.usage["cached_input_tokens"])},
            "cache_ratio": round(self.usage["cached_input_tokens"] / self.usage["input_tokens"], 4) if self.usage["input_tokens"] else None,
            "wci": wci(self.usage, settings.weights),
            "wci_label": "Índice relativo",
            "tool_calls": len(self.tool_call_ids),
            "user_messages": self.user_messages,
            "compactions": self.compactions,
            "context_window": self.context_window,
            "context_pressure": pressure,
            "recent_growth_percent": growth,
            "health": health(self.usage, len(self.tool_call_ids), pressure, growth, settings.thresholds),
            "duration_seconds": self._duration(),
            "parser": {"events": self.event_count, "invalid_lines": self.invalid_lines},
        }
        if include_evolution:
            result["evolution"] = [
                {
                    **point,
                    "wci": wci(point, settings.weights),
                    "cumulative_wci": wci({
                        "input_tokens": point["cumulative_input_tokens"],
                        "cached_input_tokens": point["cumulative_cached_input_tokens"],
                        "output_tokens": point["cumulative_output_tokens"],
                    }, settings.weights),
                    "context_pressure": round(point["input_tokens"] / self.context_window * 100, 2) if self.context_window else None,
                }
                for point in self.calls
            ]
        return result

    def _duration(self) -> int | None:
        try:
            start = datetime.fromisoformat((self.started_at or "").replace("Z", "+00:00"))
            end = datetime.fromisoformat((self.last_activity or "").replace("Z", "+00:00"))
            return max(0, int((end - start).total_seconds()))
        except ValueError:
            return None


@dataclass
class FileCursor:
    offset: int = 0
    prefix_hash: str = ""
    state: ThreadState | None = None


class SessionMonitor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.files: dict[Path, FileCursor] = {}
        self.rate_reset_count = 0
        self._latest_rate: dict[str, Any] | None = None

    def scan(self) -> None:
        root = self.settings.sessions_dir
        if not root.exists():
            return
        for path in root.glob("*/*/*/*.jsonl"):
            self._scan_file(path.resolve())

    def _scan_file(self, path: Path) -> None:
        try:
            stat = path.stat()
            with path.open("rb") as handle:
                prefix_hash = hashlib.sha256(handle.read(256)).hexdigest()
                cursor = self.files.get(path)
                replaced = cursor is not None and cursor.prefix_hash != prefix_hash
                if cursor is None or stat.st_size < cursor.offset or replaced:
                    cursor = FileCursor(prefix_hash=prefix_hash, state=ThreadState(path, path.stem))
                    self.files[path] = cursor
                handle.seek(cursor.offset)
                chunk = handle.read()
        except (OSError, PermissionError):
            return
        if not chunk:
            return
        boundary = chunk.rfind(b"\n")
        if boundary < 0:
            return
        complete = chunk[: boundary + 1]
        cursor.offset += len(complete)
        assert cursor.state is not None
        for raw in complete.splitlines():
            try:
                event = json.loads(raw.decode("utf-8"))
                if isinstance(event, dict):
                    cursor.state.ingest(event)
            except (json.JSONDecodeError, UnicodeDecodeError):
                cursor.state.invalid_lines += 1
        if cursor.state.rate_limits:
            candidate = cursor.state.rate_limits
            if self._latest_rate is None or str(candidate.get("observed_at")) >= str(self._latest_rate.get("observed_at")):
                if self._latest_rate and self._is_reset(self._latest_rate, candidate):
                    self.rate_reset_count += 1
                self._latest_rate = candidate

    @staticmethod
    def _is_reset(old: dict[str, Any], new: dict[str, Any]) -> bool:
        for key in ("primary", "secondary"):
            before, after = old.get(key), new.get(key)
            if isinstance(before, dict) and isinstance(after, dict):
                if (after.get("used_percent") or 0) < (before.get("used_percent") or 0) and after.get("resets_at") != before.get("resets_at"):
                    return True
        return False

    def threads(self, details: bool = False) -> list[dict[str, Any]]:
        values = [cursor.state.as_dict(self.settings, details) for cursor in self.files.values() if cursor.state]
        return sorted(values, key=lambda item: item.get("last_activity") or "", reverse=True)

    def dashboard(self) -> dict[str, Any]:
        threads = self.threads()
        today = datetime.now().astimezone().date()
        threads_today = [item for item in threads if self._local_date(item.get("started_at") or item.get("last_activity")) == today]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sessions_dir": str(self.settings.sessions_dir),
            "poll_seconds": self.settings.poll_seconds,
            "rate_limits": self._latest_rate,
            "rate_limit_resets_detected": self.rate_reset_count,
            "active_thread": threads[0] if threads else None,
            "threads": threads_today,
            "methodology": {"wci_weights": vars(self.settings.weights), "health_normalized": True, "rate_limits_are_global": True},
        }

    @staticmethod
    def _local_date(value: str | None):
        try:
            return datetime.fromisoformat((value or "").replace("Z", "+00:00")).astimezone().date()
        except ValueError:
            return None

    def thread(self, thread_id: str) -> dict[str, Any] | None:
        for cursor in self.files.values():
            if cursor.state and cursor.state.thread_id == thread_id:
                return cursor.state.as_dict(self.settings, True)
        return None
