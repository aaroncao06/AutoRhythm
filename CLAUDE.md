# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RapMap is a rap vocal rhythm correction pipeline. It takes a beat, dry human rap vocal, and lyrics; generates or loads an AI guide rap; extracts syllable-level timing anchors from both vocals via forced alignment; then deterministically renders the human vocal as Audacity-visible clips whose syllable anchors land exactly on the AI guide rhythm. The human voice identity is preserved — AI is only used for guide generation and alignment, never for vocal transformation.

## AI Usage Boundary

**AI is allowed in Phases 0–3** (guide generation, syllable detection, forced alignment).

**AI is NOT allowed in Phases 4–8** (anchor mapping, clip grouping, edit planning, rendering, Audacity integration). These phases must be fully deterministic — cut, stretch, compress, crossfade, and place audio only. No neural models may transform or regenerate the human voice.

## Technology Stack

| Technology | Purpose |
|------------|---------|
| Python 3.11+ | Language |
| uv | Package and project management |
| Montreal Forced Aligner | Phone-level forced alignment (primary) |
| WhisperX | Forced alignment (fallback) |
| CMUdict | Pronunciation dictionary (134k+ words) |
| Rubber Band | Pitch-preserving time-stretch |
| Demucs | Source separation (only if guide is full-mix) |
| soundfile / scipy | Audio I/O |
| Audacity mod-script-pipe | DAW integration via named pipes |
| SongGeneration / YuE / ACE-Step | AI guide vocal generation (model-adapter pattern) |

## Commands

```bash
# Full pipeline
uv run rapmap run --backing inputs/backing.wav --human inputs/human_rap.wav --lyrics inputs/lyrics.txt --out workdir

# Individual phases
uv run rapmap init --backing inputs/backing.wav --human inputs/human_rap.wav --lyrics inputs/lyrics.txt --out workdir
uv run rapmap syllabify --project workdir
uv run rapmap set-guide --project workdir --guide inputs/manual_ai_guide.wav
uv run rapmap align --project workdir --audio workdir/audio/ai_guide_vocal.wav --role guide
uv run rapmap align --project workdir --audio workdir/audio/human_rap.wav --role human
uv run rapmap anchors --project workdir --anchor onset
uv run rapmap plan --project workdir --grouping safe_boundary
uv run rapmap render --project workdir --edit-plan workdir/edit/edit_plan.json
uv run rapmap audacity --project workdir --open

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Tests
uv run pytest tests/
```

## Project Structure

```
src/rapmap/
├── cli.py                 # CLI entry point (click/typer)
├── config.py              # Config loading and defaults
├── audio/                 # Audio I/O, normalization, time-stretch, rendering
│   ├── io.py
│   ├── normalize.py
│   ├── analysis.py
│   ├── stretch.py         # Rubber Band wrapper
│   ├── render.py          # Clip rendering from edit plan
│   └── source_separation.py  # Demucs wrapper (guide fallback)
├── guide/                 # AI guide vocal generation (model-adapter pattern)
│   ├── base.py            # GuideVocalGenerator interface
│   ├── manual.py          # Manual guide fallback
│   ├── songgeneration.py
│   ├── yue.py
│   └── acestep.py
├── lyrics/                # Lyrics parsing, normalization, syllabification
│   ├── parser.py
│   ├── normalize.py
│   ├── pronunciations.py  # CMUdict + G2P fallback
│   ├── syllabify.py
│   └── overrides.py       # Rap slang pronunciation overrides
├── align/                 # Forced alignment
│   ├── base.py            # Aligner interface
│   ├── mfa.py             # Montreal Forced Aligner backend
│   ├── whisperx.py        # WhisperX fallback backend
│   ├── textgrid.py        # TextGrid parsing
│   ├── validate.py        # Alignment validation
│   └── derive_syllables.py  # Phone timestamps → syllable timestamps
├── timing/                # Anchor mapping
│   ├── anchors.py
│   ├── anchor_map.py
│   └── confidence.py
├── edit/                  # Clip grouping, edit planning, rendering
│   ├── safe_boundaries.py # Safe-boundary scoring
│   ├── grouping.py        # All grouping modes
│   ├── planner.py         # Deterministic edit plan generation
│   ├── operations.py      # Edit operation types
│   ├── crossfade.py
│   └── manifest.py        # Clip manifest generation
├── audacity/              # Audacity integration
│   ├── labels.py          # Label track generation (TSV)
│   ├── script_pipe.py     # mod-script-pipe controller
│   ├── import_project.py  # Session builder
│   └── export_mix.py
└── schemas/               # JSON schemas for validation
    ├── lyrics.schema.json
    ├── alignment.schema.json
    ├── anchor_map.schema.json
    ├── edit_plan.schema.json
    └── clip_manifest.schema.json

tests/
├── test_lyrics_parser.py
├── test_syllabification.py
├── test_anchor_mapping.py
├── test_safe_boundary_grouping.py
├── test_edit_plan_exactness.py
├── test_render_clip_lengths.py
└── test_audacity_labels.py

configs/                   # Default and per-project YAML configs
inputs/                    # User-provided inputs (backing, vocal, lyrics)
```

