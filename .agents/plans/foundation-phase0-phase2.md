# Task: Foundation — Phase 0 (Normalize) + Phase 2 (Syllabify)

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files etc.

## Task Description

Implement the two foundational phases of the RapMap pipeline:

- **Phase 0 (Normalize)**: Takes raw user inputs (`backing_track.wav`, `human_rap.wav`, `lyrics.txt`) and creates a normalized project workdir with resampled audio (48kHz, 32-bit float WAV, mono for vocals) and parsed lyrics.

- **Phase 2 (Syllabify)**: Takes parsed lyrics and produces a canonical syllable sequence. Uses CMUdict for pronunciation lookup, a syllabification algorithm to split phones into syllables, g2p_en as fallback for unknown words, and supports pronunciation overrides for rap slang.

These two phases are the foundation everything else depends on. The alignment phase (Phase 3) needs the normalized audio and canonical syllables. The entire pipeline chains from here.

## Task Metadata

**Task Type**: Code Change
**Estimated Complexity**: Medium
**Primary Systems Affected**: `src/rapmap/audio/`, `src/rapmap/lyrics/`, `src/rapmap/cli.py`
**Dependencies**: soundfile, scipy, numpy, nltk (cmudict), g2p_en (new dep)
**Supports Claim/Hypothesis**: C4 (CMUdict + G2P handles rap lyrics), C7 (determinism)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/rapmap/cli.py` (lines 1–114) — CLI commands `init` and `syllabify` need implementation wired in
- `src/rapmap/config.py` (lines 1–139) — Full config hierarchy; relevant sections: `ProjectConfig`, `SyllableDetectionConfig`
- `configs/default.yaml` — Default config values
- `CLAUDE.md` (full file) — Coding conventions, especially:
  - Integer sample indices everywhere (never float seconds internally)
  - Fail-loud error handling
  - Liberal assertions with actual values in messages
  - snake_case naming
- `pyproject.toml` — Current dependencies; need to add `g2p_en`

### Relevant Specification (from master spec passed to /create-brief)

**Phase 0 outputs:**
```
workdir/
├── audio/
│   ├── backing.wav          # Resampled to 48kHz, preserved channels
│   └── human_rap.wav        # Resampled to 48kHz, mono for analysis
├── lyrics/
│   └── lyrics.raw.txt       # Copy of original lyrics
└── project.json             # Project metadata
```

**Phase 2 — Lyric normalized structure (from spec Section 9.4):**
```json
{
  "bars": [
    {
      "bar_index": 0,
      "lines": [
        {
          "line_index": 0,
          "text": "I got money on my mind",
          "words": [
            { "word_index": 0, "text": "I", "normalized": "i" },
            { "word_index": 1, "text": "got", "normalized": "got" },
            { "word_index": 2, "text": "money", "normalized": "money" }
          ]
        }
      ]
    }
  ]
}
```

**Phase 2 — Canonical syllable schema (from spec Section 9.7):**
```json
{
  "sample_rate": 48000,
  "syllables": [
    {
      "syllable_index": 0,
      "bar_index": 0,
      "line_index": 0,
      "word_index": 0,
      "word_text": "I",
      "syllable_text": "I",
      "phones": ["AY1"],
      "is_word_initial": true,
      "is_word_final": true,
      "is_line_final": false
    },
    {
      "syllable_index": 2,
      "bar_index": 0,
      "line_index": 0,
      "word_index": 2,
      "word_text": "money",
      "syllable_text": "mon",
      "phones": ["M", "AH1", "N"],
      "is_word_initial": true,
      "is_word_final": false,
      "is_line_final": false
    }
  ]
}
```

**Phase 2 — Pronunciation override format (from spec Section 9.5):**
```yaml
tryna:
  phones: ["T", "R", "AY1", "N", "AH0"]
  syllables:
    - text: "try"
      phones: ["T", "R", "AY1"]
    - text: "na"
      phones: ["N", "AH0"]
