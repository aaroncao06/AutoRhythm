from __future__ import annotations

import numpy as np

from rapmap.align.base import AlignmentResult
from rapmap.config import SafeBoundaryConfig


def score_boundaries(
    canonical_syllables: dict,
    human_alignment: AlignmentResult,
    audio_data: np.ndarray,
    sample_rate: int,
    config: SafeBoundaryConfig,
) -> list[float]:
    syls = human_alignment.syllables
    can_syls = canonical_syllables["syllables"]
    n = len(syls)
    if n <= 1:
        return []

    track_energy = float(np.mean(audio_data**2)) + 1e-10
    scores: list[float] = []

    for i in range(n - 1):
        score = 0.0

        gap_samples = syls[i + 1].start_sample - syls[i].end_sample
        gap_ms = gap_samples * 1000 / sample_rate
        if gap_samples > 0:
            silence_score = min(1.0, max(0.0, gap_ms / config.min_silence_ms))
        else:
            silence_score = 0.0
        score += silence_score * 0.3

        boundary_sample = (syls[i].end_sample + syls[i + 1].start_sample) // 2
        window_samples = max(1, int(config.low_energy_window_ms * sample_rate / 1000))
        start = max(0, boundary_sample - window_samples // 2)
        end = min(len(audio_data), boundary_sample + window_samples // 2)
        if end > start:
            local_energy = float(np.mean(audio_data[start:end] ** 2))
            energy_score = 1.0 - min(1.0, local_energy / track_energy)
        else:
            energy_score = 0.5
        score += energy_score * 0.3

        zc_window = max(1, int(config.zero_crossing_search_ms * sample_rate / 1000))
        zc_start = max(0, boundary_sample - zc_window // 2)
        zc_end = min(len(audio_data) - 1, boundary_sample + zc_window // 2)
        if zc_end > zc_start:
            crossings = np.where(np.diff(np.sign(audio_data[zc_start:zc_end])))[0]
            zc_score = 1.0 if len(crossings) > 0 else 0.0
        else:
            zc_score = 0.0
        score += zc_score * 0.1

        if can_syls[i]["is_word_final"] and config.prefer_word_boundaries:
            score += 0.3
        elif not can_syls[i]["is_word_final"] and config.avoid_inside_words:
            score -= 0.3

        if can_syls[i]["is_line_final"] and config.prefer_line_boundaries:
            score += 0.5

        scores.append(score)

    return scores
