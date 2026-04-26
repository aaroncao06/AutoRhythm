# Task: Fix Guide Alignment When AI Guide Has Extra Syllables

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files etc.

## Task Description

When an AI guide vocal contains extra words/syllables not present in the lyrics (intros, ad-libs, outros, repeated phrases), MFA forced alignment catastrophically fails. MFA must assign ALL audio frames to the transcript words it's given. When given only canonical lyrics words, MFA absorbs the extra spoken content into adjacent word boundaries — e.g., the word "the" spans 6.72 seconds because MFA assigned a single AH0 phone covering 6.69s of extra guide singing before "the".

**Root cause:** `align_with_mfa()` generates the MFA transcript from canonical lyrics only (`_generate_transcript()`). MFA has no concept of "extra" content — it must map every audio frame to some word.

**Solution:** Pre-transcribe the guide vocal with Whisper STT to discover what words are actually spoken. Match STT words to canonical lyrics to identify extras. Give MFA the full STT transcript so it can properly segment extras into their own time regions. Then filter the MFA alignment back to only canonical words before deriving syllable timestamps.

## Task Metadata

**Task Type**: Code Change
**Estimated Complexity**: Medium-High
**Primary Systems Affected**: `guide/`, `align/mfa.py`, `align/derive_syllables.py`, `cli.py`, `config.py`
**Dependencies**: `faster-whisper` (new optional dependency)
**Supports Claim/Hypothesis**: Core pipeline quality — prerequisite for AI-generated guide vocals working reliably

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/rapmap/align/mfa.py` (lines 58-89) — `_generate_dictionary()` and `_generate_transcript()` build MFA inputs from canonical syllables only. Must be extended to support arbitrary word lists.
- `src/rapmap/align/mfa.py` (lines 91-151) — `align_with_mfa()` orchestrates MFA. Needs new params for full transcript override.
- `src/rapmap/align/derive_syllables.py` (lines 141-357) — `derive_syllable_timestamps()` asserts `len(tg_words) == len(canonical_words)` at line 170. Must be relaxed when filtering is active.
- `src/rapmap/lyrics/normalize.py` (lines 1-8) — `normalize_word()` used for word comparison.
- `src/rapmap/cli.py` (lines 175-234) — `align` command, role=guide path needs preprocessing.
- `src/rapmap/cli.py` (lines 549-784) — `run` command, Phase 3 guide alignment needs preprocessing.
- `src/rapmap/config.py` (lines 38-49) — `AlignmentConfig` dataclass, add preprocessing flag.
- `src/rapmap/guide/base.py` — guide generation interface (reference for where preprocess fits).
- `pyproject.toml` (lines 18-22) — `[project.optional-dependencies].align` section.
- `src/rapmap/lyrics/pronunciations.py` — `lookup_pronunciation()` and `lookup_all_pronunciations()` for dictionary generation.
- `configs/default.yaml` (lines 21-30) — alignment config section.

### New Files to Create

- `src/rapmap/guide/preprocess.py` — STT transcription + word matching logic
- `tests/test_guide_preprocess.py` — Unit tests for word matching and preprocessing

### Patterns to Follow

**MFA integration pattern** (from `align/mfa.py`):
- Temporary directory for corpus/output
- `_generate_dictionary()` creates tab-separated `word\tphone1 phone2 ...` format
- `_generate_transcript()` creates space-separated word list
- `_clean_word_for_mfa()` normalizes words for dictionary keys

**Word normalization** (from `lyrics/normalize.py`):
```python
def normalize_word(word: str) -> str:
    lowered = word.lower()
    return re.sub(r"^[^\w']+|[^\w']+$", "", lowered)
```

**Config dataclass pattern** (from `config.py`):
```python
@dataclass
class SomeConfig:
    field: type = default
