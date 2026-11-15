from __future__ import annotations

from typing import Any

from .config import Thresholds, WCIWeights


def wci(usage: dict[str, int | None], weights: WCIWeights) -> float | None:
    if any(usage.get(key) is None for key in ("input_tokens", "cached_input_tokens", "output_tokens")):
        return None
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
    calls = [wci(p, weights) for p in points[-6:]]
    if len(calls) < 6:
        return None
    if any(value is None for value in calls):
        return None
    previous = sum(calls[-6:-3]) / 3
    current = sum(calls[-3:]) / 3
    if previous <= 0:
        return None
    return round(((current - previous) / previous) * 100, 2)


def health(
    usage: dict[str, int | None], tool_calls: int, context_pressure: float | None,
    growth: float | None, thresholds: Thresholds,
) -> dict[str, Any]:
    if usage.get("input_tokens") is None or usage.get("output_tokens") is None:
        return {"score": None, "raw_score": None, "available_max": None, "components": {},
                "label": "INDISPONÍVEL", "heuristic": True,
                "recommendation": "Dados de entrada ou saída não informados; diagnóstico indisponível."}
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
    label = "CARGA BAIXA" if score < 25 else "CARGA MODERADA" if score < 50 else "CARGA ALTA" if score < 75 else "CARGA MUITO ALTA"
    if context_pressure is not None and context_pressure > 85:
        label = "CARGA MUITO ALTA"
    if tool_calls > 100 and usage.get("input_tokens", 0) > 8_000_000:
        label = "CARGA MUITO ALTA"
    if growth is not None and growth > 150 and score > 50:
        label = "CARGA MUITO ALTA"
    recommendations = {
        "CARGA BAIXA": "Carga estrutural heurística baixa; não mede custo financeiro ou eficiência.",
        "CARGA MODERADA": "Carga estrutural heurística moderada; não mede custo financeiro ou eficiência.",
        "CARGA ALTA": "Carga estrutural heurística alta; não determina a necessidade de reiniciar a thread.",
        "CARGA MUITO ALTA": "Carga estrutural heurística muito alta; não determina a necessidade de reiniciar a thread.",
    }
    return {"score": score, "raw_score": raw, "available_max": available_max, "components": components, "label": label, "heuristic": True, "recommendation": recommendations[label]}
