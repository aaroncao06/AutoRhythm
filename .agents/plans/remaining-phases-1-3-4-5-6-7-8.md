# Task: Remaining Pipeline — Phases 1, 3, 4, 5-6, 7, 8

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files etc.

## Task Description

Implement all remaining phases of the RapMap pipeline, building on the completed Phase 0 (normalize) and Phase 2 (syllabify) foundation.

**What we're building**: The full audio processing pipeline from guide vocal import through forced alignment, deterministic timing correction, and Audacity session output. The core invariant — zero-sample anchor error for every syllable — is enforced from Phase 4 onward.

**Phases**:
- **Phase 1**: Import/normalize a manual guide vocal into the project
- **Phase 3**: Forced alignment via MFA — produce phone-level timestamps for both guide and human vocals, then derive syllable-level timestamps
- **Phase 4**: Build anchor map — map each human syllable anchor to its corresponding guide syllable anchor
- **Phase 5**: Group syllables into clips at acoustically safe boundaries (or via 5 other modes)
- **Phase 6**: Generate a deterministic edit plan — piecewise time-warp specification per clip
- **Phase 7**: Render corrected vocals — Rubber Band time-stretch, clip assembly, flattened preview
- **Phase 8**: Build Audacity session — label tracks (TSV), optional mod-script-pipe automation

**AI boundary**: Phases 1 and 3 are the last phases where AI (MFA) is permitted. Phases 4–8 must be fully deterministic — no neural models.

## Task Metadata

**Task Type**: Code Change
**Estimated Complexity**: High
**Primary Systems Affected**: `src/rapmap/guide/`, `align/`, `timing/`, `edit/`, `audio/`, `audacity/`, `cli.py`
**Dependencies**: rubberband CLI (system), Montreal Forced Aligner (conda, optional)
**Supports Claim/Hypothesis**: C1 (zero-sample anchor error), C2 (safe-boundary grouping), C3 (Audacity transparency), C5 (MFA alignment), C6 (Rubber Band identity), C7 (determinism)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/rapmap/cli.py` (full file) — All CLI commands. `init` and `syllabify` are wired; rest raise `NotImplementedError`. Follow the same pattern for wiring new phases.
- `src/rapmap/config.py` (full file) — All config dataclasses: `ProjectConfig`, `GuideGenerationConfig`, `AlignmentConfig`, `AnchorStrategyConfig`, `SafeBoundaryConfig`, `ClipGroupingConfig`, `RenderingConfig`, `AudacityConfig`, `ValidationConfig`.
- `src/rapmap/audio/io.py` (full file) — `read_audio(path, mono)`, `write_audio(path, data, sr)`, `audio_info(path)`. Use these for all audio I/O.
- `src/rapmap/audio/normalize.py` (full file) — Phase 0 pattern. `_resample()` for sample rate conversion.
- `src/rapmap/lyrics/syllabify.py` (full file) — `build_canonical_syllables()` return format, `syllabify_phones()`, `is_vowel()`. These are used in Phase 3 (derive_syllables) and Phase 4 (anchor mapping).
- `src/rapmap/lyrics/parser.py` (full file) — `parse_lyrics()` return format (bars → lines → words).
- `src/rapmap/lyrics/pronunciations.py` (full file) — `lookup_pronunciation()` for generating MFA dictionary entries.
- `src/rapmap/lyrics/overrides.py` (full file) — `load_overrides()` for pronunciation overrides.
- `src/rapmap/configs/default.yaml` (full file) — All default config values.
- `CLAUDE.md` — Coding conventions: integer sample indices, fail-loud, liberal assertions, snake_case.

### CLI wiring pattern (from existing `cli.py`):

```python
@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
def some_phase(project: Path, config_path: Path | None):
    config = load_config(config_path or _bundled_config("default.yaml"))
    # ... load inputs, call implementation, write outputs, print summary
```

### Bundled config access pattern:

```python
def _bundled_config(filename: str) -> Path:
    return Path(str(importlib.resources.files("rapmap.configs").joinpath(filename)))
