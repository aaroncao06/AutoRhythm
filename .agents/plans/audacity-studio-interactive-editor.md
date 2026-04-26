# Task: Audacity Studio Companion + Interactive Syllable Editor + Beat-Only Mode

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files etc.

## Task Description

Build a companion application for Audacity that makes RapMap usable without leaving the DAW. The user records in Audacity, clicks buttons in our companion panel, and corrected clips appear back in Audacity. Includes:

1. **Beat detection module** — extract BPM + beat grid from the backing track, enabling a "beat-only" correction mode that doesn't require an AI guide vocal at all.
2. **PyQt companion panel** — a small desktop window that connects to Audacity via mod-script-pipe and provides push-button access to each pipeline phase.
3. **Interactive syllable editor** — a PyQt window with waveform display, beat grid overlay, and draggable syllable blocks for manual timing adjustment after the auto-correction draft.

### Why this architecture

Audacity macros and Nyquist plugins **cannot** call external programs (sandboxed). mod-script-pipe is one-directional: Python drives Audacity, not the reverse. Therefore our Python app must be the orchestrator. The user runs `rapmap studio`, which launches a PyQt companion window alongside Audacity. The companion reads/writes Audacity's tracks via pipe commands.

## Task Metadata

**Task Type**: Code Change / Infrastructure
**Estimated Complexity**: High
**Primary Systems Affected**: `src/rapmap/audacity/`, `src/rapmap/beat/` (new), `src/rapmap/editor/` (new), `src/rapmap/cli.py`, `src/rapmap/config.py`, `pyproject.toml`
**Dependencies**: PyQt6, librosa, sounddevice, pyqtgraph
**Supports Claim/Hypothesis**: Extends the pipeline from CLI-only to an interactive Audacity-integrated workflow; adds beat-only mode (no AI guide required)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/rapmap/audacity/script_pipe.py` (lines 1-91) — Existing AudacityPipe class. All pipe communication goes through here. Must extend with new commands (GetInfo, Export2, SelectTime, SelectTracks, Play/Stop).
- `src/rapmap/audacity/import_project.py` (lines 1-86) — Current session builder. Pattern for how pipe commands are chained.
- `src/rapmap/audacity/labels.py` (lines 1-104) — Label generation. The interactive editor must consume and produce the same format.
- `src/rapmap/edit/operations.py` (lines 1-108) — Segment/EditPlan dataclasses. The interactive editor modifies target_start/end_sample on these.
- `src/rapmap/edit/planner.py` (lines 1-84) — Creates EditPlan from clip_groups + anchor_map. Beat-only mode generates a synthetic anchor_map, then this planner works unchanged.
- `src/rapmap/audio/render.py` (lines 1-186) — render_clips function. Unchanged — consumes EditPlan regardless of how anchors were generated.
- `src/rapmap/config.py` (lines 1-141) — All config dataclasses. Add BeatDetectionConfig, EditorConfig.
- `src/rapmap/cli.py` — CLI entry. Add `detect-beats`, `editor`, `studio` commands.
- `src/rapmap/timing/anchor_map.py` — build_anchor_map from guide+human alignments. Beat-only mode creates an alternative anchor_map without a guide.
- `pyproject.toml` — Dependencies. Add new optional dependency groups.

### New Files to Create

```
src/rapmap/beat/
├── __init__.py
├── detect.py          # BPM + beat frame extraction (librosa)
├── grid.py            # Beat grid generation (subdivisions)
└── quantize.py        # Snap syllable anchors to beat grid

src/rapmap/editor/
├── __init__.py
├── app.py             # PyQt QApplication bootstrap
├── waveform.py        # Waveform display widget (pyqtgraph)
├── beat_grid.py       # Beat grid overlay lines
├── syllable_blocks.py # Draggable syllable region items
├── timeline.py        # Composite timeline widget (waveform + grid + blocks)
├── preview.py         # Real-time audio preview (sounddevice)
└── state.py           # Editor state: loads/saves EditPlan JSON

src/rapmap/studio/
├── __init__.py
├── panel.py           # Main companion window (buttons, status)
├── audacity_bridge.py # Enhanced Audacity communication (export, track query)
└── worker.py          # QThread workers for pipeline phases

tests/
├── test_beat_detection.py
├── test_beat_quantize.py
└── test_editor_state.py
```

### Relevant Documentation — READ BEFORE IMPLEMENTING

- Audacity Scripting Reference: https://manual.audacityteam.org/man/scripting_reference.html
  - Specific section: Full command list — Import2, Export2, GetInfo, SelectTime, SetTrack, Play/Stop
  - Why: All Audacity communication uses these exact command strings

- librosa beat tracking: https://librosa.org/doc/latest/generated/librosa.beat.beat_track.html
  - Why: Core beat detection function

- librosa onset detection: https://librosa.org/doc/latest/generated/librosa.onset.onset_detect.html
  - Why: Fallback for songs with complex rhythms

- PyQt6 Graphics View: https://doc.qt.io/qt-6/graphicsview.html
  - Why: QGraphicsView + QGraphicsScene is the framework for the interactive editor (waveform + draggable items)

- pyqtgraph PlotWidget: https://pyqtgraph.readthedocs.io/en/latest/api_reference/widgets/plotwidget.html
  - Why: Fast waveform rendering, much faster than matplotlib for real-time

- sounddevice play/stop: https://python-sounddevice.readthedocs.io/en/latest/#playback
  - Why: Real-time audio preview in the editor

- pipeclient.py (Steve Daulton's canonical reference for mod-script-pipe): https://github.com/audacity/audacity/blob/master/scripts/piped-work/pipeclient.py
  - Why: Reference implementation for robust pipe communication

### Patterns to Follow

**Config Pattern** (from `config.py`):
```python
@dataclass
class BeatDetectionConfig:
    backend: str = "librosa"
    subdivision: str = "eighth"       # quarter, eighth, sixteenth
    quantize_strength: float = 1.0    # 0.0=no snap, 1.0=full snap
    min_bpm: int = 60
    max_bpm: int = 200
