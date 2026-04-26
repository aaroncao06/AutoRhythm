from __future__ import annotations

from rapmap.align.base import AlignmentResult, PhoneTimestamp, SyllableTimestamp
from rapmap.beat.quantize import quantize_anchors
from rapmap.config import BeatDetectionConfig


def _make_alignment(syllable_samples: list[tuple[int, int]], sr: int = 48000) -> AlignmentResult:
    syllables = []
    for i, (start, end) in enumerate(syllable_samples):
        syllables.append(
            SyllableTimestamp(
                syllable_index=i,
                word_index=0,
                word_text=f"word{i}",
                start_sample=start,
                end_sample=end,
                anchor_sample=start,
                phones=[
                    PhoneTimestamp(
                        phone=f"P{i}",
                        start_sample=start,
                        end_sample=end,
                    )
                ],
                confidence=1.0,
            )
        )
    max_end = max(end for _, end in syllable_samples)
    return AlignmentResult(
        syllables=syllables,
        role="human",
        audio_path="test.wav",
        sample_rate=sr,
        total_duration_samples=max_end,
    )


def _make_grid(grid_samples: list[int], sr: int = 48000) -> dict:
    return {
        "bpm": 120.0,
        "subdivision": "eighth",
        "units_per_beat": 2,
        "grid_samples": grid_samples,
        "beat_samples": grid_samples,
        "sample_rate": sr,
        "total_grid_points": len(grid_samples),
    }


class TestQuantizeAnchors:
    def test_snaps_to_nearest_grid(self):
        alignment = _make_alignment([(1050, 1200)])
        grid = _make_grid([1000, 2000])
        config = BeatDetectionConfig(quantize_strength=1.0)

        result = quantize_anchors(alignment, grid, config)
        assert result["anchors"][0]["guide_anchor_sample"] == 1000

    def test_strength_interpolation(self):
        alignment = _make_alignment([(1000, 1200)])
        grid = _make_grid([1200, 2400])
        config = BeatDetectionConfig(quantize_strength=0.5)

        result = quantize_anchors(alignment, grid, config)
        assert result["anchors"][0]["guide_anchor_sample"] == 1100

    def test_strength_zero_no_change(self):
        alignment = _make_alignment([(1000, 1200)])
        grid = _make_grid([1200, 2400])
        config = BeatDetectionConfig(quantize_strength=0.0)

        result = quantize_anchors(alignment, grid, config)
        assert result["anchors"][0]["guide_anchor_sample"] == 1000

    def test_output_format(self):
        alignment = _make_alignment([(1000, 1500), (2000, 2500)])
        grid = _make_grid([1000, 2000, 3000])
        config = BeatDetectionConfig(quantize_strength=1.0)

        result = quantize_anchors(alignment, grid, config)

        assert "sample_rate" in result
        assert "anchor_strategy" in result
        assert "syllable_count" in result
        assert result["syllable_count"] == 2
        assert result["source"] == "beat_grid"
        assert "bpm" in result

        anchor = result["anchors"][0]
        required_fields = [
            "syllable_index",
            "human_anchor_sample",
            "guide_anchor_sample",
            "delta_samples",
            "human_start_sample",
            "human_end_sample",
            "guide_start_sample",
            "guide_end_sample",
            "confidence",
        ]
        for field in required_fields:
            assert field in anchor, f"Missing field: {field}"

    def test_monotonic_output(self):
        alignment = _make_alignment([
            (1000, 1200),
            (2000, 2200),
            (3000, 3200),
            (4000, 4200),
        ])
        grid = _make_grid([1000, 2000, 3000, 4000, 5000])
        config = BeatDetectionConfig(quantize_strength=1.0)

        result = quantize_anchors(alignment, grid, config)

        for i in range(1, len(result["anchors"])):
            assert (
                result["anchors"][i]["guide_anchor_sample"]
                > result["anchors"][i - 1]["guide_anchor_sample"]
            )

    def test_resolves_duplicate_targets(self):
        alignment = _make_alignment([(990, 1100), (1010, 1120)])
        grid = _make_grid([1000, 2000])
        config = BeatDetectionConfig(quantize_strength=1.0)

        result = quantize_anchors(alignment, grid, config)
        assert (
            result["anchors"][1]["guide_anchor_sample"]
            > result["anchors"][0]["guide_anchor_sample"]
        )

    def test_delta_sign_convention(self):
        alignment = _make_alignment([(1050, 1200)])
        grid = _make_grid([1000, 2000])
        config = BeatDetectionConfig(quantize_strength=1.0)

        result = quantize_anchors(alignment, grid, config)
        anchor = result["anchors"][0]
        expected = anchor["human_anchor_sample"] - anchor["guide_anchor_sample"]
        assert anchor["delta_samples"] == expected