```

### New Files to Create

```
src/rapmap/audio/io.py           # Audio read/write/info helpers
src/rapmap/audio/normalize.py    # Phase 0 audio normalization
src/rapmap/lyrics/parser.py      # Lyrics text → bars/lines/words JSON
src/rapmap/lyrics/normalize.py   # Word normalization (lowering, punctuation)
src/rapmap/lyrics/pronunciations.py  # CMUdict + g2p_en lookup
src/rapmap/lyrics/syllabify.py   # Phone list → syllable split
src/rapmap/lyrics/overrides.py   # Load pronunciation override YAML
tests/test_lyrics_parser.py      # Lyrics parsing tests
tests/test_syllabification.py    # Syllabification tests
tests/test_audio_normalize.py    # Audio normalization tests
configs/pronunciation_overrides.yaml  # Default rap slang overrides
```

### Patterns to Follow

**Config access pattern:**
```python
from rapmap.config import load_config, RapMapConfig

config = load_config(project_dir / "project.json")
sr = config.project.sample_rate  # 48000
```

**CLI pattern (from existing cli.py):**
```python
@main.command()
@click.option("--project", type=click.Path(exists=True, path_type=Path), required=True)
def syllabify(project: Path, out: Path | None):
    click.echo("Detecting syllables")
    # Implementation goes here
```

**Assertion pattern (from CLAUDE.md):**
```python
assert isinstance(start_sample, int) and start_sample >= 0
assert len(syllables) > 0, f"No syllables detected for lyrics with {len(words)} words"
```

**Fail-loud pattern:**
```python
if word_lower not in cmudict_entries and not g2p_available:
    raise ValueError(f"Word '{word}' not in CMUdict and no G2P fallback available")
```

### Relevant Documentation — READ BEFORE IMPLEMENTING

- soundfile: `sf.read(path, dtype='float32')` returns `(ndarray, sample_rate)`. `sf.info(path)` for metadata without loading. `sf.write(path, data, samplerate, subtype='FLOAT')` for 32-bit float WAV.
- scipy.signal.resample_poly: `resample_poly(data, up, down)` with `up=target_sr//gcd, down=source_sr//gcd`. Better than `resample()` for audio (FIR filter, no periodicity assumption).
- NLTK CMUdict: `nltk.corpus.cmudict.dict()` returns `{str: list[list[str]]}`. Vowel phones have stress digits (0/1/2) as last char. Syllable count = vowel count.
- g2p_en: `G2p()(word)` returns list of ARPAbet phones with spaces between words. Filter out `' '` and punctuation. It checks CMUdict internally before neural fallback.

### Key Library API Details

**CMUdict lookup:**
```python
from nltk.corpus import cmudict
d = cmudict.dict()
d["money"]  # [['M', 'AH1', 'N', 'IY0']]
# Multiple pronunciations possible; use first by default
```

**Vowel detection:**
```python
def is_vowel(phone: str) -> bool:
    return len(phone) > 0 and phone[-1] in ('0', '1', '2')
```

**Syllabification algorithm (onset maximization):**
```python
def syllabify_phones(phones: list[str]) -> list[list[str]]:
    """Split ARPAbet phones into syllables using onset maximization."""
    syllables: list[list[str]] = []
    current: list[str] = []
    
    for i, phone in enumerate(phones):
        if is_vowel(phone):
            current.append(phone)
        else:
            if current and any(is_vowel(p) for p in current):
                remaining = phones[i:]
                if any(is_vowel(p) for p in remaining):
                    syllables.append(current)
                    current = [phone]
                else:
                    current.append(phone)
            else:
                current.append(phone)
    if current:
        syllables.append(current)
    return syllables
```

**Audio resampling:**
```python
from scipy.signal import resample_poly
from math import gcd

def resample_audio(data: np.ndarray, sr_orig: int, sr_target: int) -> np.ndarray:
    if sr_orig == sr_target:
        return data
    g = gcd(sr_target, sr_orig)
    return resample_poly(data, sr_target // g, sr_orig // g).astype(np.float32)
```

