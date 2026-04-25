import numpy as np
import pytest

from rapmap.audio.render import render_clips
from rapmap.config import RenderingConfig
from rapmap.edit.operations import ClipOperation, EditPlan, Segment


def _identity_stretch(data, sample_rate, ratio, preserve_pitch):
    target_len = int(round(len(data) * ratio))
    if target_len == 0:
        return np.zeros(0, dtype=np.float32)
    return np.interp(
        np.linspace(0, len(data) - 1, target_len),
        np.arange(len(data)),
        data,
    ).astype(np.float32)


def _make_plan(segments_data, sr=48000):
    segments = []
    for i, (ss, se, ts, te, si) in enumerate(segments_data):
        segments.append(
            Segment(
                segment_index=i,
                syllable_index=si,
                source_start_sample=ss,
                source_end_sample=se,
                target_start_sample=ts,
                target_end_sample=te,
            )
        )
    return EditPlan(
        sample_rate=sr,
        grouping_mode="strict_syllable",
        anchor_strategy="onset",
        crossfade_samples=0,
        operations=[
            ClipOperation(
                clip_index=0,
                clip_id="clip_0000_test",
                segments=segments,
                crossfade_samples=0,
            )
        ],
    )


class TestRenderedClipLength:
    def test_single_segment_exact_length(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rapmap.audio.render.time_stretch", _identity_stretch)
        plan = _make_plan([(0, 4800, 0, 4800, 0)])
        audio = np.random.randn(10000).astype(np.float32)
        config = RenderingConfig(
            crossfade_ms=0,
            output_individual_clips=False,
            output_flattened_preview=True,
        )
        result = render_clips(plan, audio, 48000, tmp_path, config)
        assert result["report"]["total_clips"] == 1
        assert result["report"]["validation_passed"]

    def test_stretched_segment_exact_length(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rapmap.audio.render.time_stretch", _identity_stretch)
        plan = _make_plan([(0, 2400, 0, 4800, 0)])
        audio = np.random.randn(10000).astype(np.float32)
        config = RenderingConfig(
            crossfade_ms=0,
            output_individual_clips=True,
        )
        result = render_clips(plan, audio, 48000, tmp_path, config)
        assert result["report"]["total_clips"] == 1

    def test_multi_segment_clip(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rapmap.audio.render.time_stretch", _identity_stretch)
        plan = _make_plan(
            [
                (0, 2400, 0, 2400, 0),
                (2400, 4800, 2400, 4800, 1),
            ]
        )
        audio = np.random.randn(10000).astype(np.float32)
        config = RenderingConfig(crossfade_ms=0, output_individual_clips=False)
        result = render_clips(plan, audio, 48000, tmp_path, config)
        assert result["report"]["total_clips"] == 1
        assert result["report"]["total_syllables"] == 2

    def test_flattened_preview_written(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rapmap.audio.render.time_stretch", _identity_stretch)
        plan = _make_plan([(0, 4800, 0, 4800, 0)])
        audio = np.random.randn(10000).astype(np.float32)
        config = RenderingConfig(crossfade_ms=0, output_individual_clips=False)
        render_clips(plan, audio, 48000, tmp_path, config)
        assert (tmp_path / "render" / "corrected_human_rap.wav").exists()


class TestAnchorValidation:
    def test_no_anchor_errors_when_aligned(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rapmap.audio.render.time_stretch", _identity_stretch)
        plan = _make_plan(
            [
                (1000, 2000, 1500, 2500, 0),
                (3000, 4000, 3500, 4500, 1),
            ]
        )
        plan.operations = [
            ClipOperation(
                clip_index=0,
                clip_id="clip_0000_a",
                segments=[plan.operations[0].segments[0]],
            ),
            ClipOperation(
                clip_index=1,
                clip_id="clip_0001_b",
                segments=[plan.operations[0].segments[1]],
            ),
        ]
        audio = np.random.randn(10000).astype(np.float32)
        anchor_map = {
            "anchors": [
                {"syllable_index": 0, "guide_anchor_sample": 1500},
                {"syllable_index": 1, "guide_anchor_sample": 3500},
            ]
        }
        config = RenderingConfig(crossfade_ms=0, output_individual_clips=False)
        result = render_clips(plan, audio, 48000, tmp_path, config, anchor_map=anchor_map)
        assert len(result["report"]["anchor_errors"]) == 0
        assert result["report"]["validation_passed"]

    def test_anchor_error_detected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rapmap.audio.render.time_stretch", _identity_stretch)
        plan = _make_plan([(1000, 2000, 1500, 2500, 0)])
        audio = np.random.randn(10000).astype(np.float32)
        anchor_map = {
            "anchors": [
                {"syllable_index": 0, "guide_anchor_sample": 9999},
            ]
        }
        config = RenderingConfig(crossfade_ms=0, output_individual_clips=False)
        result = render_clips(plan, audio, 48000, tmp_path, config, anchor_map=anchor_map)
        assert len(result["report"]["anchor_errors"]) == 1
        assert not result["report"]["validation_passed"]

    def test_multi_segment_same_syllable_no_false_error(self, tmp_path, monkeypatch):
        """Two segments share syllable 0. The anchor (200) matches segment 1's
        target_start, not segment 0's. Validation should pass."""
        monkeypatch.setattr("rapmap.audio.render.time_stretch", _identity_stretch)
        plan = EditPlan(
            sample_rate=48000,
            grouping_mode="strict_syllable",
            anchor_strategy="vowel_nucleus",
            crossfade_samples=0,
            operations=[
                ClipOperation(
                    clip_index=0,
                    clip_id="clip_0000_test",
                    segments=[
                        Segment(0, 0, 100, 150, 150, 200),
                        Segment(1, 0, 150, 300, 200, 350),
                    ],
                )
            ],
        )
        audio = np.random.randn(10000).astype(np.float32)
        anchor_map = {
            "anchors": [
                {"syllable_index": 0, "guide_anchor_sample": 200},
            ]
        }
        config = RenderingConfig(crossfade_ms=0, output_individual_clips=False)
        result = render_clips(
            plan, audio, 48000, tmp_path, config, anchor_map=anchor_map
        )
        assert len(result["report"]["anchor_errors"]) == 0
        assert result["report"]["validation_passed"]

    def test_fail_on_anchor_error_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rapmap.audio.render.time_stretch", _identity_stretch)
        plan = _make_plan([(1000, 2000, 1500, 2500, 0)])
        audio = np.random.randn(10000).astype(np.float32)
        anchor_map = {
            "anchors": [
                {"syllable_index": 0, "guide_anchor_sample": 9999},
            ]
        }
        config = RenderingConfig(crossfade_ms=0, output_individual_clips=False)
        with pytest.raises(AssertionError, match="Zero-sample anchor invariant"):
            render_clips(
                plan, audio, 48000, tmp_path, config,
                anchor_map=anchor_map, fail_on_anchor_error=True,
            )


class TestAllEmptyClips:
    def test_all_empty_clips_writes_empty_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rapmap.audio.render.time_stretch", _identity_stretch)
        plan = EditPlan(
            sample_rate=48000,
            grouping_mode="strict_syllable",
            anchor_strategy="onset",
            crossfade_samples=0,
            operations=[
                ClipOperation(
                    clip_index=0,
                    clip_id="clip_0000_empty",
                    segments=[Segment(0, 0, 100, 100, 200, 200)],
                )
            ],
        )
        audio = np.random.randn(5000).astype(np.float32)
        config = RenderingConfig(crossfade_ms=0, output_individual_clips=False)
        result = render_clips(plan, audio, 48000, tmp_path, config)
        assert (tmp_path / "render" / "corrected_human_rap.wav").exists()
        assert result["report"]["total_clips"] == 1


class TestStretchRatioTracking:
    def test_ratios_recorded(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rapmap.audio.render.time_stretch", _identity_stretch)
        plan = _make_plan([(0, 2000, 0, 3000, 0)])
        audio = np.random.randn(5000).astype(np.float32)
        config = RenderingConfig(crossfade_ms=0, output_individual_clips=False)
        result = render_clips(plan, audio, 48000, tmp_path, config)
        assert result["report"]["max_stretch_ratio"] == result["report"]["min_stretch_ratio"]
        assert abs(result["report"]["max_stretch_ratio"] - 1.5) < 1e-9

    def test_extreme_stretch_flagged(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rapmap.audio.render.time_stretch", _identity_stretch)
        plan = _make_plan([(0, 100, 0, 1000, 0)])
        audio = np.random.randn(5000).astype(np.float32)
        config = RenderingConfig(
            crossfade_ms=0,
            output_individual_clips=False,
            min_stretch_ratio=0.5,
            max_stretch_ratio=2.0,
        )
        result = render_clips(plan, audio, 48000, tmp_path, config)
        assert len(result["report"]["extreme_stretches"]) == 1
