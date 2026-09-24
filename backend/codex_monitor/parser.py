from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json

from .config import Settings
from .metrics import health, recent_growth, wci
from .allowance import AllowanceAnalyzer, RateObservation, _parse_time


USAGE_KEYS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")


def _iso(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _usage(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    return {key: max(0, int(value.get(key, 0) or 0)) for key in USAGE_KEYS}


def _message_title(message: Any) -> str | None:
    if not isinstance(message, str):
        return None
    cleaned = " ".join(message.split())
    if not cleaned or cleaned.startswith(("<recommended_plugins>", "<environment_context>")):
        return None
    return cleaned[:72] + ("…" if len(cleaned) > 72 else "")


def _response_user_message(payload: dict[str, Any]) -> str | None:
    if payload.get("type") != "message" or payload.get("role") != "user":
        return None
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    for item in content:
        if isinstance(item, dict) and item.get("type") in {"input_text", "text"}:
            title = _message_title(item.get("text"))
            if title:
                return title
    return None


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
    rate_observations: list[RateObservation] = field(default_factory=list)
    activity_events: list[datetime] = field(default_factory=list)

    def ingest(self, event: dict[str, Any]) -> None:
        self.event_count += 1
        timestamp = _iso(event.get("timestamp"))
        self.started_at = self.started_at or timestamp
        self.last_activity = timestamp or self.last_activity
        parsed_timestamp = _parse_time(timestamp)
        if parsed_timestamp:
            self.activity_events.append(parsed_timestamp)
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
            self.title = self.title or _message_title(payload.get("message"))
        elif kind == "response_item":
            self.title = self.title or _response_user_message(payload)
        if kind == "response_item" and ptype in {"function_call", "custom_tool_call", "local_shell_call", "web_search_call"}:
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
                for window_name in ("primary", "secondary"):
                    window_data = payload["rate_limits"].get(window_name)
                    if not isinstance(window_data, dict) or parsed_timestamp is None:
                        continue
                    used, minutes = window_data.get("used_percent"), window_data.get("window_minutes")
                    if not isinstance(used, (int, float)) or not isinstance(minutes, (int, float)):
                        continue
                    reset = window_data.get("resets_at")
                    self.rate_observations.append(RateObservation(
                        observed_at=parsed_timestamp, window_minutes=int(minutes), used_percent=max(0, min(100, float(used))),
                        resets_at=int(reset) if isinstance(reset, (int, float)) else None,
                        thread_id=self.thread_id, model=self.model, source=str(self.path),
                    ))

    def as_dict(
        self,
        settings: Settings,
        include_evolution: bool = False,
        indexed_title: str | None = None,
    ) -> dict[str, Any]:
        latest = self.calls[-1] if self.calls else None
        pressure = None
        if latest and self.context_window:
            pressure = round(latest["input_tokens"] / self.context_window * 100, 2)
        growth = recent_growth(self.calls, settings.weights)
        result = {
            "id": self.thread_id,
            "started_at": self.started_at,
            "last_activity": self.last_activity,
            "title": indexed_title or self.title or f"Thread {self.thread_id[:8]}",
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
        self.allowance = AllowanceAnalyzer(settings.allowance)
        self.thread_titles: dict[str, str] = {}
        self._session_index_signature: tuple[int, int] | None = None

    def scan(self) -> None:
        self._scan_session_index()
        root = self.settings.sessions_dir
        if not root.exists():
            return
        for path in root.glob("*/*/*/*.jsonl"):
            self._scan_file(path.resolve())

    def _scan_session_index(self) -> None:
        path = self.settings.session_index_file or self.settings.sessions_dir.parent / "session_index.jsonl"
        try:
            stat = path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            if signature == self._session_index_signature:
                return
            titles: dict[str, str] = {}
            with path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    try:
                        item = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    thread_id = item.get("id") if isinstance(item, dict) else None
                    title = item.get("thread_name") if isinstance(item, dict) else None
                    if isinstance(thread_id, str) and isinstance(title, str) and title.strip():
                        titles[thread_id] = " ".join(title.split())
        except (OSError, PermissionError, UnicodeDecodeError):
            return
        self.thread_titles = titles
        self._session_index_signature = signature

    def _scan_file(self, path: Path) -> None:
        rebuilt = False
        try:
            stat = path.stat()
            with path.open("rb") as handle:
                prefix_hash = hashlib.sha256(handle.read(256)).hexdigest()
                cursor = self.files.get(path)
                replaced = cursor is not None and cursor.prefix_hash != prefix_hash
                reset_existing = cursor is not None and (stat.st_size < cursor.offset or replaced)
                if cursor is None or reset_existing:
                    cursor = FileCursor(prefix_hash=prefix_hash, state=ThreadState(path, path.stem))
                    self.files[path] = cursor
                    if reset_existing:
                        self._rebuild_allowance()
                        rebuilt = True
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
        observations_before = len(cursor.state.rate_observations)
        for raw in complete.splitlines():
            try:
                event = json.loads(raw.decode("utf-8"))
                if isinstance(event, dict):
                    cursor.state.ingest(event)
            except (json.JSONDecodeError, UnicodeDecodeError):
                cursor.state.invalid_lines += 1
        if not rebuilt:
            for observation in cursor.state.rate_observations[observations_before:]:
                self.allowance.add(observation)
        else:
            # Replacement was rebuilt before this chunk was parsed.
            self._rebuild_allowance()

    def _rebuild_allowance(self) -> None:
        self.allowance.rebuild(
            observation for cursor in self.files.values() if cursor.state
            for observation in cursor.state.rate_observations
        )

    def _activity_ranges(self) -> dict[str, list[tuple[datetime, datetime]]]:
        result: dict[str, list[tuple[datetime, datetime]]] = {}
        gap = self.settings.allowance.activity_gap_minutes * 60
        for cursor in self.files.values():
            if not cursor.state:
                continue
            times = sorted(set(cursor.state.activity_events))
            if not times:
                continue
            ranges: list[tuple[datetime, datetime]] = []
            start = end = times[0]
            for item in times[1:]:
                if (item - end).total_seconds() <= gap:
                    end = item
                else:
                    ranges.append((start, end)); start = end = item
            ranges.append((start, end))
            result[cursor.state.thread_id] = ranges
        return result

    def threads(self, details: bool = False) -> list[dict[str, Any]]:
        values = [
            cursor.state.as_dict(self.settings, details, self.thread_titles.get(cursor.state.thread_id))
            for cursor in self.files.values() if cursor.state
        ]
        return sorted(values, key=lambda item: item.get("last_activity") or "", reverse=True)

    def dashboard(self) -> dict[str, Any]:
        threads = self.threads()
        today = datetime.now().astimezone().date()
        threads_today = [item for item in threads if self._local_date(item.get("started_at") or item.get("last_activity")) == today]
        visible_threads = threads_today if len(threads_today) >= 5 else threads[:5]
        now = datetime.now(timezone.utc)
        activity = self._activity_ranges()
        primary = self.allowance.summary(300, now, activity)
        secondary = self.allowance.summary(10080, now, activity)
        return {
            "generated_at": now.isoformat(),
            "sessions_dir": str(self.settings.sessions_dir),
            "poll_seconds": self.settings.poll_seconds,
            "allowance": {"primary": primary, "secondary": secondary,
                          "models_recent": self._models_recent(),
                          "alerts": self._alerts(primary, secondary)},
            # Kept for existing local API consumers; new UI uses `allowance`.
            "rate_limits": self._legacy_rate_limits(primary, secondary),
            "active_thread": threads[0] if threads else None,
            "threads": visible_threads,
            "methodology": {"wci_weights": vars(self.settings.weights), "health_normalized": True, "rate_limits_are_global": True},
        }

    def _models_recent(self) -> list[dict[str, Any]]:
        values = {item.get("model") for item in self.threads() if item.get("model")}
        return [{"id": model, "label": self._model_label(model), "relative_cost_factor": self.settings.allowance.model_cost_factors.get(model)} for model in sorted(values)]

    @staticmethod
    def _legacy_rate_limits(primary: dict[str, Any] | None, secondary: dict[str, Any] | None) -> dict[str, Any] | None:
        if not primary and not secondary:
            return None
        def legacy(value: dict[str, Any] | None) -> dict[str, Any] | None:
            if not value:
                return None
            return {key: value[key] for key in ("used_percent", "window_minutes", "resets_at")}
        observed = max((item["observed_at"] for item in (primary, secondary) if item), default=None)
        return {"primary": legacy(primary), "secondary": legacy(secondary), "observed_at": observed}

    @staticmethod
    def _model_label(model: str) -> str:
        return {"gpt-5.6-sol": "GPT-5.6 Sol", "gpt-6-astra": "GPT-6 Astra"}.get(model, model)

    @staticmethod
    def _alerts(primary: dict[str, Any] | None, secondary: dict[str, Any] | None) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []
        if primary:
            if primary["classification"] in {"ELEVADO", "MUITO ALTO", "CRÍTICO"}:
                alerts.append({"severity": primary["classification"], "message": "O consumo da janela de 5h está acelerado."})
            for value in (90, 80):
                if primary["used_percent"] >= value:
                    alerts.append({"severity": "CRÍTICO" if value == 90 else "MUITO ALTO", "message": f"A cota de 5h atingiu {value}% utilizada."}); break
        if secondary:
            for value in (90, 80):
                if secondary["used_percent"] >= value:
                    alerts.append({"severity": "CRÍTICO" if value == 90 else "MUITO ALTO", "message": f"A cota semanal atingiu {value}% utilizada."}); break
        return alerts

    def rate_timeline(self, range_name: str) -> dict[str, Any]:
        return self.allowance.timeline(range_name, datetime.now(timezone.utc))

    @staticmethod
    def _local_date(value: str | None):
        try:
            return datetime.fromisoformat((value or "").replace("Z", "+00:00")).astimezone().date()
        except ValueError:
            return None

    def thread(self, thread_id: str) -> dict[str, Any] | None:
        for cursor in self.files.values():
            if cursor.state and cursor.state.thread_id == thread_id:
                return cursor.state.as_dict(self.settings, True, self.thread_titles.get(thread_id))
        return None
