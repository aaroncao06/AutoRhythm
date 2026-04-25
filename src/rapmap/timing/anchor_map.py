from __future__ import annotations

from rapmap.align.base import AlignmentResult
from rapmap.config import AnchorStrategyConfig
from rapmap.timing.anchors import extract_anchor


def build_anchor_map(
    guide_alignment: AlignmentResult,
    human_alignment: AlignmentResult,
    config: AnchorStrategyConfig,
) -> dict:
    assert len(guide_alignment.syllables) == len(human_alignment.syllables), (
        f"Syllable count mismatch: guide has {len(guide_alignment.syllables)}, "
        f"human has {len(human_alignment.syllables)}"
    )

    strategy = config.default
    anchors = []

    for i in range(len(guide_alignment.syllables)):
        gs = guide_alignment.syllables[i]
        hs = human_alignment.syllables[i]

        guide_anchor = extract_anchor(gs, strategy)
        human_anchor = extract_anchor(hs, strategy)

        anchors.append(
            {
                "syllable_index": i,
                "human_anchor_sample": human_anchor,
                "guide_anchor_sample": guide_anchor,
                "delta_samples": human_anchor - guide_anchor,
                "human_start_sample": hs.start_sample,
                "human_end_sample": hs.end_sample,
                "guide_start_sample": gs.start_sample,
                "guide_end_sample": gs.end_sample,
                "confidence": min(gs.confidence, hs.confidence),
            }
        )

    for i in range(1, len(anchors)):
        assert anchors[i]["guide_anchor_sample"] > anchors[i - 1]["guide_anchor_sample"], (
            f"Non-monotonic guide anchor at syllable {i}: "
            f"{anchors[i]['guide_anchor_sample']} <= {anchors[i - 1]['guide_anchor_sample']}"
        )

    return {
        "sample_rate": guide_alignment.sample_rate,
        "anchor_strategy": strategy,
        "syllable_count": len(anchors),
        "anchors": anchors,
    }
