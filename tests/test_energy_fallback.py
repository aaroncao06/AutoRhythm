from __future__ import annotations

import numpy as np

from rapmap.align.derive_syllables import _energy_split


def _make_bursts(
    num_bursts: int,
    burst_samples: int = 4800,
    gap_samples: int = 2400,
    sr: int = 48000,
) -> np.ndarray:
    parts = [np.zeros(gap_samples, dtype=np.float32)]
    for i in range(num_bursts):
        if i > 0:
            parts.append(np.zeros(gap_samples, dtype=np.float32))
        freq = 440 * (i + 1)
        t = np.linspace(0, burst_samples / sr, burst_samples, dtype=np.float32)
        parts.append(np.sin(2 * np.pi * freq * t).astype(np.float32))
    parts.append(np.zeros(gap_samples, dtype=np.float32))
    return np.concatenate(parts)


def test_energy_split_matches_syllable_count():
    audio = _make_bursts(2)
    result = _energy_split(audio, num_syllables=2, sample_rate=48000, word_start_sample=0)
    assert len(result) == 2
    assert result[0][0] == 0
    assert result[-1][1] == len(audio)
    for start, end in result:
        assert end > start


def test_energy_split_returns_empty_on_mismatch():
    audio = _make_bursts(2)
    result = _energy_split(audio, num_syllables=5, sample_rate=48000, word_start_sample=0)
    assert result == []


def test_energy_split_short_audio():
    audio = np.zeros(3, dtype=np.float32)
    result = _energy_split(audio, num_syllables=2, sample_rate=48000, word_start_sample=0)
    assert result == []


def test_energy_split_single_syllable():
    audio = _make_bursts(1)
    result = _energy_split(audio, num_syllables=1, sample_rate=48000, word_start_sample=0)
    assert len(result) == 1
    assert result[0][0] == 0
    assert result[0][1] == len(audio)


def test_energy_split_respects_word_start_offset():
    audio = _make_bursts(2)
    offset = 10000
    result = _energy_split(
        audio, num_syllables=2, sample_rate=48000, word_start_sample=offset
    )
    assert len(result) == 2
    assert result[0][0] == offset
    assert result[-1][1] == offset + len(audio)


def test_energy_split_boundaries_contiguous():
    audio = _make_bursts(3, burst_samples=4800, gap_samples=2400)
    result = _energy_split(audio, num_syllables=3, sample_rate=48000, word_start_sample=0)
    assert len(result) == 3
    for i in range(1, len(result)):
        assert result[i][0] == result[i - 1][1], (
            f"Gap at boundary {i}: prev_end={result[i-1][1]}, "
            f"this_start={result[i][0]}"
        )
