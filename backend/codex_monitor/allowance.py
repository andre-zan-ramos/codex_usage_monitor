from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .config import AllowanceSettings


def _parse_time(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


@dataclass(frozen=True)
class RateObservation:
    observed_at: datetime
    window_minutes: int
    used_percent: float
    resets_at: int | None
    thread_id: str
    model: str | None
    source: str


@dataclass
class CanonicalPoint:
    observed_at: datetime
    used_percent: float
    resets_at: int | None
    cycle: int
    sources: set[str] = field(default_factory=set)
    thread_ids: set[str] = field(default_factory=set)
    models: set[str] = field(default_factory=set)
    reset: bool = False


class AllowanceAnalyzer:
    """In-memory account-global timeline. It never assigns use to a thread."""

    def __init__(self, settings: AllowanceSettings):
        self.settings = settings
        self.observations: list[RateObservation] = []

    def rebuild(self, observations: Iterable[RateObservation]) -> None:
        self.observations = list(observations)

    def add(self, observation: RateObservation) -> None:
        self.observations.append(observation)

    def _points(self, window_minutes: int) -> list[CanonicalPoint]:
        raw = sorted((item for item in self.observations if item.window_minutes == window_minutes), key=lambda item: item.observed_at)
        merged: list[RateObservation] = []
        for item in raw:
            if merged:
                previous = merged[-1]
                if (item.used_percent == previous.used_percent and item.resets_at == previous.resets_at
                        and (item.observed_at - previous.observed_at).total_seconds() <= 2):
                    # The first item represents the timeline point; source metadata is merged below.
                    merged.append(item)
                    continue
            merged.append(item)
        points: list[CanonicalPoint] = []
        cycle = 0
        maximum: float | None = None
        reset_at: int | None = None
        for item in merged:
            if points and (item.used_percent == points[-1].used_percent and item.resets_at == points[-1].resets_at
                           and (item.observed_at - points[-1].observed_at).total_seconds() <= 2):
                point = points[-1]
                point.sources.add(item.source); point.thread_ids.add(item.thread_id)
                if item.model: point.models.add(item.model)
                continue
            reset_changed = (reset_at is not None and item.resets_at is not None
                             and abs(item.resets_at - reset_at) > self.settings.reset_jitter_seconds)
            reset_drop = (maximum is not None and maximum - item.used_percent >= self.settings.reset_drop_points
                          and item.used_percent <= self.settings.reset_low_percent)
            is_reset = reset_changed or reset_drop
            if is_reset:
                cycle += 1; maximum = None; reset_at = item.resets_at
            elif reset_at is None and item.resets_at is not None:
                reset_at = item.resets_at
            # Small decreases from concurrent producers are stale regressions, not points on the envelope.
            if maximum is not None and item.used_percent < maximum:
                continue
            maximum = item.used_percent if maximum is None else max(maximum, item.used_percent)
            point = CanonicalPoint(item.observed_at, item.used_percent, reset_at or item.resets_at, cycle, reset=is_reset)
            point.sources.add(item.source); point.thread_ids.add(item.thread_id)
            if item.model: point.models.add(item.model)
            points.append(point)
        return points

    def _sample(self, points: list[CanonicalPoint], since: datetime) -> list[CanonicalPoint]:
        buckets: dict[int, CanonicalPoint] = {}
        for point in points:
            if point.observed_at < since:
                continue
            bucket = int(point.observed_at.timestamp() // self.settings.min_bucket_seconds)
            old = buckets.get(bucket)
            if old is None or point.used_percent >= old.used_percent:
                buckets[bucket] = point
        return sorted(buckets.values(), key=lambda point: point.observed_at)

    def _rate(self, points: list[CanonicalPoint], now: datetime, minutes: int) -> float | None:
        selected = self._sample(points, now - timedelta(minutes=minutes))
        if len(selected) < self.settings.minimum_points:
            return None
        span = (selected[-1].observed_at - selected[0].observed_at).total_seconds() / 60
        if span < self.settings.minimum_span_minutes:
            return None
        xs = [(point.observed_at - selected[0].observed_at).total_seconds() / 60 for point in selected]
        ys = [point.used_percent for point in selected]
        mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
        denominator = sum((x - mean_x) ** 2 for x in xs)
        if denominator == 0:
            return None
        return round(max(0.0, sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator), 3)

    def _activity(self, thread_activities: dict[str, list[tuple[datetime, datetime]]], start: datetime, end: datetime) -> dict[str, Any]:
        active = [thread_id for thread_id, ranges in thread_activities.items() if any(left <= end and right >= start for left, right in ranges)]
        if len(active) == 1:
            return {"confidence": "MEDIUM", "active_threads": 1, "message": "Uma única thread local foi observada; isso não comprova exclusividade nem autoria do consumo global."}
        if len(active) > 1:
            return {"confidence": "LOW", "active_threads": len(active), "message": f"{len(active)} threads estavam ativas neste intervalo — atribuição individual indisponível."}
        grace = timedelta(minutes=self.settings.activity_grace_minutes)
        near = [thread_id for thread_id, ranges in thread_activities.items() if any(left - grace <= end and right + grace >= start for left, right in ranges)]
        if len(near) == 1:
            return {"confidence": "LOW", "active_threads": 1, "message": "Uma thread local próxima ao intervalo foi observada; atribuição não é causal."}
        return {"confidence": "NONE", "active_threads": 0, "message": "Atividade por thread insuficiente para contextualizar o consumo."}

    def summary(self, window_minutes: int, now: datetime, thread_activities: dict[str, list[tuple[datetime, datetime]]]) -> dict[str, Any] | None:
        points = [point for point in self._points(window_minutes) if point.observed_at <= now]
        if not points:
            return None
        latest = points[-1]
        age = max(0, int((now - latest.observed_at).total_seconds()))
        fresh = age <= self.settings.stale_seconds
        short_window = self.settings.primary_short_minutes if window_minutes == 300 else self.settings.secondary_recent_minutes
        recent_window = self.settings.primary_recent_minutes if window_minutes == 300 else self.settings.secondary_recent_minutes
        trend_window = self.settings.primary_recent_minutes if window_minutes == 300 else self.settings.secondary_trend_minutes
        current_cycle = latest.cycle
        cycle_points = [point for point in points if point.cycle == current_cycle]
        short_rate = self._rate(cycle_points, now, short_window)
        recent_rate = self._rate(cycle_points, now, recent_window)
        trend_rate = self._rate(cycle_points, now, trend_window)
        trend = "INDISPONÍVEL"
        if short_rate is not None and trend_rate is not None and max(short_rate, trend_rate) >= 0.1:
            trend = "ACELERANDO" if short_rate > trend_rate * 1.2 else "DESACELERANDO" if short_rate < trend_rate * .8 else "ESTÁVEL"
        session_start = cycle_points[0].observed_at
        for previous, current in zip(cycle_points, cycle_points[1:]):
            if (current.observed_at - previous.observed_at).total_seconds() > self.settings.session_gap_minutes * 60:
                session_start = current.observed_at
        session_rate = self._rate(cycle_points, now, max(1, int((now - session_start).total_seconds() / 60) + 1))
        classification = None
        if window_minutes == 300 and recent_rate is not None:
            classification = next((label for ceiling, label in self.settings.burn_thresholds if recent_rate < ceiling), "CRÍTICO")
        ttl = None
        if fresh and recent_rate and recent_rate > 0:
            ttl = max(0, round((100 - latest.used_percent) / recent_rate))
        start = max(now - timedelta(minutes=recent_window), cycle_points[0].observed_at)
        return {
            "window_minutes": window_minutes, "used_percent": latest.used_percent, "remaining_percent": round(100 - latest.used_percent, 2),
            "resets_at": latest.resets_at, "observed_at": latest.observed_at.isoformat(), "age_seconds": age, "fresh": fresh,
            "cycle": current_cycle, "short_rate_ppm": short_rate, "recent_rate_ppm": recent_rate,
            "session_rate_ppm": session_rate, "trend": trend, "classification": classification,
            "estimated_minutes_to_limit": ttl, "attribution": self._activity(thread_activities, start, latest.observed_at),
            "models": sorted({model for point in cycle_points[-20:] for model in point.models}),
        }

    def timeline(self, range_name: str, now: datetime) -> dict[str, Any]:
        minutes = {"1h": 60, "5h": 300, "today": 24 * 60, "7d": 7 * 24 * 60}.get(range_name)
        if minutes is None:
            raise ValueError("range inválido")
        since = now - timedelta(minutes=minutes)
        windows = {}
        for window in (300, 10080):
            points = [point for point in self._points(window) if point.observed_at <= now]
            windows[str(window)] = [{"observed_at": point.observed_at.isoformat(), "used_percent": point.used_percent,
                                     "resets_at": point.resets_at, "cycle": point.cycle, "reset": point.reset}
                                    for point in points if point.observed_at >= since]
        return {"range": range_name, "generated_at": now.isoformat(), "windows": windows}
