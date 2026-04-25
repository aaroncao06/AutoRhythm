from __future__ import annotations

import re

import numpy as np

from rapmap.align.base import AlignmentResult
from rapmap.config import ClipGroupingConfig
from rapmap.edit.safe_boundaries import score_boundaries


def group_syllables(
    canonical_syllables: dict,
    anchor_map: dict,
    human_alignment: AlignmentResult | None,
    audio_data: np.ndarray | None,
    sample_rate: int,
    config: ClipGroupingConfig,
    mode: str = "safe_boundary",
) -> dict:
    can_syls = canonical_syllables["syllables"]
    anchors = anchor_map["anchors"]
    n = len(can_syls)
    assert n > 0, "No syllables to group"
    assert len(anchors) == n, (
        f"Anchor count {len(anchors)} != syllable count {n}"
    )

    if mode == "safe_boundary":
        assert human_alignment is not None, "safe_boundary mode requires human_alignment"
        assert audio_data is not None, "safe_boundary mode requires audio_data"
        groups = _group_safe_boundary(
            can_syls, anchors, human_alignment, audio_data, sample_rate, config
        )
    elif mode == "word":
        groups = _group_by_key(can_syls, "word_index")
    elif mode == "phrase":
        groups = _group_by_key(can_syls, "line_index")
    elif mode == "bar":
        groups = _group_by_key(can_syls, "bar_index")
    elif mode == "strict_syllable":
        groups = [[i] for i in range(n)]
    elif mode == "syllable_with_handles":
        groups = [[i] for i in range(n)]
    else:
        raise ValueError(f"Unknown grouping mode: {mode}")

    clips = []
    for clip_idx, syl_indices in enumerate(groups):
        first = syl_indices[0]
        last = syl_indices[-1]
        label = _make_clip_label(can_syls, syl_indices)
        clips.append(
            {
                "clip_index": clip_idx,
                "clip_id": f"clip_{clip_idx:04d}_{label}",
                "syllable_indices": syl_indices,
                "source_start_sample": anchors[first]["human_start_sample"],
                "source_end_sample": anchors[last]["human_end_sample"],
                "target_start_sample": anchors[first]["guide_start_sample"],
                "target_end_sample": anchors[last]["guide_end_sample"],
            }
        )

    all_assigned = set()
    for c in clips:
        for si in c["syllable_indices"]:
            assert si not in all_assigned, f"Syllable {si} assigned to multiple clips"
            all_assigned.add(si)
    assert all_assigned == set(range(n)), (
        f"Not all syllables assigned: missing {set(range(n)) - all_assigned}"
    )

    return {
        "sample_rate": sample_rate,
        "grouping_mode": mode,
        "clip_count": len(clips),
        "clips": clips,
    }


def _group_by_key(can_syls: list[dict], key: str) -> list[list[int]]:
    groups: list[list[int]] = []
    current_val = None
    current_group: list[int] = []
    for i, syl in enumerate(can_syls):
        val = syl[key]
        if val != current_val:
            if current_group:
                groups.append(current_group)
            current_group = [i]
            current_val = val
        else:
            current_group.append(i)
    if current_group:
        groups.append(current_group)
    return groups


def _group_safe_boundary(
    can_syls: list[dict],
    anchors: list[dict],
    human_alignment: AlignmentResult,
    audio_data: np.ndarray,
    sample_rate: int,
    config: ClipGroupingConfig,
) -> list[list[int]]:
    sb = config.safe_boundary
    n = len(can_syls)
    if n == 1:
        return [[0]]

    boundary_scores = score_boundaries(
        {"syllables": can_syls}, human_alignment, audio_data, sample_rate, sb
    )

    max_per_clip = sb.max_syllables_per_clip
    min_dur_samples = int(sb.min_clip_duration_ms * sample_rate / 1000)
    max_dur_samples = int(sb.max_clip_duration_ms * sample_rate / 1000)

    INF = float("inf")
    dp = [-INF] * (n + 1)
    dp[0] = 0.0
    parent = [0] * (n + 1)

    for i in range(1, n + 1):
        for length in range(1, min(max_per_clip, i) + 1):
            j = i - length
            clip_start = anchors[j]["human_start_sample"]
            clip_end = anchors[i - 1]["human_end_sample"]
            clip_dur = clip_end - clip_start
            if clip_dur < min_dur_samples and length < n:
                continue
            if clip_dur > max_dur_samples and length > 1:
                continue

            boundary_bonus = boundary_scores[j - 1] if j > 0 else 0.0
            candidate = dp[j] + boundary_bonus
            if candidate > dp[i]:
                dp[i] = candidate
                parent[i] = j

    if dp[n] == -INF:
        return [[i] for i in range(n)]

    groups: list[list[int]] = []
    i = n
    while i > 0:
        j = parent[i]
        groups.append(list(range(j, i)))
        i = j
    groups.reverse()
    return groups


def _make_clip_label(can_syls: list[dict], indices: list[int]) -> str:
    words: list[str] = []
    seen: set[int] = set()
    for i in indices:
        wi = can_syls[i]["word_index"]
        if wi not in seen:
            seen.add(wi)
            words.append(can_syls[i]["word_text"])
    label = "_".join(words)[:20].lower()
    label = re.sub(r"[^a-z0-9_]", "", label)
    return label or "clip"
