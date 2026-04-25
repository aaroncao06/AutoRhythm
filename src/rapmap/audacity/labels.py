from __future__ import annotations

from pathlib import Path

from rapmap.align.base import AlignmentResult


def generate_label_track(entries: list[dict], sample_rate: int) -> str:
    lines = []
    for e in entries:
        start_sec = e["start_sample"] / sample_rate
        end_sec = e["end_sample"] / sample_rate
        lines.append(f"{start_sec:.6f}\t{end_sec:.6f}\t{e['text']}")
    return "\n".join(lines) + "\n"


def write_label_track(path: Path, entries: list[dict], sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_label_track(entries, sample_rate))


def generate_all_labels(
    canonical_syllables: dict,
    guide_alignment: AlignmentResult | None,
    human_alignment: AlignmentResult | None,
    anchor_map: dict | None,
    clip_groups: dict | None,
    sample_rate: int,
    output_dir: Path,
) -> list[Path]:
    labels_dir = output_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    canonical_entries = []
    for syl in canonical_syllables["syllables"]:
        idx = syl["syllable_index"]
        dummy_start = idx * sample_rate // 10
        dummy_end = dummy_start + sample_rate // 10
        canonical_entries.append(
            {
                "start_sample": dummy_start,
                "end_sample": dummy_end,
                "text": f"{syl['syllable_text']} [syl {idx}]",
            }
        )
    path = labels_dir / "labels_canonical.txt"
    write_label_track(path, canonical_entries, sample_rate)
    written.append(path)

    if guide_alignment:
        entries = [
            {
                "start_sample": s.start_sample,
                "end_sample": s.end_sample,
                "text": f"{s.word_text} [syl {s.syllable_index}]",
            }
            for s in guide_alignment.syllables
        ]
        path = labels_dir / "labels_guide.txt"
        write_label_track(path, entries, sample_rate)
        written.append(path)

    if human_alignment:
        entries = [
            {
                "start_sample": s.start_sample,
                "end_sample": s.end_sample,
                "text": f"{s.word_text} [syl {s.syllable_index}]",
            }
            for s in human_alignment.syllables
        ]
        path = labels_dir / "labels_human.txt"
        write_label_track(path, entries, sample_rate)
        written.append(path)

    if anchor_map:
        entries = [
            {
                "start_sample": a["guide_anchor_sample"],
                "end_sample": a["guide_anchor_sample"] + 1,
                "text": f"syl {a['syllable_index']} d={a['delta_samples']}",
            }
            for a in anchor_map["anchors"]
        ]
        path = labels_dir / "labels_anchors.txt"
        write_label_track(path, entries, sample_rate)
        written.append(path)

    if clip_groups:
        entries = [
            {
                "start_sample": c["target_start_sample"],
                "end_sample": c["target_end_sample"],
                "text": c["clip_id"],
            }
            for c in clip_groups["clips"]
        ]
        path = labels_dir / "labels_clips.txt"
        write_label_track(path, entries, sample_rate)
        written.append(path)

    return written