**g2p_en usage:**
```python
from g2p_en import G2p
g2p = G2p()
phones_raw = g2p("tryna")  # Returns list of phones + spaces + punctuation
phones = [p for p in phones_raw if p.strip() and p not in '.,!?;:']
```

---

## IMPLEMENTATION PLAN

### Phase 1: Dependencies and Audio I/O

Add g2p_en to pyproject.toml. Create audio I/O utilities. Create audio normalization (Phase 0 core).

### Phase 2: Lyrics Pipeline

Create lyrics parser (text → bars/lines/words JSON). Create word normalizer. Create pronunciation lookup (CMUdict + g2p_en). Create syllabification. Create pronunciation overrides loader. Create default rap slang overrides.

### Phase 3: Wire CLI Commands

Replace `NotImplementedError` in `init` and `syllabify` CLI commands with actual implementations.

### Phase 4: Tests and Validation

Write tests for lyrics parsing, syllabification, audio normalization. Run full test suite.

---

## STEP-BY-STEP TASKS

### 1. UPDATE `pyproject.toml` — add g2p_en dependency

- **IMPLEMENT**: Add `"g2p_en>=2.1"` to the core `dependencies` list.
- **VALIDATE**: `uv sync && uv run python -c "from g2p_en import G2p; print('OK')"`

### 2. CREATE `src/rapmap/audio/io.py` — audio I/O helpers

- **IMPLEMENT**: Three functions:
  - `read_audio(path: Path, mono: bool = False) -> tuple[np.ndarray, int]` — reads WAV/MP3/etc as float32 numpy array, optionally converts stereo to mono by averaging channels. Returns `(data, sample_rate)`.
  - `write_audio(path: Path, data: np.ndarray, sample_rate: int) -> None` — writes 32-bit float WAV. Asserts data is float32 and sample_rate > 0. Creates parent directories.
  - `audio_info(path: Path) -> dict` — returns dict with keys: `sample_rate`, `channels`, `frames`, `duration_samples`, `duration_seconds`. Uses `sf.info()`.
- **IMPORTS**: `soundfile`, `numpy`, `pathlib.Path`
- **GOTCHA**: `sf.read` returns 1D for mono, 2D for stereo. Handle both. When converting stereo to mono, use `data.mean(axis=1)`.
- **GOTCHA**: Always pass `dtype='float32'` to `sf.read` to ensure consistent output type.
- **VALIDATE**: `uv run python -c "from rapmap.audio.io import read_audio, write_audio, audio_info; print('OK')"`

### 3. CREATE `src/rapmap/audio/normalize.py` — Phase 0 audio normalization

- **IMPLEMENT**: One function:
  - `normalize_project(backing_path: Path, human_path: Path, lyrics_path: Path, output_dir: Path, config: ProjectConfig) -> dict` — does all Phase 0 work:
    1. Create output directory structure: `output_dir/{audio, lyrics}`
    2. Read backing track, resample to `config.sample_rate`, write as `audio/backing.wav` (preserve channels)
    3. Read human vocal, resample to `config.sample_rate`, convert to mono if `config.vocal_analysis_mono`, write as `audio/human_rap.wav`
    4. Copy lyrics to `lyrics/lyrics.raw.txt`
    5. Write `project.json` with: sample_rate, backing duration (samples), human duration (samples), created timestamp, original file paths
    6. Return the project metadata dict
- **IMPORTS**: `soundfile`, `numpy`, `scipy.signal.resample_poly`, `math.gcd`, `json`, `shutil`, `pathlib.Path`, `datetime`
- **PATTERN**: Use `resample_poly` for resampling (not `resample`). Compute `up = target // gcd(target, source)`, `down = source // gcd(target, source)`.
- **GOTCHA**: `resample_poly` output may not be exactly float32 — cast back after resampling.
- **GOTCHA**: When resampling, compute expected output length as `int(len(data) * target_sr / source_sr)` for the project.json metadata, but use the actual `resample_poly` output length for the written file.
- **VALIDATE**: `uv run python -c "from rapmap.audio.normalize import normalize_project; print('OK')"`

