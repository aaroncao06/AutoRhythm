from __future__ import annotations

import numpy as np

from rapmap.config import BeatDetectionConfig


def detect_beats(
    audio: np.ndarray, sample_rate: int, config: BeatDetectionConfig
) -> dict:
    import librosa

    tempo, beat_frames = librosa.beat.beat_track(
        y=audio.astype(np.float32),
        sr=sample_rate,
        hop_length=config.hop_length,
        start_bpm=120.0,
    )

    bpm = float(np.atleast_1d(tempo)[0])
    if bpm < config.min_bpm or bpm > config.max_bpm:
        clamped = max(config.min_bpm, min(config.max_bpm, bpm))
        _, beat_frames = librosa.beat.beat_track(
            y=audio.astype(np.float32),
            sr=sample_rate,
            hop_length=config.hop_length,
            bpm=clamped,
        )
        bpm = clamped

    beat_samples = librosa.frames_to_samples(beat_frames, hop_length=config.hop_length)
    beat_samples_list = [int(s) for s in beat_samples]

    for i in range(1, len(beat_samples_list)):
        assert beat_samples_list[i] > beat_samples_list[i - 1], (
            f"Non-monotonic beat at index {i}: "
            f"{beat_samples_list[i]} <= {beat_samples_list[i - 1]}"
        )

    return {
        "bpm": bpm,
        "beat_samples": beat_samples_list,
        "sample_rate": sample_rate,
        "hop_length": config.hop_length,
        "total_beats": len(beat_samples_list),
    }
