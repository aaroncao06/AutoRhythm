# Research Brief: RapMap — Rap Vocal Rhythm Mapping for Audacity

## 1. Research Summary

Rap vocal production requires precise rhythmic alignment between a performer's delivery and the underlying beat. Currently, this alignment is achieved through either re-recording (losing unique takes) or tedious manual editing in a DAW. No existing tool provides automated, syllable-level rhythmic correction for rap vocals while preserving the original voice identity and producing transparent, editable results.

RapMap proposes a pipeline that uses an AI-generated rap vocal as a rhythmic timing reference, then deterministically edits the original human vocal — cutting, stretching, compressing, and placing audio clips — so that syllable-level timing anchors match the AI guide exactly. The key constraint is that Phase 3 (human vocal correction) must be fully deterministic: no neural models may transform or regenerate the human voice. AI is only permitted for guide generation (Phase 1) and alignment/timestamp extraction (Phase 2).

The expected contribution is a working open-source system (uv-based Python CLI + Audacity integration) that produces studio-style editing sessions with visible clips, labels, and tracks — not a black-box vocal transformation. The core differentiator is the deterministic timing/editing pipeline with zero-sample anchor error guarantees.

## 2. Research Question

**Can syllable-level forced alignment, combined with deterministic piecewise time-warping, produce rhythmically corrected rap vocals that (a) match an AI guide's timing at integer sample precision, (b) preserve the original human voice identity, and (c) avoid perceptible audio artifacts through safe-boundary clip grouping?**

This question matters because it sits at the intersection of speech alignment, audio signal processing, and music production — domains that have mature individual tools but no integrated pipeline for rap-specific rhythmic correction with transparency guarantees.

## 3. Project Scope / Claims

### In Scope
- [x] **C1**: The pipeline achieves zero-sample anchor error for every syllable mapping (human anchor lands exactly on guide anchor)
- [x] **C2**: Safe-boundary clip grouping produces audibly smooth results without hard syllable cuts
- [x] **C3**: The system produces transparent, inspectable Audacity sessions with visible clips, labels, and tracks
- [x] **C4**: Automated syllable detection via CMUdict + G2P handles standard rap lyrics without manual intervention
- [x] **C5**: Montreal Forced Aligner can produce usable phone-level alignments on dry rap vocals
- [x] **C6**: Rubber Band pitch-preserving time-stretch maintains voice identity across practical stretch ratios (0.5x–2.0x)
- [x] **C7**: The pipeline is fully deterministic from edit plan onward — same inputs always produce identical outputs

### Future Work / Out of Scope
- [ ] General singing / melodic vocal correction
- [ ] Voice cloning or neural voice conversion
- [ ] Pitch correction (auto-tune)
- [ ] Multiple rappers on one vocal track
- [ ] Lyrics performed out of order
- [ ] Wet vocals with backing bleed
- [ ] Live real-time performance
- [ ] Native Audacity plugin (hackathon uses mod-script-pipe)
- [ ] Vowel-nucleus anchor mode (stretch goal)
- [ ] Hybrid hard-start / soft-end mapping (stretch goal)
- [ ] Beat-grid detection (stretch goal)

## 4. Hypotheses

**H1**: Forced alignment on dry isolated rap vocals produces syllable-level timestamps with confidence ≥ 0.70 for ≥ 95% of syllables.
- **Expected outcome**: MFA successfully aligns both guide and human vocals to the canonical syllable sequence.
- **Experiment**: Run alignment on test vocals, measure per-syllable confidence scores.
- **Reasoning**: MFA is designed for read speech; rap is rhythmic but more variable. Dry isolated vocals remove the main confounder (background music).

**H2**: Safe-boundary clip grouping produces fewer audible artifacts than word-level or strict-syllable grouping.
- **Expected outcome**: Safe-boundary mode scores highest in informal A/B listening tests.
- **Experiment**: Render the same vocal with all grouping modes; compare results.
- **Reasoning**: Safe boundaries respect acoustic continuity (silence, breaths, zero crossings) rather than arbitrary linguistic boundaries.

**H3**: Piecewise time-warping with Rubber Band preserves perceived voice identity for stretch ratios within [0.5, 2.0].
- **Expected outcome**: Listeners identify the corrected vocal as the same speaker.
- **Experiment**: Render clips at various stretch ratios; informal identity verification.
- **Reasoning**: Rubber Band's pitch-preserving mode is designed for this range; extreme ratios introduce formant artifacts.

**H4**: AI-generated guide vocals (via SongGeneration/YuE/ACE-Step) follow provided lyrics closely enough to pass forced alignment validation.
- **Expected outcome**: Guide alignment succeeds with exact syllable count match on ≥ 80% of generation attempts.
- **Experiment**: Generate guides for test lyrics; run alignment; measure syllable count match rate.
- **Reasoning**: Current open-source lyrics-to-song models are improving but not perfectly reliable — the manual guide fallback exists for this reason.