```
Added to `RapMapConfig` as a field with `field(default_factory=...)`.

**Pronunciation lookup** (from `lyrics/pronunciations.py`):
```python
phones, source = lookup_pronunciation(word, overrides, g2p_fallback=True)
variants = lookup_all_pronunciations(word, overrides)
```

---

## IMPLEMENTATION PLAN

### Phase 1: Config and Dependencies

Add preprocessing config, add `faster-whisper` optional dependency.

### Phase 2: Core Logic

Create the preprocessing module with STT transcription and word matching. Modify MFA alignment and syllable derivation to support full transcripts and word filtering.

### Phase 3: CLI Integration

Wire preprocessing into the `align` and `run` commands for guide role.

### Phase 4: Testing and Validation

Unit tests, integration test on example2/.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

### Task 1: UPDATE `pyproject.toml` — add faster-whisper dependency

- **IMPLEMENT**: Add `faster-whisper` to the `align` optional dependencies group:
  ```python
  align = [
      "montreal-forced-aligner>=3.0",
      "faster-whisper>=1.0",
  ]
  ```
- **VALIDATE**: `uv sync --extra align --extra dev` (or just check `uv lock` works)

### Task 2: UPDATE `src/rapmap/config.py` — add guide preprocessing config

- **IMPLEMENT**: Add `guide_preprocess: bool = True` field to `AlignmentConfig`:
  ```python
  @dataclass
  class AlignmentConfig:
      primary_backend: str = "mfa"
      fallback_backend: str = "whisperx"
      require_exact_syllable_count: bool = True
      min_syllable_confidence: float = 0.70
      fail_on_missing_syllables: bool = True
      fail_on_alignment_error: bool = True
      max_low_confidence_fraction: float = 0.2
      phoneme_smoothing_min_ms: float = 15.0
      energy_fallback: bool = True
      multi_pronunciation: bool = True
      guide_preprocess: bool = True           # NEW
      whisper_model: str = "base"             # NEW
      word_match_threshold: float = 0.75      # NEW — Levenshtein ratio for fuzzy matching
  ```
- **PATTERN**: Follow existing dataclass field patterns in `config.py`
- **VALIDATE**: `uv run python -c "from rapmap.config import AlignmentConfig; c = AlignmentConfig(); print(c.guide_preprocess, c.whisper_model)"`

### Task 3: UPDATE `configs/default.yaml` — add preprocessing defaults

- **IMPLEMENT**: Add to the `alignment:` section:
  ```yaml
  alignment:
    ...existing fields...
    guide_preprocess: true
    whisper_model: base
    word_match_threshold: 0.75
  ```
- **VALIDATE**: `uv run python -c "from rapmap.config import load_config; from pathlib import Path; c = load_config(Path('configs/default.yaml')); print(c.alignment.guide_preprocess)"`

### Task 4: CREATE `src/rapmap/guide/preprocess.py` — STT transcription + word matching

This is the core new module. It has three responsibilities:
1. Transcribe guide audio with faster-whisper
2. Match STT words to canonical lyrics words
3. Return a preprocessing result with match information

- **IMPLEMENT**:

```python
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from rapmap.lyrics.normalize import normalize_word

logger = logging.getLogger(__name__)


@dataclass
class WordMatch:
    """A single matched word: STT word index → canonical word index."""
    stt_index: int
    canonical_index: int
    stt_text: str
    canonical_text: str


@dataclass
class PreprocessResult:
    """Result of guide vocal preprocessing."""
    stt_words: list[str]                    # All words from STT (in order)
    canonical_words: list[str]              # Canonical words (from lyrics)
    matches: list[WordMatch]                # Matched pairs
    extra_indices: list[int]                # STT word indices that are extras
    canonical_word_to_stt: dict[int, int]   # canonical_idx → stt_idx
    stt_to_canonical_word: dict[int, int]   # stt_idx → canonical_idx
    all_matched: bool                       # True if all canonical words found


def transcribe_guide(audio_path: Path, model_size: str = "base") -> list[str]:
    """Transcribe guide vocal using faster-whisper. Returns list of words."""
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
    """Levenshtein similarity ratio between two strings (0.0 to 1.0)."""
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


