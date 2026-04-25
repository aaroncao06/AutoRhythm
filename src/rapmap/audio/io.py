from __future__ import annotations

from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def _subtype_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        return "FLOAT"
    if suffix == ".flac":
        return "PCM_24"
    return "FLOAT"


def read_audio(path: Path, mono: bool = False) -> tuple[np.ndarray, int]:
    data, sample_rate = sf.read(path, dtype="float32")
    if mono and data.ndim == 2:
        data = data.mean(axis=1)
    return data, sample_rate


def write_audio(path: Path, data: np.ndarray, sample_rate: int) -> None:
    assert data.dtype == np.float32, f"Expected float32, got {data.dtype}"
    assert sample_rate > 0, f"Invalid sample rate: {sample_rate}"
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data, sample_rate, subtype=_subtype_for_path(path))


def resample(data: np.ndarray, sr_orig: int, sr_target: int) -> np.ndarray:
    if sr_orig == sr_target:
        return data
    g = gcd(sr_target, sr_orig)
    up, down = sr_target // g, sr_orig // g
    if data.ndim == 1:
        return resample_poly(data, up, down).astype(np.float32)
    return np.stack(
        [resample_poly(data[:, ch], up, down).astype(np.float32) for ch in range(data.shape[1])],
        axis=1,
    )


def audio_info(path: Path) -> dict:
    info = sf.info(str(path))
    return {
        "sample_rate": info.samplerate,
        "channels": info.channels,
        "frames": info.frames,
        "duration_samples": info.frames,
        "duration_seconds": info.duration,
    }