## 5. Method Overview

### Pipeline Architecture (9 Phases)

```
Inputs: backing_track.wav, human_rap.wav, lyrics.txt
  │
  ├─ Phase 0: Normalize ─── WAV conversion, resampling to 48kHz, mono analysis copies
  ├─ Phase 1: Guide Gen ─── AI model or manual guide → ai_guide_vocal.wav
  ├─ Phase 2: Syllabify ─── lyrics → CMUdict → canonical_syllables.json
  ├─ Phase 3: Align ─────── MFA forced alignment → phone/syllable timestamps for both vocals
  ├─ Phase 4: Anchor Map ── human_anchor[i] → guide_anchor[i] (onset-to-onset default)
  ├─ Phase 5: Clip Group ── safe-boundary scoring → clip_groups.json
  ├─ Phase 6: Edit Plan ─── piecewise time-warp specification → edit_plan.json
  ├─ Phase 7: Render ────── Rubber Band time-stretch → clips/*.wav + corrected_human_rap.wav
  └─ Phase 8: Audacity ──── mod-script-pipe → 5 audio tracks + 5 label tracks
```

### Key Design Decisions
1. **Sample-based timing internally** — all anchors/boundaries stored as integer sample indices (48kHz), seconds only for Audacity label export
2. **Deterministic Phase 3+** — no neural models allowed after alignment; only cut/stretch/crossfade
3. **Safe-boundary default** — clips grouped at acoustically safe split points, not forced syllable boundaries
4. **Model-adapter pattern** — guide generation supports multiple backends (SongGeneration, YuE, ACE-Step, manual)
5. **Fail-loud validation** — pipeline aborts rather than silently producing incorrect edits

## 6. Experiment Groups

### Claim C1 + C7: Zero-sample anchor error & determinism
- **E1.1**: End-to-end pipeline on 3 test songs with known lyrics — verify every rendered anchor matches guide anchor at sample level
- **E1.2**: Run same inputs twice — verify byte-identical output (determinism proof)
- **Compute**: ~5 min per song on CPU

### Claim C2: Safe-boundary grouping quality
- **E2.1**: Render same vocal with all 6 grouping modes (safe_boundary, word, syllable_with_handles, strict_syllable, phrase, bar)
- **E2.2**: Count audible artifacts (clicks, choppiness) per mode via waveform inspection
- **Compute**: ~2 min per mode per song

### Claim C4 + C5: Syllable detection & forced alignment
- **E3.1**: Run syllabification on 50 bars of rap lyrics — measure CMUdict hit rate vs G2P fallback rate
- **E3.2**: Run MFA on 3 test vocals — measure per-syllable confidence distribution
- **E3.3**: Test pronunciation override mechanism with 10 slang words (tryna, finna, ion, etc.)
- **Compute**: ~10 min total

### Claim C6: Voice identity preservation
- **E4.1**: Render clips at stretch ratios 0.5, 0.75, 1.0, 1.25, 1.5, 2.0 — informal listening test
- **Compute**: ~1 min per ratio

### Claim C3: Audacity session transparency
- **E5.1**: Import generated session into Audacity — verify 5 audio tracks + 5 label tracks load correctly
- **E5.2**: Verify clip boundaries are visible and editable
- **Compute**: Manual verification, ~15 min

## 7. Software Stack

| Component | Choice | Version | Notes |
|-----------|--------|---------|-------|
| Language | Python | 3.11+ | |
| Package manager | uv | latest | Rust-based, fast |
| Forced alignment | Montreal Forced Aligner | 3.x | Primary aligner |
| Fallback alignment | WhisperX | latest | Auxiliary/fallback |
| Pronunciation | CMUdict | latest | 134k+ words |
| Time-stretch | Rubber Band | 3.x | Pitch-preserving |
| Source separation | Demucs | latest | Only if guide is full-mix |
| Audio I/O | soundfile / scipy | latest | WAV read/write |
| DAW integration | Audacity mod-script-pipe | shipped | Named pipes |
| Guide gen candidates | SongGeneration, YuE, ACE-Step | latest | Model-adapter pattern |

### Compute Resources
- **Development**: CPU-only for Phases 2–8 (alignment, editing, rendering)
- **Guide generation**: GPU required (1x consumer GPU sufficient for inference)
- **Estimated time**: Minutes per song for the deterministic pipeline; guide generation varies by model

## 8. Reproducibility Requirements

### Determinism
- Phases 3–8 must produce identical output given identical input — enforced by sample-based integer arithmetic and deterministic Rubber Band settings
- Random seeds not applicable to the deterministic pipeline; only relevant for guide generation (Phase 1)