def match_words(
    stt_words: list[str],
    canonical_words: list[str],
    threshold: float = 0.75,
) -> PreprocessResult:
    """Match STT-transcribed words to canonical lyrics words.

    Uses greedy forward matching with fuzzy comparison.
    Canonical words must appear in order within the STT words.
    """
    stt_normalized = [normalize_word(w) for w in stt_words]
    can_normalized = [normalize_word(w) for w in canonical_words]

    matches: list[WordMatch] = []
    extra_indices: list[int] = []
    canonical_to_stt: dict[int, int] = {}
    stt_to_canonical: dict[int, int] = {}

    can_ptr = 0
    for stt_idx, stt_norm in enumerate(stt_normalized):
        if can_ptr >= len(can_normalized):
            extra_indices.append(stt_idx)
            continue

        can_norm = can_normalized[can_ptr]
        if stt_norm == can_norm or (
            len(stt_norm) >= 2
            and len(can_norm) >= 2
            and _levenshtein_ratio(stt_norm, can_norm) >= threshold
        ):
            match = WordMatch(
                stt_index=stt_idx,
                canonical_index=can_ptr,
                stt_text=stt_words[stt_idx],
                canonical_text=canonical_words[can_ptr],
            )
            matches.append(match)
            canonical_to_stt[can_ptr] = stt_idx
            stt_to_canonical[stt_idx] = can_ptr
            can_ptr += 1
        else:
            extra_indices.append(stt_idx)

    all_matched = can_ptr == len(can_normalized)

    if not all_matched:
        unmatched = [
            f"'{canonical_words[i]}'" for i in range(can_ptr, len(can_normalized))
        ]
        logger.warning(
            "Guide preprocessing: %d/%d canonical words unmatched: %s",
            len(can_normalized) - can_ptr,
            len(can_normalized),
            ", ".join(unmatched[:10]),
        )

    return PreprocessResult(
        stt_words=stt_words,
        canonical_words=canonical_words,
        matches=matches,
        extra_indices=extra_indices,
        canonical_word_to_stt=canonical_to_stt,
        stt_to_canonical_word=stt_to_canonical,
        all_matched=all_matched,
    )


def preprocess_guide(
    audio_path: Path,
    canonical_syllables: dict,
    model_size: str = "base",
    match_threshold: float = 0.75,
) -> PreprocessResult | None:
    """Full preprocessing pipeline for guide vocals.

    Returns PreprocessResult if extras found, None if STT matches canonical exactly.
    """
    # Extract canonical word list (deduplicated, in order)
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
        len(stt_words), len(canonical_words),
    )

    if len(stt_words) == len(canonical_words):
        # Quick check: maybe no extras
        stt_norm = [normalize_word(w) for w in stt_words]
        can_norm = [normalize_word(w) for w in canonical_words]
        if stt_norm == can_norm:
            logger.info("Guide transcript matches canonical exactly — no preprocessing needed")
            return None

    result = match_words(stt_words, canonical_words, match_threshold)

    if not result.all_matched:
        logger.warning(
            "Guide preprocessing: not all canonical words found in STT transcript. "
            "Falling back to direct alignment (no filtering)."
        )
        return None

    n_extras = len(result.extra_indices)
    if n_extras == 0:
        logger.info("Guide has no extra words — no filtering needed")
        return None

    logger.info(
        "Guide has %d extra words (total STT: %d, canonical: %d). "
        "Will use full transcript for MFA and filter to canonical.",
        n_extras, len(stt_words), len(canonical_words),
    )
    return result
