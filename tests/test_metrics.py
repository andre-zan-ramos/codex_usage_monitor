from codex_monitor.config import Thresholds, WCIWeights
from codex_monitor.metrics import health, recent_growth, wci


def test_wci_and_reasoning_is_not_double_counted():
    usage = {"input_tokens": 1_000, "cached_input_tokens": 800, "output_tokens": 100, "reasoning_output_tokens": 90}
    assert wci(usage, WCIWeights()) == 780


def test_growth_uses_last_three_against_previous_three():
    points = [{"input_tokens": value, "cached_input_tokens": 0, "output_tokens": 0} for value in [100, 100, 100, 200, 200, 200]]
    assert recent_growth(points, WCIWeights()) == 100
    assert recent_growth(points[:5], WCIWeights()) is None


def test_health_normalizes_without_context():
    result = health({"input_tokens": 3_000_000, "output_tokens": 75_000}, 20, None, None, Thresholds())
    assert result["available_max"] == 65
    assert 0 <= result["score"] <= 100
    assert "context" not in result["components"]


def test_health_override_for_real_context_pressure():
    result = health({"input_tokens": 10, "output_tokens": 1}, 0, 86, None, Thresholds())
    assert result["label"] == "MUITO CARA"