### 4. CREATE `src/rapmap/lyrics/parser.py` — lyrics text parser

- **IMPLEMENT**: One function:
  - `parse_lyrics(lyrics_text: str) -> dict` — parses raw lyrics text into the normalized JSON structure:
    1. Split text by blank lines (one or more `\n\n`) to get bars. If no blank lines, each non-empty line is a bar.
    2. Within each bar, each non-empty line is a line.
    3. Within each line, split by whitespace to get words.
    4. For each word, store: `word_index` (within line), `text` (original), `normalized` (lowered, stripped of punctuation).
    5. Return the full structure with `bar_index`, `line_index`, `word_index`.
    6. Assert at least one bar, one line, one word.
- **IMPORTS**: `re`
- **GOTCHA**: Preserve original text for display; normalize for lookup. Normalization = lowercase + strip leading/trailing punctuation (`'",!?.;:-` etc.). Do NOT strip apostrophes mid-word (e.g., "don't" stays "don't").
- **GOTCHA**: Skip truly empty lines (whitespace only). Bars are separated by blank lines (2+ consecutive newlines).
- **VALIDATE**: `uv run python -c "from rapmap.lyrics.parser import parse_lyrics; r = parse_lyrics('I got money\non my mind'); print(len(r['bars']), 'bars')"`

### 5. CREATE `src/rapmap/lyrics/normalize.py` — word normalization

- **IMPLEMENT**: One function:
  - `normalize_word(word: str) -> str` — lowercase, strip leading/trailing punctuation, preserve internal apostrophes and hyphens.
- **IMPORTS**: `re`
- **VALIDATE**: Inline in test.

### 6. CREATE `src/rapmap/lyrics/pronunciations.py` — pronunciation lookup

- **IMPLEMENT**:
  - Module-level: lazy-load CMUdict and g2p_en on first use.
  - `_ensure_cmudict() -> dict[str, list[list[str]]]` — downloads nltk cmudict data if needed, returns dict.
  - `_ensure_g2p() -> G2p` — creates G2p instance (lazy singleton).
  - `lookup_pronunciation(word: str, overrides: dict | None = None) -> tuple[list[str], str]` — returns `(phones, source)` where source is `"override"`, `"cmudict"`, or `"g2p"`.
    1. Check overrides dict first (key = lowered word).
    2. Check CMUdict (use first pronunciation variant).
    3. Fall back to g2p_en.
    4. If all fail, raise ValueError.
    5. Assert returned phones is non-empty list of strings.
  - `lookup_all_words(words: list[str], overrides: dict | None = None) -> list[dict]` — batch lookup returning list of `{"word": str, "phones": list[str], "source": str}`.
- **IMPORTS**: `nltk`, `g2p_en.G2p`
- **GOTCHA**: g2p_en output includes `' '` separators and punctuation chars — filter them out: `[p for p in result if p.strip() and p not in '.,!?;:']`.
- **GOTCHA**: CMUdict keys are all lowercase. Always `.lower()` before lookup.
- **GOTCHA**: nltk data download: use `nltk.download('cmudict', quiet=True)` — the `quiet=True` avoids noisy output.
- **VALIDATE**: `uv run python -c "from rapmap.lyrics.pronunciations import lookup_pronunciation; p, s = lookup_pronunciation('money'); print(p, s)"`

### 7. CREATE `src/rapmap/lyrics/syllabify.py` — syllabification

