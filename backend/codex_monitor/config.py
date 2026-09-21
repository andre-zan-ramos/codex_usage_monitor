from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass(frozen=True)
class WCIWeights:
    uncached_input: float = 1.0
    cached_input: float = 0.10
    output: float = 5.0


@dataclass(frozen=True)
class Thresholds:
    input: tuple[tuple[int, int], ...] = (
        (1_000_000, 0), (3_000_000, 5), (7_000_000, 12), (10_000_000, 17),
    )
    input_above: int = 20
    tools: tuple[tuple[int, int], ...] = ((20, 0), (40, 5), (70, 12), (100, 17))
    tools_above: int = 20
    output: tuple[tuple[int, int], ...] = ((75_000, 0), (150_000, 5), (300_000, 10))
    output_above: int = 15
    context: tuple[tuple[float, int], ...] = ((35.0, 0), (50.0, 5), (65.0, 12), (80.0, 20))
    context_above: int = 25
    growth: tuple[tuple[float, int], ...] = ((20.0, 0), (50.0, 3), (100.0, 6))
    growth_above: int = 10


@dataclass(frozen=True)
class AllowanceSettings:
    min_bucket_seconds: int = 15
    minimum_points: int = 3
    minimum_span_minutes: float = 2.0
    reset_jitter_seconds: int = 60
    reset_drop_points: float = 50.0
    reset_low_percent: float = 20.0
    stale_seconds: int = 120
    activity_gap_minutes: int = 5
    activity_grace_minutes: int = 2
    session_gap_minutes: int = 30
    primary_short_minutes: int = 5
    primary_recent_minutes: int = 15
    secondary_recent_minutes: int = 60
    secondary_trend_minutes: int = 360
    burn_thresholds: tuple[tuple[float, str], ...] = (
        (0.5, "NORMAL"), (1.0, "ELEVADO"), (2.0, "MUITO ALTO"),
    )
    model_cost_factors: dict[str, float] = field(default_factory=lambda: {
        "gpt-5.6-sol": 1.0, "gpt-6-astra": 2.5,
    })


@dataclass(frozen=True)
class Settings:
    sessions_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("CODEX_SESSIONS_DIR", Path.home() / ".codex" / "sessions")
        ).resolve()
    )
    poll_seconds: float = float(os.environ.get("CODEX_MONITOR_POLL_SECONDS", "3"))
    weights: WCIWeights = field(default_factory=WCIWeights)
    thresholds: Thresholds = field(default_factory=Thresholds)
    allowance: AllowanceSettings = field(default_factory=AllowanceSettings)


settings = Settings()