```

### New Files to Create

```
src/rapmap/guide/base.py            # GuideVocalResult + interface
src/rapmap/guide/manual.py          # Manual guide loader
src/rapmap/align/base.py            # AlignmentResult + Aligner interface
src/rapmap/align/textgrid.py        # Minimal TextGrid parser
src/rapmap/align/mfa.py             # MFA subprocess wrapper
src/rapmap/align/derive_syllables.py # Phone timestamps → syllable timestamps
src/rapmap/align/validate.py        # Alignment validation
src/rapmap/timing/anchors.py        # Anchor extraction strategies
src/rapmap/timing/anchor_map.py     # Human→guide anchor map
src/rapmap/timing/confidence.py     # Confidence scoring
src/rapmap/edit/operations.py       # Data types (Segment, ClipOperation)
src/rapmap/edit/safe_boundaries.py  # Safe boundary scoring
src/rapmap/edit/grouping.py         # All 6 grouping modes
src/rapmap/edit/crossfade.py        # Crossfade computation
src/rapmap/edit/planner.py          # Deterministic edit plan
src/rapmap/edit/manifest.py         # Clip manifest generation
src/rapmap/audio/stretch.py         # Rubber Band wrapper
src/rapmap/audio/render.py          # Clip rendering + flattened preview
src/rapmap/audacity/labels.py       # TSV label generation
src/rapmap/audacity/script_pipe.py  # mod-script-pipe controller
src/rapmap/audacity/import_project.py # Session builder
tests/test_textgrid.py
tests/test_guide.py
tests/test_anchor_mapping.py
tests/test_safe_boundary_grouping.py
tests/test_edit_plan_exactness.py
tests/test_render_clip_lengths.py
tests/test_audacity_labels.py
```

---

## DATA FORMAT SPECIFICATIONS

All phases communicate through JSON files in the project workdir. Integer sample indices everywhere — never float seconds internally.

### Phase 1 Output — Guide added to project

Phase 1 adds `audio/ai_guide_vocal.wav` and updates `project.json`:
```json
{
  "sample_rate": 48000,
  "guide_path": "audio/ai_guide_vocal.wav",
  "guide_duration_samples": 240000,
  "guide_source": "manual"
}
```

### Phase 3 Output — `alignment/{role}_alignment.json`

Produced once for guide, once for human:
```json
{
  "sample_rate": 48000,
  "role": "guide",
  "audio_path": "audio/ai_guide_vocal.wav",
  "total_duration_samples": 240000,
  "words": [
    {
      "word_index": 0,
      "text": "I",
      "start_sample": 14400,
      "end_sample": 24000,
      "phones": [
        {"phone": "AY1", "start_sample": 14400, "end_sample": 24000}
      ]
    }
  ],
  "syllables": [
    {
      "syllable_index": 0,
      "word_index": 0,
      "word_text": "I",
      "start_sample": 14400,
      "end_sample": 24000,
      "anchor_sample": 14400,
      "phones": [
        {"phone": "AY1", "start_sample": 14400, "end_sample": 24000}
      ],
      "confidence": 0.95
    }
  ]
}
```

Key rules:
- `start_sample >= 0` and `end_sample > start_sample` for every entry
- `anchor_sample` is within `[start_sample, end_sample]`
- `len(syllables)` must equal canonical syllable count
- `syllable_index` is contiguous 0..N-1

### Phase 4 Output — `timing/anchor_map.json`

```json
{
  "sample_rate": 48000,
  "anchor_strategy": "onset",
  "syllable_count": 7,
  "anchors": [
    {
      "syllable_index": 0,
      "human_anchor_sample": 14400,
      "guide_anchor_sample": 12000,
      "delta_samples": -2400,
      "human_start_sample": 14400,
      "human_end_sample": 24000,
      "guide_start_sample": 12000,
      "guide_end_sample": 21600,
      "confidence": 0.95
    }
  ]
}
```

Key rules:
- `guide_anchor_sample` values must be monotonically increasing
- `delta_samples = human_anchor_sample - guide_anchor_sample`

### Phase 5 Output — `edit/clip_groups.json`

```json
{
  "sample_rate": 48000,
  "grouping_mode": "safe_boundary",
  "clip_count": 3,
  "clips": [
    {
      "clip_index": 0,
      "clip_id": "clip_0000_i_got",
      "syllable_indices": [0, 1],
      "source_start_sample": 13440,
      "source_end_sample": 48960,
      "target_start_sample": 11040,
      "target_end_sample": 44160
    }
  ]
}
```

Key rules:
- Every syllable appears in exactly one clip
- `syllable_indices` within each clip are contiguous
- Source ranges come from human alignment; target ranges from guide alignment
- Clips are non-overlapping and ordered

### Phase 6 Output — `edit/edit_plan.json`

```json
{
  "sample_rate": 48000,
  "grouping_mode": "safe_boundary",
  "anchor_strategy": "onset",
  "total_clips": 3,
  "crossfade_samples": 384,
  "operations": [
    {
      "clip_index": 0,
      "clip_id": "clip_0000_i_got",
      "segments": [
        {
          "segment_index": 0,
          "syllable_index": 0,
          "source_start_sample": 13440,
          "source_end_sample": 24000,
          "target_start_sample": 11040,
          "target_end_sample": 21600,
          "source_duration_samples": 10560,
          "target_duration_samples": 10560,
          "stretch_ratio": 1.0
        }
      ]
    }
  ]
}
```

Key rules:
- Each clip is split into segments at anchor boundaries for piecewise stretching
- `stretch_ratio = target_duration / source_duration`
- Segment target boundaries are at exact guide anchor positions
- The hard invariant: concatenating segments places anchors at exact target positions

### Phase 7 Output — `render/render_report.json` + `edit/clip_manifest.json`

**render_report.json:**
```json
{
  "sample_rate": 48000,
  "total_clips": 3,
  "total_syllables": 7,
  "anchor_errors": [],
  "max_stretch_ratio": 1.2,
  "min_stretch_ratio": 0.85,
  "extreme_stretches": [],
  "validation_passed": true
}
```

**clip_manifest.json:**
```json
{
  "sample_rate": 48000,
  "clips": [
    {
      "clip_index": 0,
      "clip_id": "clip_0000_i_got",
      "path": "audio/clips/clip_0000_i_got.wav",
      "duration_samples": 33120,
      "segment_count": 2
    }
  ],
  "flattened_path": "render/corrected_human_rap.wav",
  "flattened_duration_samples": 240000
}
```

### Phase 8 Output — Audacity label format (TSV)

```
0.300000\t0.500000\tI [syl 0]
0.500000\t1.000000\tgot [syl 1]
1.000000\t1.450000\tmon- [syl 2]
1.450000\t2.050000\t-ey [syl 3]
```

Three columns: start_seconds, end_seconds, label. Tab-delimited. Seconds are the ONLY place floats are used.

---

## IMPLEMENTATION PLAN

### Block 1: Phase 1 — Guide Vocal Import

Create the guide vocal interface and manual loader. Simple: normalize and copy a WAV.

### Block 2: Phase 3 — Forced Alignment

TextGrid parser, MFA subprocess wrapper, phone→syllable derivation, validation. This is the most complex block due to MFA's corpus-directory requirements.

### Block 3: Phase 4 — Anchor Mapping

Pure data transformation. Extract anchors from alignments, build the map, check monotonicity.

### Block 4: Phases 5–6 — Grouping + Edit Planning

The algorithmic core. Safe boundary scoring, 6 grouping modes, piecewise edit plan generation.

### Block 5: Phase 7 — Rendering

Rubber Band time-stretch, per-segment rendering, clip assembly with crossfades, flattened preview. Zero-sample anchor validation.

### Block 6: Phase 8 — Audacity Integration

TSV label generation (always works) + optional mod-script-pipe session builder.

### Block 7: Full Pipeline + Tests

Wire `run` CLI command. Write tests with fixture data (no MFA/Rubber Band required).

---

## STEP-BY-STEP TASKS

### 1. CREATE `src/rapmap/guide/base.py` — guide interface

- **IMPLEMENT**:
  ```python
  from __future__ import annotations
  from dataclasses import dataclass
  from pathlib import Path

  @dataclass
  class GuideVocalResult:
      path: Path
      duration_samples: int
      sample_rate: int
      source: str  # "manual", "songgeneration", "yue", "acestep"
  ```
- **VALIDATE**: `uv run python -c "from rapmap.guide.base import GuideVocalResult; print('OK')"`

### 2. CREATE `src/rapmap/guide/manual.py` — manual guide loader

- **IMPLEMENT**: One function:
  ```python
  def load_manual_guide(guide_path: Path, project_dir: Path, config: ProjectConfig) -> GuideVocalResult:
  ```
  - Read guide audio with `read_audio(guide_path, mono=True)` — guide must be mono for alignment
  - Resample to `config.sample_rate` using `_resample` from `audio/normalize.py`
  - Write to `project_dir / "audio" / "ai_guide_vocal.wav"` via `write_audio()`
  - Return `GuideVocalResult`
- **IMPORTS**: `rapmap.audio.io.read_audio`, `rapmap.audio.io.write_audio`, `rapmap.audio.normalize._resample`, `rapmap.config.ProjectConfig`
- **GOTCHA**: Import `_resample` — it's a private function but within the same package. Consider moving it to `audio/io.py` if cleaner, or just import it directly.
- **VALIDATE**: `uv run python -c "from rapmap.guide.manual import load_manual_guide; print('OK')"`

### 3. UPDATE `src/rapmap/cli.py` — wire `set-guide` command

- **IMPLEMENT**: Replace `NotImplementedError` in `set_guide()` with:
  1. Load config.
  2. Call `load_manual_guide(guide, project, config.project)`.
  3. Update `project.json` with guide metadata (`guide_path`, `guide_duration_samples`, `guide_source`).
  4. Print summary.
- **IMPORTS**: Add `from rapmap.guide.manual import load_manual_guide`
- **VALIDATE**: Create a synthetic guide WAV, run `uv run rapmap set-guide --project workdir --guide test_guide.wav`

### 4. CREATE `src/rapmap/align/textgrid.py` — minimal TextGrid parser

- **IMPLEMENT**: Parse Praat TextGrid "long" format (what MFA produces). No external dependency.
  ```python
  @dataclass
  class Interval:
      xmin: float  # seconds
      xmax: float  # seconds
      text: str

  @dataclass
  class IntervalTier:
      name: str
      intervals: list[Interval]

  def parse_textgrid(path: Path) -> dict[str, IntervalTier]:
  ```
  - Parse the file line by line.
  - Look for `item [N]:` blocks, each containing `class`, `name`, `intervals`.
  - Within each interval: parse `xmin`, `xmax`, `text` fields.
  - Return dict keyed by tier name (typically `"words"` and `"phones"`).
  - Skip empty-text intervals (MFA silence markers).
- **GOTCHA**: MFA TextGrid format uses `text = ""` for silence/unaligned regions. Include them in the parsed output (they carry timing information) but mark them.
- **GOTCHA**: Text values are double-quoted in TextGrid: `text = "money"`. Strip the quotes.
- **GOTCHA**: Some TextGrid files use short format (no `xmin =` prefix). MFA 3.x uses the long format by default.
- **MFA TextGrid example:**
  ```
  File type = "ooTextFile"
  Object class = "TextGrid"

  xmin = 0.0
  xmax = 1.52
  tiers? <exists>
  size = 2
  item []:
      item [1]:
          class = "IntervalTier"
          name = "words"
          ...
          intervals: size = 3
              intervals [1]:
                  xmin = 0.0
                  xmax = 0.28
                  text = ""
              intervals [2]:
                  xmin = 0.28
                  xmax = 0.98
                  text = "money"
      item [2]:
          class = "IntervalTier"
          name = "phones"
          ...
  ```
- **VALIDATE**: `uv run python -c "from rapmap.align.textgrid import parse_textgrid; print('OK')"`

### 5. CREATE `src/rapmap/align/base.py` — aligner interface

- **IMPLEMENT**:
  ```python
  from __future__ import annotations
  from dataclasses import dataclass
  from pathlib import Path

  @dataclass
  class PhoneTimestamp:
      phone: str
      start_sample: int
      end_sample: int

  @dataclass
  class WordTimestamp:
      word_index: int
      text: str
      start_sample: int
      end_sample: int
      phones: list[PhoneTimestamp]

  @dataclass
  class SyllableTimestamp:
      syllable_index: int
      word_index: int
      word_text: str
      start_sample: int
      end_sample: int
      anchor_sample: int
      phones: list[PhoneTimestamp]
      confidence: float

  @dataclass
  class AlignmentResult:
      sample_rate: int
      role: str  # "guide" or "human"
      audio_path: str
      total_duration_samples: int
      words: list[WordTimestamp]
      syllables: list[SyllableTimestamp]

  def alignment_to_dict(result: AlignmentResult) -> dict:
      # Serialize to JSON-compatible dict matching the schema in DATA FORMAT SPECIFICATIONS
      ...

  def alignment_from_dict(data: dict) -> AlignmentResult:
      # Deserialize from JSON dict
      ...
  ```
- **VALIDATE**: `uv run python -c "from rapmap.align.base import AlignmentResult; print('OK')"`

### 6. CREATE `src/rapmap/align/mfa.py` — MFA subprocess wrapper

- **IMPLEMENT**:
  ```python
  def align_with_mfa(
      audio_path: Path,
      canonical_syllables: dict,
      project_dir: Path,
      role: str,
      config: AlignmentConfig,
  ) -> Path:
  ```
  Steps:
  1. Create temp corpus directory: `tempdir/corpus/` with `{role}.wav` and `{role}.txt`
  2. Generate transcript text: space-joined word texts from canonical syllables (one line, all words)
  3. Generate MFA dictionary file: `tempdir/dictionary.txt` with entries for all words. Format: `word\tPHONE1 PHONE2 ...` (tab-separated, ARPAbet). Use `lookup_pronunciation()` to get phones matching canonical syllables.
  4. Run: `subprocess.run(["mfa", "align", corpus_dir, dict_path, "english_us_arpa", output_dir, "--clean", "--single_speaker"], check=True)`
  5. Find the output TextGrid: `output_dir/{role}.TextGrid`
  6. Copy TextGrid to `project_dir/alignment/{role}_alignment.TextGrid`
  7. Return the TextGrid path.
- **GOTCHA**: MFA requires `--clean` to overwrite existing output. Use `--single_speaker` since each file is one speaker.
- **GOTCHA**: MFA dictionary: use the SAME phone sequences as canonical syllables (from CMUdict/g2p/overrides). Generate the dictionary from `lookup_pronunciation()`.
- **GOTCHA**: MFA must be installed separately (`conda install -c conda-forge montreal-forced-aligner`). The function should check if `mfa` is on PATH and raise a clear error if not: `RuntimeError("MFA not found. Install: conda install -c conda-forge montreal-forced-aligner")`.
- **GOTCHA**: MFA needs model download first: `mfa model download acoustic english_us_arpa`. Check and give clear error.
- **IMPORTS**: `subprocess`, `tempfile`, `shutil`, `rapmap.lyrics.pronunciations.lookup_pronunciation`
- **VALIDATE**: `uv run python -c "from rapmap.align.mfa import align_with_mfa; print('OK')"`

### 7. CREATE `src/rapmap/align/derive_syllables.py` — phone timestamps → syllable timestamps

- **IMPLEMENT**: This is the critical bridge between MFA output and the canonical syllable representation.
  ```python
  def derive_syllable_timestamps(
      textgrid_path: Path,
      canonical_syllables: dict,
      sample_rate: int,
      role: str,
      anchor_strategy: str = "onset",
  ) -> AlignmentResult:
  ```
  Algorithm:
  1. Parse TextGrid with `parse_textgrid()`.
  2. Get `words` tier and `phones` tier.
  3. Convert all timestamps from float seconds to integer samples: `int(round(seconds * sample_rate))`.
  4. For each word in canonical syllables, match to the TextGrid word tier (by position order — don't match by text, since MFA may lowercase differently).
  5. For each matched word, get its phone intervals from the phones tier (phones whose time falls within the word's time range).
  6. Count vowel phones (using `is_vowel()` from `lyrics/syllabify.py`). Assert vowel count equals canonical syllable count for this word.
  7. Group phones into syllables using `syllabify_phones()` — same onset-maximization algorithm as Phase 2. The phone IDENTITIES may differ slightly from canonical, but the vowel count must match.
  8. For each derived syllable group:
     - `start_sample` = first phone's start_sample
     - `end_sample` = last phone's end_sample
     - `anchor_sample` = depends on strategy:
       - `"onset"`: first phone's start_sample
       - `"vowel_nucleus"`: the vowel phone's midpoint `(vowel.start + vowel.end) // 2`
       - `"end"`: last phone's end_sample
     - `confidence` = minimum phone duration (ms) normalized: `min(1.0, min_phone_duration_ms / 30.0)`
  9. Assert `len(syllables) == len(canonical_syllables["syllables"])`.
  10. Return `AlignmentResult`.
