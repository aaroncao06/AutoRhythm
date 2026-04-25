from __future__ import annotations

import json
from pathlib import Path

from rapmap.align.base import AlignmentResult, alignment_from_dict
from rapmap.audacity.labels import generate_all_labels
from rapmap.audacity.script_pipe import AudacityPipe
from rapmap.config import AudacityConfig


def build_audacity_session(
    project_dir: Path,
    config: AudacityConfig,
) -> dict:
    canonical_path = project_dir / "lyrics" / "canonical_syllables.json"
    assert canonical_path.exists(), f"Missing {canonical_path}"
    with open(canonical_path) as f:
        canonical_syllables = json.load(f)

    sr = canonical_syllables.get("sample_rate")
    if sr is None:
        proj_path = project_dir / "project.json"
        with open(proj_path) as f:
            sr = json.load(f)["sample_rate"]

    guide_alignment = _load_alignment(project_dir / "alignment" / "guide_alignment.json")
    human_alignment = _load_alignment(project_dir / "alignment" / "human_alignment.json")

    anchor_map = _load_json(project_dir / "timing" / "anchor_map.json")
    clip_groups = _load_json(project_dir / "edit" / "clip_groups.json")

    written = generate_all_labels(
        canonical_syllables,
        guide_alignment,
        human_alignment,
        anchor_map,
        clip_groups,
        sr,
        project_dir,
    )

    pipe_connected = False
    tracks_imported = 0

    if config.integration == "mod_script_pipe":
        pipe = AudacityPipe()
        if pipe.connect():
            pipe_connected = True
            audio_dir = project_dir / "audio"
            for name in ["backing.wav", "human_rap.wav", "ai_guide_vocal.wav"]:
                audio_file = audio_dir / name
                if audio_file.exists():
                    pipe.import_audio(audio_file)
                    tracks_imported += 1

            corrected = project_dir / "render" / "corrected_human_rap.wav"
            if corrected.exists():
                pipe.import_audio(corrected)
                tracks_imported += 1

            for label_path in written:
                pipe.import_labels(label_path)

            pipe.close()

    return {
        "labels_written": [str(p) for p in written],
        "pipe_connected": pipe_connected,
        "tracks_imported": tracks_imported,
    }


def _load_alignment(path: Path) -> AlignmentResult | None:
    if not path.exists():
        return None
    with open(path) as f:
        return alignment_from_dict(json.load(f))


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)
