import pytest

from rapmap.config import RenderingConfig
from rapmap.edit.operations import (
    ClipOperation,
    EditPlan,
    Segment,
    edit_plan_from_dict,
    edit_plan_to_dict,
)
from rapmap.edit.planner import create_edit_plan


def _make_clip_groups_and_anchors(syllable_timings, sr=48000):
    anchors = []
    for i, (h_start, h_end, g_start, g_end) in enumerate(syllable_timings):
        anchors.append(
            {
                "syllable_index": i,
                "human_anchor_sample": h_start,
                "guide_anchor_sample": g_start,
                "human_start_sample": h_start,
                "human_end_sample": h_end,
                "guide_start_sample": g_start,
                "guide_end_sample": g_end,
                "delta_samples": h_start - g_start,
            }
        )
    anchor_map = {
        "sample_rate": sr,
        "anchor_strategy": "onset",
        "syllable_count": len(anchors),
        "anchors": anchors,
    }
    clip_groups = {
        "sample_rate": sr,
        "grouping_mode": "strict_syllable",
        "clip_count": len(anchors),
        "clips": [
            {
                "clip_index": i,
                "clip_id": f"clip_{i:04d}_test",
                "syllable_indices": [i],
                "source_start_sample": anchors[i]["human_start_sample"],
                "source_end_sample": anchors[i]["human_end_sample"],
                "target_start_sample": anchors[i]["guide_start_sample"],
                "target_end_sample": anchors[i]["guide_end_sample"],
            }
            for i in range(len(anchors))
        ],
    }
    return clip_groups, anchor_map


class TestZeroSampleAnchorError:
    def test_single_syllable_target_matches_guide(self):
        clip_groups, anchor_map = _make_clip_groups_and_anchors(
            [(1000, 2000, 1500, 2500)]
        )
        config = RenderingConfig(crossfade_ms=0)
        plan = create_edit_plan(clip_groups, anchor_map, config)
        op = plan.operations[0]
        assert op.segments[0].target_start_sample == 1500
        assert op.segments[0].target_end_sample == 2500

    def test_multi_syllable_anchors_exact(self):
        clip_groups, anchor_map = _make_clip_groups_and_anchors(
            [
                (1000, 2000, 1500, 2500),
                (3000, 4000, 3500, 4500),
                (5000, 6000, 5500, 6500),
            ]
        )
        config = RenderingConfig(crossfade_ms=0)
        plan = create_edit_plan(clip_groups, anchor_map, config)
        for i, op in enumerate(plan.operations):
            a = anchor_map["anchors"][i]
            assert op.segments[0].target_start_sample == a["guide_start_sample"]
            assert op.segments[-1].target_end_sample == a["guide_end_sample"]

    def test_grouped_clip_anchors_exact(self):
        timings = [
            (1000, 3000, 1500, 3500),
            (3000, 5000, 3500, 5500),
            (5000, 7000, 5500, 7500),
        ]
        anchors = []
        for i, (h_start, h_end, g_start, g_end) in enumerate(timings):
            anchors.append(
                {
                    "syllable_index": i,
                    "human_anchor_sample": h_start,
                    "guide_anchor_sample": g_start,
                    "human_start_sample": h_start,
                    "human_end_sample": h_end,
                    "guide_start_sample": g_start,
                    "guide_end_sample": g_end,
                    "delta_samples": h_start - g_start,
                }
            )
        anchor_map = {
            "sample_rate": 48000,
            "anchor_strategy": "onset",
            "syllable_count": 3,
            "anchors": anchors,
        }
        clip_groups = {
            "sample_rate": 48000,
            "grouping_mode": "word",
            "clip_count": 1,
            "clips": [
                {
                    "clip_index": 0,
                    "clip_id": "clip_0000_group",
                    "syllable_indices": [0, 1, 2],
                    "source_start_sample": 1000,
                    "source_end_sample": 7000,
                    "target_start_sample": 1500,
                    "target_end_sample": 7500,
                }
            ],
        }
        config = RenderingConfig(crossfade_ms=0)
        plan = create_edit_plan(clip_groups, anchor_map, config)
        op = plan.operations[0]
        target_positions = {s.syllable_index: s.target_start_sample for s in op.segments}
        for a in anchors:
            si = a["syllable_index"]
            if si in target_positions:
                assert target_positions[si] == a["guide_anchor_sample"], (
                    f"Syllable {si}: target={target_positions[si]} != "
                    f"guide={a['guide_anchor_sample']}"
                )


class TestSegmentCoverage:
    def test_segments_cover_full_clip(self):
        clip_groups, anchor_map = _make_clip_groups_and_anchors(
            [(1000, 3000, 1500, 3500)]
        )
        config = RenderingConfig(crossfade_ms=0)
        plan = create_edit_plan(clip_groups, anchor_map, config)
        op = plan.operations[0]
        assert op.segments[0].source_start_sample == 1000
        assert op.segments[-1].source_end_sample == 3000
        assert op.segments[0].target_start_sample == 1500
        assert op.segments[-1].target_end_sample == 3500

    def test_segments_contiguous(self):
        clip_groups, anchor_map = _make_clip_groups_and_anchors(
            [
                (1000, 2000, 1500, 2500),
                (2000, 4000, 2500, 4500),
            ]
        )
        clip_groups["clips"] = [
            {
                "clip_index": 0,
                "clip_id": "clip_0000_test",
                "syllable_indices": [0, 1],
                "source_start_sample": 1000,
                "source_end_sample": 4000,
                "target_start_sample": 1500,
                "target_end_sample": 4500,
            }
        ]
        clip_groups["clip_count"] = 1
        config = RenderingConfig(crossfade_ms=0)
        plan = create_edit_plan(clip_groups, anchor_map, config)
        op = plan.operations[0]
        for i in range(1, len(op.segments)):
            assert op.segments[i].source_start_sample == op.segments[i - 1].source_end_sample
            assert op.segments[i].target_start_sample == op.segments[i - 1].target_end_sample