- **IMPLEMENT**:
  - `is_vowel(phone: str) -> bool` — returns True if phone ends in 0, 1, or 2 (stress marker).
  - `syllabify_phones(phones: list[str]) -> list[list[str]]` — splits ARPAbet phone list into syllable groups using onset maximization. Each group is a list of phones forming one syllable.
  - `syllable_text(phones: list[str]) -> str` — produce a readable syllable text from phones. For now, just join with empty string and lowercase: simple heuristic. This is a display-only field.
  - `build_canonical_syllables(lyrics_normalized: dict, overrides: dict | None, config: SyllableDetectionConfig) -> dict` — the main entry point:
    1. Iterate all bars → lines → words from lyrics_normalized.
    2. For each word, look up pronunciation via `pronunciations.lookup_pronunciation`.
    3. Syllabify the phones.
    4. For each syllable, create the canonical syllable entry with: `syllable_index` (global counter), `bar_index`, `line_index`, `word_index`, `word_text`, `syllable_text`, `phones`, `is_word_initial`, `is_word_final`, `is_line_final`.
    5. Return dict with `sample_rate` and `syllables` list.
    6. Assert syllable count > 0. Assert every syllable has at least one vowel phone.
- **IMPORTS**: `rapmap.lyrics.pronunciations`, `rapmap.config.SyllableDetectionConfig`
- **GOTCHA**: `syllable_text` should be derived from the original word text, not from phones. For multi-syllable words, split the word text proportionally. A pragmatic approach: for a word like "money" with syllables [["M","AH1","N"], ["IY0"]], use a simple heuristic — if the override provides text, use it; otherwise derive from the word text by splitting at approximate positions. A simpler approach: just store the phones and use the word text + syllable position for display.
- **GOTCHA**: `is_line_final` should be True only for the last syllable of the last word in a line.
- **VALIDATE**: `uv run python -c "from rapmap.lyrics.syllabify import syllabify_phones, is_vowel; print(syllabify_phones(['M','AH1','N','IY0']))"`

### 8. CREATE `src/rapmap/lyrics/overrides.py` — pronunciation override loader

- **IMPLEMENT**:
  - `load_overrides(path: Path | None) -> dict | None` — loads YAML file if path exists, returns dict keyed by lowered word, or None.
  - Override format per spec:
    ```yaml
    tryna:
      phones: ["T", "R", "AY1", "N", "AH0"]
      syllables:
        - text: "try"
          phones: ["T", "R", "AY1"]
        - text: "na"
          phones: ["N", "AH0"]
    ```
  - If a word has `syllables` key, the override provides pre-syllabified data. If only `phones`, syllabification is still needed.
- **IMPORTS**: `yaml`, `pathlib.Path`
- **VALIDATE**: Inline in test.

### 9. CREATE `configs/pronunciation_overrides.yaml` — default rap slang

- **IMPLEMENT**: Include at least these entries from the spec:
  ```yaml
  tryna:
    phones: ["T", "R", "AY1", "N", "AH0"]
    syllables:
      - text: "try"
        phones: ["T", "R", "AY1"]
      - text: "na"
        phones: ["N", "AH0"]
  finna:
    phones: ["F", "IH1", "N", "AH0"]
    syllables:
      - text: "fin"
        phones: ["F", "IH1"]
      - text: "na"
        phones: ["N", "AH0"]
  ion:
    phones: ["AY1", "OW0", "N"]
    syllables:
      - text: "i"
        phones: ["AY1"]
      - text: "on"
        phones: ["OW0", "N"]
  ```
- Add a few more common rap slang: `gotta`, `wanna`, `gonna`, `lemme`, `boutta`, `aint`.
- **VALIDATE**: `uv run python -c "import yaml; print(yaml.safe_load(open('configs/pronunciation_overrides.yaml')))"`

### 10. UPDATE `src/rapmap/cli.py` — wire `init` command

- **IMPLEMENT**: Replace `NotImplementedError` in `init()` with:
  1. Load config from `configs/default.yaml` (or a `--config` option if added).
  2. Call `normalize_project(backing, human, lyrics, out, config.project)`.
  3. Print summary: sample rate, backing duration, human duration, syllable count (if lyrics were parsed).
- **IMPORTS**: Add `from rapmap.audio.normalize import normalize_project` and `from rapmap.config import load_config`
- **VALIDATE**: Create a test WAV and lyrics, run `uv run rapmap init --backing test.wav --human test.wav --lyrics test.txt --out /tmp/rapmap_test`

### 11. UPDATE `src/rapmap/cli.py` — wire `syllabify` command

