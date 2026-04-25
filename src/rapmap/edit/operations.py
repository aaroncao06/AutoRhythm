from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Segment:
    segment_index: int
    syllable_index: int
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
class ClipOperation:
    clip_index: int
    clip_id: str
    segments: list[Segment] = field(default_factory=list)
    crossfade_samples: int = 0


@dataclass
class EditPlan:
    sample_rate: int
    grouping_mode: str
    anchor_strategy: str
    crossfade_samples: int
    operations: list[ClipOperation] = field(default_factory=list)


def edit_plan_to_dict(plan: EditPlan) -> dict:
    return {
        "sample_rate": plan.sample_rate,
        "grouping_mode": plan.grouping_mode,
        "anchor_strategy": plan.anchor_strategy,
        "total_clips": len(plan.operations),
        "crossfade_samples": plan.crossfade_samples,
        "operations": [
            {
                "clip_index": op.clip_index,
                "clip_id": op.clip_id,
                "segments": [
                    {
                        "segment_index": s.segment_index,
                        "syllable_index": s.syllable_index,
                        "source_start_sample": s.source_start_sample,
                        "source_end_sample": s.source_end_sample,
                        "target_start_sample": s.target_start_sample,
                        "target_end_sample": s.target_end_sample,
                        "source_duration_samples": s.source_duration,
                        "target_duration_samples": s.target_duration,
                        "stretch_ratio": s.stretch_ratio,
                    }
                    for s in op.segments
                ],
                "crossfade_samples": op.crossfade_samples,
            }
            for op in plan.operations
        ],
    }


def edit_plan_from_dict(data: dict) -> EditPlan:
    operations = []
    for op_data in data.get("operations", []):
        segments = [
            Segment(
                segment_index=s["segment_index"],
                syllable_index=s["syllable_index"],
                source_start_sample=s["source_start_sample"],
                source_end_sample=s["source_end_sample"],
                target_start_sample=s["target_start_sample"],
                target_end_sample=s["target_end_sample"],
            )
            for s in op_data.get("segments", [])
        ]
        operations.append(
            ClipOperation(
                clip_index=op_data["clip_index"],
                clip_id=op_data["clip_id"],
                segments=segments,
                crossfade_samples=op_data.get("crossfade_samples", 0),
            )
        )
    return EditPlan(
        sample_rate=data["sample_rate"],
        grouping_mode=data["grouping_mode"],
        anchor_strategy=data["anchor_strategy"],
        crossfade_samples=data.get("crossfade_samples", 0),
        operations=operations,
    )
