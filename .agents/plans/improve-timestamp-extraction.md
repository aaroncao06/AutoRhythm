# Task: Improve Timestamp Extraction & Contiguous Warp Rendering

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files etc.

## Task Description

Improve the quality of syllable timestamp extraction (Phase 3) and introduce a new contiguous "warp map" rendering model (Phases 5-7) that treats the entire vocal as a continuous stream partitioned at syllable boundaries. Every piece of audio — syllables AND gaps between them — is a first-class segment that gets stretched or compressed. No cutting, no moving, no splicing. The original human performance sequence is preserved with only stretch/compress operations.

Three extraction quality improvements:
1. **Multiple pronunciations per word** — emit all CMUdict variants into MFA dictionary so the acoustic model picks the best fit, reducing fallback cases
2. **Energy-based fallback splitting** — when MFA vowel count doesn't match canonical, use RMS energy peaks to find syllable nuclei instead of equal time division
3. **Phoneme boundary smoothing** — merge micro-segments (< 15ms phones) that are MFA artifacts, stabilizing anchor placement

One architectural improvement:
4. **Warp map model** — a new contiguous segment representation where the audio is partitioned into alternating syllable and gap segments, each with source (human) and target (golden) timing. The renderer applies piecewise time-stretch to produce the corrected vocal with smooth transitions preserved.

## Task Metadata

**Task Type**: Code Change
**Estimated Complexity**: High
**Primary Systems Affected**: `align/`, `lyrics/pronunciations.py`, `edit/warp_map.py` (new), `audio/render.py`, `config.py`, `cli.py`
**Dependencies**: scipy (already a dependency), numpy (already), nltk/cmudict (already)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING

- `src/rapmap/align/derive_syllables.py` (entire file) — **Primary target.** Contains the three fallback paths (lines 117-188), `_compute_anchor()`, `_phone_confidence()`. All three extraction improvements modify this file.
- `src/rapmap/align/base.py` (entire file) — Data structures: `PhoneTimestamp`, `SyllableTimestamp`, `AlignmentResult`, serialization helpers. The warp map will consume `AlignmentResult`.
- `src/rapmap/lyrics/pronunciations.py` (entire file) — `lookup_pronunciation()` returns `d[key][0]` (first pronunciation only, line 54). Must add `lookup_all_pronunciations()`.
- `src/rapmap/align/mfa.py` (lines 58-68) — `_generate_dictionary()` calls `lookup_pronunciation()` once per word. Must emit all variants.
- `src/rapmap/timing/anchor_map.py` (entire file) — `build_anchor_map()` produces the anchor_map dict with `human_start/end`, `guide_start/end` per syllable. The warp map builder consumes this.
- `src/rapmap/beat/quantize.py` (entire file) — `quantize_anchors()` produces anchor_map in beat-only mode. Same output format — warp map must work with both.
- `src/rapmap/edit/operations.py` (entire file) — Existing `Segment`, `ClipOperation`, `EditPlan` dataclasses. The warp map introduces parallel dataclasses, NOT modifications to these.
- `src/rapmap/edit/planner.py` (entire file) — `create_edit_plan()` builds clip-based edit plan. Keep as-is for Audacity clip export.
- `src/rapmap/audio/render.py` (entire file) — `render_clips()` does clip-based rendering. Add `render_warp_map()` alongside it.
- `src/rapmap/audio/stretch.py` (entire file) — `time_stretch()` wraps rubberband CLI. Used by both renderers.
- `src/rapmap/config.py` (entire file) — Config dataclasses. Must add new fields to `AlignmentConfig` and `RenderingConfig`.
- `src/rapmap/cli.py` (lines 501-712) — The `run` command orchestrates the full pipeline. Must wire warp rendering as default.
- `src/rapmap/align/validate.py` — `validate_alignment()` checks monotonicity and bounds. Read to understand existing validation.
- `src/rapmap/edit/grouping.py` — `group_syllables()` builds clip groups. Keep as-is; warp map bypasses this entirely.

### New Files to Create

- `src/rapmap/edit/warp_map.py` — WarpSegment, WarpMap dataclasses + `build_warp_map()` + serialization
- `tests/test_pronunciation_multi.py` — tests for multi-pronunciation lookup and dictionary generation
- `tests/test_energy_fallback.py` — tests for energy-based syllable splitting
- `tests/test_phoneme_smoothing.py` — tests for micro-segment merging
- `tests/test_warp_map.py` — tests for warp map construction and rendering

### Patterns to Follow

**Dataclass pattern** (from `operations.py`):
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
    def stretch_ratio(self) -> float:
        if self.source_duration == 0:
            return 1.0
        return self.target_duration / self.source_duration
```

**Serialization pattern** (from `operations.py`):
```python
def edit_plan_to_dict(plan: EditPlan) -> dict: ...
def edit_plan_from_dict(data: dict) -> EditPlan: ...
```

**Config pattern** (from `config.py`):
```python
@dataclass
class AlignmentConfig:
    primary_backend: str = "mfa"
    # ... all fields have defaults
```

**Render function pattern** (from `render.py`):
```python
def render_clips(edit_plan, human_audio, sample_rate, output_dir, config, anchor_map, fail_on_anchor_error) -> dict:
    # returns {"report": ..., "manifest": ...}
