from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from rapmap.audio.io import read_audio, resample, write_audio
from rapmap.config import GuideGenerationConfig, ProjectConfig
from rapmap.guide.base import GuideVocalResult

ACESTEP_PROJECT_ROOT = Path.home() / "code" / "ACE-Step-1.5"
ACESTEP_SCRIPT = Path(__file__).parent / "_acestep_generate.py"


def _find_acestep_python() -> str:
    venv_python = ACESTEP_PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    raise RuntimeError(
        f"ACE-Step virtual environment not found at {venv_python}. "
        f"Run: cd {ACESTEP_PROJECT_ROOT} && uv sync"
    )


def generate_guide_vocal(
    lyrics_text: str,
    project_dir: Path,
    config: ProjectConfig,
    guide_config: GuideGenerationConfig | None = None,
    duration: float | None = None,
    bpm: int | None = None,
    time_signature: str = "",
    caption: str = "rap, hip-hop, aggressive flow, male rapper, trap beat",
    seed: int = 42,
    backing_path: Path | None = None,
) -> GuideVocalResult:
    python_bin = _find_acestep_python()

    task_type = "text2music"
    if guide_config and guide_config.task_type == "lego" and backing_path is not None:
        task_type = "lego"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_output = Path(tmpdir) / "guide_raw.wav"

        cmd = [
            python_bin,
            str(ACESTEP_SCRIPT),
            "--lyrics", lyrics_text,
            "--output", str(tmp_output),
            "--caption", caption,
            "--seed", str(seed),
            "--project-root", str(ACESTEP_PROJECT_ROOT),
            "--offload",
            "--task-type", task_type,
        ]
        if task_type == "lego":
            cmd.extend(["--src-audio", str(backing_path)])
        if duration is not None:
            cmd.extend(["--duration", str(duration)])
        if bpm is not None:
            cmd.extend(["--bpm", str(bpm)])
        if time_signature:
            cmd.extend(["--time-signature", str(time_signature)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        stdout_lines = result.stdout.strip().split("\n")
        last_line = stdout_lines[-1] if stdout_lines else ""
        try:
            output = json.loads(last_line)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"ACE-Step generation failed.\nstdout: {result.stdout[-500:]}\n"
                f"stderr: {result.stderr[-500:]}"
            )

        if not output.get("success"):
            raise RuntimeError(f"ACE-Step generation failed: {output.get('error')}")

        raw_path = Path(output["path"])
        if not raw_path.exists():
            raw_path = tmp_output
        if not raw_path.exists():
            raise RuntimeError("ACE-Step produced no output file")

        if task_type == "lego":
            data, sr = read_audio(raw_path, mono=True)
        else:
            from rapmap.audio.source_separation import separate_vocals

            vocals_path = Path(tmpdir) / "guide_vocals.wav"
            separate_vocals(raw_path, vocals_path)
            data, sr = read_audio(vocals_path, mono=True)

    data = resample(data, sr, config.sample_rate)
    assert data.ndim == 1, f"Guide vocal must be mono, got {data.ndim}D"

    output_path = project_dir / "audio" / "ai_guide_vocal.wav"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_audio(output_path, data, config.sample_rate)

    source = "acestep-lego" if task_type == "lego" else "acestep+demucs"
    return GuideVocalResult(
        path=output_path,
        duration_samples=len(data),
        sample_rate=config.sample_rate,
        source=source,
    )
