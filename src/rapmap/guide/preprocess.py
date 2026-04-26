from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from rapmap.lyrics.normalize import normalize_word

logger = logging.getLogger(__name__)


@dataclass
class WordMatch:
    stt_index: int
    canonical_index: int
    stt_text: str
    canonical_text: str


@dataclass
class PreprocessResult:
    stt_words: list[str]
    canonical_words: list[str]
    matches: list[WordMatch]
    extra_indices: list[int]
    canonical_word_to_stt: dict[int, int]
    stt_to_canonical_word: dict[int, int]
    all_matched: bool
    missing_canonical_indices: list[int] = field(default_factory=list)
    mistrans_canonical_indices: list[int] = field(default_factory=list)


def transcribe_guide(audio_path: Path, model_size: str = "base") -> list[str]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, compute_type="int8")
    segments, _ = model.transcribe(str(audio_path), word_timestamps=True)

    words: list[str] = []
    for segment in segments:
        if segment.words:
            for word_info in segment.words:
                w = word_info.word.strip()
                if w:
                    words.append(w)
    return words


def _levenshtein_ratio(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    len_a, len_b = len(a), len(b)
    matrix = list(range(len_b + 1))
    for i in range(1, len_a + 1):
        prev = matrix[0]
        matrix[0] = i
        for j in range(1, len_b + 1):
            temp = matrix[j]
            if a[i - 1] == b[j - 1]:
                matrix[j] = prev
            else:
                matrix[j] = 1 + min(prev, matrix[j], matrix[j - 1])
            prev = temp
    distance = matrix[len_b]
    max_len = max(len_a, len_b)
    return 1.0 - (distance / max_len)


def _fuzzy_match(a: str, b: str, threshold: float) -> bool:
    if a == b:
        return True
    if len(a) < 2 or len(b) < 2:
        return False
    return _levenshtein_ratio(a, b) >= threshold


def _align_dp(
    stt_norm: list[str],
    can_norm: list[str],
    threshold: float,
) -> list[tuple[str, int | None, int | None]]:
    """Needleman-Wunsch sequence alignment.

    Returns ops in order. Each op is (kind, stt_idx, can_idx) where:
      - MATCH:    stt and canonical word fuzzy-match → both consumed
      - MISTRANS: paired diagonally but no fuzzy match → both consumed
      - EXTRA:    stt word with no canonical counterpart
      - MISSING:  canonical word with no stt counterpart
    """
    n, m = len(stt_norm), len(can_norm)
    MATCH = 2
    MISMATCH = -1
    GAP = -1

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    back: list[list[str | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i * GAP
        back[i][0] = "U"
    for j in range(1, m + 1):
        dp[0][j] = j * GAP
        back[0][j] = "L"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            matched = _fuzzy_match(stt_norm[i - 1], can_norm[j - 1], threshold)
            diag = dp[i - 1][j - 1] + (MATCH if matched else MISMATCH)
            up = dp[i - 1][j] + GAP
            left = dp[i][j - 1] + GAP
            best = max(diag, up, left)
            dp[i][j] = best
            if best == diag:
                back[i][j] = "DM" if matched else "DX"
            elif best == up:
                back[i][j] = "U"
            else:
                back[i][j] = "L"

    ops: list[tuple[str, int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i == 0:
            ops.append(("MISSING", None, j - 1))
            j -= 1
            continue
        if j == 0:
            ops.append(("EXTRA", i - 1, None))
            i -= 1
            continue
        a = back[i][j]
        if a == "DM":
            ops.append(("MATCH", i - 1, j - 1))
            i -= 1
            j -= 1
        elif a == "DX":
            ops.append(("MISTRANS", i - 1, j - 1))
            i -= 1
            j -= 1
        elif a == "U":
            ops.append(("EXTRA", i - 1, None))
            i -= 1
        else:
            ops.append(("MISSING", None, j - 1))
            j -= 1
    ops.reverse()
    return ops


def match_words(
    stt_words: list[str],
    canonical_words: list[str],
    threshold: float = 0.75,
) -> PreprocessResult:
    """Align STT to canonical lyrics with DP, then build an augmented MFA transcript.

    The returned ``stt_words`` is the augmented transcript fed to MFA: canonical
    words in their original positions, with extra STT words spliced in where the
    DP alignment placed them. All index fields refer to positions in this
    augmented transcript (not the original STT word list).
    """
    stt_normalized = [normalize_word(w) for w in stt_words]
    can_normalized = [normalize_word(w) for w in canonical_words]
    ops = _align_dp(stt_normalized, can_normalized, threshold)

    augmented: list[str] = []
    extra_indices: list[int] = []
    canonical_to_aug: dict[int, int] = {}
    aug_to_canonical: dict[int, int] = {}
    matches: list[WordMatch] = []

    for kind, stt_idx, can_idx in ops:
        if kind == "EXTRA":
            extra_indices.append(len(augmented))
            augmented.append(stt_words[stt_idx])  # type: ignore[index]
            continue
        # MATCH, MISTRANS, MISSING all consume one canonical
        pos = len(augmented)
        canonical_to_aug[can_idx] = pos  # type: ignore[index]
        aug_to_canonical[pos] = can_idx  # type: ignore[index]
        augmented.append(canonical_words[can_idx])  # type: ignore[index]
        if kind == "MATCH":
            matches.append(
                WordMatch(
                    stt_index=pos,
                    canonical_index=can_idx,  # type: ignore[arg-type]
                    stt_text=stt_words[stt_idx],  # type: ignore[index]
                    canonical_text=canonical_words[can_idx],  # type: ignore[index]
                )
            )

    n_canonicals = len(canonical_words)
    n_matched = sum(1 for kind, _, _ in ops if kind == "MATCH")
    all_matched = n_matched == n_canonicals

    missing_canonical_indices = [c for kind, _, c in ops if kind == "MISSING"]
    mistrans_canonical_indices = [c for kind, _, c in ops if kind == "MISTRANS"]
    if mistrans_canonical_indices or missing_canonical_indices:
        unmatched_words = [
            canonical_words[c]
            for kind, _, c in ops
            if kind in ("MISTRANS", "MISSING")
        ]
        logger.warning(
            "Guide preprocessing: %d canonicals unmatched (%d mistranscribed, %d missing): %s",
            len(mistrans_canonical_indices) + len(missing_canonical_indices),
            len(mistrans_canonical_indices),
            len(missing_canonical_indices),
            ", ".join(f"'{w}'" for w in unmatched_words[:10]),
        )

    return PreprocessResult(
        stt_words=augmented,
        canonical_words=canonical_words,
        matches=matches,
        extra_indices=extra_indices,
        canonical_word_to_stt=canonical_to_aug,
        stt_to_canonical_word=aug_to_canonical,
        all_matched=all_matched,
        missing_canonical_indices=missing_canonical_indices,
        mistrans_canonical_indices=mistrans_canonical_indices,
    )


def preprocess_guide(
    audio_path: Path,
    canonical_syllables: dict,
    model_size: str = "base",
    match_threshold: float = 0.75,
) -> PreprocessResult | None:
    canonical_words: list[str] = []
    seen: set[int] = set()
    for syl in canonical_syllables["syllables"]:
        wi = syl["word_index"]
        if wi not in seen:
            seen.add(wi)
            canonical_words.append(syl["word_text"])

    stt_words = transcribe_guide(audio_path, model_size)
    logger.info(
        "Guide STT: %d words transcribed, %d canonical words",
        len(stt_words),
        len(canonical_words),
    )

    if len(stt_words) == len(canonical_words):
        stt_norm = [normalize_word(w) for w in stt_words]
        can_norm = [normalize_word(w) for w in canonical_words]
        if stt_norm == can_norm:
            logger.info("Guide transcript matches canonical exactly — no preprocessing needed")
            return None

    result = match_words(stt_words, canonical_words, match_threshold)

    n_extras = len(result.extra_indices)
    if n_extras == 0:
        logger.info(
            "Guide has no extra words detected — no filtering needed "
            "(matched: %d/%d canonicals)",
            len(result.matches),
            len(canonical_words),
        )
        return None

    logger.info(
        "Guide preprocessing: %d STT words → augmented transcript with %d extras spliced "
        "(canonicals matched: %d/%d).",
        len(stt_words),
        n_extras,
        len(result.matches),
        len(canonical_words),
    )
    return result
