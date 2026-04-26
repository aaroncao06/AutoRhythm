from __future__ import annotations

import importlib.resources
import json
from pathlib import Path

import click

from rapmap.config import load_config


def _bundled_config(filename: str) -> Path:
    return Path(str(importlib.resources.files("rapmap.configs").joinpath(filename)))


@click.group()
@click.version_option(version="0.1.0")
def main():
    """RapMap — Rap vocal rhythm mapping for Audacity."""


@main.command()
@click.option("--backing", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--human", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--lyrics", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--out", type=click.Path(path_type=Path), required=True)
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
def init(backing: Path, human: Path, lyrics: Path, out: Path, config_path: Path | None):
    """Initialize a new RapMap project (Phase 0: normalize assets)."""
    from rapmap.audio.normalize import normalize_project

    config = load_config(config_path or _bundled_config("default.yaml"))
    click.echo(f"Initializing project in {out}")
    metadata = normalize_project(backing, human, lyrics, out, config.project)
    click.echo(f"  Sample rate: {metadata['sample_rate']} Hz")
    click.echo(f"  Backing: {metadata['backing_duration_samples']} samples")
    click.echo(f"  Human vocal: {metadata['human_duration_samples']} samples")
    click.echo("Phase 0 complete.")


@main.command("set-guide")
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--guide", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
def set_guide(project: Path, guide: Path, config_path: Path | None):
    """Set a manual guide vocal (Phase 1: Mode C)."""
    from rapmap.guide.manual import load_manual_guide

    config = load_config(config_path or _bundled_config("default.yaml"))
    click.echo(f"Setting manual guide from {guide}")
    result = load_manual_guide(guide, project, config.project)

    project_json_path = project / "project.json"
    with open(project_json_path) as f:
        proj_meta = json.load(f)
    proj_meta["guide_path"] = f"audio/{result.path.name}"
    proj_meta["guide_duration_samples"] = result.duration_samples
    proj_meta["guide_source"] = result.source
    with open(project_json_path, "w") as f:
        json.dump(proj_meta, f, indent=2)

    click.echo(f"  Duration: {result.duration_samples} samples")
    click.echo("Phase 1 complete.")


@main.command("generate-guide")
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--model",
    type=click.Choice(["songgeneration", "yue", "acestep"]),
    default="songgeneration",
)
@click.option("--out", type=click.Path(path_type=Path), default=None)
@click.option("--caption", default="rap, hip-hop, aggressive flow, male rapper, trap beat")
@click.option("--seed", type=int, default=42)
@click.option("--duration", type=float, default=None, help="Target duration in seconds (default: auto from backing)")
@click.option("--bpm", type=int, default=None)
@click.option("--time-signature", default="", help="Time signature: 2 (2/4), 3 (3/4), 4 (4/4), 6 (6/8)")
def generate_guide(project: Path, model: str, out: Path | None, caption: str, seed: int, duration: float | None, bpm: int | None, time_signature: str):
    """Generate an AI guide vocal (Phase 1: Mode A/B)."""
    project_json = project / "project.json"
    assert project_json.exists(), f"No project.json found in {project}"

    with open(project_json) as f:
        proj_meta = json.load(f)

    lyrics_path = project / "lyrics" / "lyrics.raw.txt"
    assert lyrics_path.exists(), f"No lyrics found in {project / 'lyrics'}"
    lyrics_text = lyrics_path.read_text()

    if duration is None:
        duration = proj_meta.get("backing_duration_seconds", 30.0)

    config = load_config()

    if model == "acestep":
        from rapmap.guide.acestep import generate_guide_vocal

        click.echo(f"Generating guide with ACE-Step (duration={duration:.1f}s, bpm={bpm}, time_sig={time_signature or 'auto'}, seed={seed})")
        result = generate_guide_vocal(
            lyrics_text=lyrics_text,
            project_dir=project,
            config=config.project,
            duration=duration,
            bpm=bpm,
            time_signature=time_signature,
            caption=caption,
            seed=seed,
        )
    else:
        raise NotImplementedError(f"Model '{model}' not yet implemented. Use --model acestep.")

    proj_meta["guide_path"] = f"audio/{result.path.name}"
    proj_meta["guide_duration_samples"] = result.duration_samples
    proj_meta["guide_source"] = result.source
    with open(project_json, "w") as f:
        json.dump(proj_meta, f, indent=2)

    click.echo(f"  Guide vocal: {result.path}")
    click.echo(f"  Duration: {result.duration_samples / result.sample_rate:.2f}s")
    click.echo("Phase 1 complete.")


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--out", type=click.Path(path_type=Path), default=None)
def syllabify(project: Path, config_path: Path | None, out: Path | None):
    """Detect canonical syllables from lyrics (Phase 2)."""
    from rapmap.lyrics.overrides import load_overrides
    from rapmap.lyrics.parser import parse_lyrics
    from rapmap.lyrics.syllabify import build_canonical_syllables

    project_json = project / "project.json"
    assert project_json.exists(), f"No project.json found in {project}"

    lyrics_path = project / "lyrics" / "lyrics.raw.txt"
    assert lyrics_path.exists(), f"No lyrics.raw.txt found in {project / 'lyrics'}"

    click.echo("Detecting syllables")

    lyrics_text = lyrics_path.read_text()
    lyrics_normalized = parse_lyrics(lyrics_text)

    norm_out = project / "lyrics" / "lyrics.normalized.json"
    with open(norm_out, "w") as f:
        json.dump(lyrics_normalized, f, indent=2)
    click.echo(f"  Wrote {norm_out}")

    overrides_path = _bundled_config("pronunciation_overrides.yaml")
    overrides = load_overrides(overrides_path)

    with open(project_json) as f:
        proj_meta = json.load(f)
    config = load_config(config_path or _bundled_config("default.yaml"))

    result = build_canonical_syllables(lyrics_normalized, overrides, config.syllable_detection)
    result["sample_rate"] = proj_meta["sample_rate"]

    syl_out = out or (project / "lyrics" / "canonical_syllables.json")
    with open(syl_out, "w") as f:
        json.dump(result, f, indent=2)

    sources = result.get("sources", {})
    click.echo(f"  Total syllables: {len(result['syllables'])}")
    click.echo(
        f"  CMUdict: {sources.get('cmudict', 0)}, "
        f"G2P: {sources.get('g2p', 0)}, "
        f"Overrides: {sources.get('override', 0)}"
    )
    click.echo(f"  Wrote {syl_out}")
    click.echo("Phase 2 complete.")


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--audio", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--role", type=click.Choice(["guide", "human"]), required=True)
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--out", type=click.Path(path_type=Path), default=None)
def align(project: Path, audio: Path | None, role: str, config_path: Path | None, out: Path | None):
    """Align a vocal to canonical lyrics (Phase 3)."""
    from rapmap.align.base import alignment_to_dict
    from rapmap.align.derive_syllables import derive_syllable_timestamps
    from rapmap.align.mfa import align_with_mfa
    from rapmap.align.validate import validate_alignment
    from rapmap.lyrics.overrides import load_overrides

    config = load_config(config_path or _bundled_config("default.yaml"))

    with open(project / "project.json") as f:
        proj_meta = json.load(f)
    sr = proj_meta["sample_rate"]

    canonical_path = project / "lyrics" / "canonical_syllables.json"
    assert canonical_path.exists(), f"Missing {canonical_path}"
    with open(canonical_path) as f:
        canonical = json.load(f)

    if audio is None:
        if role == "guide":
            audio = project / proj_meta["guide_path"]
        else:
            audio = project / proj_meta.get("human_analysis_path", proj_meta["human_path"])
    assert audio.exists(), f"Audio file not found: {audio}"

    overrides_path = _bundled_config("pronunciation_overrides.yaml")
    overrides = load_overrides(overrides_path)

    click.echo(f"Aligning {role} vocal: {audio}")
    textgrid_path = align_with_mfa(audio, canonical, project, role, config.alignment, overrides)
    click.echo(f"  TextGrid: {textgrid_path}")

    alignment = derive_syllable_timestamps(
        textgrid_path, canonical, sr, role, str(audio), config.anchor_strategy.default
    )

    validation = validate_alignment(alignment, canonical, config.alignment)
    low_conf = validation.get("low_confidence_count", 0)

    alignment_dir = project / "alignment"
    alignment_dir.mkdir(parents=True, exist_ok=True)
    out_path = out or (alignment_dir / f"{role}_alignment.json")
    with open(out_path, "w") as f:
        json.dump(alignment_to_dict(alignment), f, indent=2)

    click.echo(f"  Syllables: {len(alignment.syllables)}")
    click.echo(f"  Low confidence: {low_conf}")
    click.echo(f"  Wrote {out_path}")
    click.echo("Phase 3 complete.")


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--anchor",
    type=click.Choice(["onset", "vowel_nucleus", "end"]),
    default="onset",
)
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--out", type=click.Path(path_type=Path), default=None)
def anchors(project: Path, anchor: str, config_path: Path | None, out: Path | None):
    """Build syllable anchor map (Phase 4)."""
    from rapmap.align.base import alignment_from_dict
    from rapmap.config import AnchorStrategyConfig
    from rapmap.timing.anchor_map import build_anchor_map
    from rapmap.timing.confidence import flag_low_confidence

    config = load_config(config_path or _bundled_config("default.yaml"))
    strategy_config = AnchorStrategyConfig(default=anchor)

    guide_path = project / "alignment" / "guide_alignment.json"
    human_path = project / "alignment" / "human_alignment.json"
    assert guide_path.exists(), f"Missing {guide_path}"
    assert human_path.exists(), f"Missing {human_path}"

    with open(guide_path) as f:
        guide_alignment = alignment_from_dict(json.load(f))
    with open(human_path) as f:
        human_alignment = alignment_from_dict(json.load(f))

    click.echo(f"Building anchor map with strategy={anchor}")
    anchor_map = build_anchor_map(guide_alignment, human_alignment, strategy_config)

    low = flag_low_confidence(anchor_map, config.alignment.min_syllable_confidence)

    timing_dir = project / "timing"
    timing_dir.mkdir(parents=True, exist_ok=True)
    out_path = out or (timing_dir / "anchor_map.json")
    with open(out_path, "w") as f:
        json.dump(anchor_map, f, indent=2)

    click.echo(f"  Syllables: {anchor_map['syllable_count']}")
    click.echo(f"  Low confidence: {len(low)}")
    click.echo(f"  Wrote {out_path}")
    click.echo("Phase 4 complete.")


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--grouping",
    type=click.Choice(
        ["safe_boundary", "word", "syllable_with_handles", "strict_syllable", "phrase", "bar"]
    ),
    default="safe_boundary",
)
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--out", type=click.Path(path_type=Path), default=None)
def plan(project: Path, grouping: str, config_path: Path | None, out: Path | None):
    """Build deterministic edit plan (Phases 5-6)."""
    from rapmap.align.base import alignment_from_dict
    from rapmap.audio.io import read_audio
    from rapmap.edit.grouping import group_syllables
    from rapmap.edit.operations import edit_plan_to_dict
    from rapmap.edit.planner import create_edit_plan

    config = load_config(config_path or _bundled_config("default.yaml"))

    with open(project / "project.json") as f:
        proj_meta = json.load(f)
    sr = proj_meta["sample_rate"]

    with open(project / "lyrics" / "canonical_syllables.json") as f:
        canonical = json.load(f)
    with open(project / "timing" / "anchor_map.json") as f:
        anchor_map = json.load(f)

    human_alignment = None
    audio_data = None
    if grouping == "safe_boundary":
        with open(project / "alignment" / "human_alignment.json") as f:
            human_alignment = alignment_from_dict(json.load(f))
        audio_path = project / proj_meta.get("human_analysis_path", proj_meta["human_path"])
        audio_data, _ = read_audio(audio_path, mono=True)

    click.echo(f"Planning edits with grouping={grouping}")
    clip_groups = group_syllables(
        canonical, anchor_map, human_alignment, audio_data, sr, config.clip_grouping, grouping
    )

    edit_dir = project / "edit"
    edit_dir.mkdir(parents=True, exist_ok=True)
    groups_path = edit_dir / "clip_groups.json"
    with open(groups_path, "w") as f:
        json.dump(clip_groups, f, indent=2)
    click.echo(f"  Clips: {clip_groups['clip_count']}")

    edit_plan = create_edit_plan(clip_groups, anchor_map, config.rendering)
    plan_path = out or (edit_dir / "edit_plan.json")
    with open(plan_path, "w") as f:
        json.dump(edit_plan_to_dict(edit_plan), f, indent=2)

    ratios = [
        s.stretch_ratio for op in edit_plan.operations
        for s in op.segments if s.source_duration > 0
    ]
    if ratios:
        click.echo(f"  Stretch range: [{min(ratios):.3f}, {max(ratios):.3f}]")
    else:
        click.echo("  No segments")
    click.echo(f"  Wrote {plan_path}")
    click.echo("Phases 5-6 complete.")


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--edit-plan", "edit_plan_path", type=click.Path(exists=True, path_type=Path), default=None
)
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--out", type=click.Path(path_type=Path), default=None)
def render(project: Path, edit_plan_path: Path | None, config_path: Path | None, out: Path | None):
    """Render corrected human vocal from edit plan (Phase 7)."""
    from rapmap.audio.io import read_audio
    from rapmap.audio.render import render_clips
    from rapmap.edit.operations import edit_plan_from_dict

    config = load_config(config_path or _bundled_config("default.yaml"))

    with open(project / "project.json") as f:
        proj_meta = json.load(f)
    sr = proj_meta["sample_rate"]

    plan_path = edit_plan_path or (project / "edit" / "edit_plan.json")
    with open(plan_path) as f:
        edit_plan = edit_plan_from_dict(json.load(f))

    anchor_map_path = project / "timing" / "anchor_map.json"
    anchor_map = None
    if anchor_map_path.exists():
        with open(anchor_map_path) as f:
            anchor_map = json.load(f)

    audio_path = project / proj_meta.get("human_analysis_path", proj_meta["human_path"])
    human_audio, _ = read_audio(audio_path, mono=True)

    click.echo("Rendering corrected vocal")
    result = render_clips(
        edit_plan, human_audio, sr, project, config.rendering, anchor_map,
        fail_on_anchor_error=config.validation.require_zero_sample_anchor_error,
    )

    report = result["report"]
    render_dir = project / "render"
    render_dir.mkdir(parents=True, exist_ok=True)
    with open(render_dir / "render_report.json", "w") as f:
        json.dump(report, f, indent=2)

    edit_dir = project / "edit"
    edit_dir.mkdir(parents=True, exist_ok=True)
    with open(edit_dir / "clip_manifest.json", "w") as f:
        json.dump(result["manifest"], f, indent=2)

    click.echo(f"  Clips: {report['total_clips']}")
    click.echo(f"  Validation: {'PASSED' if report['validation_passed'] else 'FAILED'}")
    if report["extreme_stretches"]:
        click.echo(f"  Extreme stretches: {len(report['extreme_stretches'])}")
    click.echo("Phase 7 complete.")


