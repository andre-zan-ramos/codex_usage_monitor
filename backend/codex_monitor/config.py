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
class Settings:
    sessions_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("CODEX_SESSIONS_DIR", Path.home() / ".codex" / "sessions")
        ).resolve()
    )
    poll_seconds: float = float(os.environ.get("CODEX_MONITOR_POLL_SECONDS", "3"))
    weights: WCIWeights = field(default_factory=WCIWeights)
    thresholds: Thresholds = field(default_factory=Thresholds)


settings = Settings()