## Pipeline Phases

| Phase | Name | Module | AI Allowed |
|-------|------|--------|-----------|
| 0 | Normalize project assets | `audio/` | No |
| 1 | Generate or load AI guide | `guide/` | Yes |
| 2 | Detect canonical syllables | `lyrics/` | Yes (G2P) |
| 3 | Align vocals to lyrics | `align/` | Yes (MFA) |
| 4 | Build syllable anchor map | `timing/` | No |
| 5 | Group syllables into clips | `edit/` | No |
| 6 | Create deterministic edit plan | `edit/` | No |
| 7 | Render corrected human vocal | `audio/`, `edit/` | No |
| 8 | Build Audacity session | `audacity/` | No |

## Code Patterns

### Timing: Always Use Integer Sample Indices

All internal timing must use integer sample indices, never floating-point seconds. Seconds are only used for Audacity label export.

```python
# CORRECT
{"sample_rate": 48000, "start_sample": 144000, "end_sample": 151200}

# WRONG — never use float seconds internally
{"start_seconds": 3.0, "end_seconds": 3.15}
```

### Audio Format

- Internal: WAV, 48kHz, 32-bit float, mono for vocal analysis
- Never use MP3 for intermediate files (encoder delay, compression artifacts)
- MP3 allowed only as optional final export

### Config Management

- YAML config files in `configs/`
- Default config defined in code (`config.py`)
- Per-project overrides stored in `workdir/project.json`
- All config values should have sensible defaults

### Clip Grouping Modes

Default is `safe_boundary`. All six modes must produce valid results from the same underlying syllable anchor map:

1. `safe_boundary` (default) — split at acoustically safe points
2. `word` — split at word boundaries
3. `syllable_with_handles` — one clip per syllable with pre/post handles and crossfades
4. `strict_syllable` — hard cut per syllable (debug mode)
5. `phrase` — group by line/breath
6. `bar` — group by bar/newline

### Anchor Strategies

Default is `onset` (syllable onset). All strategies:
- `onset` — syllable onset → guide onset (default, best for rap)
- `vowel_nucleus` — vowel center → guide vowel center
- `end` — syllable end → guide end
- `onset_and_end` — both endpoints mapped
- `hybrid` — hard start, soft end

### Model-Adapter Pattern for Guide Generation

Guide generators implement a common interface:

```python
class GuideVocalGenerator:
    def generate(self, backing_wav: Path, lyrics_json: Path, output_dir: Path, config: GuideGenerationConfig) -> GuideGenerationResult: ...
```

Adapters: `manual.py`, `songgeneration.py`, `yue.py`, `acestep.py`.

### Error Handling: Fail Loudly

**Never silently accept unexpected state.**

- If alignment syllable count doesn't match canonical count → fail, don't stretch wrong syllables
- If a syllable confidence < threshold → report it, don't guess
- If rendered anchor doesn't land exactly on guide anchor → render fails
- If guide audio fails alignment → require regeneration, don't proceed

The pipeline should produce failure reports with Audacity labels for inspection rather than silently producing wrong output.

### Assertions

Use assertions liberally — they are free documentation and catch bugs at the earliest possible moment.

```python
# Sample indices must be non-negative integers
assert isinstance(start_sample, int) and start_sample >= 0

# Syllable count must match across all representations
assert len(canonical) == len(guide_aligned) == len(human_aligned), \
    f"Syllable count mismatch: canonical={len(canonical)}, guide={len(guide_aligned)}, human={len(human_aligned)}"

# Anchors must be monotonically ordered
for i in range(1, len(anchors)):
    assert anchors[i].target_sample > anchors[i-1].target_sample, \
        f"Non-monotonic anchor at index {i}: {anchors[i].target_sample} <= {anchors[i-1].target_sample}"

# Rendered anchor must exactly match guide anchor (the core invariant)
assert rendered_anchor == guide_anchor, \
    f"Anchor error at syllable {idx}: rendered={rendered_anchor}, guide={guide_anchor}, error={rendered_anchor - guide_anchor}"

# Stretch ratio within bounds
ratio = target_duration / source_duration
assert 0.5 <= ratio <= 2.0, f"Extreme stretch ratio {ratio:.3f} for clip {clip_id}"
```

### Naming Conventions

- Python: `snake_case` for everything (files, functions, variables)
- Clip IDs: `clip_NNNN_label` (e.g., `clip_0003_money`)
- JSON metadata files: descriptive names (e.g., `guide_alignment.json`, `anchor_map.json`, `edit_plan.json`)
- Audacity labels: `labels_{description}.txt`

## Validation Requirements

The hard invariant — every commit must preserve this:

```
For every syllable i:
    rendered_anchor_sample[i] == guide_anchor_sample[i]
```

Zero-sample error. No tolerance. If this cannot be proven, the render must fail.

Additional validation:
- `canonical_syllable_count == guide_syllable_count == human_syllable_count`
- Every syllable: `start_sample >= 0`, `end_sample > start_sample`, `anchor_sample` inside `[start_sample, end_sample]`
- Every clip: `source_start < source_end`, `target_start < target_end`, internal anchors inside clip bounds
- Anchor order is monotonic
- Stretch ratios within `[min_stretch_ratio, max_stretch_ratio]`

## Key Files

| File | Purpose |
|------|---------|
| `RESEARCH-BRIEF.md` | Full project specification and experiment plan |
| `EXPERIMENT-LOG.md` | Record of all pipeline tests and results |
| `src/rapmap/cli.py` | CLI entry point — all user-facing commands |
| `src/rapmap/config.py` | Default config and config loading |
| `src/rapmap/edit/planner.py` | Core deterministic edit plan generation |
| `src/rapmap/edit/safe_boundaries.py` | Safe-boundary scoring algorithm |
| `src/rapmap/audio/stretch.py` | Rubber Band time-stretch wrapper |
| `src/rapmap/align/mfa.py` | Montreal Forced Aligner integration |
| `src/rapmap/lyrics/syllabify.py` | Automated syllable detection |
| `src/rapmap/audacity/import_project.py` | Audacity session builder |

## On-Demand Context

| Topic | File |
|-------|------|
| Full project specification | `RESEARCH-BRIEF.md` |
| Experiment history | `EXPERIMENT-LOG.md` |

## Notes

- The hackathon MVP can use a manually supplied guide vocal (Mode C) — AI guide generation is a stretch goal
- Audacity integration uses mod-script-pipe (must be enabled in Audacity preferences)
- Pronunciation overrides for rap slang go in `pronunciation_overrides.yaml`
- The same syllable alignments are reusable across all grouping modes — changing grouping mode should not require re-alignment
- ruff is configured as a PostToolUse hook for auto-formatting Python files