```

**Pipe Command Pattern** (from `script_pipe.py:50-52`):
```python
def import_audio(self, path: Path) -> bool:
    resp = self.send(f'Import2: Filename="{path}"')
    return "OK" in resp
```

**CLI Command Pattern** (from `cli.py`):
```python
@main.command()
@click.option("--project", type=click.Path(exists=True), required=True)
def command_name(project):
    ...
```

**JSON Serialization Pattern** (from `operations.py:47-76`):
All intermediate data serialized to JSON in the project workdir. The editor loads/saves the same format.

**Integer Sample Pattern** (from CLAUDE.md):
All internal timing uses integer sample indices at 48kHz. Never float seconds except for Audacity label export.

---

## IMPLEMENTATION PLAN

### Phase 1: Beat Detection Module

Add beat/BPM analysis for the backing track. This enables "beat-only" mode where syllable timing targets come from the beat grid instead of an AI guide.

**Tasks:**
- Create `src/rapmap/beat/detect.py` — librosa-based BPM and beat frame extraction
- Create `src/rapmap/beat/grid.py` — generate beat grid at configurable subdivisions (quarter, eighth, sixteenth note)
- Create `src/rapmap/beat/quantize.py` — snap syllable anchors to nearest beat grid position, with configurable strength
- Add `BeatDetectionConfig` to `config.py`
- Add `detect-beats` CLI command
- Add beat-only anchor map generation (synthetic anchor_map from beat grid + human alignment, no guide needed)

### Phase 2: Interactive Syllable Editor

A PyQt window for manual timing adjustment. Shows waveform with beat grid lines and draggable syllable blocks.

**Tasks:**
- Create editor PyQt app shell (`editor/app.py`)
- Waveform rendering widget using pyqtgraph (`editor/waveform.py`)
- Beat grid overlay as vertical lines on the waveform (`editor/beat_grid.py`)
- Syllable blocks as draggable rectangular regions (`editor/syllable_blocks.py`)
- Composite timeline widget assembling waveform + grid + blocks (`editor/timeline.py`)
- Audio preview engine using sounddevice (`editor/preview.py`)
- Editor state management — loads EditPlan + anchor_map JSON, saves modified timing back (`editor/state.py`)
- Add `editor` CLI command that launches the PyQt window
- Snap-to-grid behavior: blocks snap to nearest beat grid line when released
- Quantize strength slider: 0% (free drag) to 100% (hard snap)

### Phase 3: Audacity Studio Companion

A PyQt companion panel that connects to Audacity and provides buttons for each pipeline step.

**Tasks:**
- Create `studio/panel.py` — main companion window with buttons and status display
- Create `studio/audacity_bridge.py` — enhanced pipe communication (GetInfo for track listing, Export2 for grabbing audio, Play/Stop for preview)
- Create `studio/worker.py` — QThread workers so pipeline phases don't freeze the UI
- Extend `AudacityPipe` with new commands: `get_tracks()`, `export_track()`, `select_time()`, `play()`, `stop()`
- Add `studio` CLI command that launches the companion
- Wire companion buttons to pipeline phases:
  1. "Grab Audio" — exports vocal + backing from Audacity tracks
  2. "Set Lyrics" — file dialog or text entry
  3. "Detect Beats" — runs beat detection on backing
  4. "Syllabify" — runs syllable detection
  5. "Align" — runs forced alignment
  6. "Auto-Correct" — runs anchor mapping + edit plan + render
  7. "Edit Timing" — opens interactive editor window
  8. "Apply to Audacity" — imports corrected clips back into Audacity

### Phase 4: Integration & Testing

- Tests for beat detection (known BPM WAVs)
- Tests for quantize logic (snap positions, strength interpolation)
- Tests for editor state (load/save round-trip)
- Integration test: companion → pipeline → editor → apply
- Update CLAUDE.md with new commands and module descriptions

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `src/rapmap/beat/__init__.py`

- **IMPLEMENT**: Empty init file for the beat detection package
- **VALIDATE**: `python -c "import rapmap.beat"`

---

### Task 2: CONFIG `src/rapmap/config.py` — Add BeatDetectionConfig and EditorConfig

- **IMPLEMENT**: Add two new dataclasses:
  ```python
  @dataclass
  class BeatDetectionConfig:
      backend: str = "librosa"
      subdivision: str = "eighth"
      quantize_strength: float = 1.0
      min_bpm: int = 60
      max_bpm: int = 200
      units_per_beat: int = 2  # 1=quarter, 2=eighth, 4=sixteenth
      hop_length: int = 512

  @dataclass
  class EditorConfig:
      waveform_color: str = "#2196F3"
      beat_grid_color: str = "#FF5722"
      syllable_block_color: str = "#4CAF50"
      snap_to_grid: bool = True
      preview_buffer_ms: int = 200
      default_zoom_seconds: float = 10.0
  ```
- **IMPLEMENT**: Add both to `RapMapConfig`:
  ```python
  beat_detection: BeatDetectionConfig = field(default_factory=BeatDetectionConfig)
  editor: EditorConfig = field(default_factory=EditorConfig)
  ```
- **PATTERN**: `src/rapmap/config.py` lines 11-114 — follows existing dataclass pattern
- **VALIDATE**: `uv run python -c "from rapmap.config import RapMapConfig; c = RapMapConfig(); print(c.beat_detection.subdivision)"`

---

### Task 3: CREATE `src/rapmap/beat/detect.py` — BPM and beat frame extraction

- **IMPLEMENT**:
  ```python
  def detect_beats(audio: np.ndarray, sample_rate: int, config: BeatDetectionConfig) -> dict:
  ```
  - Use `librosa.beat.beat_track(y=audio, sr=sample_rate, hop_length=config.hop_length)` to get BPM and beat frames
  - Convert beat frames to integer sample indices: `beat_samples = librosa.frames_to_samples(beat_frames, hop_length=config.hop_length)`
  - Return dict:
    ```python
    {
        "bpm": float,
        "beat_samples": list[int],    # sample indices of each beat
        "sample_rate": int,
        "hop_length": int,
        "total_beats": int,
    }
    ```
  - Assert all beat_samples are non-negative integers
  - Assert beats are monotonically increasing
- **IMPORTS**: `numpy`, `librosa`
- **GOTCHA**: librosa returns beat frames as frame indices, not sample indices. Must convert with `librosa.frames_to_samples()`. Also, librosa returns numpy int types — cast to Python `int` for JSON serialization.
- **VALIDATE**: `uv run python -c "from rapmap.beat.detect import detect_beats; print('OK')"`

---

### Task 4: CREATE `src/rapmap/beat/grid.py` — Beat grid subdivision

- **IMPLEMENT**:
  ```python
  def build_beat_grid(beat_info: dict, subdivision: str, total_duration_samples: int) -> dict:
  ```
  - Takes the output of `detect_beats` + a subdivision level
  - Subdivisions: `"quarter"` (1 per beat), `"eighth"` (2 per beat), `"sixteenth"` (4 per beat), `"triplet"` (3 per beat)
  - Interpolates between beat positions to create subdivision grid lines
  - For each pair of adjacent beats, compute subdivision positions by equal division:
    ```python
    for i in range(len(beats) - 1):
        span = beats[i+1] - beats[i]
        for s in range(units_per_beat):
            grid_sample = beats[i] + int(round(span * s / units_per_beat))
            grid_positions.append(grid_sample)
    ```
  - Return dict:
    ```python
    {
        "bpm": float,
        "subdivision": str,
        "units_per_beat": int,
        "grid_samples": list[int],   # every grid line as sample index
        "beat_samples": list[int],    # just the main beats (for visual emphasis)
        "sample_rate": int,
    }
    ```
  - Assert grid_samples are monotonic and unique
- **PATTERN**: All timing as integer sample indices (CLAUDE.md rule)
- **VALIDATE**: `uv run pytest tests/test_beat_detection.py -v` (after Task 9)

---

### Task 5: CREATE `src/rapmap/beat/quantize.py` — Snap syllable anchors to beat grid

- **IMPLEMENT**:
  ```python
  def quantize_anchors(
      human_alignment: AlignmentResult,
      beat_grid: dict,
      config: BeatDetectionConfig,
  ) -> dict:
  ```
  - For each syllable in human_alignment:
    - Find the nearest grid position to the syllable's anchor sample
    - Apply quantize strength: `target = human_anchor + int(round((nearest_grid - human_anchor) * config.quantize_strength))`
    - If strength=1.0, target=nearest_grid. If strength=0.0, target=human_anchor (no change).
  - Build an anchor_map dict in the **exact same format** as `build_anchor_map()` in `timing/anchor_map.py` produces:
    ```python
    {
        "sample_rate": int,
        "anchor_strategy": "onset",
        "syllable_count": int,
        "source": "beat_grid",  # distinguishes from guide-based
        "bpm": float,
        "subdivision": str,
        "quantize_strength": float,
        "anchors": [
            {
                "syllable_index": int,
                "human_anchor_sample": int,
                "guide_anchor_sample": int,   # repurposed: the beat grid target
                "human_start_sample": int,
                "human_end_sample": int,
                "guide_start_sample": int,    # same as guide_anchor_sample
                "guide_end_sample": int,      # human_end offset by same delta
                "delta_samples": int,
                "confidence": 1.0,
            },
            ...
        ]
    }
    ```
  - **CRITICAL**: The output must be a valid anchor_map that `create_edit_plan()` in `edit/planner.py` can consume without modification. This means using the same field names (`guide_anchor_sample`, `human_anchor_sample`, etc.) even though there is no AI guide — the "guide" fields hold beat-grid target positions.
  - Assert anchors are monotonically ordered by `guide_anchor_sample`
  - Assert no two syllables map to the same target position (warn if they do, resolve by offsetting later syllable by 1 subdivision)
- **IMPORTS**: `numpy`, `rapmap.align.base.AlignmentResult`
- **GOTCHA**: The reuse of "guide_*" field names is intentional — the entire downstream pipeline (planner, renderer, validator) reads these fields. Renaming would require changes everywhere. The `"source": "beat_grid"` field disambiguates.
- **VALIDATE**: `uv run pytest tests/test_beat_quantize.py -v` (after Task 10)

---

### Task 6: UPDATE `src/rapmap/cli.py` — Add `detect-beats` command

- **IMPLEMENT**: New CLI command:
  ```python
  @main.command("detect-beats")
  @click.option("--project", type=click.Path(exists=True), required=True)
  @click.option("--subdivision", type=click.Choice(["quarter", "eighth", "sixteenth", "triplet"]), default="eighth")
  @click.option("--strength", type=float, default=1.0)
  @click.option("--config", "config_path", type=click.Path(), default=None)
  def detect_beats_cmd(project, subdivision, strength, config_path):
  ```
  - Loads backing audio from `{project}/audio/backing.wav`
  - Runs `detect_beats()` → `build_beat_grid()` → saves to `{project}/timing/beat_grid.json`
  - If human alignment exists at `{project}/alignment/human_alignment.json`:
    - Runs `quantize_anchors()` → saves to `{project}/timing/anchor_map.json` (same path as guide-based anchor map, since only one is used at a time)
  - Prints BPM, beat count, grid positions count
- **PATTERN**: `src/rapmap/cli.py` lines 189-232 — `anchors` command pattern
- **VALIDATE**: `ruff check src/rapmap/cli.py`

---

### Task 7: UPDATE `src/rapmap/cli.py` — Add `--mode` to `run` command

- **IMPLEMENT**: Add `--mode` option to the `run` command:
  ```python
  @click.option("--mode", type=click.Choice(["guide", "beat-only"]), default="guide")
  ```
  - `guide` mode: existing behavior (requires AI guide vocal)
  - `beat-only` mode: skips guide generation/alignment, runs detect-beats + quantize instead
  - In beat-only mode:
    1. Phase 0: normalize (same)
    2. Phase 2: syllabify (same)
    3. Phase 3: align human only (skip guide alignment)
    4. Phase 4: detect-beats + quantize_anchors (replaces anchor map from guide)
    5. Phases 5-8: same (clip grouping, edit plan, render, audacity)
- **PATTERN**: `src/rapmap/cli.py` lines 380-536 — existing `run` command
- **GOTCHA**: In beat-only mode, the clip_groups step still needs `source_start/end_sample` (from human alignment) and `target_start/end_sample` (from beat-quantized anchor map). The grouping function `group_syllables()` in `edit/grouping.py` takes the anchor_map and human_alignment — verify it works with beat-grid anchor_map format.
- **VALIDATE**: `ruff check src/rapmap/cli.py`

---

### Task 8: UPDATE `pyproject.toml` — Add new dependencies

- **IMPLEMENT**: Add new optional dependency groups:
  ```toml
  [project.optional-dependencies]
  beat = [
      "librosa>=0.10",
  ]
  editor = [
      "PyQt6>=6.5",
      "pyqtgraph>=0.13",
      "sounddevice>=0.4",
  ]
  studio = [
      "PyQt6>=6.5",
      "sounddevice>=0.4",
  ]
  ```
  Also add a convenience `all` group:
  ```toml
  all = [
      "rapmap[align,guide,beat,editor,studio,dev]",
  ]
  ```
- **PATTERN**: `pyproject.toml` lines 17-27 — existing optional groups
- **VALIDATE**: `uv sync --extra beat --extra editor --extra studio --extra dev`

---

### Task 9: CREATE `tests/test_beat_detection.py`

- **IMPLEMENT**:
  - `test_detect_beats_click_track()` — generate a synthetic click track (impulses at known BPM), verify detected BPM within 1% and beat positions within 1 hop_length
  - `test_beat_grid_subdivisions()` — given known beat positions, verify eighth note grid has 2x the positions, sixteenth has 4x
  - `test_beat_grid_monotonic()` — verify all grid positions are strictly increasing
  - `test_detect_beats_returns_integer_samples()` — verify all beat_samples are Python `int`
- **IMPORTS**: `numpy`, `rapmap.beat.detect`, `rapmap.beat.grid`, `rapmap.config.BeatDetectionConfig`
- **GOTCHA**: Generate test audio with numpy, don't depend on external WAV files. A click track: silence with impulses at exact intervals.
- **VALIDATE**: `uv run pytest tests/test_beat_detection.py -v`

---

### Task 10: CREATE `tests/test_beat_quantize.py`

- **IMPLEMENT**:
  - `test_quantize_snaps_to_nearest_grid()` — syllable at sample 1050, grid at [1000, 2000], strength=1.0 → target=1000
  - `test_quantize_strength_interpolation()` — syllable at 1000, nearest grid at 1200, strength=0.5 → target=1100
  - `test_quantize_strength_zero_is_identity()` — strength=0.0 → target=human_anchor
  - `test_quantize_produces_valid_anchor_map()` — verify output has all required fields and is consumable by `create_edit_plan()`
  - `test_quantize_monotonic_anchors()` — verify output anchors ordered by guide_anchor_sample
  - `test_quantize_no_duplicate_targets()` — two syllables near same grid line get different targets
- **IMPORTS**: `numpy`, `rapmap.beat.quantize`, `rapmap.align.base.AlignmentResult`, `rapmap.align.base.SyllableTimestamp`, `rapmap.config.BeatDetectionConfig`
- **VALIDATE**: `uv run pytest tests/test_beat_quantize.py -v`

---

### Task 11: CREATE `src/rapmap/editor/__init__.py`

- **IMPLEMENT**: Empty init file
- **VALIDATE**: `python -c "import rapmap.editor"`

---

### Task 12: CREATE `src/rapmap/editor/state.py` — Editor state management

- **IMPLEMENT**:
  ```python
  @dataclass
  class EditorState:
      sample_rate: int
      backing_audio: np.ndarray          # backing track waveform
      human_audio: np.ndarray            # human vocal waveform
      beat_grid: dict                     # from beat detection
      anchor_map: dict                    # current anchor positions (mutable)
      canonical_syllables: dict           # syllable text/metadata
      edit_plan: EditPlan | None = None   # generated after editing

  def load_editor_state(project_dir: Path) -> EditorState:
      """Load all project data needed for the interactive editor."""

  def save_anchor_map(state: EditorState, project_dir: Path) -> Path:
      """Save the modified anchor_map back to project dir."""

  def update_syllable_target(state: EditorState, syllable_index: int, new_target_sample: int) -> None:
      """Move a syllable's target to a new position. Updates anchor_map in place."""
  ```
  - `load_editor_state` reads: `audio/backing.wav`, `audio/human_rap.wav`, `timing/beat_grid.json`, `timing/anchor_map.json`, `lyrics/canonical_syllables.json`
  - `update_syllable_target` modifies the anchor at `syllable_index`: sets `guide_anchor_sample = new_target_sample`, recomputes `delta_samples`, updates `guide_start_sample`/`guide_end_sample` proportionally
  - Validates monotonicity after each move (raises ValueError if move would create non-monotonic anchors)
- **IMPORTS**: `numpy`, `json`, `pathlib.Path`, `rapmap.audio.io.read_audio`, `rapmap.edit.operations.EditPlan`
- **PATTERN**: JSON load/save pattern from `audacity/import_project.py` lines 74-85
- **VALIDATE**: `uv run pytest tests/test_editor_state.py -v` (after Task 19)

---

### Task 13: CREATE `src/rapmap/editor/waveform.py` — Waveform display widget

- **IMPLEMENT**:
  ```python
  class WaveformWidget(pg.PlotWidget):
      """Displays an audio waveform as a fast line plot."""
      def __init__(self, parent=None):
          ...
      def set_audio(self, audio: np.ndarray, sample_rate: int):
          """Load audio data. Downsamples for display performance."""
      def set_view_range(self, start_sample: int, end_sample: int):
          """Zoom to a specific sample range."""
  ```
  - Downsample waveform for display: at typical zoom levels, display ~2000 points per screen width (take min/max envelope per block)
  - X axis in samples (integer), Y axis in amplitude [-1, 1]
  - Color from `EditorConfig.waveform_color`
- **IMPORTS**: `pyqtgraph as pg`, `numpy`
- **GOTCHA**: Raw waveform at 48kHz for a 3-minute song = 8.6M samples. Must downsample for rendering. Use min/max envelope: for each display pixel, show the min and max sample values as a filled region. This is the standard approach for audio waveform display.
- **VALIDATE**: Manual — launch with test audio and verify waveform renders

---

### Task 14: CREATE `src/rapmap/editor/beat_grid.py` — Beat grid overlay

- **IMPLEMENT**:
  ```python
  class BeatGridOverlay:
      """Draws vertical lines on a pyqtgraph PlotWidget at beat grid positions."""
      def __init__(self, plot_widget: pg.PlotWidget):
          ...
      def set_grid(self, beat_grid: dict):
          """Set grid positions. Draws main beats as thick lines, subdivisions as thin."""
      def set_visible(self, visible: bool):
          ...
  ```
  - Main beats (from `beat_grid["beat_samples"]`): thick lines, full opacity
  - Subdivision grid (from `beat_grid["grid_samples"]`): thin lines, 40% opacity
  - Uses `pg.InfiniteLine(pos=sample, angle=90, pen=...)` for each grid line
  - Only render lines visible in current viewport (performance)
- **IMPORTS**: `pyqtgraph as pg`
- **GOTCHA**: For a 3-minute song at eighth-note subdivision at 120 BPM = ~720 grid lines. InfiniteLine items are lightweight but still need viewport culling for zoom.
- **VALIDATE**: Manual — launch editor, verify grid lines visible and aligned to beats

---

### Task 15: CREATE `src/rapmap/editor/syllable_blocks.py` — Draggable syllable regions

- **IMPLEMENT**:
  ```python
  class SyllableBlock(pg.LinearRegionItem):
      """A draggable region representing one syllable's target timing."""
      syllable_index: int
      moved = Signal(int, int)  # emits (syllable_index, new_center_sample)

      def __init__(self, syllable_index: int, start_sample: int, end_sample: int, text: str, ...):
          ...

  class SyllableBlockManager:
      """Manages all syllable blocks on a timeline."""
      def __init__(self, plot_widget: pg.PlotWidget, snap_to_grid: bool = True):
          ...
      def set_syllables(self, anchor_map: dict, canonical: dict):
          """Create blocks from anchor map data."""
      def set_beat_grid(self, grid_samples: list[int]):
          """Set grid positions for snapping."""
      def on_block_moved(self, syllable_index: int, new_center: int):
          """Handle block drag. Snaps to grid if enabled."""
  ```
  - Each block is a `LinearRegionItem` (shows as a colored horizontal band on the waveform)
  - Block label shows syllable text (e.g., "mon-" from "money")
  - On drag release: snap center to nearest grid position (if snap enabled), emit signal with new position
  - Blocks cannot overlap — if dragging would overlap neighbor, clamp to neighbor's edge
  - Color from `EditorConfig.syllable_block_color`, selected block highlighted differently
- **IMPORTS**: `pyqtgraph as pg`, `PyQt6.QtCore.pyqtSignal`
- **GOTCHA**: `LinearRegionItem` allows dragging both edges and the whole region. We want the whole region to move together (preserving duration) when dragged, but allow edge dragging too for advanced users who want to change duration. Override `mouseDragEvent` or use `setMovable(True)`.
- **VALIDATE**: Manual — launch editor, verify blocks are visible, draggable, and snap to grid

---

### Task 16: CREATE `src/rapmap/editor/preview.py` — Audio preview

- **IMPLEMENT**:
  ```python
  class AudioPreview:
      """Plays audio segments using sounddevice for real-time preview."""
      def __init__(self, sample_rate: int):
          ...
      def play_range(self, audio: np.ndarray, start_sample: int, end_sample: int):
          """Play a segment of audio."""
      def play_with_correction(self, human_audio: np.ndarray, edit_plan: EditPlan):
          """Play the corrected version (stretched/shifted) in real-time."""
      def stop(self):
          ...
      @property
      def is_playing(self) -> bool:
          ...
  ```
  - Uses `sounddevice.play()` for simple playback
  - For corrected preview: pre-render the affected region using the same stretch logic as `render_clips`, play the result
  - Non-blocking — runs on sounddevice's internal callback thread
- **IMPORTS**: `sounddevice`, `numpy`
- **GOTCHA**: sounddevice requires PortAudio to be installed. On macOS it's bundled; on Linux may need `sudo apt install libportaudio2`. Note this in install instructions.
- **VALIDATE**: Manual — play test audio through speakers/headphones

---

### Task 17: CREATE `src/rapmap/editor/timeline.py` — Composite timeline widget

- **IMPLEMENT**:
  ```python
  class TimelineWidget(QWidget):
      """Main editor widget: waveform + beat grid + syllable blocks + controls."""
      def __init__(self, state: EditorState, config: EditorConfig, parent=None):
          ...
      def _setup_ui(self):
          """Layout: toolbar on top, waveform in center, controls on bottom."""
      def _on_syllable_moved(self, syllable_index: int, new_target_sample: int):
          """Handle syllable drag: update state, refresh display."""
      def _on_play_clicked(self):
          """Play original or corrected audio."""
      def _on_save_clicked(self):
          """Save modified anchor_map to project dir."""
  ```
  - Toolbar: Play Original, Play Corrected, Zoom In/Out, Snap Toggle, Quantize Strength slider
  - Waveform panel: stacked — backing track (top, muted color) + human vocal (bottom, bright color)
  - Beat grid overlay on both waveform panels
  - Syllable blocks on the human vocal panel
  - Bottom: status bar showing BPM, current syllable info, total syllables
- **IMPORTS**: `PyQt6.QtWidgets`, `pyqtgraph`, editor submodules
- **VALIDATE**: Manual — launch full editor window, verify all components render

---

### Task 18: CREATE `src/rapmap/editor/app.py` — PyQt app bootstrap

- **IMPLEMENT**:
  ```python
  def launch_editor(project_dir: Path, config: RapMapConfig) -> None:
      """Launch the interactive syllable editor."""
      app = QApplication.instance() or QApplication(sys.argv)
      state = load_editor_state(project_dir)
      window = QMainWindow()
      window.setWindowTitle(f"RapMap Editor — {project_dir.name}")
      window.setCentralWidget(TimelineWidget(state, config.editor))
      window.resize(1200, 600)
      window.show()
      if not QApplication.instance()._in_exec:
          app.exec()
  ```
  - Handles case where QApplication already exists (launched from studio panel)
  - Sets window icon, minimum size
  - Connects window close to cleanup (stop audio preview)
- **IMPORTS**: `PyQt6.QtWidgets`, `sys`, `pathlib.Path`, editor submodules
- **VALIDATE**: `uv run rapmap editor --project <test_workdir>` (manual)

---

### Task 19: CREATE `tests/test_editor_state.py`

- **IMPLEMENT**:
  - `test_update_syllable_target()` — move syllable to new position, verify anchor_map updated
  - `test_update_syllable_preserves_duration()` — moving a syllable changes start but preserves duration
  - `test_update_syllable_rejects_non_monotonic()` — moving syl 1 before syl 0 raises ValueError
  - `test_save_load_round_trip()` — save modified state, reload, verify changes persisted
- **IMPORTS**: `rapmap.editor.state`, `rapmap.config`, `json`, `numpy`, `tmp_path` fixture
- **VALIDATE**: `uv run pytest tests/test_editor_state.py -v`

---

### Task 20: UPDATE `src/rapmap/cli.py` — Add `editor` command

- **IMPLEMENT**:
  ```python
  @main.command()
  @click.option("--project", type=click.Path(exists=True), required=True)
  @click.option("--config", "config_path", type=click.Path(), default=None)
  def editor(project, config_path):
      """Launch interactive syllable timing editor."""
      from rapmap.editor.app import launch_editor
      config = load_config(Path(config_path) if config_path else None)
      launch_editor(Path(project), config)
  ```
- **PATTERN**: `src/rapmap/cli.py` — existing command pattern
- **GOTCHA**: Import PyQt6 lazily (inside function) so CLI doesn't require it for non-editor commands
- **VALIDATE**: `ruff check src/rapmap/cli.py`

---

### Task 21: CREATE `src/rapmap/studio/__init__.py`

- **IMPLEMENT**: Empty init file
- **VALIDATE**: `python -c "import rapmap.studio"`

---

### Task 22: UPDATE `src/rapmap/audacity/script_pipe.py` — Add new pipe commands

- **IMPLEMENT**: Add methods to `AudacityPipe`:
  ```python
  def get_tracks(self) -> list[dict]:
      """Query all tracks in Audacity. Returns parsed JSON."""
      resp = self.send('GetInfo: Type=Tracks Format=JSON')
      # Parse JSON from response (strip BatchCommand footer)
      ...

  def export_audio(self, path: Path, num_channels: int = 1) -> bool:
      """Export current selection or full project to a file."""
      resp = self.send(f'Export2: Filename="{path}" NumChannels={num_channels}')
      return "OK" in resp

  def select_tracks(self, track: int, count: int = 1) -> bool:
      resp = self.send(f'SelectTracks: Track={track} TrackCount={count} Mode=Set')
      return "OK" in resp

  def select_time(self, start_sec: float, end_sec: float) -> bool:
      resp = self.send(f'SelectTime: Start={start_sec} End={end_sec} RelativeTo=ProjectStart')
      return "OK" in resp

  def select_all(self) -> bool:
      resp = self.send('SelectAll:')
      return "OK" in resp

  def play(self) -> bool:
      resp = self.send('Play:')
      return "OK" in resp

  def stop(self) -> bool:
      resp = self.send('Stop:')
      return "OK" in resp

  def get_info_json(self, info_type: str) -> list | dict:
      """Generic GetInfo query. Parses JSON response."""
      resp = self.send(f'GetInfo: Type={info_type} Format=JSON')
      # Extract JSON between first '[' or '{' and the BatchCommand footer
      ...
  ```
- **PATTERN**: `src/rapmap/audacity/script_pipe.py` lines 50-64 — existing command methods
- **GOTCHA**: Response from GetInfo contains JSON followed by "BatchCommand finished: OK". Must strip the footer before JSON parsing. Parse from the first `[` or `{` to the last `]` or `}`.
- **VALIDATE**: `ruff check src/rapmap/audacity/script_pipe.py`

---

### Task 23: CREATE `src/rapmap/studio/audacity_bridge.py` — Enhanced Audacity communication

- **IMPLEMENT**:
  ```python
  class AudacityBridge:
      """High-level Audacity integration for the studio companion."""
      def __init__(self):
          self.pipe = AudacityPipe()
          self._connected = False

      def connect(self) -> bool:
          ...

      def identify_tracks(self) -> dict:
          """Query Audacity tracks and classify them (backing, vocal, etc.)"""
          tracks = self.pipe.get_tracks()
          # Heuristic: first stereo track = backing, first mono track = vocal
          # Or match by track name if user has named them
          ...

      def export_track(self, track_index: int, output_path: Path) -> bool:
          """Solo a track, export it, then unsolo."""
          self.pipe.select_tracks(track_index)
          self.pipe.send(f'SetTrack: Track={track_index} Solo=1')
          self.pipe.select_all()
          result = self.pipe.export_audio(output_path)
          self.pipe.send(f'SetTrack: Track={track_index} Solo=0')
          return result

      def import_corrected(self, project_dir: Path) -> bool:
          """Import corrected clips and labels back into Audacity."""
          # Uses existing build_audacity_session logic
          ...
  ```
- **IMPORTS**: `rapmap.audacity.script_pipe.AudacityPipe`, `pathlib.Path`
- **VALIDATE**: `ruff check src/rapmap/studio/audacity_bridge.py`

---

### Task 24: CREATE `src/rapmap/studio/worker.py` — Background pipeline workers

- **IMPLEMENT**:
  ```python
  class PipelineWorker(QThread):
      """Runs a pipeline phase in a background thread so the UI stays responsive."""
      phase_started = pyqtSignal(str)      # phase name
      phase_completed = pyqtSignal(str, dict)  # phase name, result dict
      phase_failed = pyqtSignal(str, str)  # phase name, error message

      def __init__(self, phase: str, project_dir: Path, config: RapMapConfig, **kwargs):
          ...

      def run(self):
          try:
              self.phase_started.emit(self.phase)
              result = self._run_phase()
              self.phase_completed.emit(self.phase, result)
          except Exception as e:
              self.phase_failed.emit(self.phase, str(e))

      def _run_phase(self) -> dict:
          # Dispatch to the appropriate pipeline function based on self.phase
          if self.phase == "syllabify":
              ...
          elif self.phase == "align":
              ...
          elif self.phase == "detect_beats":
              ...
          elif self.phase == "auto_correct":
              # Runs: anchors (or quantize) → plan → render
              ...
  ```
- **IMPORTS**: `PyQt6.QtCore.QThread, pyqtSignal`, pipeline modules
- **GOTCHA**: Pipeline functions use numpy/scipy which release the GIL during heavy computation, so QThread works fine. But subprocess calls (MFA, rubberband) block — that's OK since they're I/O-bound and the thread keeps the UI responsive.
- **VALIDATE**: `ruff check src/rapmap/studio/worker.py`

---

### Task 25: CREATE `src/rapmap/studio/panel.py` — Main companion window

- **IMPLEMENT**:
  ```python
  class StudioPanel(QMainWindow):
      """RapMap Studio — Audacity companion panel."""
      def __init__(self, config: RapMapConfig):
          ...
      def _setup_ui(self):
          """
          Layout:
          ┌─────────────────────────────────┐
          │ Audacity Connection: [●] / [○]  │
          │ Project: [Select Dir...]        │
          ├─────────────────────────────────┤
          │ 1. [Grab Audio from Audacity]   │
          │ 2. [Set Lyrics...]              │
          │ 3. [Detect Beats]  BPM: ---     │
          │ 4. [Syllabify]     Syls: ---    │
          │ 5. [Align Vocal]                │
          │ 6. [Auto-Correct]               │
          │ 7. [Edit Timing...]  ← opens editor │
          │ 8. [Apply to Audacity]          │
          ├─────────────────────────────────┤
          │ Mode: (●) Beat-Only (○) Guide   │
          │ Status: Ready                   │
          │ [Progress Bar]                  │
          └─────────────────────────────────┘
          """
      def _on_grab_audio(self):
          """Export backing + vocal from Audacity into project dir."""
      def _on_set_lyrics(self):
          """Open file dialog or text editor for lyrics input."""
      def _on_detect_beats(self):
          """Run beat detection, update BPM display."""
      def _on_syllabify(self):
          """Run syllabification, update syllable count display."""
      def _on_align(self):
          """Run forced alignment on human vocal."""
      def _on_auto_correct(self):
          """Run full correction pipeline (beat-only or guide mode)."""
      def _on_edit_timing(self):
          """Launch interactive editor window."""
      def _on_apply(self):
          """Import corrected clips back into Audacity."""
  ```
  - Each button spawns a `PipelineWorker` on a QThread
  - Buttons gray out while a phase is running
  - Status bar shows progress and error messages
  - Connection indicator polls Audacity pipe every 5 seconds
  - Project dir persisted between sessions (QSettings)
- **IMPORTS**: `PyQt6.QtWidgets`, `PyQt6.QtCore`, studio submodules
- **VALIDATE**: Manual — `uv run rapmap studio`

---

### Task 26: UPDATE `src/rapmap/cli.py` — Add `studio` command

- **IMPLEMENT**:
  ```python
  @main.command()
  @click.option("--config", "config_path", type=click.Path(), default=None)
  def studio(config_path):
      """Launch RapMap Studio companion panel for Audacity."""
      from rapmap.studio.panel import launch_studio
      config = load_config(Path(config_path) if config_path else None)
      launch_studio(config)
  ```
  - Add `launch_studio()` function in `studio/panel.py` that creates QApplication + StudioPanel + exec()
- **VALIDATE**: `ruff check src/rapmap/cli.py`

---

### Task 27: UPDATE `CLAUDE.md` — Document new modules and commands

- **IMPLEMENT**: Add to project structure:
  ```
  src/rapmap/
  ├── beat/                  # Beat detection and quantization
  │   ├── detect.py          # BPM + beat frame extraction (librosa)
  │   ├── grid.py            # Beat grid generation (subdivisions)
  │   └── quantize.py        # Snap syllable anchors to beat grid
  ├── editor/                # Interactive syllable timing editor (PyQt6)
  │   ├── app.py             # Editor bootstrap
  │   ├── waveform.py        # Waveform display (pyqtgraph)
  │   ├── beat_grid.py       # Beat grid overlay
  │   ├── syllable_blocks.py # Draggable syllable regions
  │   ├── timeline.py        # Composite editor widget
  │   ├── preview.py         # Audio preview (sounddevice)
  │   └── state.py           # Editor state load/save
  ├── studio/                # Audacity companion panel (PyQt6)
  │   ├── panel.py           # Main companion window
  │   ├── audacity_bridge.py # Enhanced Audacity communication
  │   └── worker.py          # Background pipeline workers
  ```
  - Add new commands to Commands section:
    ```bash
    uv run rapmap detect-beats --project workdir --subdivision eighth --strength 1.0
    uv run rapmap editor --project workdir
    uv run rapmap studio
    uv run rapmap run --mode beat-only --backing backing.wav --human human.wav --lyrics lyrics.txt --out workdir
    ```
  - Add Beat Detection to pipeline phases table
  - Add note: "The studio companion and editor require PyQt6: `uv sync --extra editor --extra studio`"
- **VALIDATE**: Manual review of CLAUDE.md

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
ruff check src/ tests/
ruff format src/ tests/
```