### Config Management
- All pipeline parameters in YAML configs under `configs/`
- Default config specified in Section 18 of master spec
- Per-project overrides via `workdir/project.json`

### Artifact Tracking
- Every pipeline run produces: `edit_plan.json`, `clip_manifest.json`, `render_report.json`, `validation_report.json`
- These are the reproducibility artifacts — given the edit plan and source audio, the render is deterministic

### Environment
- `uv.lock` pins all dependencies
- `pyproject.toml` declares version constraints

## 9. Evaluation Protocol

### Primary Metric
- **Anchor error**: For every syllable i, `|rendered_anchor_sample[i] - guide_anchor_sample[i]|` must equal 0. Binary pass/fail.

### Secondary Metrics
- **Alignment confidence**: Per-syllable confidence from MFA, threshold ≥ 0.70
- **Syllable count match**: `canonical_count == guide_count == human_count` (binary)
- **Stretch ratio distribution**: Per-clip stretch ratio, flagging any outside [0.5, 2.0]
- **Clip count by grouping mode**: How many clips each mode produces
- **CMUdict hit rate**: Fraction of words resolved without G2P fallback

### Baselines
- **No correction**: Original human vocal timing (baseline for rhythmic accuracy)
- **Strict syllable mode**: Hard-cut per syllable (baseline for artifact comparison)
- **Manual DAW edit**: Human producer's edit of the same material (gold standard, if available)

### Validation
- All validation is automated via `validation_report.json`
- Render fails if any anchor error > 0 samples
- Pipeline fails if alignment syllable count mismatches

## 10. Implementation Phases

### Phase 1: Foundation (Days 1–2)
**Goal**: Working CLI skeleton, audio normalization, lyrics parsing, syllable detection.
- Implement: `cli.py`, `config.py`, `audio/io.py`, `audio/normalize.py`, `lyrics/parser.py`, `lyrics/normalize.py`, `lyrics/syllabify.py`, `lyrics/pronunciations.py`
- Validation: `uv run rapmap init` and `uv run rapmap syllabify` produce correct JSON outputs
- Tests: `test_lyrics_parser.py`, `test_syllabification.py`

### Phase 2: Alignment Core (Days 2–3)
**Goal**: Forced alignment working for both guide and human vocals.
- Implement: `align/mfa.py`, `align/base.py`, `align/derive_syllables.py`, `align/validate.py`, `align/textgrid.py`
- Validation: MFA produces phone-level timestamps; syllable timestamps derived correctly; validation passes
- Tests: Manual guide + human vocal aligned to same lyrics

### Phase 3: Timing & Edit Pipeline (Days 3–4)
**Goal**: Anchor mapping, clip grouping, deterministic edit planning.
- Implement: `timing/anchors.py`, `timing/anchor_map.py`, `edit/safe_boundaries.py`, `edit/grouping.py`, `edit/planner.py`, `edit/operations.py`, `edit/crossfade.py`
- Validation: Edit plan passes all validation checks; anchor mapping is exact
- Tests: `test_anchor_mapping.py`, `test_safe_boundary_grouping.py`, `test_edit_plan_exactness.py`

### Phase 4: Rendering (Days 4–5)
**Goal**: Corrected vocal rendered as clips and flattened preview.
- Implement: `audio/stretch.py`, `audio/render.py`, `edit/manifest.py`
- Validation: Zero-sample anchor error; clips match expected durations; flattened preview matches song duration
- Tests: `test_render_clip_lengths.py`

### Phase 5: Audacity Integration (Days 5–6)
**Goal**: Full Audacity session with 5 audio tracks + 5 label tracks.
- Implement: `audacity/labels.py`, `audacity/script_pipe.py`, `audacity/import_project.py`, `audacity/export_mix.py`
- Validation: Session opens in Audacity with all tracks visible and clips editable
- Tests: `test_audacity_labels.py`

### Phase 6: Guide Generation (Stretch)
**Goal**: AI guide generation with at least one model adapter.
- Implement: `guide/base.py`, `guide/manual.py`, `guide/songgeneration.py`
- Validation: Generated guide passes alignment validation
- Fallback: Manual guide always available

## 11. Related Work / Prior Art

