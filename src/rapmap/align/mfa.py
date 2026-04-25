from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from rapmap.config import AlignmentConfig
from rapmap.lyrics.pronunciations import lookup_pronunciation


def _check_mfa_available() -> None:
    try:
        subprocess.run(["mfa", "version"], capture_output=True, check=True)
    except FileNotFoundError:
        raise RuntimeError(
            "MFA not found on PATH. Install: conda install -c conda-forge montreal-forced-aligner\n"
            "Then download models: mfa model download acoustic english_us_arpa"
        )


def _generate_dictionary(canonical_syllables: dict, overrides: dict | None) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for syl in canonical_syllables["syllables"]:
        word = syl["word_text"].lower()
        if word in seen:
            continue
        seen.add(word)
        normalized = word
        phones, _ = lookup_pronunciation(normalized, overrides)
        lines.append(f"{word}\t{' '.join(phones)}")
    return "\n".join(lines) + "\n"


def _generate_transcript(canonical_syllables: dict) -> str:
    words: list[str] = []
    seen_indices: set[int] = set()
    for syl in canonical_syllables["syllables"]:
        wi = syl["word_index"]
        if wi not in seen_indices:
            seen_indices.add(wi)
            words.append(syl["word_text"].lower())
    return " ".join(words)


def align_with_mfa(
    audio_path: Path,
    canonical_syllables: dict,
    project_dir: Path,
    role: str,
    config: AlignmentConfig,
    overrides: dict | None = None,
) -> Path:
    _check_mfa_available()

    alignment_dir = project_dir / "alignment"
    alignment_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        corpus_dir = tmp / "corpus"
        corpus_dir.mkdir()
        output_dir = tmp / "output"

        shutil.copy2(audio_path, corpus_dir / f"{role}.wav")
        transcript = _generate_transcript(canonical_syllables)
        (corpus_dir / f"{role}.txt").write_text(transcript)

        dict_path = tmp / "dictionary.txt"
        dict_path.write_text(_generate_dictionary(canonical_syllables, overrides))

        cmd = [
            "mfa",
            "align",
            str(corpus_dir),
            str(dict_path),
            "english_us_arpa",
            str(output_dir),
            "--clean",
            "--single_speaker",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"MFA alignment failed (exit {result.returncode}):\n{result.stderr}"
            )

        textgrid_path = output_dir / f"{role}.TextGrid"
        if not textgrid_path.exists():
            candidates = list(output_dir.rglob("*.TextGrid"))
            if candidates:
                textgrid_path = candidates[0]
            else:
                raise FileNotFoundError(
                    f"MFA produced no TextGrid output. Output dir contents: "
                    f"{list(output_dir.rglob('*'))}"
                )

        dest = alignment_dir / f"{role}_alignment.TextGrid"
        shutil.copy2(textgrid_path, dest)

    return dest