```

---

## IMPLEMENTATION PLAN

### Phase 1: Config & Dependencies

Add new config fields to support the three extraction improvements and warp rendering mode.

### Phase 2: Multiple Pronunciations

Add `lookup_all_pronunciations()` to `pronunciations.py`. Modify MFA dictionary generation to emit all variants. MFA dictionary format supports multiple lines with the same word key — MFA chooses the best-scoring pronunciation during alignment.

### Phase 3: Phoneme Boundary Smoothing

Post-process the phone list in `derive_syllable_timestamps()` to merge micro-segments before syllabification. This stabilizes anchor placement by removing jittery MFA artifacts.

### Phase 4: Energy-Based Fallback

Replace equal-time-division fallback in `derive_syllable_timestamps()` with energy-based peak detection. Requires passing audio data as an optional parameter. When audio is available and peak count matches canonical, use energy valleys as syllable boundaries. Fall back to equal division if peaks don't match.

### Phase 5: Warp Map Model

New `WarpSegment` and `WarpMap` dataclasses. Builder constructs a contiguous partition of the audio: alternating syllable segments and gap segments. Each has source timing (human) and target timing (golden). Invariant: `segments[i].source_end == segments[i+1].source_start` and same for target.

### Phase 6: Warp Renderer

New `render_warp_map()` function that applies piecewise time-stretch. Walks the segment sequence, stretches each, concatenates. No clips, no crossfades needed (audio is continuous). Validates the zero-sample anchor invariant.

### Phase 7: CLI Integration

Wire the warp rendering path into the `run` command. Keep clip-based rendering for Audacity integration (the `plan` → `render` → `audacity` path).

### Phase 8: Tests

Comprehensive tests for each new component.

---

## STEP-BY-STEP TASKS

### Task 1: UPDATE `src/rapmap/config.py`

Add new config fields.

- **IMPLEMENT**: Add to `AlignmentConfig`:
  ```python
  phoneme_smoothing_min_ms: float = 15.0
  energy_fallback: bool = True
  multi_pronunciation: bool = True
  ```
- **IMPLEMENT**: Add to `RenderingConfig`:
  ```python
  rendering_mode: str = "warp"  # "warp" or "clip"
  ```
- **PATTERN**: Follow existing dataclass field pattern (config.py lines 37-44)
- **GOTCHA**: `_merge_config()` uses `setattr` — new fields are automatically picked up from YAML
- **VALIDATE**: `uv run python -c "from rapmap.config import AlignmentConfig; c = AlignmentConfig(); assert c.phoneme_smoothing_min_ms == 15.0; assert c.energy_fallback is True; assert c.multi_pronunciation is True; print('OK')"`

### Task 2: UPDATE `src/rapmap/lyrics/pronunciations.py`

Add multi-pronunciation lookup.

- **IMPLEMENT**: Add function `lookup_all_pronunciations()` below `lookup_pronunciation()`:
  ```python
  def lookup_all_pronunciations(
      word: str, overrides: dict | None = None, g2p_fallback: bool = True
  ) -> list[tuple[list[str], str]]:
  ```
  Priority logic:
  1. If word is in overrides → return `[(override_phones, "override")]` (single variant — overrides are authoritative)
  2. If word is in CMUdict → return ALL variants: `[(d[key][i], "cmudict") for i in range(len(d[key]))]`
  3. If g2p_fallback → return `[(g2p_phones, "g2p")]` (single variant)
  4. Else raise ValueError
- **PATTERN**: Mirror `lookup_pronunciation()` structure (lines 41-69)
- **IMPORTS**: No new imports needed
- **GOTCHA**: CMUdict returns `list[list[str]]` per word (multiple pronunciations). Currently line 54 takes `d[key][0]`. The new function returns ALL entries from `d[key]`.
- **VALIDATE**: `uv run python -c "from rapmap.lyrics.pronunciations import lookup_all_pronunciations; results = lookup_all_pronunciations('the'); print(f'{len(results)} pronunciations for the'); assert len(results) >= 2"`

### Task 3: UPDATE `src/rapmap/align/mfa.py`

Use multi-pronunciation dictionary.

- **IMPLEMENT**: Modify `_generate_dictionary()` to use `lookup_all_pronunciations()` when config allows:
  - Add `multi_pronunciation: bool = True` parameter to `_generate_dictionary()`
  - When `multi_pronunciation=True`: call `lookup_all_pronunciations()` and emit one line per variant (MFA dictionary format: same word key on multiple lines)
  - When `multi_pronunciation=False`: keep current behavior (first pronunciation only)
- **IMPLEMENT**: Update import at top of file:
  ```python
  from rapmap.lyrics.pronunciations import lookup_all_pronunciations, lookup_pronunciation
  ```
- **IMPLEMENT**: Update `_generate_dictionary()`:
  ```python
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
  ```
- **IMPLEMENT**: Update `align_with_mfa()` to pass `config.multi_pronunciation` if available. Add `multi_pronunciation` parameter defaulting to True:
  ```python
  dict_path.write_text(_generate_dictionary(canonical_syllables, overrides, multi_pronunciation=True))
  ```
  To thread this from config, the simplest approach is to check `hasattr(config, 'multi_pronunciation')` since AlignmentConfig now has this field. But actually the function signature already takes `config: AlignmentConfig`. So:
  ```python
  dict_path.write_text(
      _generate_dictionary(canonical_syllables, overrides, config.multi_pronunciation)
  )
  ```
- **GOTCHA**: MFA dictionary format: each line is `word\tPH1 PH2 PH3`. Multiple pronunciations for the same word are on separate lines with the same word key. MFA will score all variants and pick the best.
- **VALIDATE**: `uv run ruff check src/rapmap/align/mfa.py src/rapmap/lyrics/pronunciations.py`

### Task 4: UPDATE `src/rapmap/align/derive_syllables.py` — Phoneme Smoothing

Add phone merging as a post-processing step before syllabification.

- **IMPLEMENT**: Add function `_smooth_phones()` above `derive_syllable_timestamps()`:
  ```python
  def _smooth_phones(
      phones: list[PhoneTimestamp], min_duration_samples: int
  ) -> list[PhoneTimestamp]:
      """Merge phones shorter than min_duration into their longer neighbor."""
      if len(phones) <= 1:
          return phones
      result = list(phones)
      changed = True
      while changed:
          changed = False
          i = 0
          while i < len(result):
              dur = result[i].end_sample - result[i].start_sample
              if dur < min_duration_samples and len(result) > 1:
                  if i == 0:
                      # Merge into next
                      result[1] = PhoneTimestamp(
                          phone=result[1].phone,
                          start_sample=result[0].start_sample,
                          end_sample=result[1].end_sample,
                      )
                      result.pop(0)
                  elif i == len(result) - 1:
                      # Merge into previous
                      result[-2] = PhoneTimestamp(
                          phone=result[-2].phone,
                          start_sample=result[-2].start_sample,
                          end_sample=result[-1].end_sample,
                      )
                      result.pop(-1)
                  else:
                      # Merge into longer neighbor
                      prev_dur = result[i - 1].end_sample - result[i - 1].start_sample
                      next_dur = result[i + 1].end_sample - result[i + 1].start_sample
                      if prev_dur >= next_dur:
                          result[i - 1] = PhoneTimestamp(
                              phone=result[i - 1].phone,
                              start_sample=result[i - 1].start_sample,
                              end_sample=result[i].end_sample,
                          )
                      else:
                          result[i + 1] = PhoneTimestamp(
                              phone=result[i + 1].phone,
                              start_sample=result[i].start_sample,
                              end_sample=result[i + 1].end_sample,
                          )
                      result.pop(i)
                  changed = True
                  continue
              i += 1
      return result
  ```
- **IMPLEMENT**: Add `smoothing_min_ms: float = 0.0` parameter to `derive_syllable_timestamps()`. When > 0, apply `_smooth_phones()` to `word_phones` before syllabification (before line 111).
  ```python
  if smoothing_min_ms > 0:
      min_dur = int(smoothing_min_ms * sample_rate / 1000)
      word_phones = _smooth_phones(word_phones, min_dur)
  ```
- **GOTCHA**: Smoothing changes phone labels (the merged phone keeps the neighbor's label, losing the short phone's identity). This is intentional — the short phone was an artifact. But it means `word_phone_labels` (line 111) must be recomputed AFTER smoothing.
- **GOTCHA**: Smoothing may reduce vowel count (if a very short vowel merges into a consonant neighbor). This could push more words into the fallback path. The min_duration threshold (15ms) is chosen to avoid this — real vowels are almost always > 30ms.
- **VALIDATE**: `uv run ruff check src/rapmap/align/derive_syllables.py`

### Task 5: UPDATE `src/rapmap/align/derive_syllables.py` — Energy-Based Fallback

Replace equal-time-division with energy-based splitting when audio is available.

- **IMPLEMENT**: Add `audio_data: np.ndarray | None = None` parameter to `derive_syllable_timestamps()`.
- **IMPLEMENT**: Add function `_energy_split()`:
  ```python
  def _energy_split(
      audio_segment: np.ndarray,
      num_syllables: int,
      sample_rate: int,
      word_start_sample: int,
  ) -> list[tuple[int, int]]:
      """Split audio segment into syllables by RMS energy peaks.
      
      Returns list of (start_sample, end_sample) in absolute sample indices.
      Returns empty list if peak detection fails to match num_syllables.
      """
      if len(audio_segment) < num_syllables * 2:
          return []
      
      # Windowed RMS energy
      win_samples = max(1, int(0.010 * sample_rate))  # 10ms window
      hop = max(1, win_samples // 2)
      n_frames = (len(audio_segment) - win_samples) // hop + 1
      if n_frames < num_syllables:
          return []
      
      rms = np.zeros(n_frames, dtype=np.float32)
      for i in range(n_frames):
          start = i * hop
          frame = audio_segment[start : start + win_samples]
          rms[i] = np.sqrt(np.mean(frame ** 2))
      
      from scipy.signal import find_peaks
      
      # Find peaks (vowel nuclei) with minimum distance between them
      min_distance = max(1, n_frames // (num_syllables * 2))
      peaks, properties = find_peaks(rms, distance=min_distance, prominence=np.max(rms) * 0.05)
      
      if len(peaks) != num_syllables:
          return []
      
      # Find valleys between consecutive peaks as boundaries
      boundaries_frames = [0]
      for i in range(len(peaks) - 1):
          valley_region = rms[peaks[i] : peaks[i + 1]]
          valley_offset = np.argmin(valley_region)
          boundaries_frames.append(peaks[i] + valley_offset)
      boundaries_frames.append(n_frames)
      
      # Convert frame boundaries to absolute sample indices
      result = []
      for i in range(num_syllables):
          s_start = word_start_sample + boundaries_frames[i] * hop
          s_end = word_start_sample + boundaries_frames[i + 1] * hop
          if i == num_syllables - 1:
              s_end = word_start_sample + len(audio_segment)
          result.append((s_start, s_end))
      
      return result
  ```
- **IMPLEMENT**: In the two fallback branches (lines 137-161 and 162-188), before the equal-division code, try energy-based splitting:
  ```python
  # At the start of each fallback branch, after the logger.warning():
  energy_boundaries = []
  if audio_data is not None:
      word_audio = audio_data[w_start:w_end]
      energy_boundaries = _energy_split(
          word_audio, canonical_syl_count, sample_rate, w_start,
      )
  
  if energy_boundaries:
      for si, (s_start, s_end) in enumerate(energy_boundaries):
          all_syllables.append(
              SyllableTimestamp(
                  syllable_index=global_syl_idx,
                  word_index=cw["word_index"],
                  word_text=cw["text"],
                  start_sample=s_start,
                  end_sample=s_end,
                  anchor_sample=s_start,
                  phones=word_phones if si == 0 else [],
                  confidence=0.5,  # better than equal division (0.1/0.3) but not ideal
              )
          )
          global_syl_idx += 1
  else:
      # ... existing equal-division code ...
  ```
- **IMPORTS**: Add `import numpy as np` at top of file
- **GOTCHA**: The `audio_data` parameter is the full mono audio array. We extract the word's segment via `audio_data[w_start:w_end]`. The sample indices `w_start`/`w_end` come from the TextGrid word tier conversion.
- **GOTCHA**: `_energy_split()` returns empty list if peak count doesn't match, triggering the existing equal-division fallback. This is safe — energy detection is best-effort.
- **GOTCHA**: Confidence for energy-based splits is 0.5 — better than equal division (0.1/0.3) but below well-matched MFA alignment (~0.7-1.0).
- **VALIDATE**: `uv run ruff check src/rapmap/align/derive_syllables.py`

### Task 6: UPDATE `src/rapmap/cli.py` — Thread New Parameters

Pass audio data and config into `derive_syllable_timestamps()`.

- **IMPLEMENT**: In the `align` command (line 137), after reading audio, pass it to `derive_syllable_timestamps()`:
  ```python
  from rapmap.audio.io import read_audio
  audio_for_fallback, _ = read_audio(audio, mono=True)
  ```
  Then in the call to `derive_syllable_timestamps()`:
  ```python
  al = derive_syllable_timestamps(
      tg, canonical, sr, role_name, str(audio_path), anchor,
      smoothing_min_ms=config.alignment.phoneme_smoothing_min_ms,
      audio_data=audio_for_fallback,
  )
  ```
- **IMPLEMENT**: Same in the `run` command's Phase 3 loop (around line 618):
  ```python
  audio_for_fallback, _ = read_audio(audio_path, mono=True)
  al = derive_syllable_timestamps(
      tg, canonical, sr, role_name, str(audio_path), anchor,
      smoothing_min_ms=config.alignment.phoneme_smoothing_min_ms,
      audio_data=audio_for_fallback,
  )
  ```
- **GOTCHA**: The audio is already read elsewhere in the `run` command (for safe_boundary grouping). Reuse the variable if the path matches, or just read it again — it's fast for the file sizes involved.
- **VALIDATE**: `uv run ruff check src/rapmap/cli.py`

### Task 7: CREATE `src/rapmap/edit/warp_map.py`

New module for the contiguous segment model.

- **IMPLEMENT**: Create the file with:
  ```python
  from __future__ import annotations
  
  from dataclasses import dataclass
  from typing import Literal
  
  
  @dataclass
  class WarpSegment:
      segment_index: int
      segment_type: Literal["syllable", "gap", "lead_in", "trail"]
      syllable_index: int | None
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
  class WarpMap:
      sample_rate: int
      anchor_strategy: str
      total_source_samples: int
      total_target_samples: int
      segments: list[WarpSegment]
  
  
  def build_warp_map(
      anchor_map: dict,
      human_total_samples: int,
      guide_total_samples: int | None = None,
  ) -> WarpMap:
      """Build contiguous warp map from anchor_map.
      
      The warp map partitions the human audio into alternating syllable and gap
      segments. Each segment has source timing (human) and target timing (golden).
      
      Invariants:
      - segments[i].source_end == segments[i+1].source_start (contiguous source)
      - segments[i].target_end == segments[i+1].target_start (contiguous target)
      - All source/target samples are non-negative
      """
      sr = anchor_map["sample_rate"]
      strategy = anchor_map["anchor_strategy"]
      anchors = anchor_map["anchors"]
      n = len(anchors)
      
      if guide_total_samples is None:
          if n > 0:
              guide_total_samples = anchors[-1]["guide_end_sample"]
          else:
              guide_total_samples = human_total_samples
      
      segments: list[WarpSegment] = []
      seg_idx = 0
      
      if n == 0:
          segments.append(WarpSegment(
              segment_index=0,
              segment_type="lead_in",
              syllable_index=None,
              source_start_sample=0,
              source_end_sample=human_total_samples,
              target_start_sample=0,
              target_end_sample=guide_total_samples,
          ))
          return WarpMap(
              sample_rate=sr,
              anchor_strategy=strategy,
              total_source_samples=human_total_samples,
              total_target_samples=guide_total_samples,
              segments=segments,
          )
      
      # Lead-in: audio before the first syllable
      first_h_start = anchors[0]["human_start_sample"]
      first_g_start = anchors[0]["guide_start_sample"]
      if first_h_start > 0 or first_g_start > 0:
          segments.append(WarpSegment(
              segment_index=seg_idx,
              segment_type="lead_in",
              syllable_index=None,
              source_start_sample=0,
              source_end_sample=first_h_start,
              target_start_sample=0,
              target_end_sample=first_g_start,
          ))
          seg_idx += 1
      
      for i in range(n):
          a = anchors[i]
          
          # Syllable segment
          segments.append(WarpSegment(
              segment_index=seg_idx,
              segment_type="syllable",
              syllable_index=i,
              source_start_sample=a["human_start_sample"],
              source_end_sample=a["human_end_sample"],
              target_start_sample=a["guide_start_sample"],
              target_end_sample=a["guide_end_sample"],
          ))
          seg_idx += 1
          
          # Gap between this syllable and the next
          if i < n - 1:
              next_a = anchors[i + 1]
              gap_src_start = a["human_end_sample"]
              gap_src_end = next_a["human_start_sample"]
              gap_tgt_start = a["guide_end_sample"]
              gap_tgt_end = next_a["guide_start_sample"]
              
              # Include gap even if zero-length (preserves contiguity)
              segments.append(WarpSegment(
                  segment_index=seg_idx,
                  segment_type="gap",
                  syllable_index=None,
                  source_start_sample=gap_src_start,
                  source_end_sample=gap_src_end,
                  target_start_sample=gap_tgt_start,
                  target_end_sample=gap_tgt_end,
              ))
              seg_idx += 1
      
      # Trail: audio after the last syllable
      last_h_end = anchors[-1]["human_end_sample"]
      last_g_end = anchors[-1]["guide_end_sample"]
      if last_h_end < human_total_samples or last_g_end < guide_total_samples:
          segments.append(WarpSegment(
              segment_index=seg_idx,
              segment_type="trail",
              syllable_index=None,
              source_start_sample=last_h_end,
              source_end_sample=human_total_samples,
              target_start_sample=last_g_end,
              target_end_sample=guide_total_samples,
          ))
      
      return WarpMap(
          sample_rate=sr,
          anchor_strategy=strategy,
          total_source_samples=human_total_samples,
          total_target_samples=guide_total_samples,
          segments=segments,
      )
  
  
  def validate_warp_map(warp_map: WarpMap) -> list[str]:
      """Validate contiguity and non-negativity. Returns list of error strings."""
      errors = []
      for i, seg in enumerate(warp_map.segments):
          if seg.source_start_sample < 0:
              errors.append(f"Segment {i}: negative source_start {seg.source_start_sample}")
          if seg.target_start_sample < 0:
              errors.append(f"Segment {i}: negative target_start {seg.target_start_sample}")
          if seg.source_end_sample < seg.source_start_sample:
              errors.append(f"Segment {i}: source_end < source_start")
          if seg.target_end_sample < seg.target_start_sample:
              errors.append(f"Segment {i}: target_end < target_start")
          if i > 0:
              prev = warp_map.segments[i - 1]
              if seg.source_start_sample != prev.source_end_sample:
                  errors.append(
                      f"Segment {i}: source gap/overlap: prev_end={prev.source_end_sample}, "
                      f"this_start={seg.source_start_sample}"
                  )
              if seg.target_start_sample != prev.target_end_sample:
                  errors.append(
                      f"Segment {i}: target gap/overlap: prev_end={prev.target_end_sample}, "
                      f"this_start={seg.target_start_sample}"
                  )
      return errors
  
  
  def warp_map_to_dict(warp_map: WarpMap) -> dict:
      return {
          "sample_rate": warp_map.sample_rate,
          "anchor_strategy": warp_map.anchor_strategy,
          "total_source_samples": warp_map.total_source_samples,
          "total_target_samples": warp_map.total_target_samples,
          "segment_count": len(warp_map.segments),
          "segments": [
              {
                  "segment_index": s.segment_index,
                  "segment_type": s.segment_type,
                  "syllable_index": s.syllable_index,
                  "source_start_sample": s.source_start_sample,
                  "source_end_sample": s.source_end_sample,
                  "target_start_sample": s.target_start_sample,
                  "target_end_sample": s.target_end_sample,
                  "source_duration": s.source_duration,
                  "target_duration": s.target_duration,
                  "stretch_ratio": s.stretch_ratio,
              }
              for s in warp_map.segments
          ],
      }
  
  
  def warp_map_from_dict(data: dict) -> WarpMap:
      segments = [
          WarpSegment(
              segment_index=s["segment_index"],
              segment_type=s["segment_type"],
              syllable_index=s.get("syllable_index"),
              source_start_sample=s["source_start_sample"],
              source_end_sample=s["source_end_sample"],
              target_start_sample=s["target_start_sample"],
              target_end_sample=s["target_end_sample"],
          )
          for s in data["segments"]
      ]
      return WarpMap(
          sample_rate=data["sample_rate"],
          anchor_strategy=data["anchor_strategy"],
          total_source_samples=data["total_source_samples"],
          total_target_samples=data["total_target_samples"],
          segments=segments,
      )
  ```
- **GOTCHA**: Zero-length gaps (source_duration == 0 AND target_duration == 0) are valid and should be included in the segment list. They preserve the contiguity invariant. The renderer skips them.
- **GOTCHA**: When target gap duration is zero but source gap is positive, the renderer must compress the gap to near-zero. Use a minimum target of 1 sample to avoid division by zero.
- **GOTCHA**: The `guide_total_samples` parameter may not be available in beat-only mode. Default to the last syllable's guide_end_sample.
- **VALIDATE**: `uv run python -c "from rapmap.edit.warp_map import WarpSegment, WarpMap, build_warp_map; print('OK')"`

### Task 8: UPDATE `src/rapmap/audio/render.py` — Add Warp Renderer

Add `render_warp_map()` alongside existing `render_clips()`.

- **IMPLEMENT**: Add function after `render_clips()`:
  ```python
  def render_warp_map(
      warp_map,
      human_audio: np.ndarray,
      sample_rate: int,
      output_dir: Path,
      config: RenderingConfig,
      anchor_map: dict | None = None,
      fail_on_anchor_error: bool = False,
  ) -> dict:
      from rapmap.edit.warp_map import WarpMap, validate_warp_map, warp_map_to_dict
      
      render_dir = output_dir / "render"
      render_dir.mkdir(parents=True, exist_ok=True)
      
      errors = validate_warp_map(warp_map)
      if errors:
          raise ValueError(f"Invalid warp map: {'; '.join(errors)}")
      
      parts: list[np.ndarray] = []
      all_ratios: list[float] = []
      extreme_stretches: list[dict] = []
      syllable_target_starts: dict[int, int] = {}
      
      running_target_sample = 0
      
      for seg in warp_map.segments:
          if seg.source_duration == 0 and seg.target_duration == 0:
              continue
          
          if seg.segment_type == "syllable" and seg.syllable_index is not None:
              syllable_target_starts[seg.syllable_index] = running_target_sample
          
          if seg.source_duration == 0 and seg.target_duration > 0:
              parts.append(np.zeros(seg.target_duration, dtype=np.float32))
              running_target_sample += seg.target_duration
              continue
          
          source = human_audio[seg.source_start_sample : seg.source_end_sample]
          ratio = seg.stretch_ratio
          all_ratios.append(ratio)
          
          if ratio < config.min_stretch_ratio or ratio > config.max_stretch_ratio:
              extreme_stretches.append({
                  "segment_index": seg.segment_index,
                  "segment_type": seg.segment_type,
                  "syllable_index": seg.syllable_index,
                  "ratio": ratio,
              })
          
          if abs(ratio - 1.0) < 1e-6:
              stretched = source.copy()
          else:
              stretched = time_stretch(source, sample_rate, ratio, config.preserve_pitch)
          
          target_len = seg.target_duration
          if len(stretched) > target_len:
              stretched = stretched[:target_len]
          elif len(stretched) < target_len:
              pad = np.zeros(target_len - len(stretched), dtype=np.float32)
              stretched = np.concatenate([stretched, pad])
          
          parts.append(stretched)
          running_target_sample += target_len
      
      if parts:
          output = np.concatenate(parts)
      else:
          output = np.zeros(0, dtype=np.float32)
      
      output_path = render_dir / "corrected_human_rap.wav"
      write_audio(output_path, output, sample_rate)
      
      # Validate zero-sample anchor invariant
      anchor_errors = []
      if anchor_map:
          for a in anchor_map["anchors"]:
              si = a["syllable_index"]
              guide_anchor = a["guide_anchor_sample"]
              target_start = syllable_target_starts.get(si)
              if target_start is None:
                  anchor_errors.append({
                      "syllable_index": si,
                      "guide_anchor": guide_anchor,
                      "error": "syllable not in warp map",
                  })
              elif target_start != a["guide_start_sample"]:
                  anchor_errors.append({
                      "syllable_index": si,
                      "guide_anchor": guide_anchor,
                      "rendered_start": target_start,
                      "expected_start": a["guide_start_sample"],
                      "error_samples": target_start - a["guide_start_sample"],
                  })
      
      if fail_on_anchor_error and anchor_errors:
          errors_str = "; ".join(
              f"syl {e['syllable_index']}: {e.get('error', f'off by {e.get(\"error_samples\", \"?\")}')}"
              for e in anchor_errors
          )
          raise AssertionError(
              f"Zero-sample anchor invariant violated for "
              f"{len(anchor_errors)} syllable(s): {errors_str}"
          )
      
      # Save warp map JSON
      edit_dir = output_dir / "edit"
      edit_dir.mkdir(parents=True, exist_ok=True)
      import json
      with open(edit_dir / "warp_map.json", "w") as f:
          json.dump(warp_map_to_dict(warp_map), f, indent=2)
      
      report = {
          "sample_rate": sample_rate,
          "rendering_mode": "warp",
          "total_segments": len(warp_map.segments),
          "syllable_segments": sum(1 for s in warp_map.segments if s.segment_type == "syllable"),
          "gap_segments": sum(1 for s in warp_map.segments if s.segment_type == "gap"),
          "anchor_errors": anchor_errors,
          "max_stretch_ratio": max(all_ratios) if all_ratios else 1.0,
          "min_stretch_ratio": min(all_ratios) if all_ratios else 1.0,
          "extreme_stretches": extreme_stretches,
          "validation_passed": len(anchor_errors) == 0,
          "output_duration_samples": len(output),
      }
      
      return {"report": report}
  ```
- **IMPORTS**: Add `from rapmap.edit.warp_map import WarpMap` import (but use lazy import inside function to avoid circular imports, as shown above)
- **GOTCHA**: The anchor validation here checks that each syllable segment's target_start matches the expected guide_start_sample. This is simpler than the clip-based validation because segments are contiguous — there's no search needed.
- **GOTCHA**: `running_target_sample` tracks the cumulative output position. For the anchor invariant check, we need to verify that `running_target_sample` at each syllable start equals `guide_start_sample`. But actually, the warp map already has target positions built in — so we compare `seg.target_start_sample` against what it should be.
- **VALIDATE**: `uv run ruff check src/rapmap/audio/render.py`

### Task 9: UPDATE `src/rapmap/cli.py` — Wire Warp Rendering in `run` Command

Add warp rendering path to the full pipeline.

- **IMPLEMENT**: After Phase 6 (edit plan) in the `run` command, add warp rendering:
  ```python
  # Phase 7: Rendering
  click.echo("Phase 7: Rendering")
  human_audio, _ = read_audio(
      out / proj_meta.get("human_analysis_path", proj_meta["human_path"]), mono=True
  )
  
  if config.rendering.rendering_mode == "warp":
      from rapmap.edit.warp_map import build_warp_map, warp_map_to_dict
      
      click.echo("  Mode: warp (contiguous piecewise time-stretch)")
      warp_map = build_warp_map(
          anchor_map, len(human_audio),
          guide_total_samples=None,
      )
      click.echo(f"  Segments: {len(warp_map.segments)} "
                 f"({sum(1 for s in warp_map.segments if s.segment_type == 'syllable')} syllables, "
                 f"{sum(1 for s in warp_map.segments if s.segment_type == 'gap')} gaps)")
      
      from rapmap.audio.render import render_warp_map
      render_result = render_warp_map(
          warp_map, human_audio, sr, out, config.rendering, anchor_map,
          fail_on_anchor_error=config.validation.require_zero_sample_anchor_error,
      )
  else:
      # Existing clip-based rendering path
      render_result = render_clips(
          edit_plan, human_audio, sr, out, config.rendering, anchor_map,
          fail_on_anchor_error=config.validation.require_zero_sample_anchor_error,
      )
  
  render_dir = out / "render"
  render_dir.mkdir(parents=True, exist_ok=True)
  with open(render_dir / "render_report.json", "w") as f:
      json.dump(render_result["report"], f, indent=2)
  passed = render_result["report"]["validation_passed"]
  click.echo(f"  Validation: {'PASSED' if passed else 'FAILED'}")
  ```
- **IMPLEMENT**: Keep the clip-based path (Phases 5-6: grouping + planning) always running — it's needed for Audacity clip export regardless of rendering mode.
- **IMPLEMENT**: Also wire warp rendering into the editor's `render-apply` endpoint in `server.py`, using the same config check.
- **GOTCHA**: The clip manifest is only produced by clip-based rendering. When warp mode is used, the manifest write should be skipped or an empty manifest written.
- **VALIDATE**: `uv run ruff check src/rapmap/cli.py`

### Task 10: CREATE `tests/test_pronunciation_multi.py`

- **IMPLEMENT**: Tests:
  - `test_lookup_all_returns_multiple_for_common_word` — "the" has ≥2 CMUdict entries
  - `test_lookup_all_returns_single_for_override` — override is authoritative
  - `test_lookup_all_g2p_fallback` — unknown word returns single G2P variant
  - `test_dictionary_generation_multi` — verify MFA dictionary has multiple lines for polyphonic words
- **VALIDATE**: `uv run pytest tests/test_pronunciation_multi.py -v`

### Task 11: CREATE `tests/test_phoneme_smoothing.py`

- **IMPLEMENT**: Tests:
  - `test_smooth_merges_short_phone` — 10-sample phone merges into neighbor
  - `test_smooth_preserves_long_phones` — no merging when all phones above threshold
  - `test_smooth_merges_into_longer_neighbor` — verify merge direction is correct
  - `test_smooth_single_phone_unchanged` — single phone list returns as-is
  - `test_smooth_empty_list` — empty list returns empty
- **PATTERN**: Import `PhoneTimestamp` from `rapmap.align.base`, create test phones with explicit sample ranges
- **VALIDATE**: `uv run pytest tests/test_phoneme_smoothing.py -v`

### Task 12: CREATE `tests/test_energy_fallback.py`

- **IMPLEMENT**: Tests:
  - `test_energy_split_matches_syllable_count` — synthetic audio with 2 energy peaks → 2 boundaries
  - `test_energy_split_returns_empty_on_mismatch` — 3 peaks but 2 expected → empty (triggers equal fallback)
  - `test_energy_split_short_audio` — audio shorter than threshold → empty
  - `test_derive_syllables_uses_energy_when_available` — end-to-end: provide audio_data, verify confidence=0.5 in fallback
- **PATTERN**: Generate synthetic audio with `np.sin()` bursts separated by silence to simulate vowels
- **VALIDATE**: `uv run pytest tests/test_energy_fallback.py -v`

### Task 13: CREATE `tests/test_warp_map.py`

- **IMPLEMENT**: Tests:
  - `test_build_warp_map_basic` — 2 syllables with gap → 5 segments (lead_in, syl, gap, syl, trail)
  - `test_build_warp_map_contiguous` — verify `segments[i].source_end == segments[i+1].source_start`
  - `test_build_warp_map_zero_gap` — adjacent syllables → gap with source_duration=0
  - `test_build_warp_map_no_syllables` — empty anchors → single lead_in segment
  - `test_validate_warp_map_catches_gap` — manually break contiguity, verify validation error
  - `test_warp_map_serialization` — round-trip through to_dict/from_dict
  - `test_stretch_ratios` — verify ratios are target_dur/source_dur for each segment type
  - `test_build_warp_map_from_beat_quantize` — use beat-mode anchor_map format (has `source: "beat_grid"`)
- **PATTERN**: Build anchor_map dicts manually (same structure as `test_editor_api.py` fixture)
- **VALIDATE**: `uv run pytest tests/test_warp_map.py -v`

### Task 14: UPDATE `CLAUDE.md`

- **IMPLEMENT**: Add `edit/warp_map.py` to project structure
- **IMPLEMENT**: Add note about warp rendering mode vs clip rendering mode
- **IMPLEMENT**: Update rendering config documentation
- **VALIDATE**: Read CLAUDE.md to verify accuracy

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

### Level 2: Import Verification

```bash
uv run python -c "
from rapmap.config import AlignmentConfig, RenderingConfig
from rapmap.lyrics.pronunciations import lookup_all_pronunciations
from rapmap.align.derive_syllables import derive_syllable_timestamps
from rapmap.edit.warp_map import WarpSegment, WarpMap, build_warp_map, validate_warp_map
from rapmap.audio.render import render_warp_map
print('All imports OK')
"
```

### Level 3: Existing Tests (Regression)

```bash
uv run pytest tests/ -x -q
```

### Level 4: New Tests

```bash
uv run pytest tests/test_pronunciation_multi.py tests/test_phoneme_smoothing.py tests/test_energy_fallback.py tests/test_warp_map.py -v
```

---

## ACCEPTANCE CRITERIA

- [ ] `lookup_all_pronunciations("the")` returns ≥2 variants
- [ ] MFA dictionary generation emits multiple lines for polyphonic words
- [ ] Phoneme smoothing merges phones shorter than configurable threshold
- [ ] Energy-based fallback detects peaks and splits at valleys when peak count matches
- [ ] Energy-based fallback gracefully falls back to equal division when peaks don't match
- [ ] `build_warp_map()` produces contiguous segments (validated by `validate_warp_map()`)
- [ ] `render_warp_map()` produces corrected audio with zero-sample anchor errors
- [ ] `run` command uses warp rendering by default
- [ ] Clip-based rendering still works for Audacity integration
- [ ] All existing tests pass (no regressions)
- [ ] All new tests pass
- [ ] Lint clean

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (1-14)
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully
- [ ] Manual verification confirms task works
- [ ] Acceptance criteria all met
- [ ] Ready for `/commit`

---

## NOTES

### Edge Cases for Warp Map

1. **Zero-length source gap, positive target gap**: Occurs when human syllables are adjacent but guide has space. Renderer inserts silence. This is correct — the guide rhythm has a pause that the human skipped.

2. **Positive source gap, zero-length target gap**: Occurs when guide syllables are adjacent but human has a breath. Renderer must compress gap to near-zero. Use `max(1, target_duration)` to avoid zero-duration stretch. The breath is effectively compressed away.

3. **Very extreme stretch ratios in gaps**: Gap compression/expansion can produce extreme ratios (e.g., 0.05 or 20.0). Gaps are often silence or near-silence, so quality degradation is acceptable. Log a warning but don't fail.

4. **Lead-in / trail segments**: These are the audio before the first syllable and after the last. Their target duration comes from the guide timing. If the guide starts later than the human, the lead-in gets stretched. If it starts earlier, it gets compressed. Same logic as any other segment.

### Why Warp Replaces Clip Grouping for Rendering

The clip-based pipeline (grouping → planning → rendering) was designed for Audacity integration where you want discrete clip files. The warp model is simpler and produces smoother results because:
- No splice points between clips (no crossfades needed)
- Gaps preserve natural transitions
- The entire audio is processed as one continuous stream
- The output is a single corrected vocal file

Both models coexist: warp for the corrected vocal, clips for Audacity visual editing.

### Performance

Warp rendering calls `time_stretch()` (rubberband CLI subprocess) per segment. For a typical track with ~100 syllables, that's ~200 segments (syllables + gaps). At ~50ms per rubberband call, total rendering time is ~10s. This is acceptable for an offline tool. Future optimization: batch adjacent segments with similar ratios, or use rubberband's library API.