- **IMPLEMENT**: Replace `NotImplementedError` in `syllabify()` with:
  1. Load project.json from `project/project.json`.
  2. Read lyrics from `project/lyrics/lyrics.raw.txt`.
  3. Parse lyrics with `parse_lyrics()`.
  4. Write `lyrics.normalized.json` to `project/lyrics/`.
  5. Load pronunciation overrides if present.
  6. Build canonical syllables with `build_canonical_syllables()`.
  7. Write `canonical_syllables.json` to output path (default: `project/lyrics/canonical_syllables.json`).
  8. Print summary: total syllables, CMUdict hits, G2P fallbacks, override hits.
- **IMPORTS**: Add lyrics module imports
- **VALIDATE**: `uv run rapmap syllabify --project /tmp/rapmap_test`

### 12. CREATE `tests/test_lyrics_parser.py`

- **IMPLEMENT** tests:
  - `test_parse_single_bar` — single line of lyrics produces 1 bar, 1 line, correct words
  - `test_parse_multi_bar` — blank line separates bars
  - `test_parse_word_normalization` — punctuation stripped, lowercase, apostrophes preserved
  - `test_parse_empty_lyrics_fails` — empty string raises or produces empty result
  - `test_parse_whitespace_handling` — extra whitespace ignored
- **VALIDATE**: `uv run pytest tests/test_lyrics_parser.py -v`

### 13. CREATE `tests/test_syllabification.py`

- **IMPLEMENT** tests:
  - `test_is_vowel` — "AH1" is vowel, "M" is not, "IY0" is vowel
  - `test_syllabify_monosyllable` — "got" → 1 syllable
  - `test_syllabify_two_syllables` — "money" → 2 syllables ["M","AH1","N"] + ["IY0"]
  - `test_syllabify_three_syllables` — "beautiful" → 3 syllables
  - `test_cmudict_lookup` — "money" found in CMUdict
  - `test_g2p_fallback` — made-up word still returns phones
  - `test_override_applied` — override dict takes precedence over CMUdict
  - `test_build_canonical_syllables` — full pipeline from lyrics text to canonical syllables JSON
  - `test_canonical_syllable_indices_contiguous` — syllable_index values are 0, 1, 2, ... with no gaps
  - `test_word_boundary_flags` — is_word_initial and is_word_final are correct
- **VALIDATE**: `uv run pytest tests/test_syllabification.py -v`

### 14. CREATE `tests/test_audio_normalize.py`

- **IMPLEMENT** tests:
  - `test_read_write_roundtrip` — write a float32 WAV, read it back, values match
  - `test_stereo_to_mono` — stereo input read with mono=True produces 1D array
  - `test_audio_info` — info dict has correct keys and types
  - `test_normalize_project` — creates workdir structure with expected files (use synthetic test audio: `np.random.randn(48000).astype(np.float32)` as a 1-second test WAV at 48kHz)
  - `test_resample` — 44100 Hz input resampled to 48000 Hz has correct length
- **GOTCHA**: Use `tmp_path` pytest fixture for all test output.
- **VALIDATE**: `uv run pytest tests/test_audio_normalize.py -v`

### 15. Run full test suite and lint

- **VALIDATE**: `uv run pytest tests/ -v && uv run ruff check src/ tests/`

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

### Level 2: Import Smoke Tests

```bash
uv run python -c "from rapmap.audio.io import read_audio, write_audio, audio_info; print('audio.io OK')"
uv run python -c "from rapmap.audio.normalize import normalize_project; print('audio.normalize OK')"
uv run python -c "from rapmap.lyrics.parser import parse_lyrics; print('lyrics.parser OK')"
uv run python -c "from rapmap.lyrics.pronunciations import lookup_pronunciation; print('lyrics.pronunciations OK')"
uv run python -c "from rapmap.lyrics.syllabify import build_canonical_syllables, syllabify_phones; print('lyrics.syllabify OK')"
uv run python -c "from rapmap.lyrics.overrides import load_overrides; print('lyrics.overrides OK')"
```

