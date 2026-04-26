from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class WarpSegment:
    segment_index: int
    segment_type: Literal["syllable", "gap", "lead_in", "trail"]
    syllable_index: int | None
    source_start_sample: int
    source_end_sample: int
    target_start_sample: int
    target_end_sample: int

    @property
    def source_duration(self) -> int:
        return self.source_end_sample - self.source_start_sample

    @property
    def target_duration(self) -> int:
        return self.target_end_sample - self.target_start_sample

    @property
    def stretch_ratio(self) -> float:
        if self.source_duration == 0:
            return 1.0
        return self.target_duration / self.source_duration


@dataclass
class WarpMap:
    sample_rate: int
    anchor_strategy: str
    total_source_samples: int
    total_target_samples: int
    segments: list[WarpSegment]


def build_warp_map(
    anchor_map: dict,
    human_total_samples: int,
    guide_total_samples: int | None = None,
) -> WarpMap:
    sr = anchor_map["sample_rate"]
    strategy = anchor_map["anchor_strategy"]
    anchors = anchor_map["anchors"]
    n = len(anchors)

    if guide_total_samples is None:
        if n > 0:
            guide_total_samples = anchors[-1]["guide_end_sample"]
        else:
            guide_total_samples = human_total_samples

    segments: list[WarpSegment] = []
    seg_idx = 0

    if n == 0:
        segments.append(WarpSegment(
            segment_index=0,
            segment_type="lead_in",
            syllable_index=None,
            source_start_sample=0,
            source_end_sample=human_total_samples,
            target_start_sample=0,
            target_end_sample=guide_total_samples,
        ))
        return WarpMap(
            sample_rate=sr,
            anchor_strategy=strategy,
            total_source_samples=human_total_samples,
            total_target_samples=guide_total_samples,
            segments=segments,
        )

    first_h_start = anchors[0]["human_start_sample"]
    first_g_start = anchors[0]["guide_start_sample"]
    if first_h_start > 0 or first_g_start > 0:
        segments.append(WarpSegment(
            segment_index=seg_idx,
            segment_type="lead_in",
            syllable_index=None,
            source_start_sample=0,
            source_end_sample=first_h_start,
            target_start_sample=0,
            target_end_sample=first_g_start,
        ))
        seg_idx += 1

    for i in range(n):
        a = anchors[i]

        segments.append(WarpSegment(
            segment_index=seg_idx,
            segment_type="syllable",
            syllable_index=i,
            source_start_sample=a["human_start_sample"],
            source_end_sample=a["human_end_sample"],
            target_start_sample=a["guide_start_sample"],
            target_end_sample=a["guide_end_sample"],
        ))
        seg_idx += 1

        if i < n - 1:
            next_a = anchors[i + 1]
            segments.append(WarpSegment(
                segment_index=seg_idx,
                segment_type="gap",
                syllable_index=None,
                source_start_sample=a["human_end_sample"],
                source_end_sample=next_a["human_start_sample"],
                target_start_sample=a["guide_end_sample"],
                target_end_sample=next_a["guide_start_sample"],
            ))
            seg_idx += 1

    last_h_end = anchors[-1]["human_end_sample"]
    last_g_end = anchors[-1]["guide_end_sample"]
    if last_h_end < human_total_samples or last_g_end < guide_total_samples:
        segments.append(WarpSegment(
            segment_index=seg_idx,
            segment_type="trail",
            syllable_index=None,
            source_start_sample=last_h_end,
            source_end_sample=human_total_samples,
            target_start_sample=last_g_end,
            target_end_sample=guide_total_samples,
        ))

    return WarpMap(
        sample_rate=sr,
        anchor_strategy=strategy,
        total_source_samples=human_total_samples,
        total_target_samples=guide_total_samples,
        segments=segments,
    )


def validate_warp_map(warp_map: WarpMap) -> list[str]:
    errors = []
    for i, seg in enumerate(warp_map.segments):
        if seg.source_start_sample < 0:
            errors.append(f"Segment {i}: negative source_start {seg.source_start_sample}")
        if seg.target_start_sample < 0:
            errors.append(f"Segment {i}: negative target_start {seg.target_start_sample}")
        if seg.source_end_sample < seg.source_start_sample:
            errors.append(f"Segment {i}: source_end < source_start")
        if seg.target_end_sample < seg.target_start_sample:
            errors.append(f"Segment {i}: target_end < target_start")
        if i > 0:
            prev = warp_map.segments[i - 1]
            if seg.source_start_sample != prev.source_end_sample:
                errors.append(
                    f"Segment {i}: source gap/overlap: "
                    f"prev_end={prev.source_end_sample}, "
                    f"this_start={seg.source_start_sample}"
                )
            if seg.target_start_sample != prev.target_end_sample:
                errors.append(
                    f"Segment {i}: target gap/overlap: "
                    f"prev_end={prev.target_end_sample}, "
                    f"this_start={seg.target_start_sample}"
                )
    return errors


def warp_map_to_dict(warp_map: WarpMap) -> dict:
    return {
        "sample_rate": warp_map.sample_rate,
        "anchor_strategy": warp_map.anchor_strategy,
        "total_source_samples": warp_map.total_source_samples,
        "total_target_samples": warp_map.total_target_samples,
        "segment_count": len(warp_map.segments),
        "segments": [
            {
                "segment_index": s.segment_index,
                "segment_type": s.segment_type,
                "syllable_index": s.syllable_index,
                "source_start_sample": s.source_start_sample,
                "source_end_sample": s.source_end_sample,
                "target_start_sample": s.target_start_sample,
                "target_end_sample": s.target_end_sample,
                "source_duration": s.source_duration,
                "target_duration": s.target_duration,
                "stretch_ratio": s.stretch_ratio,
            }
            for s in warp_map.segments
        ],
    }


def warp_map_from_dict(data: dict) -> WarpMap:
    segments = [
        WarpSegment(
            segment_index=s["segment_index"],
            segment_type=s["segment_type"],
            syllable_index=s.get("syllable_index"),
            source_start_sample=s["source_start_sample"],
            source_end_sample=s["source_end_sample"],
            target_start_sample=s["target_start_sample"],
            target_end_sample=s["target_end_sample"],
        )
        for s in data["segments"]
    ]
    return WarpMap(
        sample_rate=data["sample_rate"],
        anchor_strategy=data["anchor_strategy"],
        total_source_samples=data["total_source_samples"],
        total_target_samples=data["total_target_samples"],
        segments=segments,
    )
