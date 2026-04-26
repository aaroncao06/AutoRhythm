from __future__ import annotations

from rapmap.edit.warp_map import (
    WarpMap,
    WarpSegment,
    build_warp_map,
    validate_warp_map,
    warp_map_from_dict,
    warp_map_to_dict,
)


def _anchor_map(anchors: list[dict], sr: int = 48000) -> dict:
    return {
        "sample_rate": sr,
        "anchor_strategy": "onset",
        "syllable_count": len(anchors),
        "anchors": anchors,
    }


def _anchor(
    idx: int,
    h_start: int, h_end: int, h_anchor: int,
    g_start: int, g_end: int, g_anchor: int,
) -> dict:
    return {
        "syllable_index": idx,
        "human_start_sample": h_start,
        "human_end_sample": h_end,
        "human_anchor_sample": h_anchor,
        "guide_start_sample": g_start,
        "guide_end_sample": g_end,
        "guide_anchor_sample": g_anchor,
    }


def test_build_warp_map_basic():
    am = _anchor_map([
        _anchor(0, 1000, 2000, 1000, 1200, 2400, 1200),
        _anchor(1, 3000, 4000, 3000, 3600, 4800, 3600),
    ])
    wm = build_warp_map(am, human_total_samples=5000, guide_total_samples=6000)

    assert len(wm.segments) == 5
    types = [s.segment_type for s in wm.segments]
    assert types == ["lead_in", "syllable", "gap", "syllable", "trail"]


def test_build_warp_map_contiguous():
    am = _anchor_map([
        _anchor(0, 500, 1500, 500, 600, 1800, 600),
        _anchor(1, 2000, 3000, 2000, 2400, 3600, 2400),
        _anchor(2, 3500, 4500, 3500, 4200, 5400, 4200),
    ])
    wm = build_warp_map(am, human_total_samples=5000, guide_total_samples=6000)

    errors = validate_warp_map(wm)
    assert errors == [], f"Validation errors: {errors}"

    for i in range(1, len(wm.segments)):
        assert wm.segments[i].source_start_sample == wm.segments[i - 1].source_end_sample
        assert wm.segments[i].target_start_sample == wm.segments[i - 1].target_end_sample


def test_build_warp_map_zero_gap():
    am = _anchor_map([
        _anchor(0, 1000, 2000, 1000, 1200, 2400, 1200),
        _anchor(1, 2000, 3000, 2000, 2400, 3600, 2400),
    ])
    wm = build_warp_map(am, human_total_samples=4000, guide_total_samples=4800)

    gap_segs = [s for s in wm.segments if s.segment_type == "gap"]
    assert len(gap_segs) == 1
    assert gap_segs[0].source_duration == 0
    assert gap_segs[0].target_duration == 0


def test_build_warp_map_no_syllables():
    am = _anchor_map([])
    wm = build_warp_map(am, human_total_samples=48000, guide_total_samples=48000)

    assert len(wm.segments) == 1
    assert wm.segments[0].segment_type == "lead_in"
    assert wm.segments[0].source_duration == 48000
    assert wm.segments[0].target_duration == 48000


def test_validate_warp_map_catches_gap():
    wm = WarpMap(
        sample_rate=48000,
        anchor_strategy="onset",
        total_source_samples=3000,
        total_target_samples=3000,
        segments=[
            WarpSegment(0, "syllable", 0, 0, 1000, 0, 1000),
            WarpSegment(1, "syllable", 1, 1500, 3000, 1500, 3000),
        ],
    )
    errors = validate_warp_map(wm)
    assert len(errors) >= 1
    assert "source gap/overlap" in errors[0]


def test_validate_warp_map_catches_negative():
    wm = WarpMap(
        sample_rate=48000,
        anchor_strategy="onset",
        total_source_samples=1000,
        total_target_samples=1000,
        segments=[
            WarpSegment(0, "syllable", 0, -100, 500, 0, 500),
        ],
    )
    errors = validate_warp_map(wm)
    assert any("negative" in e for e in errors)


def test_warp_map_serialization():
    am = _anchor_map([
        _anchor(0, 1000, 2000, 1000, 1200, 2400, 1200),
        _anchor(1, 3000, 4000, 3000, 3600, 4800, 3600),
    ])
    wm = build_warp_map(am, human_total_samples=5000, guide_total_samples=6000)

    d = warp_map_to_dict(wm)
    assert d["segment_count"] == len(wm.segments)

    wm2 = warp_map_from_dict(d)
    assert wm2.sample_rate == wm.sample_rate
    assert wm2.total_source_samples == wm.total_source_samples
    assert len(wm2.segments) == len(wm.segments)
    for s1, s2 in zip(wm.segments, wm2.segments):
        assert s1.source_start_sample == s2.source_start_sample
        assert s1.source_end_sample == s2.source_end_sample
        assert s1.target_start_sample == s2.target_start_sample
        assert s1.target_end_sample == s2.target_end_sample
        assert s1.segment_type == s2.segment_type


def test_stretch_ratios():
    am = _anchor_map([
        _anchor(0, 0, 1000, 0, 0, 2000, 0),
    ])
    wm = build_warp_map(am, human_total_samples=1000, guide_total_samples=2000)

    syl = [s for s in wm.segments if s.segment_type == "syllable"][0]
    assert abs(syl.stretch_ratio - 2.0) < 1e-6

    am2 = _anchor_map([
        _anchor(0, 0, 2000, 0, 0, 1000, 0),
    ])
    wm2 = build_warp_map(am2, human_total_samples=2000, guide_total_samples=1000)
    syl2 = [s for s in wm2.segments if s.segment_type == "syllable"][0]
    assert abs(syl2.stretch_ratio - 0.5) < 1e-6


def test_stretch_ratio_zero_source():
    seg = WarpSegment(0, "gap", None, 100, 100, 200, 300)
    assert seg.source_duration == 0
    assert seg.stretch_ratio == 1.0


def test_build_warp_map_no_lead_in():
    am = _anchor_map([
        _anchor(0, 0, 1000, 0, 0, 1200, 0),
    ])
    wm = build_warp_map(am, human_total_samples=2000, guide_total_samples=2400)

    assert wm.segments[0].segment_type == "syllable"
    errors = validate_warp_map(wm)
    assert errors == []
