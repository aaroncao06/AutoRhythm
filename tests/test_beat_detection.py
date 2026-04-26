from __future__ import annotations

import numpy as np
import pytest

from rapmap.beat.detect import detect_beats
from rapmap.beat.grid import build_beat_grid
from rapmap.config import BeatDetectionConfig


def _make_click_track(
    bpm: float = 120.0, duration_sec: float = 10.0, sr: int = 48000,
) -> np.ndarray:
    total_samples = int(sr * duration_sec)
    audio = np.zeros(total_samples, dtype=np.float32)
    interval = int(sr * 60 / bpm)
    for i in range(0, total_samples - 100, interval):
        audio[i : i + 100] = 0.8
    return audio


class TestDetectBeats:
    def test_detect_beats_click_track(self):
        audio = _make_click_track(bpm=120.0, duration_sec=10.0, sr=48000)
        config = BeatDetectionConfig()
        result = detect_beats(audio, 48000, config)

        assert abs(result["bpm"] - 120.0) / 120.0 < 0.05
        expected_beats = int(120.0 * 10 / 60)
        assert abs(result["total_beats"] - expected_beats) <= 3

    def test_detect_beats_returns_python_int(self):
        audio = _make_click_track(bpm=120.0, duration_sec=5.0, sr=48000)
        config = BeatDetectionConfig()
        result = detect_beats(audio, 48000, config)

        for s in result["beat_samples"]:
            assert isinstance(s, int), f"Expected int, got {type(s)}"
        assert isinstance(result["bpm"], float)

    def test_detect_beats_monotonic(self):
        audio = _make_click_track(bpm=100.0, duration_sec=8.0, sr=48000)
        config = BeatDetectionConfig()
        result = detect_beats(audio, 48000, config)

        for i in range(1, len(result["beat_samples"])):
            assert result["beat_samples"][i] > result["beat_samples"][i - 1]

    def test_detect_beats_clamps_bpm(self):
        audio = _make_click_track(bpm=120.0, duration_sec=5.0, sr=48000)
        config = BeatDetectionConfig(min_bpm=130, max_bpm=200)
        result = detect_beats(audio, 48000, config)
        assert result["bpm"] >= 130


class TestBeatGrid:
    def test_beat_grid_quarter(self):
        beat_info = {
            "bpm": 120.0,
            "beat_samples": [0, 48000, 96000],
            "sample_rate": 48000,
        }
        grid = build_beat_grid(beat_info, "quarter", 100000)

        assert grid["grid_samples"] == [0, 48000, 96000]
        assert grid["units_per_beat"] == 1

    def test_beat_grid_eighth(self):
        beat_info = {
            "bpm": 120.0,
            "beat_samples": [0, 48000, 96000],
            "sample_rate": 48000,
        }
        grid = build_beat_grid(beat_info, "eighth", 100000)

        assert 0 in grid["grid_samples"]
        assert 24000 in grid["grid_samples"]
        assert 48000 in grid["grid_samples"]
        assert 72000 in grid["grid_samples"]
        assert 96000 in grid["grid_samples"]
        assert grid["units_per_beat"] == 2

    def test_beat_grid_sixteenth(self):
        beat_info = {
            "bpm": 120.0,
            "beat_samples": [0, 48000, 96000],
            "sample_rate": 48000,
        }
        grid = build_beat_grid(beat_info, "sixteenth", 100000)

        expected = [0, 12000, 24000, 36000, 48000, 60000, 72000, 84000, 96000]
        assert grid["grid_samples"] == expected
        assert grid["units_per_beat"] == 4

    def test_beat_grid_monotonic(self):
        beat_info = {
            "bpm": 120.0,
            "beat_samples": [0, 48000, 96000, 144000],
            "sample_rate": 48000,
        }
        grid = build_beat_grid(beat_info, "triplet", 150000)

        for i in range(1, len(grid["grid_samples"])):
            assert grid["grid_samples"][i] > grid["grid_samples"][i - 1]

    def test_beat_grid_invalid_subdivision(self):
        beat_info = {"bpm": 120.0, "beat_samples": [0, 48000], "sample_rate": 48000}
        with pytest.raises(AssertionError, match="Unknown subdivision"):
            build_beat_grid(beat_info, "half", 50000)