@main.command("audacity")
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--open", "open_after", is_flag=True, default=False)
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
def audacity_session(project: Path, open_after: bool, config_path: Path | None):
    """Build Audacity session with tracks and labels (Phase 8)."""
    from rapmap.audacity.import_project import build_audacity_session

    config = load_config(config_path or _bundled_config("default.yaml"))
    click.echo("Building Audacity session")
    result = build_audacity_session(project, config.audacity)

    click.echo(f"  Labels written: {len(result['labels_written'])}")
    if result["pipe_connected"]:
        click.echo(f"  Audacity pipe: connected, {result['tracks_imported']} tracks imported")
    else:
        click.echo("  Audacity pipe: not connected (label files written for manual import)")
    if open_after and not result["pipe_connected"]:
        click.echo("  To import: File > Import > Labels in Audacity for each .txt in labels/")
    click.echo("Phase 8 complete.")


@main.command("detect-beats")
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--subdivision",
    type=click.Choice(["quarter", "eighth", "sixteenth", "triplet"]),
    default="eighth",
)
@click.option("--strength", type=float, default=1.0)
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
def detect_beats_cmd(
    project: Path, subdivision: str, strength: float, config_path: Path | None
):
    """Detect beats in backing track and quantize syllable anchors to beat grid."""
    from rapmap.audio.io import read_audio
    from rapmap.beat.detect import detect_beats
    from rapmap.beat.grid import build_beat_grid
    from rapmap.beat.quantize import quantize_anchors

    config = load_config(config_path or _bundled_config("default.yaml"))
    config.beat_detection.quantize_strength = strength

    backing_path = project / "audio" / "backing.wav"
    assert backing_path.exists(), f"Missing {backing_path}"
    audio, sr = read_audio(backing_path, mono=True)

    click.echo(f"Detecting beats (subdivision={subdivision}, strength={strength})")
    beat_info = detect_beats(audio, sr, config.beat_detection)

    timing_dir = project / "timing"
    timing_dir.mkdir(parents=True, exist_ok=True)
    with open(timing_dir / "beat_info.json", "w") as f:
        json.dump(beat_info, f, indent=2)

    beat_grid = build_beat_grid(beat_info, subdivision, len(audio))
    with open(timing_dir / "beat_grid.json", "w") as f:
        json.dump(beat_grid, f, indent=2)

    click.echo(f"  BPM: {beat_info['bpm']:.1f}")
    click.echo(f"  Beats: {beat_info['total_beats']}")
    click.echo(f"  Grid points: {beat_grid['total_grid_points']}")

    human_alignment_path = project / "alignment" / "human_alignment.json"
    if human_alignment_path.exists():
        from rapmap.align.base import alignment_from_dict

        with open(human_alignment_path) as f:
            human_al = alignment_from_dict(json.load(f))
        anchor_map = quantize_anchors(human_al, beat_grid, config.beat_detection)
        with open(timing_dir / "anchor_map.json", "w") as f:
            json.dump(anchor_map, f, indent=2)
        click.echo(f"  Syllables quantized: {anchor_map['syllable_count']}")
    else:
        click.echo("  Run `align` first to quantize syllables.")

    click.echo("Beat detection complete.")


