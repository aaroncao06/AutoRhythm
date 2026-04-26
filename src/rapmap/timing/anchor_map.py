from __future__ import annotations

from rapmap.align.base import AlignmentResult
from rapmap.config import AnchorStrategyConfig
from rapmap.timing.anchors import extract_anchor


def build_anchor_map(
    guide_alignment: AlignmentResult,
    human_alignment: AlignmentResult,
    config: AnchorStrategyConfig,
    untrusted_syllable_indices: set[int] | None = None,
) -> dict:
    assert len(guide_alignment.syllables) == len(human_alignment.syllables), (
        f"Syllable count mismatch: guide has {len(guide_alignment.syllables)}, "
        f"human has {len(human_alignment.syllables)}"
    )

    strategy = config.default
    sr = guide_alignment.sample_rate
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
                "trusted": True,
            }
        )

    n_repaired = 0
    if untrusted_syllable_indices:
        n_repaired = _repair_untrusted_runs(anchors, untrusted_syllable_indices)

    n_synth_gaps = _ensure_min_target_gaps(
        anchors,
        min_human_gap_samples=int(round(config.min_human_gap_ms * sr / 1000)),
        max_synthetic_gap_samples=int(round(config.min_target_gap_ms * sr / 1000)),
        min_syllable_samples=int(round(config.min_syllable_target_ms * sr / 1000)),
    )

    for i in range(1, len(anchors)):
        assert anchors[i]["guide_anchor_sample"] > anchors[i - 1]["guide_anchor_sample"], (
            f"Non-monotonic guide anchor at syllable {i}: "
            f"{anchors[i]['guide_anchor_sample']} <= {anchors[i - 1]['guide_anchor_sample']}"
        )

    return {
        "sample_rate": sr,
        "anchor_strategy": strategy,
        "syllable_count": len(anchors),
        "untrusted_syllable_count": len(untrusted_syllable_indices or set()),
        "repaired_syllable_count": n_repaired,
        "synthetic_gap_count": n_synth_gaps,
        "anchors": anchors,
    }


def _ensure_min_target_gaps(
    anchors: list[dict],
    min_human_gap_samples: int,
    max_synthetic_gap_samples: int,
    min_syllable_samples: int,
) -> int:
    """Inject a synthetic guide-side gap when the guide gap is too small to render
    a non-trivial human gap.

    For each adjacent pair: if the human gap is large enough to be perceptually
    meaningful AND the guide gap is smaller than the desired floor, pull the
    previous syllable's end backward so the gap segment has somewhere to render
    the human audio. Time is taken only from the previous syllable's end; the
    next syllable's anchor stays exactly where MFA / the repair pass placed it.
    """
    n = 0
    for i in range(len(anchors) - 1):
        h_gap = anchors[i + 1]["human_start_sample"] - anchors[i]["human_end_sample"]
        g_gap = anchors[i + 1]["guide_start_sample"] - anchors[i]["guide_end_sample"]
        if h_gap <= min_human_gap_samples:
            continue
        target_gap = min(h_gap, max_synthetic_gap_samples)
        if g_gap >= target_gap:
            continue

        needed = target_gap - g_gap
        syl_dur = anchors[i]["guide_end_sample"] - anchors[i]["guide_start_sample"]
        spareable = max(0, syl_dur - min_syllable_samples)
        take = min(needed, spareable)
        if take <= 0:
            continue

        new_end = anchors[i]["guide_end_sample"] - take
        anchors[i]["guide_end_sample"] = new_end
        # Anchor stays in [start, end). For "end" or "vowel_nucleus" strategies the
        # anchor may now exceed the new end; clamp.
        if anchors[i]["guide_anchor_sample"] >= new_end:
            anchors[i]["guide_anchor_sample"] = max(
                anchors[i]["guide_start_sample"], new_end - 1
            )
            anchors[i]["delta_samples"] = (
                anchors[i]["human_anchor_sample"] - anchors[i]["guide_anchor_sample"]
            )
        n += 1
    return n


def _repair_untrusted_runs(anchors: list[dict], untrusted: set[int]) -> int:
    """Re-time consecutive runs of untrusted syllables.

    For each run, uniformly map the human region [prev.human_end → next.human_start]
    onto the guide gap [prev.guide_end → next.guide_start]. Within-run syllable +
    inter-syllable proportions are preserved.

    Trailing runs (no trusted anchor after) are left untouched. Returns the number
    of syllables whose timestamps were rewritten.
    """
    n = len(anchors)
    repaired = 0
    i = 0
    while i < n:
        if anchors[i]["syllable_index"] not in untrusted:
            i += 1
            continue
        run_start = i
        while i < n and anchors[i]["syllable_index"] in untrusted:
            i += 1
        run_end = i  # exclusive

        if run_end >= n:
            break  # trailing run — leave as-is

        if run_start == 0:
            prev_g_end = 0
            prev_h_end = 0
        else:
            prev_g_end = anchors[run_start - 1]["guide_end_sample"]
            prev_h_end = anchors[run_start - 1]["human_end_sample"]
        next_g_start = anchors[run_end]["guide_start_sample"]
        next_h_start = anchors[run_end]["human_start_sample"]

        guide_gap = next_g_start - prev_g_end
        human_region = next_h_start - prev_h_end
        if human_region <= 0 or guide_gap <= 0:
            continue

        ratio = guide_gap / human_region
        for k in range(run_start, run_end):
            h_off_s = anchors[k]["human_start_sample"] - prev_h_end
            h_off_e = anchors[k]["human_end_sample"] - prev_h_end
            h_off_a = anchors[k]["human_anchor_sample"] - prev_h_end
            new_g_s = prev_g_end + int(round(h_off_s * ratio))
            new_g_e = prev_g_end + int(round(h_off_e * ratio))
            new_g_a = prev_g_end + int(round(h_off_a * ratio))
            anchors[k]["guide_start_sample"] = new_g_s
            anchors[k]["guide_end_sample"] = new_g_e
            anchors[k]["guide_anchor_sample"] = new_g_a
            anchors[k]["delta_samples"] = anchors[k]["human_anchor_sample"] - new_g_a
            anchors[k]["trusted"] = False
            repaired += 1
    return repaired