| System | What It Does | Gap RapMap Fills |
|--------|-------------|-----------------|
| **Montreal Forced Aligner** | Phone-level forced alignment from transcript | Only alignment — no editing, no guide generation, no Audacity integration |
| **WhisperX** | Speech recognition with word-level timestamps | ASR-first (not transcript-first); no syllable-level control |
| **Rubber Band** | Pitch-preserving time-stretch | Library only — no alignment awareness, no clip management |
| **Demucs** | Source separation (vocals from mix) | Separation only — no rhythmic editing |
| **Vocaloid / Synthesizer V** | Singing voice synthesis | Generates new voice; doesn't preserve human identity |
| **Auto-Tune / Melodyne** | Pitch correction + some timing | Pitch-focused; timing tools are manual, not syllable-anchored |
| **SongGeneration / YuE** | Lyrics-to-song generation | Generation only — no alignment or deterministic editing pipeline |
| **ACE-Step** | Music generation foundation model | Generation only — same gap as above |
| **Audacity built-in** | Manual audio editing | No automated alignment, no syllable-level clip generation |
| **DAW beat-align tools** | Beat-level quantization | Beat-level, not syllable-level; not rap-specific |

**Key gap**: No existing system combines forced alignment + deterministic syllable-level time-warping + transparent DAW session output for rap vocals.

## 12. Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | **MFA fails on rap delivery** — rapid, slurred, or stylized speech degrades alignment confidence | Medium | High | WhisperX fallback; pronunciation overrides for slang; fail-loud validation prevents silent errors |
| 2 | **AI guide doesn't follow lyrics** — generated vocal skips/adds words, breaking syllable count match | High | Medium | Manual guide fallback (Mode C); guide validation gate; can regenerate with different model |
| 3 | **Extreme stretch ratios** — human timing differs wildly from guide, requiring >2x stretch | Medium | Medium | Configurable `min_stretch_ratio`/`max_stretch_ratio`; warn or fail; suggest phrase-level grouping to absorb timing |
| 4 | **mod-script-pipe unavailable** — Audacity scripting module disabled or incompatible | Low | Medium | Label files + clip WAVs can be manually imported; document manual import procedure |
| 5 | **Slang/invented words not in CMUdict** — G2P fallback produces wrong syllable count | Medium | Low | Pronunciation override YAML; explicit rap slang dictionary; fail on low-confidence words |

## 13. Future Work

### Near-term Extensions (Post-Hackathon)
- Vowel-nucleus anchor mode for smoother delivery styles
- Hybrid hard-start / soft-end anchor mapping
- Confidence heatmap labels in Audacity
- Automatic beat-grid detection for guide-less operation
- Phrase-level loudness smoothing
- Breath preservation controls

### Longer-term Directions
- Native Audacity plugin with interactive re-rendering
- Export to other DAW formats (Reaper, Ableton, Logic)
- Formant-aware stretch settings for extreme ratios
- Multi-rapper track separation and independent alignment
- De-click and de-pop pass for rendered clips
- Real-time preview during parameter adjustment

## 14. Deliverables

### Hackathon Target
- **Format**: Working CLI tool + Audacity demo session
- **Timeline**: ~6 days (Phases 1–5 above)
- **Core deliverable**: End-to-end pipeline from inputs to Audacity session with visible clips

### Artifacts
- `rapmap` CLI (`uv run rapmap <command>`)
- Test songs demonstrating all grouping modes
- Audacity session screenshots/recording for demo
- This Research Brief as project documentation

### Code Release
- Repository: this repo (`AutoRapper`)
- License: TBD
- Dependencies pinned via `uv.lock`

## 15. Terminology Quick Reference

| Term | Definition |
|------|-----------|
| **Canonical syllable** | Normalized syllable unit from lyrics + pronunciation dictionary; shared index for both vocals |
| **Anchor** | Timing point inside a syllable (default: onset) that must map exactly from human to guide |
| **Guide vocal** | AI-generated rap used only as timing reference |
| **Human vocal** | Original dry isolated rap whose voice identity is preserved |
| **Clip group** | Contiguous syllables rendered as one Audacity-visible clip |
| **Safe boundary** | Split point where cutting is unlikely to produce artifacts (silence, breath, zero crossing) |
| **Anchor error** | `|rendered_anchor - guide_anchor|` in samples; must be 0 for all syllables |
| **Edit plan** | Deterministic specification of every cut, stretch, crossfade, and placement operation |

## 16. File Format Summary

### Audio
- Internal: WAV, 48kHz, 32-bit float, mono for analysis
- No MP3 for intermediate files (encoder delay, compression artifacts)
- MP3 allowed only as optional final export

### Metadata
- **JSON**: All machine-readable metadata (`*_alignment.json`, `anchor_map.json`, `edit_plan.json`, `clip_manifest.json`)
- **TextGrid**: MFA-compatible alignment files
- **TSV**: Audacity label tracks (`start_seconds\tend_seconds\tlabel`)
- **YAML**: Configuration files

### Master timing format
```json
{
  "sample_rate": 48000,
  "start_sample": 144000,
  "end_sample": 151200
}
```
All internal timing uses integer sample indices, not floating-point seconds.