### Level 3: Full Test Suite

```bash
uv run pytest tests/ -v
```

### Level 4: End-to-End Smoke Test

```bash
# Generate synthetic test inputs
uv run python -c "
import numpy as np
import soundfile as sf
sr = 48000
sf.write('inputs/test_backing.wav', np.random.randn(sr * 5).astype(np.float32), sr, subtype='FLOAT')
sf.write('inputs/test_vocal.wav', np.random.randn(sr * 5).astype(np.float32), sr, subtype='FLOAT')
with open('inputs/test_lyrics.txt', 'w') as f:
    f.write('I got money on my mind\nI been running through the night')
print('Test inputs created')
"

# Run Phase 0
uv run rapmap init \
  --backing inputs/test_backing.wav \
  --human inputs/test_vocal.wav \
  --lyrics inputs/test_lyrics.txt \
  --out /tmp/rapmap_smoke

# Verify Phase 0 outputs
ls -la /tmp/rapmap_smoke/audio/ /tmp/rapmap_smoke/lyrics/
cat /tmp/rapmap_smoke/project.json

# Run Phase 2
uv run rapmap syllabify --project /tmp/rapmap_smoke

# Verify Phase 2 outputs
cat /tmp/rapmap_smoke/lyrics/lyrics.normalized.json | python3 -m json.tool | head -30
cat /tmp/rapmap_smoke/lyrics/canonical_syllables.json | python3 -m json.tool | head -30
```

---

## ACCEPTANCE CRITERIA

- [ ] `uv run rapmap init` creates workdir with `audio/backing.wav`, `audio/human_rap.wav`, `lyrics/lyrics.raw.txt`, `project.json`
- [ ] Audio files resampled to 48kHz, vocals mono, 32-bit float WAV
- [ ] `project.json` contains sample_rate, durations in integer samples
- [ ] `uv run rapmap syllabify` produces `lyrics.normalized.json` and `canonical_syllables.json`
- [ ] `lyrics.normalized.json` has correct bar/line/word structure
- [ ] `canonical_syllables.json` has correct syllable schema with contiguous indices
- [ ] CMUdict lookup works for standard English words
- [ ] g2p_en fallback works for unknown words
- [ ] Pronunciation overrides take precedence
- [ ] Syllabification produces correct syllable count (e.g., "money" → 2, "running" → 2, "through" → 1)
- [ ] All assertions include actual values in messages
- [ ] Pipeline fails loudly on empty lyrics, missing files, etc.
- [ ] All tests pass: `uv run pytest tests/ -v`
- [ ] Lint passes: `uv run ruff check src/ tests/`
- [ ] End-to-end smoke test completes successfully

---

## COMPLETION CHECKLIST

- [ ] All 15 tasks completed in order
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully
- [ ] End-to-end smoke test confirms Phase 0 → Phase 2 works
- [ ] Acceptance criteria all met
- [ ] Ready for `/commit`

---

## NOTES

- **g2p_en downloads a model on first use** (~50MB). This is a one-time cost. The `G2p()` constructor triggers it. Consider lazy initialization.
- **NLTK cmudict download**: Use `nltk.download('cmudict', quiet=True)`. Consider calling this in the pronunciation module on first use.
- **Syllable text derivation**: The spec shows `syllable_text` as e.g., "mon" for the first syllable of "money". The simplest approach is to use the override text if available, otherwise generate from the word text by splitting proportionally to phone count per syllable. An acceptable fallback is to just store the word text for mono-syllable words and use a heuristic split for multi-syllable.
- **`_merge_config` limitation**: The current `_merge_config` in config.py only merges top-level sections, not nested dataclasses like `SafeBoundaryConfig`. This is fine for now since we don't need deep config overrides in Phase 0/2, but note it for later.
- **Phase numbering**: The spec calls syllable detection "Phase 2" but it runs before alignment (Phase 3). In the pipeline, Phase 0 → Phase 2 can run without Phase 1 (guide generation), since syllable detection only needs lyrics.
