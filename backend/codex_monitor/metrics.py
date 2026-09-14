from __future__ import annotations

from typing import Any

from .config import Thresholds, WCIWeights


def wci(usage: dict[str, int], weights: WCIWeights) -> float:
    input_tokens = max(0, int(usage.get("input_tokens", 0) or 0))
    cached = min(input_tokens, max(0, int(usage.get("cached_input_tokens", 0) or 0)))
    output = max(0, int(usage.get("output_tokens", 0) or 0))
    return round((input_tokens - cached) * weights.uncached_input + cached * weights.cached_input + output * weights.output, 2)


def _bucket(value: float, limits: tuple[tuple[float, int], ...], above: int) -> int:
    for ceiling, points in limits:
        if value < ceiling:
            return points
    return above


def recent_growth(points: list[dict[str, Any]], weights: WCIWeights) -> float | None:
    calls = [wci(p, weights) for p in points if p.get("input_tokens") is not None]
    if len(calls) < 6:
        return None
    previous = sum(calls[-6:-3]) / 3
    current = sum(calls[-3:]) / 3
    if previous <= 0:
        return None
    return round(((current - previous) / previous) * 100, 2)


def health(
    usage: dict[str, int], tool_calls: int, context_pressure: float | None,
    growth: float | None, thresholds: Thresholds,
) -> dict[str, Any]:
    components = {
        "input": _bucket(usage.get("input_tokens", 0), thresholds.input, thresholds.input_above),
        "tools": _bucket(tool_calls, thresholds.tools, thresholds.tools_above),
        "output": _bucket(usage.get("output_tokens", 0), thresholds.output, thresholds.output_above),
        "growth": _bucket(growth or 0, thresholds.growth, thresholds.growth_above),
    }
    available_max = 65
    if context_pressure is not None:
        components["context"] = _bucket(context_pressure, thresholds.context, thresholds.context_above)
        available_max += 25
    raw = sum(components.values())
    score = min(100, round(raw / available_max * 100)) if available_max else 0
    label = "LEVE" if score < 25 else "CRESCENDO" if score < 50 else "CARA" if score < 75 else "MUITO CARA"
    if context_pressure is not None and context_pressure > 85:
        label = "MUITO CARA"
    if tool_calls > 100 and usage.get("input_tokens", 0) > 8_000_000:
        label = "MUITO CARA"
    if growth is not None and growth > 150 and score > 50:
        label = "MUITO CARA"
    recommendations = {
        "LEVE": "Continue normalmente.",
        "CRESCENDO": "A thread está acumulando contexto.",
        "CARA": "Termine a etapa atual e considere abrir uma nova thread.",
        "MUITO CARA": "Recomenda-se consolidar o estado e continuar em nova thread.",
    }
    return {"score": score, "raw_score": raw, "available_max": available_max, "components": components, "label": label, "recommendation": recommendations[label]}
