from __future__ import annotations

from pathlib import Path

from rapmap.edit.operations import EditPlan


def build_manifest(
    edit_plan: EditPlan,
    clips_dir: Path,
    flattened_path: str | None = None,
    flattened_duration: int = 0,
) -> dict:
    clips = []
    for op in edit_plan.operations:
        total_target = sum(s.target_duration for s in op.segments)
        clips.append(
            {
                "clip_index": op.clip_index,
                "clip_id": op.clip_id,
                "path": str(clips_dir / f"{op.clip_id}.wav"),
                "duration_samples": total_target,
                "segment_count": len(op.segments),
            }
        )
    result: dict = {
        "sample_rate": edit_plan.sample_rate,
        "clips": clips,
    }
    if flattened_path:
        result["flattened_path"] = flattened_path
        result["flattened_duration_samples"] = flattened_duration
    return result
