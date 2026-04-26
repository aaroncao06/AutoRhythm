# RapMap

Syllable-level rhythm correction for rap vocals. RapMap takes a beat, a dry human rap vocal, and lyrics, then deterministically edits the vocal so every syllable lands on the beat. The original voice is preserved -- AI is only used for guide generation and alignment, never for vocal transformation.

The output is a transparent Audacity session with visible clips, labels, and tracks that you can inspect and adjust.

## How It Works

```
Inputs: backing_track.wav + human_rap.wav + lyrics.txt
  |
  +-- Phase 0: Normalize -- resample to 48kHz, mono for analysis
  +-- Phase 1: Guide     -- AI guide vocal or beat-only mode
  +-- Phase 2: Syllabify -- lyrics -> CMUdict -> canonical syllables
  +-- Phase 3: Align     -- MFA forced alignment -> syllable timestamps
  +-- Phase 4: Anchors   -- human_anchor[i] -> guide_anchor[i]
  +-- Phase 5: Group     -- safe-boundary clip grouping
  +-- Phase 6: Plan      -- deterministic edit plan (cut/stretch/crossfade)
  +-- Phase 7: Render    -- Rubber Band time-stretch -> corrected vocal
  +-- Phase 8: Audacity  -- mod-script-pipe -> tracks + labels
```

**Two modes:**
- **Guide mode** -- uses an AI-generated or manually-supplied rap vocal as a timing reference. Syllable anchors in the human vocal are mapped to the guide's timing.
- **Beat-only mode** -- detects BPM from the backing track and snaps syllable anchors to the beat grid. No guide vocal needed.

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# Core dependencies
uv sync

# With beat detection (librosa)
uv sync --extra beat

# With interactive editor (Flask + pywebview)
uv sync --extra editor

# With MFA alignment
uv sync --extra align

# Development (pytest + ruff)
uv sync --extra dev
```

NLTK's CMUdict and the g2p_en model are downloaded automatically on first use.

## Quick Start

### Beat-only mode (no guide vocal)

```bash
uv run rapmap run \
  --backing inputs/backing.wav \
  --human inputs/human_rap.wav \
  --lyrics inputs/lyrics.txt \
  --out workdir \
  --mode beat-only
```

### Guide mode (with a manual guide vocal)

```bash
uv run rapmap run \
  --backing inputs/backing.wav \
  --human inputs/human_rap.wav \
  --lyrics inputs/lyrics.txt \
  --guide inputs/guide_vocal.wav \
  --out workdir \
  --mode guide
```

### Step by step

```bash
# Phase 0: Normalize
uv run rapmap init --backing inputs/backing.wav --human inputs/human_rap.wav --lyrics inputs/lyrics.txt --out workdir

# Phase 1: Set guide (or skip for beat-only)
uv run rapmap set-guide --project workdir --guide inputs/guide.wav

# Phase 2: Syllabify
uv run rapmap syllabify --project workdir

# Phase 3: Align
uv run rapmap align --project workdir --role guide
uv run rapmap align --project workdir --role human

# Phase 4: Build anchor map
uv run rapmap anchors --project workdir --anchor onset

# Phases 5-6: Group + plan
uv run rapmap plan --project workdir --grouping safe_boundary

# Phase 7: Render
uv run rapmap render --project workdir

# Phase 8: Audacity session
uv run rapmap audacity --project workdir --open
```

### Beat-only (step by step)

```bash
uv run rapmap init --backing inputs/backing.wav --human inputs/human_rap.wav --lyrics inputs/lyrics.txt --out workdir
uv run rapmap syllabify --project workdir
uv run rapmap align --project workdir --role human
uv run rapmap detect-beats --project workdir --subdivision eighth --strength 1.0
uv run rapmap plan --project workdir
uv run rapmap render --project workdir
uv run rapmap audacity --project workdir
```

## Interactive Editor

Launch a waveform-based syllable timing editor:

```bash
uv run rapmap editor --project workdir           # native window (pywebview)
uv run rapmap editor --project workdir --browser  # fallback: open in browser
```

Launch Audacity + editor side by side:

```bash
uv run rapmap studio --project workdir
```

## Clip Grouping Modes

All modes produce valid results from the same anchor map:

| Mode | Description |
|------|-------------|
| `safe_boundary` | Split at acoustically safe points (default) |
| `word` | Split at word boundaries |
| `syllable_with_handles` | One clip per syllable with pre/post handles and crossfades |
| `strict_syllable` | Hard cut per syllable (debug mode) |
| `phrase` | Group by line/breath |
| `bar` | Group by bar/newline |

```bash
uv run rapmap plan --project workdir --grouping word
```

## Anchor Strategies

| Strategy | Description |
|----------|-------------|
| `onset` | Syllable onset to guide onset (default, best for rap) |
| `vowel_nucleus` | Vowel center to guide vowel center |
| `end` | Syllable end to guide end |

## Project Structure

```
src/rapmap/
  cli.py              # CLI entry point (click)
  config.py            # Config loading and defaults
  audio/               # I/O, normalization, time-stretch, rendering
  beat/                # Beat detection, grid, syllable quantization
  lyrics/              # Parsing, syllabification, CMUdict + g2p
  align/               # MFA forced alignment, TextGrid parsing
  timing/              # Anchor mapping, confidence scoring
  edit/                # Clip grouping, edit planning, operations
  guide/               # Guide vocal generation (model-adapter pattern)
  audacity/            # Label tracks, script_pipe, session builder
  editor/              # Interactive syllable editor (Flask + wavesurfer.js)
  studio/              # Studio launcher (Audacity + editor)
```

## The Core Invariant

Every syllable anchor in the rendered output must land exactly on the guide anchor, at integer sample precision:

```
For every syllable i:
    rendered_anchor_sample[i] == guide_anchor_sample[i]
```

Zero-sample error. No tolerance. The render fails if this cannot be achieved.

## Key Design Decisions

- **Integer sample indices everywhere** -- all timing uses 48kHz integer sample indices internally. Seconds are only used for Audacity label export.
- **Deterministic Phases 4-8** -- no neural models after alignment. Only cut, stretch, crossfade, and place audio.
- **Fail-loud validation** -- the pipeline aborts rather than silently producing incorrect edits.
- **Pronunciation overrides** -- rap slang (tryna, finna, ion, etc.) handled via YAML override file.

## Tests

```bash
uv run pytest tests/
uv run ruff check src/ tests/
```

## Example

The `example/` directory contains a backing track (`beat.m4a`) and lyrics (`lyrics.txt`) for testing.

## License

TBD
