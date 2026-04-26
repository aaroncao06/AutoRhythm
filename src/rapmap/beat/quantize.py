from __future__ import annotations

import numpy as np

from rapmap.align.base import AlignmentResult
from rapmap.config import BeatDetectionConfig


def quantize_anchors(
    human_alignment: AlignmentResult,
    beat_grid: dict,
    config: BeatDetectionConfig,
) -> dict:
    grid_samples = np.array(beat_grid["grid_samples"])
    assert len(grid_samples) > 0, "Beat grid has no positions"

    grid_interval = 1
    if len(grid_samples) > 1:
        grid_interval = int(grid_samples[1] - grid_samples[0])

    anchors: list[dict] = []
    prev_target = -1

    for i, syl in enumerate(human_alignment.syllables):
        human_anchor = syl.start_sample
        diffs = np.abs(grid_samples - human_anchor)
        nearest = int(grid_samples[np.argmin(diffs)])

        target = human_anchor + int(
            round((nearest - human_anchor) * config.quantize_strength)
        )

        if target <= prev_target:
            target = prev_target + max(1, grid_interval)

        delta = target - human_anchor
        guide_start = syl.start_sample + delta
        guide_end = syl.end_sample + delta

        anchors.append(
            {
                "syllable_index": i,
                "human_anchor_sample": human_anchor,
                "guide_anchor_sample": target,
                "delta_samples": human_anchor - target,
                "human_start_sample": syl.start_sample,
                "human_end_sample": syl.end_sample,
                "guide_start_sample": guide_start,
                "guide_end_sample": guide_end,
                "confidence": 1.0,
            }
        )
        prev_target = target

    for i in range(1, len(anchors)):
        assert (
            anchors[i]["guide_anchor_sample"] > anchors[i - 1]["guide_anchor_sample"]
        ), (
            f"Non-monotonic guide anchor at syllable {i}: "
            f"{anchors[i]['guide_anchor_sample']} <= "
            f"{anchors[i - 1]['guide_anchor_sample']}"
        )

    return {
        "sample_rate": human_alignment.sample_rate,
        "anchor_strategy": "onset",
        "source": "beat_grid",
        "bpm": beat_grid["bpm"],
        "subdivision": beat_grid["subdivision"],
        "quantize_strength": config.quantize_strength,
        "syllable_count": len(anchors),
        "anchors": anchors,
    }
