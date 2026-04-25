from __future__ import annotations

from rapmap.align.base import SyllableTimestamp
from rapmap.lyrics.syllabify import is_vowel


def extract_anchor(syllable: SyllableTimestamp, strategy: str) -> int:
    if strategy == "onset":
        return syllable.start_sample
    if strategy == "end":
        return syllable.end_sample
    if strategy == "vowel_nucleus":
        for p in syllable.phones:
            if is_vowel(p.phone):
                return (p.start_sample + p.end_sample) // 2
        return syllable.start_sample
    raise ValueError(f"Unknown anchor strategy: {strategy}")
