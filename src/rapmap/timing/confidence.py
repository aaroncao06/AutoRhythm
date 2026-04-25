from __future__ import annotations

from rapmap.align.base import SyllableTimestamp


def compute_syllable_confidence(syllable: SyllableTimestamp, sample_rate: int = 48000) -> float:
    if not syllable.phones:
        return 0.0
    min_duration = min(p.end_sample - p.start_sample for p in syllable.phones)
    min_duration_ms = min_duration * 1000 / sample_rate
    return min(1.0, max(0.0, min_duration_ms / 30.0))


def flag_low_confidence(anchor_map: dict, threshold: float) -> list[int]:
    return [
        a["syllable_index"]
        for a in anchor_map["anchors"]
        if a["confidence"] < threshold
    ]
