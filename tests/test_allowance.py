from datetime import datetime, timedelta, timezone

from codex_monitor.allowance import AllowanceAnalyzer, RateObservation
from codex_monitor.config import AllowanceSettings


NOW = datetime(2026, 9, 19, 18, 30, tzinfo=timezone.utc)


def point(minute, used, *, thread="one", reset=100, window=300):
    return RateObservation(NOW - timedelta(minutes=minute), window, used, reset, thread, "gpt-6-astra", f"{thread}.jsonl")


def summary(items, window=300):
    analyzer = AllowanceAnalyzer(AllowanceSettings())
    analyzer.rebuild(items)
    return analyzer.summary(window, NOW, {"one": [(NOW - timedelta(minutes=20), NOW)], "two": [(NOW - timedelta(minutes=20), NOW)]})


def test_recent_burn_classification_and_time_to_limit():
    value = summary([point(14, 10), point(9, 20), point(4, 30), point(0, 38)])
    assert value["recent_rate_ppm"] == 2.0
    assert value["classification"] == "CRÍTICO"
    assert value["estimated_minutes_to_limit"] == 31


def test_close_and_duplicate_observations_are_merged_and_regressions_ignored():
    first = point(10, 40)
    duplicate = RateObservation(first.observed_at + timedelta(seconds=1), 300, 40, 100, "two", "gpt-5.6-sol", "two.jsonl")
    value = summary([point(14, 10), first, duplicate, point(5, 39, thread="two"), point(0, 60)])
    assert value["used_percent"] == 60
    assert value["cycle"] == 0


def test_reset_drop_starts_new_cycle_without_negative_burn():
    value = summary([point(14, 80), point(10, 98), point(5, 2, reset=None), point(2, 6, reset=None), point(0, 10, reset=None)])
    assert value["cycle"] == 1
    assert value["used_percent"] == 10
    assert value["recent_rate_ppm"] >= 0


def test_explicit_reset_and_staleness_disable_ttl():
    old = NOW - timedelta(minutes=5)
    analyzer = AllowanceAnalyzer(AllowanceSettings())
    analyzer.rebuild([
        RateObservation(old - timedelta(minutes=5), 300, 90, 100, "one", None, "a"),
        RateObservation(old, 300, 2, 300, "one", None, "a"),
    ])
    value = analyzer.summary(300, NOW, {})
    assert value["cycle"] == 1
    assert value["fresh"] is False
    assert value["estimated_minutes_to_limit"] is None


def test_weekly_and_attribution_are_global_context_only():
    value = summary([point(55, 70, window=10080), point(30, 71, window=10080), point(0, 73, window=10080)], 10080)
    assert value["classification"] is None
    assert value["attribution"]["confidence"] == "LOW"


def test_timeline_marks_reset_and_ranges():
    analyzer = AllowanceAnalyzer(AllowanceSettings())
    analyzer.rebuild([point(14, 98), point(10, 2, reset=None), point(0, 8, reset=None)])
    timeline = analyzer.timeline("1h", NOW)
    assert any(item["reset"] for item in timeline["windows"]["300"])
