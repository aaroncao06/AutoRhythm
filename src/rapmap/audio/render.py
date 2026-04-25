from __future__ import annotations

from pathlib import Path

import numpy as np

from rapmap.audio.io import write_audio
from rapmap.audio.stretch import time_stretch
from rapmap.config import RenderingConfig
from rapmap.edit.manifest import build_manifest
from rapmap.edit.operations import EditPlan


def render_clips(
    edit_plan: EditPlan,
    human_audio: np.ndarray,
    sample_rate: int,
    output_dir: Path,
    config: RenderingConfig,
    anchor_map: dict | None = None,
    fail_on_anchor_error: bool = False,
) -> dict:
    clips_dir = output_dir / "audio" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    render_dir = output_dir / "render"
    render_dir.mkdir(parents=True, exist_ok=True)

    rendered_clips: list[tuple[int, int, np.ndarray]] = []
    extreme_stretches: list[dict] = []
    all_ratios: list[float] = []

    for op in edit_plan.operations:
        parts: list[np.ndarray] = []
        for seg in op.segments:
            if seg.source_duration == 0 or seg.target_duration == 0:
                if seg.target_duration > 0:
                    parts.append(np.zeros(seg.target_duration, dtype=np.float32))
                continue

            source = human_audio[seg.source_start_sample : seg.source_end_sample]
            ratio = seg.stretch_ratio
            all_ratios.append(ratio)

            if ratio < config.min_stretch_ratio or ratio > config.max_stretch_ratio:
                extreme_stretches.append(
                    {
                        "clip_id": op.clip_id,
                        "segment_index": seg.segment_index,
                        "ratio": ratio,
                    }
                )

            if abs(ratio - 1.0) < 1e-6:
                stretched = source.copy()
            else:
                stretched = time_stretch(source, sample_rate, ratio, config.preserve_pitch)

            target_len = seg.target_duration
            if len(stretched) > target_len:
                stretched = stretched[:target_len]
            elif len(stretched) < target_len:
                pad = np.zeros(target_len - len(stretched), dtype=np.float32)
                stretched = np.concatenate([stretched, pad])

            parts.append(stretched)

        if parts:
            clip_audio = np.concatenate(parts)
        else:
            clip_audio = np.zeros(0, dtype=np.float32)

        if config.output_individual_clips and len(clip_audio) > 0:
            write_audio(clips_dir / f"{op.clip_id}.wav", clip_audio, sample_rate)

        target_start = op.segments[0].target_start_sample if op.segments else 0
        rendered_clips.append((op.clip_index, target_start, clip_audio))

    anchor_errors: list[dict] = []
    if anchor_map:
        starts_by_syl: dict[int, set[int]] = {}
        for op in edit_plan.operations:
            for seg in op.segments:
                starts_by_syl.setdefault(
                    seg.syllable_index, set()
                ).add(seg.target_start_sample)

        for a in anchor_map["anchors"]:
            si = a["syllable_index"]
            guide_anchor = a["guide_anchor_sample"]
            seg_starts = starts_by_syl.get(si, set())
            if guide_anchor not in seg_starts:
                if seg_starts:
                    closest = min(seg_starts, key=lambda s: abs(s - guide_anchor))
                else:
                    closest = None
                anchor_errors.append(
                    {
                        "syllable_index": si,
                        "guide_anchor": guide_anchor,
                        "nearest_segment_start": closest,
                        "error_samples": (
                            closest - guide_anchor if closest is not None
                            else None
                        ),
                    }
                )

    if fail_on_anchor_error and anchor_errors:
        errors_str = "; ".join(
            f"syl {e['syllable_index']}: guide={e['guide_anchor']}, "
            f"nearest={e['nearest_segment_start']}"
            for e in anchor_errors
        )
        raise AssertionError(
            f"Zero-sample anchor invariant violated for "
            f"{len(anchor_errors)} syllable(s): {errors_str}"
        )

    flattened_path = render_dir / "corrected_human_rap.wav"
    flattened_dur = _assemble_flattened(
        rendered_clips, flattened_path, sample_rate, edit_plan.crossfade_samples
    )

    manifest = build_manifest(
        edit_plan,
        clips_dir,
        flattened_path=str(flattened_path.relative_to(output_dir)),
        flattened_duration=flattened_dur,
    )

    report = {
        "sample_rate": sample_rate,
        "total_clips": len(edit_plan.operations),
        "total_syllables": sum(len(op.segments) for op in edit_plan.operations),
        "anchor_errors": anchor_errors,
        "max_stretch_ratio": max(all_ratios) if all_ratios else 1.0,
        "min_stretch_ratio": min(all_ratios) if all_ratios else 1.0,
        "extreme_stretches": extreme_stretches,
        "validation_passed": len(anchor_errors) == 0,
    }

    return {"report": report, "manifest": manifest}


def _assemble_flattened(
    rendered_clips: list[tuple[int, int, np.ndarray]],
    output_path: Path,
    sample_rate: int,
    crossfade_samples: int,
) -> int:
    if not rendered_clips:
        write_audio(output_path, np.zeros(0, dtype=np.float32), sample_rate)
        return 0

    non_empty = [(s, a) for _, s, a in rendered_clips if len(a) > 0]
    if not non_empty:
        write_audio(output_path, np.zeros(0, dtype=np.float32), sample_rate)
        return 0

    max_end = max(s + len(a) for s, a in non_empty)
    output = np.zeros(max_end, dtype=np.float32)

    sorted_clips = sorted(rendered_clips, key=lambda x: x[1])
    for _, start, audio in sorted_clips:
        if len(audio) == 0:
            continue
        end = start + len(audio)
        if end > len(output):
            output = np.concatenate([output, np.zeros(end - len(output), dtype=np.float32)])

        overlap_start = start
        overlap_end = min(end, len(output))
        existing = output[overlap_start:overlap_end]
        if np.any(existing != 0) and crossfade_samples > 0:
            xf = min(crossfade_samples, len(audio))
            fade_in = np.linspace(0.0, 1.0, xf).astype(np.float32)
            fade_out = np.linspace(1.0, 0.0, xf).astype(np.float32)
            blended = output[start : start + xf] * fade_out + audio[:xf] * fade_in
            output[start : start + xf] = blended
            output[start + xf : end] += audio[xf:]
        else:
            output[start:end] = audio

    write_audio(output_path, output, sample_rate)
    return len(output)