### Level 2: Type Check

```bash
uv run python -c "from rapmap.beat.detect import detect_beats; from rapmap.beat.grid import build_beat_grid; from rapmap.beat.quantize import quantize_anchors; print('Beat imports OK')"
uv run python -c "from rapmap.editor.state import EditorState, load_editor_state; print('Editor imports OK')"
uv run python -c "from rapmap.studio.panel import StudioPanel; print('Studio imports OK')"
```

### Level 3: Automated Tests

```bash
uv run pytest tests/test_beat_detection.py tests/test_beat_quantize.py tests/test_editor_state.py -v
```

### Level 4: Regression Tests

```bash
uv run pytest tests/ -v
```

### Level 5: Manual Validation

- Launch `rapmap studio`, verify Audacity connection indicator
- With Audacity running + mod-script-pipe enabled:
  - Click "Grab Audio" — verify WAV files created in project dir
  - Click "Detect Beats" — verify BPM displayed
  - Click "Edit Timing" — verify editor opens with waveform + grid + blocks
  - Drag a syllable block — verify it snaps to grid
  - Click "Apply to Audacity" — verify corrected clips appear in Audacity

---

## ACCEPTANCE CRITERIA

- [ ] Beat detection extracts BPM and beat positions from backing track
- [ ] Beat grid generates correct subdivisions (quarter, eighth, sixteenth, triplet)
- [ ] Quantize snaps syllable anchors to beat grid with configurable strength
- [ ] Beat-only mode produces valid anchor_map consumable by existing planner
- [ ] `rapmap run --mode beat-only` completes full pipeline without AI guide
- [ ] Interactive editor displays waveform, beat grid, and syllable blocks
- [ ] Syllable blocks are draggable and snap to beat grid
- [ ] Editor saves modified timing back to project dir
- [ ] Studio companion connects to Audacity and provides button access to all phases
- [ ] "Grab Audio" exports tracks from Audacity
- [ ] "Apply to Audacity" imports corrected clips
- [ ] All new tests pass
- [ ] All existing tests still pass (no regressions)
- [ ] CLAUDE.md updated with new modules and commands

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (1-27)
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully
- [ ] Manual verification confirms studio + editor work
- [ ] Acceptance criteria all met
- [ ] Ready for `/commit`