class TestStretchRatios:
    def test_ratio_computation(self):
        seg = Segment(
            segment_index=0,
            syllable_index=0,
            source_start_sample=0,
            source_end_sample=1000,
            target_start_sample=0,
            target_end_sample=1500,
        )
        assert abs(seg.stretch_ratio - 1.5) < 1e-9

    def test_identity_ratio(self):
        seg = Segment(
            segment_index=0,
            syllable_index=0,
            source_start_sample=0,
            source_end_sample=1000,
            target_start_sample=0,
            target_end_sample=1000,
        )
        assert seg.stretch_ratio == 1.0

    def test_zero_source_duration_ratio(self):
        seg = Segment(
            segment_index=0,
            syllable_index=0,
            source_start_sample=100,
            source_end_sample=100,
            target_start_sample=0,
            target_end_sample=500,
        )
        assert seg.stretch_ratio == 1.0

    def test_extreme_stretch_fails_when_configured(self):
        timings = [(0, 100, 0, 1000)]
        clip_groups, anchor_map = _make_clip_groups_and_anchors(timings)
        config = RenderingConfig(
            crossfade_ms=0,
            fail_on_extreme_stretch=True,
            max_stretch_ratio=2.0,
        )
        with pytest.raises(AssertionError, match="Extreme stretch ratio"):
            create_edit_plan(clip_groups, anchor_map, config)


class TestNonOnsetAnchorStrategy:
    def test_vowel_nucleus_segment_boundary_at_anchor(self):
        """For vowel_nucleus, the anchor is mid-syllable. The planner must
        create a segment boundary there so validation can match it."""
        anchors = [
            {
                "syllable_index": 0,
                "human_anchor_sample": 1500,
                "guide_anchor_sample": 2000,
                "human_start_sample": 1000,
                "human_end_sample": 2000,
                "guide_start_sample": 1500,
                "guide_end_sample": 2500,
                "delta_samples": -500,
            }
        ]
        anchor_map = {
            "sample_rate": 48000,
            "anchor_strategy": "vowel_nucleus",
            "syllable_count": 1,
            "anchors": anchors,
        }
        clip_groups = {
            "sample_rate": 48000,
            "grouping_mode": "strict_syllable",
            "clip_count": 1,
            "clips": [
                {
                    "clip_index": 0,
                    "clip_id": "clip_0000_test",
                    "syllable_indices": [0],
                    "source_start_sample": 1000,
                    "source_end_sample": 2000,
                    "target_start_sample": 1500,
                    "target_end_sample": 2500,
                }
            ],
        }
        config = RenderingConfig(crossfade_ms=0)
        plan = create_edit_plan(clip_groups, anchor_map, config)
        op = plan.operations[0]
        all_starts = {s.target_start_sample for s in op.segments}
        assert 2000 in all_starts, (
            f"Guide anchor 2000 not found in segment starts: {all_starts}"
        )


class TestEditPlanSerialization:
    def test_round_trip(self):
        plan = EditPlan(
            sample_rate=48000,
            grouping_mode="safe_boundary",
            anchor_strategy="onset",
            crossfade_samples=384,
            operations=[
                ClipOperation(
                    clip_index=0,
                    clip_id="clip_0000_test",
                    segments=[
                        Segment(
                            segment_index=0,
                            syllable_index=0,
                            source_start_sample=1000,
                            source_end_sample=2000,
                            target_start_sample=1500,
                            target_end_sample=2500,
                        )
                    ],
                    crossfade_samples=384,
                )
            ],
        )
        d = edit_plan_to_dict(plan)
        restored = edit_plan_from_dict(d)
        assert restored.sample_rate == plan.sample_rate
        assert restored.grouping_mode == plan.grouping_mode
        assert len(restored.operations) == 1
        seg = restored.operations[0].segments[0]
        assert seg.source_start_sample == 1000
        assert seg.target_end_sample == 2500

    def test_dict_contains_derived_fields(self):
        plan = EditPlan(
            sample_rate=48000,
            grouping_mode="word",
            anchor_strategy="onset",
            crossfade_samples=0,
            operations=[
                ClipOperation(
                    clip_index=0,
                    clip_id="clip_0000_test",
                    segments=[
                        Segment(
                            segment_index=0,
                            syllable_index=0,
                            source_start_sample=0,
                            source_end_sample=1000,
                            target_start_sample=0,
                            target_end_sample=1500,
                        )
                    ],
                )
            ],
        )
        d = edit_plan_to_dict(plan)
        seg_d = d["operations"][0]["segments"][0]
        assert seg_d["source_duration_samples"] == 1000
        assert seg_d["target_duration_samples"] == 1500
        assert abs(seg_d["stretch_ratio"] - 1.5) < 1e-9
