from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from rapmap.config import AlignmentConfig
from rapmap.lyrics.normalize import normalize_word
from rapmap.lyrics.pronunciations import lookup_all_pronunciations, lookup_pronunciation

_mfa_env: dict[str, str] | None = None


def _find_mfa_env() -> tuple[str, dict[str, str]]:
    global _mfa_env
    if _mfa_env is not None:
        for p in _mfa_env.get("PATH", "").split(os.pathsep):
            mfa = Path(p) / "mfa"
            if mfa.exists():
                return str(mfa), _mfa_env

    env = os.environ.copy()
    if shutil.which("mfa"):
        _mfa_env = env
        return "mfa", env

    conda_dirs = [
        Path.home() / "miniconda3" / "envs" / "aligner",
        Path.home() / "miniforge3" / "envs" / "aligner",
        Path.home() / "anaconda3" / "envs" / "aligner",
    ]
    for conda_env in conda_dirs:
        mfa_bin = conda_env / "bin" / "mfa"
        if mfa_bin.exists():
            env["PATH"] = str(conda_env / "bin") + os.pathsep + env.get("PATH", "")
            _mfa_env = env
            return str(mfa_bin), env

    raise RuntimeError(
        "MFA not found on PATH. Install: conda install -c conda-forge montreal-forced-aligner\n"
        "Then download models: mfa model download acoustic english_us_arpa"
    )


def _check_mfa_available() -> tuple[str, dict[str, str]]:
    mfa, env = _find_mfa_env()
    subprocess.run([mfa, "version"], capture_output=True, check=True, env=env)
    return mfa, env


def _clean_word_for_mfa(word_text: str) -> str:
    normalized = normalize_word(word_text)
    return normalized if normalized else word_text.lower().strip()


def _generate_dictionary(
    canonical_syllables: dict,
    overrides: dict | None,
    multi_pronunciation: bool = True,
) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for syl in canonical_syllables["syllables"]:
        word = _clean_word_for_mfa(syl["word_text"])
        if word in seen:
            continue
        seen.add(word)
        if multi_pronunciation:
            variants = lookup_all_pronunciations(word, overrides)
            for phones, _ in variants:
                lines.append(f"{word}\t{' '.join(phones)}")
        else:
            phones, _ = lookup_pronunciation(word, overrides)
            lines.append(f"{word}\t{' '.join(phones)}")
    return "\n".join(lines) + "\n"


def _generate_transcript(canonical_syllables: dict) -> str:
    words: list[str] = []
    seen_indices: set[int] = set()
    for syl in canonical_syllables["syllables"]:
        wi = syl["word_index"]
        if wi not in seen_indices:
            seen_indices.add(wi)
            words.append(_clean_word_for_mfa(syl["word_text"]))
    return " ".join(words)


def _generate_dictionary_for_words(
    words: list[str],
    overrides: dict | None,
    multi_pronunciation: bool = True,
) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for raw_word in words:
        word = _clean_word_for_mfa(raw_word)
        if not word or word in seen:
            continue
        seen.add(word)
        if multi_pronunciation:
            variants = lookup_all_pronunciations(word, overrides)
            for phones, _ in variants:
                lines.append(f"{word}\t{' '.join(phones)}")
        else:
            phones, _ = lookup_pronunciation(word, overrides)
            lines.append(f"{word}\t{' '.join(phones)}")
    return "\n".join(lines) + "\n"


def align_with_mfa(
    audio_path: Path,
    canonical_syllables: dict,
    project_dir: Path,
    role: str,
    config: AlignmentConfig,
    overrides: dict | None = None,
    stt_transcript: list[str] | None = None,
) -> Path:
    mfa_bin, mfa_env = _check_mfa_available()

    alignment_dir = project_dir / "alignment"
    alignment_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        corpus_dir = tmp / "corpus"
        corpus_dir.mkdir()
        output_dir = tmp / "output"

        shutil.copy2(audio_path, corpus_dir / f"{role}.wav")

        if stt_transcript is not None:
            cleaned = [_clean_word_for_mfa(w) for w in stt_transcript]
            transcript = " ".join(w for w in cleaned if w)
            dict_text = _generate_dictionary_for_words(
                stt_transcript, overrides, config.multi_pronunciation
            )
        else:
            transcript = _generate_transcript(canonical_syllables)
            dict_text = _generate_dictionary(
                canonical_syllables, overrides, config.multi_pronunciation
            )

        (corpus_dir / f"{role}.txt").write_text(transcript)
        dict_path = tmp / "dictionary.txt"
        dict_path.write_text(dict_text)

        cmd = [
            mfa_bin,
            "align",
            str(corpus_dir),
            str(dict_path),
            "english_us_arpa",
            str(output_dir),
            "--clean",
            "--single_speaker",
            "--beam",
            "400",
            "--retry_beam",
            "1000",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, env=mfa_env)
        if result.returncode != 0:
            raise RuntimeError(f"MFA alignment failed (exit {result.returncode}):\n{result.stderr}")

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