---

## NOTES

### Architecture Decision: Python Orchestrator, Not Audacity Plugin

Audacity macros and Nyquist plugins are sandboxed — they cannot call external programs. mod-script-pipe is one-directional (Python → Audacity). Therefore our Python app must be the orchestrator that drives Audacity, not the other way around. The user runs `rapmap studio` alongside Audacity.

### "guide_*" Field Reuse in Beat-Only Mode

The beat-quantized anchor_map reuses `guide_anchor_sample`, `guide_start_sample`, `guide_end_sample` fields even though there is no AI guide. This is intentional — the entire downstream pipeline (planner, renderer, validator) reads these fields. The `"source": "beat_grid"` field disambiguates. This avoids changing 6+ files that consume the anchor_map format.

### Performance Considerations

- Waveform rendering: Must downsample for display. Min/max envelope at ~2000 points per screen width.
- Beat grid: ~720 lines for a 3-minute song at eighth-note 120 BPM. Needs viewport culling.
- Syllable blocks: Typically 50-200 per song. LinearRegionItem handles this fine.
- Audio preview: sounddevice callback is real-time; pre-render corrected segments before playback.

### Dependency Weight

PyQt6 and librosa are heavyweight dependencies. They're in optional groups so the core CLI pipeline doesn't require them. Users who only want CLI operation can skip `--extra editor --extra studio`.

### Platform Notes

- **macOS**: mod-script-pipe paths include `os.getuid()` suffix in some Audacity versions. Current code uses `/tmp/audacity_script_pipe.to` (no uid). May need to handle both variants.
- **Linux**: sounddevice requires `libportaudio2` (`sudo apt install libportaudio2`).
- **Windows**: Named pipes use `\\.\pipe\ToSrvPipe` / `FromSrvPipe`. PyQt6 works natively.

### Future Extensions

- MIDI export of quantized timing for use in other DAWs
- Multi-track support (harmonies, ad-libs)
- Undo/redo stack in the editor
- Real-time waveform preview during drag (stretch preview)
- FL Studio / Ableton integration via their respective APIs
