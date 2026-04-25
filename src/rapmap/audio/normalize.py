from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from rapmap.audio.io import read_audio, resample, write_audio
from rapmap.config import ProjectConfig


def normalize_project(
    backing_path: Path,
    human_path: Path,
    lyrics_path: Path,
    output_dir: Path,
    config: ProjectConfig,
) -> dict:
    audio_dir = output_dir / "audio"
    lyrics_dir = output_dir / "lyrics"
    audio_dir.mkdir(parents=True, exist_ok=True)
    lyrics_dir.mkdir(parents=True, exist_ok=True)

    target_sr = config.sample_rate
    audio_ext = config.internal_audio_format.lstrip(".").lower()
    assert audio_ext, "internal_audio_format must not be empty"
    backing_output = audio_dir / f"backing.{audio_ext}"
    human_output = audio_dir / f"human_rap.{audio_ext}"
    human_analysis_output = audio_dir / f"human_rap_analysis.{audio_ext}"

    backing_data, backing_sr = read_audio(backing_path)
    backing_data = resample(backing_data, backing_sr, target_sr)
    write_audio(backing_output, backing_data, target_sr)

    human_data, human_sr = read_audio(human_path, mono=False)
    human_data = resample(human_data, human_sr, target_sr)
    write_audio(human_output, human_data, target_sr)

    if config.vocal_analysis_mono and human_data.ndim == 2:
        # Preserve the original take for later rendering and create a mono analysis view separately.
        human_analysis_data = human_data.mean(axis=1).astype(np.float32)
        write_audio(human_analysis_output, human_analysis_data, target_sr)

    shutil.copy2(lyrics_path, lyrics_dir / "lyrics.raw.txt")

    metadata = {
        "sample_rate": target_sr,
        "backing_duration_samples": int(
            len(backing_data) if backing_data.ndim == 1 else backing_data.shape[0]
        ),
        "human_duration_samples": int(len(human_data)),
        "human_channels": int(1 if human_data.ndim == 1 else human_data.shape[1]),
        "backing_path": f"audio/{backing_output.name}",
        "human_path": f"audio/{human_output.name}",
        "human_analysis_path": f"audio/{human_analysis_output.name}"
        if config.vocal_analysis_mono and human_data.ndim == 2
        else f"audio/{human_output.name}",
        "created": datetime.now(timezone.utc).isoformat(),
        "original_files": {
            "backing": str(backing_path.resolve()),
            "human": str(human_path.resolve()),
            "lyrics": str(lyrics_path.resolve()),
        },
    }

    with open(output_dir / "project.json", "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata
