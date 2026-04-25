from __future__ import annotations

from pathlib import Path

import click


@click.group()
@click.version_option(version="0.1.0")
def main():
    """RapMap — Rap vocal rhythm mapping for Audacity."""


@main.command()
@click.option("--backing", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--human", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--lyrics", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--out", type=click.Path(path_type=Path), required=True)
def init(backing: Path, human: Path, lyrics: Path, out: Path):
    """Initialize a new RapMap project (Phase 0: normalize assets)."""
    click.echo(f"Initializing project in {out}")
    raise NotImplementedError("Phase 0 not yet implemented")


@main.command("set-guide")
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--guide", type=click.Path(exists=True, path_type=Path), required=True)
def set_guide(project: Path, guide: Path):
    """Set a manual guide vocal (Phase 1: Mode C)."""
    click.echo(f"Setting manual guide from {guide}")
    raise NotImplementedError("Phase 1 (manual guide) not yet implemented")


@main.command("generate-guide")
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--model", type=click.Choice(["songgeneration", "yue", "acestep"]), default="songgeneration")
@click.option("--out", type=click.Path(path_type=Path), default=None)
def generate_guide(project: Path, model: str, out: Path | None):
    """Generate an AI guide vocal (Phase 1: Mode A/B)."""
    click.echo(f"Generating guide with model={model}")
    raise NotImplementedError("Phase 1 (AI guide generation) not yet implemented")


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--out", type=click.Path(path_type=Path), default=None)
def syllabify(project: Path, out: Path | None):
    """Detect canonical syllables from lyrics (Phase 2)."""
    click.echo("Detecting syllables")
    raise NotImplementedError("Phase 2 not yet implemented")


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--audio", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--role", type=click.Choice(["guide", "human"]), required=True)
@click.option("--out", type=click.Path(path_type=Path), default=None)
def align(project: Path, audio: Path, role: str, out: Path | None):
    """Align a vocal to canonical lyrics (Phase 3)."""
    click.echo(f"Aligning {role} vocal: {audio}")
    raise NotImplementedError("Phase 3 not yet implemented")


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--anchor", type=click.Choice(["onset", "vowel_nucleus", "end", "onset_and_end", "hybrid"]), default="onset")
@click.option("--out", type=click.Path(path_type=Path), default=None)
def anchors(project: Path, anchor: str, out: Path | None):
    """Build syllable anchor map (Phase 4)."""
    click.echo(f"Building anchor map with strategy={anchor}")
    raise NotImplementedError("Phase 4 not yet implemented")


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--grouping", type=click.Choice(["safe_boundary", "word", "syllable_with_handles", "strict_syllable", "phrase", "bar"]), default="safe_boundary")
@click.option("--out", type=click.Path(path_type=Path), default=None)
def plan(project: Path, grouping: str, out: Path | None):
    """Build deterministic edit plan (Phases 5–6)."""
    click.echo(f"Planning edits with grouping={grouping}")
    raise NotImplementedError("Phases 5-6 not yet implemented")


@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--edit-plan", "edit_plan", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--out", type=click.Path(path_type=Path), default=None)
def render(project: Path, edit_plan: Path | None, out: Path | None):
    """Render corrected human vocal from edit plan (Phase 7)."""
    click.echo("Rendering corrected vocal")
    raise NotImplementedError("Phase 7 not yet implemented")


@main.command("audacity")
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--open", "open_after", is_flag=True, default=False)
def audacity_session(project: Path, open_after: bool):
    """Build Audacity session with tracks and labels (Phase 8)."""
    click.echo("Building Audacity session")
    raise NotImplementedError("Phase 8 not yet implemented")


@main.command("run")
@click.option("--backing", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--human", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--lyrics", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--out", type=click.Path(path_type=Path), required=True)
@click.option("--grouping", type=click.Choice(["safe_boundary", "word", "syllable_with_handles", "strict_syllable", "phrase", "bar"]), default="safe_boundary")
@click.option("--anchor", type=click.Choice(["onset", "vowel_nucleus", "end", "onset_and_end", "hybrid"]), default="onset")
def run(backing: Path, human: Path, lyrics: Path, out: Path, grouping: str, anchor: str):
    """Run the full pipeline (Phases 0–8)."""
    click.echo(f"Running full pipeline: grouping={grouping}, anchor={anchor}")
    raise NotImplementedError("Full pipeline not yet implemented")