```

- **KEY DECISIONS**:
  - Greedy forward matching (canonical words must appear in order in STT)
  - Levenshtein fuzzy matching with configurable threshold (default 0.75)
  - Returns `None` if no extras found or matching fails → falls back to current behavior
  - `_levenshtein_ratio()` is self-contained (no external dep)
- **VALIDATE**: `uv run python -c "from rapmap.guide.preprocess import match_words; r = match_words(['yo','what','up','yeah','load'], ['yeah','load']); print(r.all_matched, r.extra_indices)"`

### Task 5: UPDATE `src/rapmap/align/mfa.py` — support full transcript override

- **IMPLEMENT**: Add two new params to `align_with_mfa()`:
  ```python
  def align_with_mfa(
      audio_path: Path,
      canonical_syllables: dict,
      project_dir: Path,
      role: str,
      config: AlignmentConfig,
      overrides: dict | None = None,
      stt_transcript: list[str] | None = None,  # NEW
  ) -> Path:
  ```
  When `stt_transcript` is provided:
  1. Use it for `_generate_transcript()` instead of canonical-derived transcript
  2. Generate a dictionary that covers ALL words in `stt_transcript` (canonical + extras)

- **IMPLEMENT**: Add `_generate_dictionary_for_words()`:
  ```python
  def _generate_dictionary_for_words(
      words: list[str],
      overrides: dict | None,
      multi_pronunciation: bool = True,
  ) -> str:
      """Generate MFA dictionary covering an arbitrary word list."""
      seen: set[str] = set()
      lines: list[str] = []
      for raw_word in words:
          word = _clean_word_for_mfa(raw_word)
          if word in seen or not word:
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
  ```

- **IMPLEMENT**: In `align_with_mfa()`, change the corpus setup block:
  ```python
  if stt_transcript is not None:
      transcript = " ".join(_clean_word_for_mfa(w) for w in stt_transcript if _clean_word_for_mfa(w))
      dict_text = _generate_dictionary_for_words(stt_transcript, overrides, config.multi_pronunciation)
  else:
      transcript = _generate_transcript(canonical_syllables)
      dict_text = _generate_dictionary(canonical_syllables, overrides, config.multi_pronunciation)
  
  (corpus_dir / f"{role}.txt").write_text(transcript)
  dict_path.write_text(dict_text)
  ```

- **GOTCHA**: All words in `stt_transcript` must have pronunciations. G2P fallback handles unknown words, but verify that `lookup_pronunciation` never returns empty phones for a non-empty word.
- **VALIDATE**: `ruff check src/rapmap/align/mfa.py`

### Task 6: UPDATE `src/rapmap/align/derive_syllables.py` — accept word filter

- **IMPLEMENT**: Add `canonical_word_indices: list[int] | None = None` parameter to `derive_syllable_timestamps()`:
  ```python
  def derive_syllable_timestamps(
      textgrid_path: Path,
      canonical_syllables: dict,
      sample_rate: int,
      role: str,
      audio_path: str,
      anchor_strategy: str = "onset",
      smoothing_min_ms: float = 0.0,
      audio_data: np.ndarray | None = None,
      canonical_word_indices: list[int] | None = None,  # NEW
  ) -> AlignmentResult:
  ```

- **IMPLEMENT**: After building `tg_words` (line 158), add filtering:
  ```python
  tg_words = [iv for iv in word_tier.intervals if iv.text]
  
  # Filter to canonical words only (when guide has extras)
  if canonical_word_indices is not None:
      assert all(0 <= i < len(tg_words) for i in canonical_word_indices), (
          f"canonical_word_indices out of range: max={max(canonical_word_indices)}, "
          f"tg_words count={len(tg_words)}"
      )
      tg_words = [tg_words[i] for i in canonical_word_indices]
  ```

- **IMPLEMENT**: The assertion at line 170 (`assert len(tg_words) == len(canonical_words)`) stays as-is — after filtering, the counts should match. If they don't, we want to fail loudly.

- **GOTCHA**: `tg_phones` is NOT filtered — phone matching is position-based (phones within word boundaries). Filtering `tg_words` is sufficient; the phone loop at line 191-199 already selects phones by sample position within each word's range.
- **VALIDATE**: `ruff check src/rapmap/align/derive_syllables.py`

### Task 7: UPDATE `src/rapmap/cli.py` — integrate preprocessing into `align` command

- **IMPLEMENT**: In the `align` command (around line 211), add preprocessing for guide role:
  ```python
  stt_transcript = None
  canonical_word_indices = None

  if role == "guide" and config.alignment.guide_preprocess:
      from rapmap.guide.preprocess import preprocess_guide
      
      click.echo("  Preprocessing guide vocal (STT transcription)...")
      preprocess_result = preprocess_guide(
          audio, canonical, config.alignment.whisper_model, config.alignment.word_match_threshold,
      )
      if preprocess_result is not None:
          stt_transcript = preprocess_result.stt_words
          # Map canonical word indices to STT (=TextGrid) word indices
          canonical_word_indices = [
              preprocess_result.canonical_word_to_stt[i]
              for i in range(len(preprocess_result.canonical_words))
          ]
          click.echo(
              f"  STT: {len(preprocess_result.stt_words)} words, "
              f"{len(preprocess_result.extra_indices)} extras filtered"
          )
          # Save preprocessing result for debugging
          import json as _json
          preprocess_out = project / "alignment" / f"{role}_preprocess.json"
          with open(preprocess_out, "w") as f:
              _json.dump({
                  "stt_words": preprocess_result.stt_words,
                  "extras": preprocess_result.extra_indices,
                  "matches": [
                      {"stt": m.stt_index, "canonical": m.canonical_index,
                       "stt_text": m.stt_text, "canonical_text": m.canonical_text}
                      for m in preprocess_result.matches
                  ],
              }, f, indent=2)
  ```
  Then pass `stt_transcript` to `align_with_mfa()` and `canonical_word_indices` to `derive_syllable_timestamps()`.

- **IMPLEMENT**: Update the `align_with_mfa` call:
  ```python
  textgrid_path = align_with_mfa(
      audio, canonical, project, role, config.alignment, overrides,
      stt_transcript=stt_transcript,
  )
  ```

- **IMPLEMENT**: Update the `derive_syllable_timestamps` call:
  ```python
  alignment = derive_syllable_timestamps(
      textgrid_path, canonical, sr, role, str(audio), config.anchor_strategy.default,
      smoothing_min_ms=config.alignment.phoneme_smoothing_min_ms,
      audio_data=audio_for_fallback,
      canonical_word_indices=canonical_word_indices,
  )
  ```

- **VALIDATE**: `ruff check src/rapmap/cli.py`

### Task 8: UPDATE `src/rapmap/cli.py` — integrate preprocessing into `run` command

- **IMPLEMENT**: In the `run` command's Phase 3 loop (around line 661), add the same preprocessing logic but only for the guide role:
  ```python
  for role_name, audio_key in roles:
      audio_path = out / proj_meta.get(audio_key, proj_meta.get("human_path", ""))
      if not audio_path.exists() and role_name == "human":
          audio_path = out / proj_meta["human_path"]
      
      stt_transcript = None
      canonical_word_indices = None
      
      if role_name == "guide" and config.alignment.guide_preprocess:
          from rapmap.guide.preprocess import preprocess_guide
          
          click.echo("  Preprocessing guide vocal (STT)...")
          preprocess_result = preprocess_guide(
              audio_path, canonical,
              config.alignment.whisper_model,
              config.alignment.word_match_threshold,
          )
          if preprocess_result is not None:
              stt_transcript = preprocess_result.stt_words
              canonical_word_indices = [
                  preprocess_result.canonical_word_to_stt[i]
                  for i in range(len(preprocess_result.canonical_words))
              ]
              click.echo(
                  f"  STT: {len(preprocess_result.stt_words)} words, "
                  f"{len(preprocess_result.extra_indices)} extras filtered"
              )
              preprocess_out = alignment_dir / f"{role_name}_preprocess.json"
              with open(preprocess_out, "w") as f:
                  json.dump({
                      "stt_words": preprocess_result.stt_words,
                      "extras": preprocess_result.extra_indices,
                      "matches": [
                          {"stt": m.stt_index, "canonical": m.canonical_index,
                           "stt_text": m.stt_text, "canonical_text": m.canonical_text}
                          for m in preprocess_result.matches
                      ],
                  }, f, indent=2)
      
      tg = align_with_mfa(
          audio_path, canonical, out, role_name, config.alignment, overrides,
          stt_transcript=stt_transcript,
      )
      audio_for_fallback, _ = read_audio(audio_path, mono=True)
      al = derive_syllable_timestamps(
          tg, canonical, sr, role_name, str(audio_path), anchor,
          smoothing_min_ms=config.alignment.phoneme_smoothing_min_ms,
          audio_data=audio_for_fallback,
          canonical_word_indices=canonical_word_indices,
      )
      ...
  ```

- **VALIDATE**: `ruff check src/rapmap/cli.py`

### Task 9: CREATE `tests/test_guide_preprocess.py` — unit tests

- **IMPLEMENT**: Test the word matching logic (does not require faster-whisper):
  ```python
  """Tests for guide vocal preprocessing — word matching logic."""
  from rapmap.guide.preprocess import (
      PreprocessResult,
      _levenshtein_ratio,
      match_words,
  )


  class TestLevenshteinRatio:
      def test_identical(self):
          assert _levenshtein_ratio("hello", "hello") == 1.0

      def test_empty(self):
          assert _levenshtein_ratio("", "hello") == 0.0
          assert _levenshtein_ratio("hello", "") == 0.0

      def test_similar(self):
          ratio = _levenshtein_ratio("sittin", "sitting")
          assert ratio > 0.75

      def test_different(self):
          ratio = _levenshtein_ratio("yo", "yeah")
          assert ratio < 0.75


  class TestMatchWords:
      def test_exact_match_no_extras(self):
          stt = ["yeah", "load", "up"]
          canonical = ["yeah", "load", "up"]
          result = match_words(stt, canonical)
          assert result.all_matched
          assert len(result.extra_indices) == 0
          assert len(result.matches) == 3

      def test_extras_at_start(self):
          stt = ["yo", "what", "up", "yeah", "load"]
          canonical = ["yeah", "load"]
          result = match_words(stt, canonical)
          assert result.all_matched
          assert result.extra_indices == [0, 1, 2]
          assert len(result.matches) == 2
          assert result.matches[0].stt_index == 3
          assert result.matches[1].stt_index == 4

      def test_extras_at_end(self):
          stt = ["yeah", "load", "peace", "out"]
          canonical = ["yeah", "load"]
          result = match_words(stt, canonical)
          assert result.all_matched
          assert result.extra_indices == [2, 3]

      def test_extras_in_middle(self):
          stt = ["yeah", "uh", "huh", "load"]
          canonical = ["yeah", "load"]
          result = match_words(stt, canonical)
          assert result.all_matched
          assert result.extra_indices == [1, 2]

      def test_extras_everywhere(self):
          stt = ["yo", "yeah", "uh", "load", "peace"]
          canonical = ["yeah", "load"]
          result = match_words(stt, canonical)
          assert result.all_matched
          assert result.extra_indices == [0, 2, 4]

      def test_fuzzy_match(self):
          stt = ["sittin", "on"]
          canonical = ["sitting", "on"]
          result = match_words(stt, canonical, threshold=0.75)
          assert result.all_matched

      def test_canonical_not_found(self):
          stt = ["yo", "what", "up"]
          canonical = ["yeah", "load"]
          result = match_words(stt, canonical)
          assert not result.all_matched

      def test_repeated_word_correct_matching(self):
          """If a canonical word appears earlier as an extra, greedy skips it."""
          stt = ["up", "yeah", "load", "up"]
          canonical = ["yeah", "load", "up"]
          result = match_words(stt, canonical)
          assert result.all_matched
          assert result.extra_indices == [0]
          assert result.matches[0].stt_index == 1  # "yeah"
          assert result.matches[2].stt_index == 3  # "up" (second occurrence)

      def test_canonical_word_to_stt_mapping(self):
          stt = ["intro", "yeah", "load"]
          canonical = ["yeah", "load"]
          result = match_words(stt, canonical)
          assert result.canonical_word_to_stt == {0: 1, 1: 2}
          assert result.stt_to_canonical_word == {1: 0, 2: 1}

      def test_empty_canonical(self):
          stt = ["yo", "what"]
          canonical = []
          result = match_words(stt, canonical)
          assert result.all_matched
          assert result.extra_indices == [0, 1]

      def test_empty_stt(self):
          stt = []
          canonical = ["yeah"]
          result = match_words(stt, canonical)
          assert not result.all_matched

      def test_punctuation_handling(self):
          """Words with different punctuation should still match after normalization."""
          stt = ["yeah,", "load!"]
          canonical = ["yeah", "load"]
          result = match_words(stt, canonical)
          assert result.all_matched
  ```

- **VALIDATE**: `uv run pytest tests/test_guide_preprocess.py -v`

### Task 10: UPDATE `src/rapmap/align/derive_syllables.py` — add test for filtered alignment

- **IMPLEMENT**: Add a test in `tests/test_guide_preprocess.py` or a new `tests/test_filtered_alignment.py` that:
  1. Creates a mock TextGrid with 5 words (2 extras + 3 canonical)
  2. Calls `derive_syllable_timestamps` with `canonical_word_indices=[1, 2, 4]`
  3. Verifies correct syllable count matches canonical
  4. Verifies extra words' time regions are excluded

  This can be a minimal test using the existing TextGrid parser infrastructure. If creating a real TextGrid is complex, verify the filtering logic by testing the key assertion behavior.

- **VALIDATE**: `uv run pytest tests/ -v`

### Task 11: VALIDATE — run all existing tests

- **IMPLEMENT**: Run the full test suite to ensure no regressions:
  ```bash
  uv run pytest tests/ -v
  ```
- **VALIDATE**: All tests pass (existing 168 + new tests from Tasks 9-10)

### Task 12: VALIDATE — end-to-end test on example2/

- **IMPLEMENT**: Run the full pipeline on example2/ which has the extra-syllable guide vocal:
  ```bash
  uv run rapmap run \
      --backing example2/beat.m4a \
      --human example2/vocals.wav \
      --lyrics example2/lyrics.txt \
      --guide example2/ai_guide_vocal.wav \
      --out workdir_example2_fixed
  ```
- **VALIDATE**:
  - Pipeline completes without errors
  - Check `workdir_example2_fixed/alignment/guide_preprocess.json` — extras identified
  - Check `workdir_example2_fixed/alignment/guide_alignment.json` — word durations reasonable (no 6+ second single words)
  - Check `workdir_example2_fixed/render/render_report.json` — validation_passed=true
  - Listen to `workdir_example2_fixed/render/corrected_human_rap.wav` — should sound natural, not distorted

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

### Level 2: Unit Tests

```bash
uv run pytest tests/test_guide_preprocess.py -v
```

### Level 3: Full Test Suite

```bash
uv run pytest tests/ -v
```

### Level 4: Integration Test

```bash
uv run rapmap run --backing example2/beat.m4a --human example2/vocals.wav --lyrics example2/lyrics.txt --guide example2/ai_guide_vocal.wav --out workdir_example2_fixed
```

### Level 5: Manual Validation

- Inspect `guide_preprocess.json` for correct word matching
- Inspect `guide_alignment.json` for reasonable word durations
- Listen to rendered output

---

## ACCEPTANCE CRITERIA

- [ ] `faster-whisper` added as optional dependency under `align` group
- [ ] `AlignmentConfig` has `guide_preprocess`, `whisper_model`, `word_match_threshold` fields
- [ ] `preprocess.py` module correctly identifies extra words in guide vocals
- [ ] `align_with_mfa()` accepts and uses full STT transcript when provided
- [ ] `derive_syllable_timestamps()` correctly filters TextGrid to canonical words
- [ ] `align` CLI command runs preprocessing for guide role
- [ ] `run` CLI command runs preprocessing for guide role in Phase 3
- [ ] All existing tests pass (no regressions)
- [ ] New word matching tests pass (12+ test cases)
- [ ] example2/ pipeline produces correct results — no inflated word durations
- [ ] Rendered audio sounds natural (not distorted by extreme stretch ratios)
- [ ] Preprocessing result saved to `alignment/guide_preprocess.json` for debugging
- [ ] Graceful fallback: if STT matching fails, falls back to current behavior (no filtering)

---

## NOTES

### Why faster-whisper over openai-whisper

- 4x faster inference on CPU (CTranslate2 backend)
- Lower memory usage (~500MB for "base" model vs ~1.5GB)
- Same accuracy (identical Whisper model weights)
- Clean Python API with word timestamps

### Why greedy matching over SequenceMatcher

- Canonical words MUST appear in order — this is a hard constraint
- Greedy forward scan is O(n) and handles the ordering naturally
- SequenceMatcher allows reorderings which we don't want
- Fuzzy threshold (Levenshtein ratio ≥ 0.75) handles Whisper transcription errors

### Graceful degradation

If preprocessing fails (STT unavailable, matching fails), the pipeline falls back to current behavior. This is deliberate — preprocessing is an optimization for imperfect guide vocals, not a hard requirement.

### Future improvements

- Cache Whisper model across multiple align calls (model loading is ~2s)
- Support WhisperX for better word boundary accuracy
- Two-pass matching (exact first, then fuzzy for gaps) for edge cases
- Confidence scoring for matches to detect questionable pairings
- Auto-detect when preprocessing is needed (based on guide duration vs. expected duration)

### Performance

- Whisper "base" model: ~2-3s for a 30s audio file on modern CPU
- Word matching: negligible (<1ms)
- MFA alignment: unchanged (~10-15s, same as before)
- Total overhead: ~3s per guide alignment

### Confidence Score

**8/10** — High confidence for one-pass success. The core logic (word matching, MFA transcript override, TextGrid filtering) is straightforward. Main risks:
1. Whisper transcription quality on heavily processed rap vocals (mitigated by fuzzy matching + fallback)
2. MFA handling a mixed transcript of real + G2P-only pronunciations (mitigated by existing multi-pronunciation support)
3. Edge case where canonical word appears multiple times with extras between occurrences (covered by greedy ordering)
