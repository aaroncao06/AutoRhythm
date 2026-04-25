from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class GuideVocalResult:
    path: Path
    duration_samples: int
    sample_rate: int
    source: str