- **IMPORTS**: `rapmap.align.textgrid.parse_textgrid`, `rapmap.align.base.*`, `rapmap.lyrics.syllabify.is_vowel`, `rapmap.lyrics.syllabify.syllabify_phones`
- **GOTCHA**: MFA phone labels use uppercase ARPAbet with stress digits — same as CMUdict. No conversion needed.
- **GOTCHA**: MFA may produce silence intervals (`""` text) between or around words. Skip these when matching phones to words.
- **GOTCHA**: Phone-to-word assignment: a phone belongs to a word if the phone's midpoint falls within the word's time range. Edge cases: use `phone.xmin >= word.xmin and phone.xmax <= word.xmax`.
- **GOTCHA**: If vowel count mismatch: check `config.require_exact_syllable_count`. If True, raise `ValueError`. If False, attempt heuristic redistribution (evenly split the word's time across canonical syllable count).
- **VALIDATE**: `uv run python -c "from rapmap.align.derive_syllables import derive_syllable_timestamps; print('OK')"`

### 8. CREATE `src/rapmap/align/validate.py` — alignment validation

- **IMPLEMENT**:
  ```python
  def validate_alignment(
      alignment: AlignmentResult,
      canonical_syllables: dict,
      config: AlignmentConfig,
  ) -> dict:
  ```
  Checks:
  1. Syllable count: `len(alignment.syllables) == len(canonical["syllables"])`
  2. Monotonicity: each syllable starts after the previous one ends (or at least starts)
  3. Non-negative: all `start_sample >= 0` and `end_sample > start_sample`
  4. Anchor within bounds: `start_sample <= anchor_sample <= end_sample`
  5. Confidence threshold: count syllables below `config.min_syllable_confidence`
  6. Return validation dict: `{"passed": bool, "checks": {...}, "low_confidence_syllables": [...]}`
  - If `config.fail_on_missing_syllables` and syllable count mismatch → raise ValueError
  - If `config.fail_on_alignment_error` and validation fails → raise ValueError
- **VALIDATE**: `uv run python -c "from rapmap.align.validate import validate_alignment; print('OK')"`

### 9. UPDATE `src/rapmap/cli.py` — wire `align` command

- **IMPLEMENT**: Replace `NotImplementedError` in `align()` with:
  1. Load project.json, canonical syllables, config.
  2. Determine audio path: for `role=guide`, use `project.json["guide_path"]`; for `role=human`, use `project.json["human_analysis_path"]` (or `human_path`).
  3. Call `align_with_mfa()` to get TextGrid.
  4. Call `derive_syllable_timestamps()` to get `AlignmentResult`.
  5. Call `validate_alignment()`.
  6. Write `alignment/{role}_alignment.json`.
  7. Print summary: syllable count, low-confidence count, source.
- **IMPORTS**: Add align module imports.
- **GOTCHA**: The `--audio` option in the existing CLI lets the user override the audio path. Respect it if provided, otherwise derive from project.json.
- **VALIDATE**: `uv run rapmap align --help` should show options without error

### 10. CREATE `src/rapmap/timing/anchors.py` — anchor extraction strategies

- **IMPLEMENT**:
  ```python
  def extract_anchor(syllable: SyllableTimestamp, strategy: str) -> int:
      """Return the anchor sample for a syllable given the strategy."""
  ```
  Strategies:
  - `"onset"`: `syllable.start_sample` (default for rap — syllable attack is the anchor)
  - `"vowel_nucleus"`: midpoint of the first vowel phone in the syllable
  - `"end"`: `syllable.end_sample`
  - `"onset_and_end"`: returns onset (end is used separately in anchor_map)
  - `"hybrid"`: onset for onset, soft weight toward end for end

  Also:
  ```python
  def extract_anchor_pair(syllable: SyllableTimestamp, strategy: str) -> tuple[int, int | None]:
      """For strategies that use two points (onset_and_end), return (primary, secondary)."""
  ```
- **VALIDATE**: `uv run python -c "from rapmap.timing.anchors import extract_anchor; print('OK')"`

### 11. CREATE `src/rapmap/timing/anchor_map.py` — build human→guide anchor map

- **IMPLEMENT**:
  ```python
  def build_anchor_map(
      guide_alignment: AlignmentResult,
      human_alignment: AlignmentResult,
      config: AnchorStrategyConfig,
  ) -> dict:
  ```
  Algorithm:
  1. Assert `len(guide.syllables) == len(human.syllables)`.
  2. For each syllable index i:
     - `human_anchor = extract_anchor(human.syllables[i], config.default)`
     - `guide_anchor = extract_anchor(guide.syllables[i], config.default)`
     - Record mapping.
  3. Validate guide anchors are monotonically increasing:
     ```python
     for i in range(1, len(anchors)):
         assert anchors[i]["guide_anchor_sample"] > anchors[i-1]["guide_anchor_sample"], \
             f"Non-monotonic guide anchor at syllable {i}"
     ```
  4. Return dict matching the anchor_map.json schema.
- **VALIDATE**: `uv run python -c "from rapmap.timing.anchor_map import build_anchor_map; print('OK')"`

### 12. CREATE `src/rapmap/timing/confidence.py` — confidence scoring

- **IMPLEMENT**:
  ```python
  def compute_syllable_confidence(syllable: SyllableTimestamp) -> float:
      """Confidence based on phone durations. Short phones = low confidence."""
      if not syllable.phones:
          return 0.0
      min_duration = min(p.end_sample - p.start_sample for p in syllable.phones)
      min_duration_ms = min_duration * 1000 / 48000  # approximate
      return min(1.0, max(0.0, min_duration_ms / 30.0))

  def flag_low_confidence(anchor_map: dict, threshold: float) -> list[int]:
      """Return syllable indices with confidence below threshold."""
  ```
- **VALIDATE**: `uv run python -c "from rapmap.timing.confidence import compute_syllable_confidence; print('OK')"`

### 13. UPDATE `src/rapmap/cli.py` — wire `anchors` command

- **IMPLEMENT**: Replace `NotImplementedError` in `anchors()` with:
  1. Load guide and human alignments from `alignment/` dir.
  2. Load config.
  3. Call `build_anchor_map()`.
  4. Write `timing/anchor_map.json`.
  5. Flag low-confidence syllables, print summary.
- **VALIDATE**: `uv run rapmap anchors --help`

### 14. CREATE `src/rapmap/edit/operations.py` — data types

- **IMPLEMENT**: Dataclasses for the edit pipeline:
  ```python
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
      segments: list[Segment]
      crossfade_samples: int

  @dataclass
  class EditPlan:
      sample_rate: int
      grouping_mode: str
      anchor_strategy: str
      crossfade_samples: int
      operations: list[ClipOperation]

  def edit_plan_to_dict(plan: EditPlan) -> dict: ...
  def edit_plan_from_dict(data: dict) -> EditPlan: ...
  ```
- **VALIDATE**: `uv run python -c "from rapmap.edit.operations import EditPlan, Segment, ClipOperation; print('OK')"`

### 15. CREATE `src/rapmap/edit/safe_boundaries.py` — safe boundary scoring

- **IMPLEMENT**:
  ```python
  def score_boundaries(
      canonical_syllables: dict,
      human_alignment: AlignmentResult,
      audio_data: np.ndarray,
      sample_rate: int,
      config: SafeBoundaryConfig,
  ) -> list[float]:
  ```
  Returns a list of scores, one per boundary between consecutive syllables (length = N-1 for N syllables). Higher score = better split point.

  For boundary between syllable i and i+1:
  1. **Silence gap** (weight 0.3): `gap = syl[i+1].start - syl[i].end`. Score = `min(1.0, gap_ms / config.min_silence_ms)`.
  2. **Low energy** (weight 0.3): Compute RMS energy in a window of `config.low_energy_window_ms` centered at the boundary. Normalize against track average. Score = `1.0 - normalized_energy`.
  3. **Zero crossing** (weight 0.1): Search `config.zero_crossing_search_ms` window for zero crossings. Score = `1.0` if found, `0.0` if not.
  4. **Word boundary bonus** (+0.3): If syllable i is `is_word_final` and `config.prefer_word_boundaries`.
  5. **Line boundary bonus** (+0.5): If syllable i is `is_line_final` and `config.prefer_line_boundaries`.
  6. **Mid-word penalty** (-0.3): If not at a word boundary and `config.avoid_inside_words`.
- **IMPORTS**: `numpy`, `rapmap.config.SafeBoundaryConfig`
- **VALIDATE**: `uv run python -c "from rapmap.edit.safe_boundaries import score_boundaries; print('OK')"`

### 16. CREATE `src/rapmap/edit/grouping.py` — all 6 grouping modes

- **IMPLEMENT**: Main entry point + per-mode functions:
  ```python
  def group_syllables(
      canonical_syllables: dict,
      anchor_map: dict,
      human_alignment: AlignmentResult | None,
      audio_data: np.ndarray | None,
      sample_rate: int,
      config: ClipGroupingConfig,
      mode: str = "safe_boundary",
  ) -> dict:
  ```
  Returns dict matching clip_groups.json schema.

  **Mode implementations:**

  1. **`safe_boundary`**: Dynamic programming.
     - Compute boundary scores via `score_boundaries()`.
     - DP: `dp[i]` = best total boundary score for grouping syllables 0..i-1.
     - Transition: try all clip lengths from 1 to `config.safe_boundary.max_syllables_per_clip`. Enforce `min_clip_duration_ms` and `max_clip_duration_ms` using human alignment timestamps.
     - Backtrack to find optimal grouping.

  2. **`word`**: One clip per word. Group syllables by `word_index`.

  3. **`syllable_with_handles`**: One clip per syllable. Source ranges include pre/post handle padding.

  4. **`strict_syllable`**: One clip per syllable. Hard cut at syllable boundaries. No handles.

  5. **`phrase`**: One clip per line. Group syllables by `line_index`.

  6. **`bar`**: One clip per bar. Group syllables by `bar_index`.

  **Clip ID generation**: `f"clip_{clip_index:04d}_{label}"` where label is the first word text (or joined words if short), truncated to 20 chars, lowercased, non-alphanumeric replaced with `_`.

  **Source/target range computation** (shared by all modes):
  For each clip with syllable indices [i, j]:
  - `source_start = human_alignment.syllables[i].start_sample`
  - `source_end = human_alignment.syllables[j].end_sample`
  - `target_start = guide_alignment anchors[i].guide_start_sample` (from anchor_map)
  - `target_end = guide_alignment anchors[j].guide_end_sample` (from anchor_map)
- **GOTCHA**: `safe_boundary` mode needs audio data and human alignment for scoring. Other modes only need canonical syllables and anchor_map.
- **GOTCHA**: `syllable_with_handles` mode extends source ranges by pre/post handle samples from `RenderingConfig`, but must clamp to `[0, total_samples]`.
- **VALIDATE**: `uv run python -c "from rapmap.edit.grouping import group_syllables; print('OK')"`

### 17. CREATE `src/rapmap/edit/crossfade.py` — crossfade computation

- **IMPLEMENT**:
  ```python
  def compute_crossfade(
      left: np.ndarray,
      right: np.ndarray,
      crossfade_samples: int,
  ) -> np.ndarray:
      """Apply equal-power crossfade between end of left and start of right."""
      if crossfade_samples <= 0 or len(left) == 0 or len(right) == 0:
          return np.concatenate([left, right])
      xf = min(crossfade_samples, len(left), len(right))
      fade_out = np.sqrt(np.linspace(1.0, 0.0, xf)).astype(np.float32)
      fade_in = np.sqrt(np.linspace(0.0, 1.0, xf)).astype(np.float32)
      result = np.concatenate([
          left[:-xf],
          left[-xf:] * fade_out + right[:xf] * fade_in,
          right[xf:],
      ])
      return result
  ```
- **GOTCHA**: Equal-power crossfade preserves energy: `fade_out^2 + fade_in^2 = 1`.
- **VALIDATE**: `uv run python -c "from rapmap.edit.crossfade import compute_crossfade; print('OK')"`

### 18. CREATE `src/rapmap/edit/planner.py` — deterministic edit plan generation

- **IMPLEMENT**: This is the core of the zero-sample-error guarantee.
  ```python
  def create_edit_plan(
      clip_groups: dict,
      anchor_map: dict,
      config: RenderingConfig,
  ) -> EditPlan:
  ```
  For each clip in `clip_groups["clips"]`:
  1. Get the syllable indices in this clip.
  2. Get the anchor positions for each syllable (from anchor_map).
  3. Build segments by splitting at anchor boundaries:
     - First segment: `[clip_source_start, first_anchor_source]` → `[clip_target_start, first_anchor_target]`
     - Inter-anchor segments: `[anchor_i_source, anchor_i+1_source]` → `[anchor_i_target, anchor_i+1_target]`
     - Last segment: `[last_anchor_source, clip_source_end]` → `[last_anchor_target, clip_target_end]`
  4. Compute stretch ratio per segment: `target_duration / source_duration`.
  5. Validate: `config.min_stretch_ratio <= ratio <= config.max_stretch_ratio` (or flag if outside bounds).
  6. `crossfade_samples = int(config.crossfade_ms * anchor_map["sample_rate"] / 1000)`.
  7. Return `EditPlan`.

  **The anchor guarantee**: Segments are split exactly at anchor sample positions. When segments are concatenated (with NO crossfade between segments within a clip), the anchor position is at the segment boundary — exactly `target_start + sum(preceding_segment_target_durations)`. This equals the target anchor position by construction.
- **GOTCHA**: `source_duration == 0` can happen if two adjacent anchors have the same source position. Handle by creating a zero-length segment with ratio 1.0.
- **GOTCHA**: For the first segment (pre-first-anchor), source_start is the clip's source_start, NOT the first anchor. This includes any handle audio before the first syllable onset.
- **VALIDATE**: `uv run python -c "from rapmap.edit.planner import create_edit_plan; print('OK')"`

### 19. CREATE `src/rapmap/edit/manifest.py` — clip manifest generation

- **IMPLEMENT**:
  ```python
  def build_manifest(edit_plan: EditPlan, clips_dir: Path) -> dict:
      """Build clip manifest from edit plan. Called after rendering."""
  ```
  Iterates over `edit_plan.operations`, records each clip's path, duration, and segment count. Returns dict matching clip_manifest.json schema.
- **VALIDATE**: `uv run python -c "from rapmap.edit.manifest import build_manifest; print('OK')"`

### 20. UPDATE `src/rapmap/cli.py` — wire `plan` command

- **IMPLEMENT**: Replace `NotImplementedError` in `plan()` with:
  1. Load anchor_map.json, canonical_syllables.json, human_alignment.json, human audio.
  2. Load config.
  3. Call `group_syllables()` with the selected `--grouping` mode.
  4. Write `edit/clip_groups.json`.
  5. Call `create_edit_plan()`.
  6. Write `edit/edit_plan.json`.
  7. Print summary: clip count, syllable count, min/max stretch ratio.
- **GOTCHA**: Only `safe_boundary` mode needs audio data. For other modes, pass `None` for audio_data and human_alignment.
- **VALIDATE**: `uv run rapmap plan --help`

### 21. CREATE `src/rapmap/audio/stretch.py` — Rubber Band subprocess wrapper

- **IMPLEMENT**:
  ```python
  def time_stretch(
      data: np.ndarray,
      sample_rate: int,
      ratio: float,
      preserve_pitch: bool = True,
  ) -> np.ndarray:
  ```
  - If `ratio == 1.0` (within epsilon 1e-6), return data unchanged.
  - Write input to temp WAV file.
  - Run: `subprocess.run(["rubberband", "-t", str(ratio), "--no-threads", input_path, output_path], check=True)`.
  - If `preserve_pitch` is True (default), rubberband preserves pitch by default (no extra flag needed).
  - Read output WAV and return.
  - If `rubberband` binary not found, raise `RuntimeError("rubberband CLI not found. Install: brew install rubberband (macOS) or apt install rubberband-cli (Linux)")`.
- **IMPORTS**: `subprocess`, `tempfile`, `soundfile`, `numpy`
- **GOTCHA**: Use `--no-threads` for deterministic output (single-threaded avoids floating-point ordering differences).
- **GOTCHA**: Rubber Band output length may differ from `int(len(data) * ratio)` by ±1 sample due to internal windowing. The caller must handle this (truncate/pad to exact target).
- **GOTCHA**: Use `$TMPDIR` or `tempfile` module for temp files — never hardcode `/tmp`.
- **VALIDATE**: `uv run python -c "from rapmap.audio.stretch import time_stretch; print('OK')"`

### 22. CREATE `src/rapmap/audio/render.py` — clip rendering + flattened preview

- **IMPLEMENT**: The rendering engine.
  ```python
  def render_clips(
      edit_plan: EditPlan,
      human_audio: np.ndarray,
      sample_rate: int,
      output_dir: Path,
      config: RenderingConfig,
  ) -> dict:
  ```
  Algorithm for each `ClipOperation` in `edit_plan.operations`:
  1. For each segment in the clip:
     a. Extract source audio: `human_audio[seg.source_start:seg.source_end]`.
     b. If `source_duration == target_duration`, no stretch needed.
     c. Otherwise, call `time_stretch(data, sr, seg.stretch_ratio)`.
     d. Truncate or pad result to EXACTLY `seg.target_duration` samples.
  2. Concatenate all segments (NO crossfade between segments within a clip — this guarantees anchor positions).
  3. Write clip WAV to `output_dir / "audio" / "clips" / f"{clip.clip_id}.wav"`.

  **Flattened preview** — assemble all clips into one continuous track:
  1. Create output buffer of length = end of last clip target position.
  2. For each clip, place the rendered clip at its target position.
  3. Apply crossfade in overlap regions between adjacent clips.
  4. Write to `output_dir / "render" / "corrected_human_rap.wav"`.

  **Validation** — verify the hard invariant:
  ```python
  for anchor in anchor_map["anchors"]:
      syl_idx = anchor["syllable_index"]
      guide_anchor = anchor["guide_anchor_sample"]
      # Find which clip contains this syllable
      # Compute rendered anchor position = clip_target_start + sum(preceding segment target durations)
      rendered_anchor = computed_position
      assert rendered_anchor == guide_anchor, \
          f"Anchor error at syllable {syl_idx}: rendered={rendered_anchor}, guide={guide_anchor}"
  ```

  Return render_report dict.
- **IMPORTS**: `rapmap.audio.stretch.time_stretch`, `rapmap.audio.io.write_audio`, `rapmap.edit.crossfade.compute_crossfade`, `numpy`
- **GOTCHA**: The flattened preview must cover the full guide duration, not just up to the last clip end. Pad with silence.
- **GOTCHA**: Truncate/pad each stretched segment to EXACT target duration. This is how we get zero-sample error.
- **GOTCHA**: `config.output_individual_clips` controls whether individual clip WAVs are written. Always write the flattened preview.
- **VALIDATE**: `uv run python -c "from rapmap.audio.render import render_clips; print('OK')"`

### 23. UPDATE `src/rapmap/cli.py` — wire `render` command

- **IMPLEMENT**: Replace `NotImplementedError` in `render()` with:
  1. Load edit_plan.json, anchor_map.json, project.json.
  2. Read human audio.
  3. Load config.
  4. Call `render_clips()`.
  5. Write render_report.json and clip_manifest.json.
  6. Print summary: clips rendered, validation pass/fail, extreme stretch ratios.
- **VALIDATE**: `uv run rapmap render --help`

### 24. CREATE `src/rapmap/audacity/labels.py` — TSV label track generation

- **IMPLEMENT**:
  ```python
  def generate_label_track(
      entries: list[dict],
      sample_rate: int,
  ) -> str:
      """Generate Audacity label TSV from list of {start_sample, end_sample, text}."""
      lines = []
      for e in entries:
          start_sec = e["start_sample"] / sample_rate
          end_sec = e["end_sample"] / sample_rate
          lines.append(f"{start_sec:.6f}\t{end_sec:.6f}\t{e['text']}")
      return "\n".join(lines) + "\n"

  def write_label_track(path: Path, entries: list[dict], sample_rate: int) -> None:
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(generate_label_track(entries, sample_rate))
  ```

  **Standard label tracks to generate** (5 tracks):
  ```python
  def generate_all_labels(
      canonical_syllables: dict,
      guide_alignment: AlignmentResult | None,
      human_alignment: AlignmentResult | None,
      anchor_map: dict | None,
      clip_groups: dict | None,
      sample_rate: int,
      output_dir: Path,
  ) -> list[Path]:
  ```
  Tracks:
  1. `labels_canonical.txt` — one label per canonical syllable (text = syllable_text, dummy timing from word index if no alignment)
  2. `labels_guide.txt` — guide alignment syllable timestamps (if available)
  3. `labels_human.txt` — human alignment syllable timestamps (if available)
  4. `labels_anchors.txt` — anchor map entries showing human→guide mapping
  5. `labels_clips.txt` — clip group boundaries (if available)
- **GOTCHA**: This is the ONLY place float seconds are used. All internal data is integer samples.
- **VALIDATE**: `uv run python -c "from rapmap.audacity.labels import generate_label_track; print('OK')"`

### 25. CREATE `src/rapmap/audacity/script_pipe.py` — mod-script-pipe controller

- **IMPLEMENT**:
  ```python
  class AudacityPipe:
      def __init__(self):
          """Connect to Audacity's mod-script-pipe."""
          # Try platform-specific pipe paths
          # macOS/Linux: /tmp/audacity_script_pipe.to and .from
          self._to_pipe = None
          self._from_pipe = None

      def connect(self) -> bool:
          """Attempt to connect. Returns False if Audacity not running or pipe unavailable."""

      def send(self, command: str) -> str:
          """Send command, read response. Blocks until 'BatchCommand finished'."""

      def import_audio(self, path: Path) -> bool: ...
      def new_label_track(self) -> bool: ...
      def set_track_name(self, track: int, name: str) -> bool: ...
      def import_labels(self, path: Path) -> bool: ...
      def save_project(self, path: Path) -> bool: ...
      def close(self) -> None: ...
  ```
- **GOTCHA**: mod-script-pipe may not be enabled. `connect()` should timeout after 2 seconds and return False. Never block indefinitely.
- **GOTCHA**: Pipe paths may include PID in newer Audacity versions. Try both fixed and PID-based paths.
- **GOTCHA**: This is an OPTIONAL integration. The pipeline must work without Audacity running — label files are the primary output.
- **VALIDATE**: `uv run python -c "from rapmap.audacity.script_pipe import AudacityPipe; print('OK')"`

### 26. CREATE `src/rapmap/audacity/import_project.py` — session builder

- **IMPLEMENT**:
  ```python
  def build_audacity_session(
      project_dir: Path,
      config: AudacityConfig,
  ) -> dict:
  ```
  Steps:
  1. Generate all label tracks via `generate_all_labels()`.
  2. If `config.integration == "mod_script_pipe"`:
     a. Try connecting to Audacity via `AudacityPipe`.
     b. If connected: import backing track, human vocal, corrected vocal, guide vocal. Create label tracks. Set track names.
     c. If not connected: print message suggesting manual import.
  3. Always: write label files regardless of pipe status.
  4. Return summary dict: `{"labels_written": [...], "pipe_connected": bool, "tracks_imported": int}`.
- **VALIDATE**: `uv run python -c "from rapmap.audacity.import_project import build_audacity_session; print('OK')"`

### 27. UPDATE `src/rapmap/cli.py` — wire `audacity` command

- **IMPLEMENT**: Replace `NotImplementedError` in `audacity_session()` with:
  1. Call `build_audacity_session()`.
  2. Print summary: labels written, whether pipe was connected.
  3. If `--open` flag and pipe connected: done. If `--open` and no pipe: print instructions for manual import.
- **VALIDATE**: `uv run rapmap audacity --help`

### 28. UPDATE `src/rapmap/cli.py` — wire `run` command (full pipeline)

- **IMPLEMENT**: Replace `NotImplementedError` in `run()` with:
  1. Add `--guide` option (required for now — manual guide path).
  2. Chain all phases:
     ```python
     # Phase 0
     metadata = normalize_project(backing, human, lyrics, out, config.project)
     # Phase 1
     guide_result = load_manual_guide(guide, out, config.project)
     # Phase 2
     lyrics_text = (out / "lyrics" / "lyrics.raw.txt").read_text()
     lyrics_normalized = parse_lyrics(lyrics_text)
     # ... write normalized, build canonical syllables
     # Phase 3
     # ... align guide and human
     # Phase 4
     # ... build anchor map
     # Phase 5-6
     # ... group and plan
     # Phase 7
     # ... render
     # Phase 8
     # ... audacity labels
     ```
  3. Print overall summary.
- **GOTCHA**: Add `--guide` click option: `@click.option("--guide", type=click.Path(exists=True, path_type=Path), required=True)`.
- **VALIDATE**: `uv run rapmap run --help`

### 29. CREATE `tests/test_textgrid.py` — TextGrid parser tests

- **IMPLEMENT**: Test with embedded fixture TextGrid content.
  ```python
  FIXTURE_TEXTGRID = '''File type = "ooTextFile"
  Object class = "TextGrid"
  ...
  '''

  def test_parse_two_tiers():
      # Write fixture to tmp_path, parse, verify two tiers
  def test_parse_word_intervals():
      # Verify word texts and timestamps
  def test_parse_phone_intervals():
      # Verify phone texts and timestamps
  def test_parse_skips_silence():
      # Empty-text intervals are included but empty
  ```
- **VALIDATE**: `uv run pytest tests/test_textgrid.py -v`

### 30. CREATE `tests/test_guide.py` — guide import tests

- **IMPLEMENT**:
  ```python
  def test_load_manual_guide(tmp_path):
      # Create synthetic guide WAV, load it, verify output file exists
  def test_guide_resampled(tmp_path):
      # Create 44100Hz guide, verify resampled to 48000
  def test_guide_result_metadata(tmp_path):
      # Verify GuideVocalResult fields
  ```
- **VALIDATE**: `uv run pytest tests/test_guide.py -v`

### 31. CREATE `tests/test_anchor_mapping.py` — anchor map tests

- **IMPLEMENT**: Use synthetic alignment fixtures (no MFA needed).
  ```python
  def _make_alignment(syllables_data, sample_rate=48000, role="guide"):
      """Build a minimal AlignmentResult from a list of (start, end, word) tuples."""
      ...

  def test_onset_anchor_extraction():
      # Verify onset = start_sample
  def test_vowel_nucleus_anchor():
      # Verify vowel midpoint
  def test_anchor_map_construction():
      # Build map from two alignments, verify delta computation
  def test_anchor_map_monotonic():
      # Guide anchors must be monotonically increasing
  def test_anchor_map_non_monotonic_fails():
      # Non-monotonic guide anchors should raise
  def test_syllable_count_mismatch_fails():
      # Different syllable counts between guide and human should raise
  ```
- **VALIDATE**: `uv run pytest tests/test_anchor_mapping.py -v`

### 32. CREATE `tests/test_safe_boundary_grouping.py` — grouping tests

- **IMPLEMENT**: Use synthetic data fixtures.
  ```python
  def test_strict_syllable_mode():
      # One clip per syllable
  def test_word_mode():
      # One clip per word
  def test_phrase_mode():
      # One clip per line
  def test_bar_mode():
      # One clip per bar
  def test_safe_boundary_respects_max_syllables():
      # No clip exceeds max_syllables_per_clip
  def test_safe_boundary_respects_duration_limits():
      # Clips within min/max duration
  def test_all_syllables_assigned():
      # Every syllable appears in exactly one clip
  def test_clip_ids_unique():
      # All clip_id values are distinct
  ```
- **VALIDATE**: `uv run pytest tests/test_safe_boundary_grouping.py -v`

### 33. CREATE `tests/test_edit_plan_exactness.py` — zero-sample-error guarantee

- **IMPLEMENT**: The most critical test file.
  ```python
  def test_segment_boundaries_at_anchors():
      # Segment boundaries align exactly with anchor positions
  def test_zero_sample_anchor_error():
      # For every syllable, rendered position equals guide anchor
      # This is the HARD INVARIANT
  def test_stretch_ratios_computed_correctly():
      # ratio = target_duration / source_duration for each segment
  def test_stretch_ratios_within_bounds():
      # All ratios in [min_stretch_ratio, max_stretch_ratio]
  def test_single_syllable_clip():
      # Clip with one syllable has correct segment layout
  def test_multi_syllable_clip():
      # Clip with multiple syllables splits at anchor boundaries
  def test_piecewise_stretch_preserves_anchors():
      # Full render simulation: segments concatenated, verify anchor positions
  ```
- **GOTCHA**: These tests exercise the math, not actual audio rendering. Use integer arithmetic to verify positions.
- **VALIDATE**: `uv run pytest tests/test_edit_plan_exactness.py -v`

### 34. CREATE `tests/test_render_clip_lengths.py` — rendering tests

- **IMPLEMENT**: Test clip rendering logic without Rubber Band (mock `time_stretch`).
  ```python
  def _mock_stretch(data, sr, ratio):
      """Simple resampling mock — resizes array to target length."""
      target_len = int(round(len(data) * ratio))
      return np.interp(
          np.linspace(0, len(data) - 1, target_len),
          np.arange(len(data)),
          data,
      ).astype(np.float32)

  def test_clip_exact_duration(monkeypatch):
      # Rendered clip has exact target duration
  def test_flattened_preview_length(monkeypatch):
      # Flattened preview covers full guide duration
  def test_segment_truncation(monkeypatch):
      # Stretched segments truncated/padded to exact target
  def test_crossfade_between_clips(monkeypatch):
      # Adjacent clips crossfaded in flattened preview
  ```
- **GOTCHA**: Use `monkeypatch` to replace `time_stretch` with `_mock_stretch` so tests run without rubberband installed.
- **VALIDATE**: `uv run pytest tests/test_render_clip_lengths.py -v`

### 35. CREATE `tests/test_audacity_labels.py` — label format tests

- **IMPLEMENT**:
  ```python
  def test_label_tsv_format():
      # Verify tab-delimited, 3 columns
  def test_label_seconds_precision():
      # Verify 6 decimal places
  def test_sample_to_seconds_conversion():
      # 48000 samples at 48kHz = 1.000000 seconds
  def test_generate_all_labels(tmp_path):
      # Verify all 5 label files created
  def test_label_content_matches_alignment():
      # Label start/end match alignment timestamps
  ```
- **VALIDATE**: `uv run pytest tests/test_audacity_labels.py -v`

### 36. Run full test suite and lint

- **VALIDATE**: `uv run pytest tests/ -v && uv run ruff check src/ tests/`
- All existing 48 tests must still pass (no regressions).
- All new tests must pass.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

### Level 2: Import Smoke Tests

```bash
uv run python -c "from rapmap.guide.base import GuideVocalResult; print('guide.base OK')"
uv run python -c "from rapmap.guide.manual import load_manual_guide; print('guide.manual OK')"
uv run python -c "from rapmap.align.textgrid import parse_textgrid; print('align.textgrid OK')"
uv run python -c "from rapmap.align.base import AlignmentResult; print('align.base OK')"
uv run python -c "from rapmap.align.mfa import align_with_mfa; print('align.mfa OK')"
uv run python -c "from rapmap.align.derive_syllables import derive_syllable_timestamps; print('align.derive OK')"
uv run python -c "from rapmap.align.validate import validate_alignment; print('align.validate OK')"
uv run python -c "from rapmap.timing.anchors import extract_anchor; print('timing.anchors OK')"
uv run python -c "from rapmap.timing.anchor_map import build_anchor_map; print('timing.anchor_map OK')"
uv run python -c "from rapmap.timing.confidence import compute_syllable_confidence; print('timing.confidence OK')"
uv run python -c "from rapmap.edit.operations import EditPlan; print('edit.operations OK')"
uv run python -c "from rapmap.edit.safe_boundaries import score_boundaries; print('edit.safe_boundaries OK')"
uv run python -c "from rapmap.edit.grouping import group_syllables; print('edit.grouping OK')"
uv run python -c "from rapmap.edit.crossfade import compute_crossfade; print('edit.crossfade OK')"
uv run python -c "from rapmap.edit.planner import create_edit_plan; print('edit.planner OK')"
uv run python -c "from rapmap.edit.manifest import build_manifest; print('edit.manifest OK')"
uv run python -c "from rapmap.audio.stretch import time_stretch; print('audio.stretch OK')"
uv run python -c "from rapmap.audio.render import render_clips; print('audio.render OK')"
uv run python -c "from rapmap.audacity.labels import generate_label_track; print('audacity.labels OK')"
uv run python -c "from rapmap.audacity.script_pipe import AudacityPipe; print('audacity.pipe OK')"
uv run python -c "from rapmap.audacity.import_project import build_audacity_session; print('audacity.import OK')"
```

### Level 3: Full Test Suite

```bash
uv run pytest tests/ -v
```

### Level 4: CLI Smoke Tests

```bash
uv run rapmap --help
uv run rapmap set-guide --help
uv run rapmap align --help
uv run rapmap anchors --help
uv run rapmap plan --help
uv run rapmap render --help
uv run rapmap audacity --help
uv run rapmap run --help
```

### Level 5: End-to-End (requires MFA + Rubber Band)

```bash
# Generate synthetic test inputs
uv run python -c "
import numpy as np
import soundfile as sf
sr = 48000
sf.write('inputs/test_backing.wav', np.random.randn(sr * 5).astype(np.float32), sr, subtype='FLOAT')
sf.write('inputs/test_vocal.wav', np.random.randn(sr * 3).astype(np.float32), sr, subtype='FLOAT')
sf.write('inputs/test_guide.wav', np.random.randn(sr * 3).astype(np.float32), sr, subtype='FLOAT')
with open('inputs/test_lyrics.txt', 'w') as f:
    f.write('I got money on my mind')
print('Test inputs created')
"

# Run full pipeline
uv run rapmap run \
  --backing inputs/test_backing.wav \
  --human inputs/test_vocal.wav \
  --guide inputs/test_guide.wav \
  --lyrics inputs/test_lyrics.txt \
  --out /tmp/rapmap_e2e

# Verify outputs
ls -la /tmp/rapmap_e2e/alignment/
ls -la /tmp/rapmap_e2e/timing/
ls -la /tmp/rapmap_e2e/edit/
ls -la /tmp/rapmap_e2e/render/
ls -la /tmp/rapmap_e2e/labels/
```

---

## ACCEPTANCE CRITERIA

- [ ] `uv run rapmap set-guide` imports and normalizes a guide vocal
- [ ] `uv run rapmap align` produces alignment JSON for guide and human (when MFA is installed)
- [ ] `uv run rapmap anchors` builds anchor map with monotonic guide anchors
- [ ] `uv run rapmap plan` produces clip_groups.json and edit_plan.json for all 6 grouping modes
- [ ] Edit plan segments split at anchor boundaries — zero-sample anchor error by construction
- [ ] All stretch ratios computed correctly: `target_duration / source_duration`
- [ ] `uv run rapmap render` produces individual clips and flattened preview (when rubberband is installed)
- [ ] Anchor validation passes: `rendered_anchor == guide_anchor` for every syllable
- [ ] `uv run rapmap audacity` generates 5 TSV label files
- [ ] `uv run rapmap run` chains all phases end-to-end
- [ ] All new tests pass with synthetic fixtures (no MFA/Rubber Band required)
- [ ] All 48 existing tests still pass (no regressions)
- [ ] `uv run ruff check src/ tests/` passes
- [ ] Every assertion includes actual values in error messages
- [ ] Pipeline fails loudly on: syllable count mismatch, non-monotonic anchors, anchor error > 0

---

## COMPLETION CHECKLIST

- [ ] All 36 tasks completed in order
- [ ] Each task validation passed immediately
- [ ] All validation commands (levels 1-4) executed successfully
- [ ] Level 5 (end-to-end) documented but may require MFA/Rubber Band
- [ ] Acceptance criteria all met
- [ ] Ready for `/commit`

---

## NOTES

### System Dependencies (not pip-installable)

- **Montreal Forced Aligner**: `conda install -c conda-forge montreal-forced-aligner`. Then: `mfa model download acoustic english_us_arpa`. Required for Phase 3 but tests work without it via fixtures.
- **Rubber Band**: `brew install rubberband` (macOS) or `apt install rubberband-cli` (Linux). Required for Phase 7 but tests mock the stretch function.

### Design Decisions

1. **No praatio dependency** — TextGrid parser is ~60 lines and avoids adding a dependency for a simple file format.
2. **No pyrubberband dependency** — Direct subprocess call to `rubberband` is cleaner and avoids a dependency that's just a subprocess wrapper anyway.
3. **No crossfade between segments within a clip** — This is how we guarantee zero-sample anchor error. Segments are concatenated at exact anchor positions. Crossfades only happen between clips in the flattened preview.
4. **Dynamic programming for safe_boundary** — Greedy grouping can miss globally optimal split points. DP finds the best grouping subject to all constraints.
5. **Custom MFA dictionary** — We generate a dictionary from the same pronunciation lookups used in Phase 2, ensuring MFA uses matching phone sequences.
6. **WhisperX stub only** — Not implementing the full WhisperX fallback in this round. The interface is defined for future work.
7. **AI guide generation stubs** — Only manual guide implemented. `songgeneration.py`, `yue.py`, `acestep.py` are stretch goals.

### Piecewise Stretch — The Zero-Sample Guarantee

The hard invariant `rendered_anchor[i] == guide_anchor[i]` is achieved by construction:

1. Each clip is split into segments at anchor sample positions.
2. Each segment is independently time-stretched.
3. Stretched output is truncated/padded to EXACT target duration (integer samples).
4. Segments are concatenated with NO internal crossfade.
5. Anchor i is at position = clip_target_start + sum(target_durations of segments before anchor_i).
6. By construction, this equals the guide anchor position.

The only potential audio artifact is at segment boundaries (no crossfade). In practice, these occur at syllable onsets — natural acoustic transition points — so artifacts are minimal.

### `_resample` Import

Phase 1 (guide/manual.py) needs the `_resample` helper from `audio/normalize.py`. Two options:
- Import `_resample` directly (it's a private function but same package — acceptable)
- Move `_resample` to `audio/io.py` as a public function `resample()`

Recommend: move to `audio/io.py` as `resample()` to make it a proper public utility. Update `audio/normalize.py` to import from `audio/io.py`.

### Suggested Execution Order

This plan can be implemented in 2-3 sessions:
1. **Session 1**: Tasks 1-13 (Phases 1, 3, 4) — guide import + alignment + anchor mapping
2. **Session 2**: Tasks 14-23 (Phases 5-7) — grouping + planning + rendering
3. **Session 3**: Tasks 24-36 (Phase 8 + tests + full pipeline wiring)

Or in one session if tackling everything at once.
