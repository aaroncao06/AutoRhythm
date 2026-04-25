from __future__ import annotations

from rapmap.config import RenderingConfig
from rapmap.edit.operations import ClipOperation, EditPlan, Segment


def create_edit_plan(
    clip_groups: dict,
    anchor_map: dict,
    config: RenderingConfig,
) -> EditPlan:
    sr = anchor_map["sample_rate"]
    crossfade_samples = int(config.crossfade_ms * sr / 1000)
    anchors = anchor_map["anchors"]
    anchor_by_idx = {a["syllable_index"]: a for a in anchors}

    operations: list[ClipOperation] = []

    for clip in clip_groups["clips"]:
        syl_indices = clip["syllable_indices"]
        clip_source_start = clip["source_start_sample"]
        clip_source_end = clip["source_end_sample"]
        clip_target_start = clip["target_start_sample"]
        clip_target_end = clip["target_end_sample"]

        anchor_points: list[tuple[int, int, int]] = []
        for si in syl_indices:
            a = anchor_by_idx[si]
            anchor_points.append(
                (si, a["human_anchor_sample"], a["guide_anchor_sample"])
            )

        boundaries_source = [clip_source_start]
        boundaries_target = [clip_target_start]
        syl_for_segment = [anchor_points[0][0]]

        for si, h_anchor, g_anchor in anchor_points:
            if h_anchor > boundaries_source[-1]:
                boundaries_source.append(h_anchor)
                boundaries_target.append(g_anchor)
                syl_for_segment.append(si)
            elif h_anchor == boundaries_source[-1] and h_anchor == clip_source_start:
                boundaries_target[-1] = g_anchor

        boundaries_source.append(clip_source_end)
        boundaries_target.append(clip_target_end)

        segments: list[Segment] = []
        for seg_idx in range(len(boundaries_source) - 1):
            seg = Segment(
                segment_index=seg_idx,
                syllable_index=syl_for_segment[min(seg_idx, len(syl_for_segment) - 1)],
                source_start_sample=boundaries_source[seg_idx],
                source_end_sample=boundaries_source[seg_idx + 1],
                target_start_sample=boundaries_target[seg_idx],
                target_end_sample=boundaries_target[seg_idx + 1],
            )
            if seg.source_duration > 0:
                ratio = seg.stretch_ratio
                if config.fail_on_extreme_stretch:
                    assert config.min_stretch_ratio <= ratio <= config.max_stretch_ratio, (
                        f"Extreme stretch ratio {ratio:.3f} in clip {clip['clip_id']} "
                        f"segment {seg_idx} (bounds: [{config.min_stretch_ratio}, "
                        f"{config.max_stretch_ratio}])"
                    )
            segments.append(seg)

        operations.append(
            ClipOperation(
                clip_index=clip["clip_index"],
                clip_id=clip["clip_id"],
                segments=segments,
                crossfade_samples=crossfade_samples,
            )
        )

    return EditPlan(
        sample_rate=sr,
        grouping_mode=clip_groups["grouping_mode"],
        anchor_strategy=anchor_map["anchor_strategy"],
        crossfade_samples=crossfade_samples,
        operations=operations,
    )
