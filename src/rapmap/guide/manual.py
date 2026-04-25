from __future__ import annotations

from pathlib import Path

from rapmap.audio.io import read_audio, resample, write_audio
from rapmap.config import ProjectConfig
from rapmap.guide.base import GuideVocalResult


def load_manual_guide(
    guide_path: Path,
    project_dir: Path,
    config: ProjectConfig,
) -> GuideVocalResult:
    data, sr = read_audio(guide_path, mono=True)
    data = resample(data, sr, config.sample_rate)
    assert data.ndim == 1, f"Guide vocal must be mono, got {data.ndim}D"

    output_path = project_dir / "audio" / "ai_guide_vocal.wav"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_audio(output_path, data, config.sample_rate)

    return GuideVocalResult(
        path=output_path,
        duration_samples=len(data),
        sample_rate=config.sample_rate,
        source="manual",
    )