@main.command("grab-audio")
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--backing-track", type=int, default=0, help="Audacity track index for backing")
@click.option("--vocal-track", type=int, default=1, help="Audacity track index for vocal")
def grab_audio(project: Path, backing_track: int, vocal_track: int):
    """Export backing and vocal tracks from Audacity into project dir."""
    from rapmap.audacity.script_pipe import AudacityPipe

    pipe = AudacityPipe()
    if not pipe.connect():
        click.echo("Error: Could not connect to Audacity via mod-script-pipe")
        click.echo("Ensure Audacity is running and mod-script-pipe is enabled")
        raise SystemExit(1)

    audio_dir = project / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    tracks = [
        (backing_track, "backing.wav"),
        (vocal_track, "human_rap.wav"),
    ]
    exported = 0
    try:
        for track_idx, filename in tracks:
            pipe.solo_track(track_idx, True)
            pipe.select_all()
            out_path = audio_dir / filename
            if pipe.export_audio(out_path):
                click.echo(f"  Exported track {track_idx} → {out_path}")
                exported += 1
            else:
                click.echo(f"  Failed to export track {track_idx}")
            pipe.solo_track(track_idx, False)
    finally:
        for track_idx, _ in tracks:
            pipe.solo_track(track_idx, False)
        pipe.close()

    click.echo(f"Exported {exported} tracks from Audacity.")


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--port", type=int, default=8765)
@click.option("--browser", is_flag=True, help="Open in browser instead of native window")
def editor(project: Path, port: int, browser: bool):
    """Launch interactive syllable timing editor."""
    from rapmap.editor.server import launch_editor

    click.echo(f"Launching editor for {project}")
    launch_editor(project, port=port, use_webview=not browser)


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--port", type=int, default=8765)
def studio(project: Path, port: int):
    """Launch RapMap Studio — opens Audacity + editor side by side."""
    from rapmap.studio.launcher import launch_studio

    click.echo(f"Launching RapMap Studio for {project}")
    launch_studio(project, port=port)


@main.command("run")
@click.option("--backing", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--human", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--lyrics", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--guide", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--out", type=click.Path(path_type=Path), required=True)
@click.option("--mode", type=click.Choice(["guide", "beat-only"]), default="guide")
@click.option(
    "--grouping",
    type=click.Choice(
        ["safe_boundary", "word", "syllable_with_handles", "strict_syllable", "phrase", "bar"]
    ),
    default="safe_boundary",
)
@click.option(
    "--anchor",
    type=click.Choice(["onset", "vowel_nucleus", "end"]),
    default="onset",
)
@click.option(
    "--subdivision",
    type=click.Choice(["quarter", "eighth", "sixteenth", "triplet"]),
    default="eighth",
)
@click.option("--strength", type=float, default=1.0)
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
def run(
    backing: Path,
    human: Path,
    lyrics: Path,
    guide: Path | None,
    out: Path,
    mode: str,
    grouping: str,
    anchor: str,
    subdivision: str,
    strength: float,
    config_path: Path | None,
):
    """Run the full pipeline (Phases 0-8).

    Use --mode guide (default) for AI guide-based rhythm correction.
    Use --mode beat-only to snap syllables to the beat grid without a guide vocal.
    """
    if mode == "guide" and guide is None:
        raise click.UsageError("--guide is required when --mode is 'guide'. Use --guide /path/to/guide.wav or --mode beat-only")

    from rapmap.align.base import alignment_from_dict, alignment_to_dict
    from rapmap.align.derive_syllables import derive_syllable_timestamps
    from rapmap.align.mfa import align_with_mfa
    from rapmap.align.validate import validate_alignment
    from rapmap.audacity.import_project import build_audacity_session
    from rapmap.audio.io import read_audio
    from rapmap.audio.normalize import normalize_project
    from rapmap.audio.render import render_clips
    from rapmap.edit.grouping import group_syllables
    from rapmap.edit.operations import edit_plan_to_dict
    from rapmap.edit.planner import create_edit_plan
    from rapmap.lyrics.overrides import load_overrides
    from rapmap.lyrics.parser import parse_lyrics
    from rapmap.lyrics.syllabify import build_canonical_syllables

    config = load_config(config_path or _bundled_config("default.yaml"))
    click.echo(f"Running full pipeline: mode={mode}, grouping={grouping}, anchor={anchor}")

    # Phase 0
    click.echo("Phase 0: Normalizing assets")
    metadata = normalize_project(backing, human, lyrics, out, config.project)
    sr = metadata["sample_rate"]

    proj_json = out / "project.json"
    with open(proj_json) as f:
        proj_meta = json.load(f)

    # Phase 1 (guide mode only)
    if mode == "guide":
        from rapmap.guide.manual import load_manual_guide

        click.echo("Phase 1: Setting guide vocal")
        guide_result = load_manual_guide(guide, out, config.project)
        proj_meta["guide_path"] = f"audio/{guide_result.path.name}"
        proj_meta["guide_duration_samples"] = guide_result.duration_samples
        proj_meta["guide_source"] = guide_result.source
        with open(proj_json, "w") as f:
            json.dump(proj_meta, f, indent=2)
    else:
        click.echo("Phase 1: Skipped (beat-only mode)")

    # Phase 2
    click.echo("Phase 2: Detecting syllables")
    lyrics_text = (out / "lyrics" / "lyrics.raw.txt").read_text()
    lyrics_normalized = parse_lyrics(lyrics_text)
    with open(out / "lyrics" / "lyrics.normalized.json", "w") as f:
        json.dump(lyrics_normalized, f, indent=2)

    overrides = load_overrides(_bundled_config("pronunciation_overrides.yaml"))
    canonical = build_canonical_syllables(lyrics_normalized, overrides, config.syllable_detection)
    canonical["sample_rate"] = sr
    with open(out / "lyrics" / "canonical_syllables.json", "w") as f:
        json.dump(canonical, f, indent=2)
    click.echo(f"  Syllables: {len(canonical['syllables'])}")

    # Phase 3
    click.echo("Phase 3: Aligning vocals")
    alignment_dir = out / "alignment"
    alignment_dir.mkdir(parents=True, exist_ok=True)

    if mode == "guide":
        roles = [("guide", "guide_path"), ("human", "human_analysis_path")]
    else:
        roles = [("human", "human_analysis_path")]

    for role_name, audio_key in roles:
        audio_path = out / proj_meta.get(audio_key, proj_meta.get("human_path", ""))
        if not audio_path.exists() and role_name == "human":
            audio_path = out / proj_meta["human_path"]
        tg = align_with_mfa(audio_path, canonical, out, role_name, config.alignment, overrides)
        al = derive_syllable_timestamps(tg, canonical, sr, role_name, str(audio_path), anchor)
        validate_alignment(al, canonical, config.alignment)
        with open(alignment_dir / f"{role_name}_alignment.json", "w") as f:
            json.dump(alignment_to_dict(al), f, indent=2)
        click.echo(f"  {role_name}: {len(al.syllables)} syllables")

    # Phase 4
    timing_dir = out / "timing"
    timing_dir.mkdir(parents=True, exist_ok=True)

    if mode == "guide":
        from rapmap.config import AnchorStrategyConfig
        from rapmap.timing.anchor_map import build_anchor_map

        click.echo("Phase 4: Building anchor map")
        with open(alignment_dir / "guide_alignment.json") as f:
            guide_al = alignment_from_dict(json.load(f))
        with open(alignment_dir / "human_alignment.json") as f:
            human_al = alignment_from_dict(json.load(f))
        strategy_config = AnchorStrategyConfig(default=anchor)
        anchor_map = build_anchor_map(guide_al, human_al, strategy_config)
    else:
        from rapmap.beat.detect import detect_beats
        from rapmap.beat.grid import build_beat_grid
        from rapmap.beat.quantize import quantize_anchors

        click.echo("Phase 4: Beat detection + quantize")
        config.beat_detection.quantize_strength = strength
        backing_audio, _ = read_audio(out / "audio" / "backing.wav", mono=True)
        beat_info = detect_beats(backing_audio, sr, config.beat_detection)
        with open(timing_dir / "beat_info.json", "w") as f:
            json.dump(beat_info, f, indent=2)

        beat_grid = build_beat_grid(beat_info, subdivision, len(backing_audio))
        with open(timing_dir / "beat_grid.json", "w") as f:
            json.dump(beat_grid, f, indent=2)

        click.echo(f"  BPM: {beat_info['bpm']:.1f}, Grid points: {beat_grid['total_grid_points']}")

        with open(alignment_dir / "human_alignment.json") as f:
            human_al = alignment_from_dict(json.load(f))
        anchor_map = quantize_anchors(human_al, beat_grid, config.beat_detection)

    with open(timing_dir / "anchor_map.json", "w") as f:
        json.dump(anchor_map, f, indent=2)

    # Phases 5-6
    click.echo("Phases 5-6: Grouping and planning")
    if mode == "guide":
        with open(alignment_dir / "human_alignment.json") as f:
            human_al = alignment_from_dict(json.load(f))
    human_alignment_for_grouping = human_al if grouping == "safe_boundary" else None
    audio_data = None
    if grouping == "safe_boundary":
        audio_path = out / proj_meta.get("human_analysis_path", proj_meta["human_path"])
        audio_data, _ = read_audio(audio_path, mono=True)

    clip_groups = group_syllables(
        canonical, anchor_map, human_alignment_for_grouping, audio_data, sr,
        config.clip_grouping, grouping,
    )
    edit_dir = out / "edit"
    edit_dir.mkdir(parents=True, exist_ok=True)
    with open(edit_dir / "clip_groups.json", "w") as f:
        json.dump(clip_groups, f, indent=2)

    edit_plan = create_edit_plan(clip_groups, anchor_map, config.rendering)
    with open(edit_dir / "edit_plan.json", "w") as f:
        json.dump(edit_plan_to_dict(edit_plan), f, indent=2)
    click.echo(f"  Clips: {clip_groups['clip_count']}")

    # Phase 7
    click.echo("Phase 7: Rendering")
    human_audio, _ = read_audio(
        out / proj_meta.get("human_analysis_path", proj_meta["human_path"]), mono=True
    )
    render_result = render_clips(
        edit_plan, human_audio, sr, out, config.rendering, anchor_map,
        fail_on_anchor_error=config.validation.require_zero_sample_anchor_error,
    )
    render_dir = out / "render"
    render_dir.mkdir(parents=True, exist_ok=True)
    with open(render_dir / "render_report.json", "w") as f:
        json.dump(render_result["report"], f, indent=2)
    with open(edit_dir / "clip_manifest.json", "w") as f:
        json.dump(render_result["manifest"], f, indent=2)
    passed = render_result["report"]["validation_passed"]
    click.echo(f"  Validation: {'PASSED' if passed else 'FAILED'}")

    # Phase 8
    click.echo("Phase 8: Building Audacity session")
    session = build_audacity_session(out, config.audacity)
    click.echo(f"  Labels: {len(session['labels_written'])}")

    click.echo("Pipeline complete.")
