# Task: Beat-Only Mode + Interactive Editor + Audacity Round-Trip

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files etc.

## Task Description

Three additions to the RapMap pipeline:

1. **Beat detection + beat-only mode** — extract BPM and beat grid from the backing track, quantize human syllable anchors to the grid. Produces a valid anchor_map without needing an AI guide vocal. The entire downstream pipeline (grouping, edit plan, render) works unchanged.

2. **Audacity round-trip** — add export commands to `AudacityPipe` so we can grab the recorded vocal from Audacity, not just import results back. Completes the loop: record in Audacity → export via pipe → pipeline → import corrected clips via pipe → play in Audacity.

3. **Interactive syllable editor** — a native-looking desktop window (pywebview + Flask) where the user sees the waveform, beat grid lines, and draggable syllable blocks. They adjust timing by hand, save, then render + import to Audacity. It's just a visual way to edit the anchor_map JSON — same file the rest of the pipeline reads.

4. **Studio launcher** — one command (`rapmap studio`) launches both Audacity and the editor window, arranged side-by-side. Buttons in the editor toggle window focus ("Switch to Audacity" / "Switch to Editor"). The user runs one thing; both windows appear ready.

### Architecture

```
rapmap studio (launcher)
    ├── Launches Audacity (subprocess)
    ├── Opens editor (pywebview — native window, no browser chrome)
    └── Manages window focus (AppleScript on macOS, wmctrl on Linux)

Editor window (pywebview + Flask backend)
    ├── [Switch to Audacity] button → brings Audacity to front
    ├── [Grab Audio] button → exports tracks via mod-script-pipe
    ├── Waveform + beat grid + draggable syllable blocks
    ├── [Render + Apply] button → runs pipeline, imports back via pipe
    └── Reads/writes JSON files in project workdir

Audacity (recording/playback)
    ↕ mod-script-pipe (export vocal, import corrected clips)

Project workdir (files on disk)
    ↕ read/write JSON + WAV
```

No live sync. No WebSockets. No Tauri. The editor is a pipeline step that happens to have a native window. Communication is all through files and pipe commands.

## Task Metadata

**Task Type**: Code Change
**Estimated Complexity**: High
**Primary Systems Affected**: `src/rapmap/beat/` (new), `src/rapmap/editor/` (new), `src/rapmap/studio/` (new), `src/rapmap/audacity/script_pipe.py`, `src/rapmap/cli.py`, `src/rapmap/config.py`, `pyproject.toml`
**Dependencies**: librosa (beat detection), Flask (editor server), pywebview (native window), wavesurfer.js (waveform — CDN, no install)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/rapmap/audacity/script_pipe.py` (lines 1-91) — AudacityPipe class. Add export/query methods here.
- `src/rapmap/timing/anchor_map.py` (lines 1-54) — `build_anchor_map()`. Beat-only mode produces output in the exact same format. Key fields: `guide_anchor_sample`, `human_anchor_sample`, `guide_start_sample`, `guide_end_sample`, `delta_samples`.
- `src/rapmap/edit/planner.py` (lines 1-84) — `create_edit_plan()` consumes anchor_map. Must work identically with beat-generated anchor_map.
- `src/rapmap/edit/grouping.py` (lines 1-167) — `group_syllables()` reads `anchors[i]["human_start_sample"]`, `anchors[i]["guide_start_sample"]` etc. Beat anchor_map must have all these fields.
- `src/rapmap/audio/render.py` (lines 1-186) — `render_clips()` unchanged.
- `src/rapmap/config.py` (lines 1-141) — Add BeatDetectionConfig here.
- `src/rapmap/cli.py` — Add `detect-beats`, `editor` commands. Add `--mode` to `run`.
- `src/rapmap/align/base.py` — `AlignmentResult`, `SyllableTimestamp` dataclasses. Beat quantize reads these.
- `pyproject.toml` (lines 1-47) — Add optional dependency groups.

### New Files to Create

```
src/rapmap/beat/
├── __init__.py
├── detect.py          # BPM + beat frame extraction (librosa)
├── grid.py            # Beat grid subdivision generation
└── quantize.py        # Snap syllable anchors to beat grid → anchor_map

src/rapmap/editor/
├── __init__.py
├── server.py          # Flask app: serves static files + JSON API
├── static/
│   ├── index.html     # Editor page
│   ├── editor.js      # Waveform + beat grid + draggable blocks
│   └── editor.css     # Styling

src/rapmap/studio/
├── __init__.py
├── launcher.py        # Launches Audacity + editor, arranges windows
└── window_manager.py  # OS-level window focus toggling

tests/
├── test_beat_detection.py
├── test_beat_quantize.py
├── test_editor_api.py
```

### Patterns to Follow

**Anchor map format** (from `timing/anchor_map.py` lines 48-53):
```python
{
    "sample_rate": 48000,
    "anchor_strategy": "onset",
    "syllable_count": N,
    "anchors": [
        {
            "syllable_index": 0,
            "human_anchor_sample": int,
            "guide_anchor_sample": int,    # beat grid target in beat-only mode
            "delta_samples": int,
            "human_start_sample": int,
            "human_end_sample": int,
            "guide_start_sample": int,     # beat grid target start
            "guide_end_sample": int,       # computed from target start + human duration
            "confidence": float,
        },
        ...
    ]
}
```

**Config pattern** (from `config.py`):
```python
@dataclass
class BeatDetectionConfig:
    field: type = default
```
Added to `RapMapConfig` with `field(default_factory=...)`.

**CLI command pattern** (from `cli.py`):
```python
@main.command("command-name")
@click.option("--project", type=click.Path(exists=True), required=True)
def command_name(project):
    ...
```

**Pipe command pattern** (from `script_pipe.py:50-52`):
```python
def method_name(self, path: Path) -> bool:
    resp = self.send(f'CommandName: Param="{path}"')
    return "OK" in resp
```

---

## IMPLEMENTATION PLAN

### Phase 1: Beat Detection Module

Add BPM extraction and beat grid generation. This is pure Python with librosa — no UI, no Audacity.

### Phase 2: Beat-Only Anchor Map

Quantize human syllable anchors to the beat grid. Output is a standard anchor_map dict that the existing planner/renderer consume without changes.

### Phase 3: Audacity Round-Trip

Add export commands to AudacityPipe. Add CLI commands for grabbing audio from Audacity and applying results back.

### Phase 4: Interactive Editor

Native desktop window (pywebview) backed by a local Flask server. Flask serves static files and provides a JSON API for loading/saving the anchor_map. Frontend uses wavesurfer.js for waveform display and vanilla JS for draggable syllable blocks + beat grid overlay. The window has no browser chrome — it looks like a native app.

### Phase 5: Studio Launcher + Window Management

One command (`rapmap studio`) that launches Audacity, opens the editor window, and arranges them side-by-side. OS-level window focus toggling via AppleScript (macOS) or wmctrl (Linux). Editor UI includes "Switch to Audacity" button.

### Phase 6: CLI Integration

Wire everything together: `detect-beats`, `editor`, `studio` commands, `--mode beat-only` on `run`.

### Phase 7: Tests

---

## STEP-BY-STEP TASKS

### Task 1: UPDATE `pyproject.toml` — Add new dependencies

- **IMPLEMENT**: Add optional dependency groups:
  ```toml
  beat = [
      "librosa>=0.10",
  ]
  editor = [
      "flask>=3.0",
      "pywebview>=5.0",
  ]
  ```
  Add to existing `dev` group: `"flask>=3.0"` (for test client).
- **PATTERN**: `pyproject.toml` lines 17-27
- **VALIDATE**: `uv sync --extra beat --extra editor --extra dev`

---

### Task 2: UPDATE `src/rapmap/config.py` — Add BeatDetectionConfig

- **IMPLEMENT**: Add dataclass:
  ```python
  @dataclass
  class BeatDetectionConfig:
      subdivision: str = "eighth"
      quantize_strength: float = 1.0
      min_bpm: int = 60
      max_bpm: int = 200
      hop_length: int = 512
  ```
  Add to `RapMapConfig`:
  ```python
  beat_detection: BeatDetectionConfig = field(default_factory=BeatDetectionConfig)
  ```
- **PATTERN**: `src/rapmap/config.py` lines 48-49 (AnchorStrategyConfig)
- **VALIDATE**: `uv run python -c "from rapmap.config import RapMapConfig; c = RapMapConfig(); print(c.beat_detection.subdivision)"`

---

### Task 3: CREATE `src/rapmap/beat/__init__.py`

- **IMPLEMENT**: Empty init file.
- **VALIDATE**: `uv run python -c "import rapmap.beat"`

---

### Task 4: CREATE `src/rapmap/beat/detect.py` — BPM and beat frame extraction

- **IMPLEMENT**:
  ```python
  from __future__ import annotations
  import numpy as np
  from rapmap.config import BeatDetectionConfig

  def detect_beats(audio: np.ndarray, sample_rate: int, config: BeatDetectionConfig) -> dict:
  ```
  - Call `librosa.beat.beat_track(y=audio, sr=sample_rate, hop_length=config.hop_length, start_bpm=120.0)` → returns `(tempo, beat_frames)`
  - Clamp detected BPM to `[config.min_bpm, config.max_bpm]`. If outside range, use `librosa.beat.beat_track` with `bpm` parameter forced.
  - Convert beat frames to sample indices: `librosa.frames_to_samples(beat_frames, hop_length=config.hop_length)`
  - Cast all values to Python `int` (not numpy int64) for JSON serialization
  - Assert beat_samples are monotonically increasing
  - Return:
    ```python
    {
        "bpm": float(tempo),
        "beat_samples": [int(s) for s in beat_samples],
        "sample_rate": sample_rate,
        "hop_length": config.hop_length,
        "total_beats": len(beat_samples),
    }
    ```
- **IMPORTS**: `numpy`, `librosa` (import inside function for lazy loading — librosa is heavy)
- **GOTCHA**: librosa returns numpy scalar for tempo and numpy int array for frames. Must cast to Python native types for JSON. `float(tempo)` and `int(s)`.
- **VALIDATE**: `uv run python -c "from rapmap.beat.detect import detect_beats; print('OK')"`

---

### Task 5: CREATE `src/rapmap/beat/grid.py` — Beat grid subdivision

- **IMPLEMENT**:
  ```python
  from __future__ import annotations

  SUBDIVISION_UNITS = {
      "quarter": 1,
      "eighth": 2,
      "sixteenth": 4,
      "triplet": 3,
  }

  def build_beat_grid(beat_info: dict, subdivision: str, total_duration_samples: int) -> dict:
  ```
  - Look up `units_per_beat` from `SUBDIVISION_UNITS[subdivision]`
  - For each pair of adjacent beats, interpolate subdivisions:
    ```python
    grid = []
    beats = beat_info["beat_samples"]
    for i in range(len(beats) - 1):
        span = beats[i + 1] - beats[i]
        for s in range(units_per_beat):
            pos = beats[i] + int(round(span * s / units_per_beat))
            grid.append(pos)
    grid.append(beats[-1])
    ```
  - Deduplicate and sort (shouldn't be needed but defensive)
  - Return:
    ```python
    {
        "bpm": beat_info["bpm"],
        "subdivision": subdivision,
        "units_per_beat": units_per_beat,
        "grid_samples": grid,
        "beat_samples": beat_info["beat_samples"],
        "sample_rate": beat_info["sample_rate"],
        "total_grid_points": len(grid),
    }
    ```
- **VALIDATE**: `uv run python -c "from rapmap.beat.grid import build_beat_grid; print('OK')"`

---

### Task 6: CREATE `src/rapmap/beat/quantize.py` — Snap syllable anchors to beat grid

- **IMPLEMENT**:
  ```python
  from __future__ import annotations
  import numpy as np
  from rapmap.align.base import AlignmentResult
  from rapmap.config import BeatDetectionConfig

  def quantize_anchors(
      human_alignment: AlignmentResult,
      beat_grid: dict,
      config: BeatDetectionConfig,
  ) -> dict:
  ```
  - For each syllable in `human_alignment.syllables`:
    - `human_anchor = syllable.start_sample` (onset strategy)
    - Find nearest grid position: `nearest = min(grid_samples, key=lambda g: abs(g - human_anchor))`
    - Apply quantize strength: `target = human_anchor + int(round((nearest - human_anchor) * config.quantize_strength))`
    - Compute guide_start and guide_end: shift by the same delta as the anchor
      ```python
      delta = target - human_anchor
      guide_start = syllable.start_sample + delta
      guide_end = syllable.end_sample + delta
      ```
  - Build anchor list in the **exact format** `build_anchor_map()` produces (lines 28-39 of `timing/anchor_map.py`):
    ```python
    {
        "syllable_index": i,
        "human_anchor_sample": human_anchor,
        "guide_anchor_sample": target,
        "delta_samples": human_anchor - target,
        "human_start_sample": syllable.start_sample,
        "human_end_sample": syllable.end_sample,
        "guide_start_sample": guide_start,
        "guide_end_sample": guide_end,
        "confidence": 1.0,
    }
    ```
  - Validate: anchors must be monotonically increasing by `guide_anchor_sample`. If two syllables map to the same grid position, offset the later one by one subdivision interval.
  - Return:
    ```python
    {
        "sample_rate": human_alignment.sample_rate,
        "anchor_strategy": "onset",
        "source": "beat_grid",
        "bpm": beat_grid["bpm"],
        "subdivision": beat_grid["subdivision"],
        "quantize_strength": config.quantize_strength,
        "syllable_count": len(anchors),
        "anchors": anchors,
    }
    ```
  - **CRITICAL**: The extra fields (`source`, `bpm`, `subdivision`, `quantize_strength`) are metadata only. The planner reads only `sample_rate`, `anchor_strategy`, `syllable_count`, and `anchors[]` with the standard field names. Adding extra fields is safe.
- **GOTCHA**: `delta_samples` sign convention must match `build_anchor_map`: it's `human_anchor - guide_anchor`, not the reverse. Check `timing/anchor_map.py` line 33.
- **VALIDATE**: `uv run python -c "from rapmap.beat.quantize import quantize_anchors; print('OK')"`

---

### Task 7: UPDATE `src/rapmap/audacity/script_pipe.py` — Add export/query methods

- **IMPLEMENT**: Add methods to `AudacityPipe`:
  ```python
  def get_tracks(self) -> list[dict]:
      """Query all tracks via GetInfo."""
      import json as _json
      resp = self.send("GetInfo: Type=Tracks Format=JSON")
      return _json.loads(_extract_json(resp))

  def export_audio(self, path: Path, num_channels: int = 1) -> bool:
      resp = self.send(f'Export2: Filename="{path}" NumChannels={num_channels}')
      return "OK" in resp

  def select_tracks(self, track: int, count: int = 1) -> bool:
      resp = self.send(f"SelectTracks: Track={track} TrackCount={count} Mode=Set")
      return "OK" in resp

  def select_all(self) -> bool:
      resp = self.send("SelectAll:")
      return "OK" in resp

  def solo_track(self, track: int, solo: bool = True) -> bool:
      val = 1 if solo else 0
      resp = self.send(f"SetTrack: Track={track} Solo={val}")
      return "OK" in resp

  def play(self) -> bool:
      resp = self.send("Play:")
      return "OK" in resp

  def stop(self) -> bool:
      resp = self.send("Stop:")
      return "OK" in resp
  ```
  - Add module-level helper:
    ```python
    def _extract_json(response: str) -> str:
        """Extract JSON from pipe response (before BatchCommand footer)."""
        # Find first '[' or '{', take everything up to matching closer
        ...
    ```
- **PATTERN**: `src/rapmap/audacity/script_pipe.py` lines 50-64
- **GOTCHA**: `GetInfo` response contains JSON followed by `\nBatchCommand finished: OK\n`. Must strip the footer before parsing. Find the last `]` or `}` and slice there.
- **VALIDATE**: `ruff check src/rapmap/audacity/script_pipe.py`

---

### Task 8: UPDATE `src/rapmap/cli.py` — Add `detect-beats` command

- **IMPLEMENT**:
  ```python
  @main.command("detect-beats")
  @click.option("--project", type=click.Path(exists=True), required=True)
  @click.option("--subdivision", type=click.Choice(["quarter", "eighth", "sixteenth", "triplet"]), default="eighth")
  @click.option("--strength", type=float, default=1.0)
  @click.option("--config", "config_path", type=click.Path(), default=None)
  def detect_beats_cmd(project, subdivision, strength, config_path):
      """Detect beats in backing track and quantize syllable anchors to beat grid."""
  ```
  - Load backing audio from `{project}/audio/backing.wav` using `read_audio`
  - Call `detect_beats()` → save to `{project}/timing/beat_info.json`
  - Call `build_beat_grid(beat_info, subdivision, total_duration)` → save to `{project}/timing/beat_grid.json`
  - If human alignment exists at `{project}/alignment/human_alignment.json`:
    - Override config: `config.beat_detection.quantize_strength = strength`
    - Call `quantize_anchors()` → save to `{project}/timing/anchor_map.json`
    - Print: "BPM: {bpm}, Beats: {n}, Grid points: {n}, Syllables quantized: {n}"
  - Else: print "BPM: {bpm}, Beats: {n}. Run `align` first to quantize syllables."
- **PATTERN**: `src/rapmap/cli.py` — `anchors` command (lines 189-232)
- **VALIDATE**: `ruff check src/rapmap/cli.py`

---

### Task 9: UPDATE `src/rapmap/cli.py` — Add `--mode` to `run` command

- **IMPLEMENT**: Add option to the `run` command:
  ```python
  @click.option("--mode", type=click.Choice(["guide", "beat-only"]), default="guide")
  ```
  - In `beat-only` mode, the `run` command:
    1. Phase 0: `init` (normalize) — same
    2. Phase 2: `syllabify` — same
    3. Phase 3: `align` human only (skip `--role guide`)
    4. Phase 4: `detect-beats` + `quantize_anchors` (replaces guide-based anchor map)
    5. Phases 5-8: same (grouping, edit plan, render, audacity)
  - Skip guide-related steps: no `set-guide`, no guide alignment, no guide audio import in Audacity step
- **PATTERN**: `src/rapmap/cli.py` — existing `run` command flow
- **GOTCHA**: The `group_syllables()` call in `run` passes `human_alignment` and `audio_data` for safe_boundary mode. These are available in beat-only mode since we still align the human vocal. No changes needed to grouping.
- **VALIDATE**: `ruff check src/rapmap/cli.py`

---

### Task 10: UPDATE `src/rapmap/cli.py` — Add `grab-audio` and `apply` commands

- **IMPLEMENT**: Two new commands for the Audacity round-trip:
  ```python
  @main.command("grab-audio")
  @click.option("--project", type=click.Path(exists=True), required=True)
  @click.option("--backing-track", type=int, default=0, help="Audacity track index for backing")
  @click.option("--vocal-track", type=int, default=1, help="Audacity track index for vocal")
  def grab_audio(project, backing_track, vocal_track):
      """Export backing and vocal tracks from Audacity into project dir."""
  ```
  - Connect to Audacity via pipe
  - For each track: solo it, select all, export to `{project}/audio/backing.wav` or `human_rap.wav`, unsolo
  - Print track count and exported paths

  The `apply` command already exists as `audacity` — just document this in help text.
- **PATTERN**: `src/rapmap/audacity/import_project.py` lines 46-65 — pipe usage pattern
- **VALIDATE**: `ruff check src/rapmap/cli.py`

---

### Task 11: CREATE `src/rapmap/editor/__init__.py`

- **IMPLEMENT**: Empty init file.
- **VALIDATE**: `uv run python -c "import rapmap.editor"`

---

### Task 12: CREATE `src/rapmap/editor/server.py` — Flask app for the editor

- **IMPLEMENT**: A minimal Flask app with these endpoints:
  ```python
  from __future__ import annotations
  import json
  import webbrowser
  from pathlib import Path
  from flask import Flask, jsonify, request, send_from_directory

  def create_app(project_dir: Path) -> Flask:
      app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"))
      # Store project_dir on the app for endpoint access
      app.config["PROJECT_DIR"] = project_dir
      ...
      return app

  def launch_editor(project_dir: Path, port: int = 8765, use_webview: bool = True) -> None:
      """Launch the editor. If use_webview=True, opens in a native pywebview window.
      Otherwise falls back to browser (for testing or if pywebview unavailable)."""
      app = create_app(project_dir)
      if use_webview:
          import threading
          import webview
          # Start Flask in a background thread
          server_thread = threading.Thread(
              target=lambda: app.run(port=port, debug=False, use_reloader=False),
              daemon=True,
          )
          server_thread.start()
          # Open native window — no browser chrome, looks like a desktop app
          webview.create_window(
              f"RapMap Editor — {project_dir.name}",
              f"http://localhost:{port}",
              width=1200,
              height=700,
          )
          webview.start()
      else:
          import webbrowser
          webbrowser.open(f"http://localhost:{port}")
          app.run(port=port, debug=False)
  ```

  **Endpoints:**

  `GET /api/state` — return everything the editor needs:
  ```python
  {
      "sample_rate": 48000,
      "anchor_map": { ... },           # from timing/anchor_map.json
      "beat_grid": { ... } | null,     # from timing/beat_grid.json (if exists)
      "canonical_syllables": { ... },  # from lyrics/canonical_syllables.json
      "audio_urls": {
          "backing": "/audio/backing.wav",
          "human": "/audio/human_rap.wav",
      }
  }
  ```

  `POST /api/anchor_map` — save modified anchor_map:
  ```python
  # Request body: the full modified anchor_map dict
  # Writes to {project_dir}/timing/anchor_map.json
  # Validates: monotonic guide_anchor_sample, all required fields present
  # Returns: {"ok": true} or {"error": "..."}
  ```

  `GET /audio/<path:filename>` — serve WAV files from project audio dir:
  ```python
  @app.route("/audio/<path:filename>")
  def serve_audio(filename):
      audio_dir = Path(app.config["PROJECT_DIR"]) / "audio"
      return send_from_directory(audio_dir, filename)
  ```

  `POST /api/focus-audacity` — bring Audacity window to front:
  ```python
  # Calls window_manager.focus_audacity() — see studio/window_manager.py
  # Returns: {"ok": true}
  ```

  `POST /api/grab-audio` — export tracks from Audacity:
  ```python
  # Connects to Audacity via pipe, exports backing + vocal to project audio dir
  # Returns: {"ok": true, "tracks_exported": 2} or {"error": "..."}
  ```

  `POST /api/render-apply` — run render pipeline and import back to Audacity:
  ```python
  # Saves current anchor_map, runs edit plan + render, imports clips via pipe
  # Returns: {"ok": true, "report": {...}} or {"error": "..."}
  ```

  `GET /` — serve `static/index.html`

- **IMPORTS**: `flask`, `json`, `pathlib`, `webview` (lazy), `webbrowser` (fallback), `threading`
- **GOTCHA**: Flask runs in a daemon thread when using pywebview. `use_reloader=False` is required — Flask's reloader spawns a child process which conflicts with pywebview's main thread. WAV files can be large (~50MB for a 3-minute 48kHz mono float32). Flask's `send_from_directory` streams them — no issue.
- **VALIDATE**: `uv run python -c "from rapmap.editor.server import create_app; print('OK')"`

---

### Task 13: CREATE `src/rapmap/editor/static/index.html` — Editor page

- **IMPLEMENT**: Single HTML page that loads wavesurfer.js from CDN and our `editor.js`:
  ```html
  <!DOCTYPE html>
  <html>
  <head>
      <title>RapMap Editor</title>
      <link rel="stylesheet" href="/static/editor.css">
  </head>
  <body>
      <div id="toolbar">
          <div id="toolbar-left">
              <button id="btn-audacity" class="toolbar-accent">Switch to Audacity</button>
              <button id="btn-grab-audio">Grab Audio</button>
              <span class="toolbar-sep">|</span>
              <button id="btn-play-original">Play Original</button>
              <button id="btn-stop">Stop</button>
          </div>
          <div id="toolbar-center">
              <label>Snap <input type="checkbox" id="snap-toggle" checked></label>
              <label>Strength <input type="range" id="strength-slider" min="0" max="100" value="100"></label>
              <span id="bpm-display">BPM: ---</span>
          </div>
          <div id="toolbar-right">
              <button id="btn-save">Save</button>
              <button id="btn-render-apply" class="toolbar-accent">Render + Apply</button>
              <span id="save-status"></span>
          </div>
      </div>
      <div id="waveform-backing"></div>
      <div id="waveform-human"></div>
      <div id="syllable-info">
          <span id="syl-count">Syllables: ---</span>
          <span id="syl-selected">Selected: none</span>
      </div>
      <script src="https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.min.js"></script>
      <script src="/static/editor.js"></script>
  </body>
  </html>
  ```
  - "Switch to Audacity" calls `POST /api/focus-audacity` (server brings Audacity window to front)
  - "Grab Audio" calls `POST /api/grab-audio` (server exports tracks from Audacity via pipe)
  - "Render + Apply" calls `POST /api/render-apply` (server runs render pipeline + imports clips back to Audacity)
- **VALIDATE**: Manual — open in browser after server is running

---

### Task 14: CREATE `src/rapmap/editor/static/editor.css` — Styling

- **IMPLEMENT**: Basic styling:
  - Dark background (#1a1a2e), light text
  - Toolbar: horizontal bar with padding
  - Waveform containers: full width, fixed height (~150px each)
  - Beat grid lines: red/orange vertical lines (rendered in canvas by JS)
  - Syllable blocks: green rectangles with text labels, highlighted on hover/select
  - Save status: green text on success, red on error
- **VALIDATE**: Manual — visual inspection

---

### Task 15: CREATE `src/rapmap/editor/static/editor.js` — Editor logic

- **IMPLEMENT**: The main editor JavaScript. This is the largest single file. Structure:

  **1. Initialization:**
  ```javascript
  async function init() {
      const state = await fetch('/api/state').then(r => r.json());
      initWaveforms(state);
      initBeatGrid(state);
      initSyllableBlocks(state);
      initToolbar(state);
  }
  ```

  **2. Waveform display (wavesurfer.js):**
  ```javascript
  function initWaveforms(state) {
      // Create two wavesurfer instances: backing (top) and human vocal (bottom)
      const wsBacking = WaveSurfer.create({
          container: '#waveform-backing',
          url: state.audio_urls.backing,
          waveColor: '#666',
          progressColor: '#888',
          height: 120,
          interact: false,  // no seeking on backing track
      });
      const wsHuman = WaveSurfer.create({
          container: '#waveform-human',
          url: state.audio_urls.human,
          waveColor: '#2196F3',
          progressColor: '#64B5F6',
          height: 150,
      });
      // Sync scroll/zoom between both waveforms
  }
  ```

  **3. Beat grid overlay:**
  - After wavesurfer renders, overlay a canvas on top of the human waveform container
  - Draw vertical lines at each `beat_grid.grid_samples[i] / sample_rate` position
  - Main beats: thick orange line. Subdivisions: thin semi-transparent line.
  - Redraw on scroll/zoom events

  **4. Syllable blocks:**
  - For each anchor in `anchor_map.anchors`:
    - Create a `<div>` positioned absolutely over the waveform
    - Position: `left = (guide_start_sample / sample_rate) * pixelsPerSecond`
    - Width: `(guide_end_sample - guide_start_sample) / sample_rate * pixelsPerSecond`
    - Text: syllable text from `canonical_syllables`
    - Make draggable horizontally (mousedown/mousemove/mouseup)
  - On drag end:
    - If snap enabled: find nearest grid position to the block's new center, snap to it
    - Apply quantize strength: interpolate between drag position and grid position
    - Update anchor_map in memory: `guide_anchor_sample`, `guide_start_sample`, `guide_end_sample`, `delta_samples`
    - Enforce monotonicity: clamp so block doesn't pass its neighbors
    - Re-render block position

  **5. Toolbar handlers:**
  - Switch to Audacity: `POST /api/focus-audacity` — server uses OS-level command to bring Audacity to front
  - Grab Audio: `POST /api/grab-audio` — server exports tracks from Audacity, then reloads waveforms
  - Play Original: `wsHuman.play()`
  - Stop: `wsHuman.stop(); wsBacking.stop()`
  - Save: `POST /api/anchor_map` with current anchor_map state, show status message
  - Render + Apply: `POST /api/render-apply` — saves anchor_map, runs pipeline, imports to Audacity. Show progress overlay.
  - Snap toggle + strength slider: update snap behavior for subsequent drags

  **6. Zoom/scroll:**
  - Mouse wheel = zoom (adjust wavesurfer zoom level, recompute block positions and grid lines)
  - Scroll bar or drag on waveform = scroll
  - Both waveforms and the grid overlay stay synchronized

- **GOTCHA**:
  - wavesurfer.js 7.x uses WebAudio and canvas. The regions plugin handles some of what we need, but syllable blocks with custom rendering and snap logic are better done as positioned DOM elements over the waveform canvas.
  - `pixelsPerSecond` changes with zoom. All block positions must be recomputed on zoom. Store positions in samples (integer), convert to pixels for display.
  - Large anchor_maps (200+ syllables) mean 200+ DOM elements. Fine for modern browsers but avoid per-frame reflows — use `transform: translateX()` for positioning, not `left`.
- **VALIDATE**: Manual — open editor, verify waveform renders, grid lines visible, blocks draggable

---

### Task 16: UPDATE `src/rapmap/cli.py` — Add `editor` and `studio` commands

- **IMPLEMENT**: Two new commands:
  ```python
  @main.command()
  @click.option("--project", type=click.Path(exists=True), required=True)
  @click.option("--port", type=int, default=8765)
  @click.option("--browser", is_flag=True, help="Open in browser instead of native window")
  def editor(project, port, browser):
      """Launch interactive syllable timing editor."""
      from rapmap.editor.server import launch_editor
      launch_editor(Path(project), port=port, use_webview=not browser)

  @main.command()
  @click.option("--project", type=click.Path(exists=True), required=True)
  @click.option("--port", type=int, default=8765)
  def studio(project, port):
      """Launch RapMap Studio — opens Audacity + editor side by side."""
      from rapmap.studio.launcher import launch_studio
      launch_studio(Path(project), port=port)
  ```
  - Lazy imports so PyQt/Flask/pywebview aren't required for non-editor commands
  - `editor` opens just the editor window (for users who manage Audacity themselves)
  - `studio` opens both Audacity and editor, arranged side-by-side
- **PATTERN**: `src/rapmap/cli.py` — existing command pattern
- **VALIDATE**: `ruff check src/rapmap/cli.py`

---

### Task 17: CREATE `src/rapmap/studio/__init__.py`

- **IMPLEMENT**: Empty init file.
- **VALIDATE**: `uv run python -c "import rapmap.studio"`

---

### Task 18: CREATE `src/rapmap/studio/window_manager.py` — OS-level window focus

- **IMPLEMENT**:
  ```python
  from __future__ import annotations
  import platform
  import subprocess

  def focus_audacity() -> bool:
      """Bring the Audacity window to front."""
      system = platform.system()
      if system == "Darwin":
          script = 'tell application "Audacity" to activate'
          result = subprocess.run(
              ["osascript", "-e", script], capture_output=True, timeout=5
          )
          return result.returncode == 0
      elif system == "Linux":
          result = subprocess.run(
              ["wmctrl", "-a", "Audacity"], capture_output=True, timeout=5
          )
          return result.returncode == 0
      elif system == "Windows":
          # PowerShell: bring Audacity window to front
          script = (
              '(New-Object -ComObject WScript.Shell)'
              '.AppActivate("Audacity")'
          )
          result = subprocess.run(
              ["powershell", "-Command", script], capture_output=True, timeout=5
          )
          return result.returncode == 0
      return False

  def launch_audacity() -> subprocess.Popen | None:
      """Launch Audacity if not already running."""
      system = platform.system()
      if system == "Darwin":
          return subprocess.Popen(["open", "-a", "Audacity"])
      elif system == "Linux":
          return subprocess.Popen(["audacity"])
      elif system == "Windows":
          return subprocess.Popen(["audacity.exe"])
      return None

  def arrange_side_by_side() -> None:
      """Position Audacity on left half, editor on right half of screen."""
      system = platform.system()
      if system == "Darwin":
          # AppleScript to resize and position windows
          # Audacity: left half of screen
          # Our window (pywebview): right half
          ...
      # Linux/Windows: similar with wmctrl / PowerShell
  ```
- **GOTCHA**: `wmctrl` may not be installed on Linux. Fail gracefully — print a message but don't crash. On macOS, AppleScript `tell application` works reliably. On Windows, `AppActivate` is best-effort.
- **VALIDATE**: `ruff check src/rapmap/studio/window_manager.py`

---

### Task 19: CREATE `src/rapmap/studio/launcher.py` — Studio launcher

- **IMPLEMENT**:
  ```python
  from __future__ import annotations
  import time
  from pathlib import Path

  from rapmap.studio.window_manager import launch_audacity, arrange_side_by_side

  def launch_studio(project_dir: Path, port: int = 8765) -> None:
      """Launch Audacity + editor side by side."""
      # 1. Launch Audacity (if not already running)
      audacity_proc = launch_audacity()

      # 2. Wait briefly for Audacity to start
      time.sleep(2)

      # 3. Try to connect via mod-script-pipe
      from rapmap.audacity.script_pipe import AudacityPipe
      pipe = AudacityPipe()
      connected = pipe.connect()
      if connected:
          pipe.close()
          print(f"Connected to Audacity via mod-script-pipe")
      else:
          print("Audacity is starting — mod-script-pipe not ready yet")
          print("Enable it in Edit > Preferences > Modules if not already enabled")

      # 4. Arrange windows side-by-side
      arrange_side_by_side()

      # 5. Launch editor (blocks until window is closed)
      from rapmap.editor.server import launch_editor
      launch_editor(project_dir, port=port, use_webview=True)
  ```
- **IMPORTS**: `pathlib`, `time`, `rapmap.studio.window_manager`, `rapmap.audacity.script_pipe`, `rapmap.editor.server`
- **VALIDATE**: `ruff check src/rapmap/studio/launcher.py`

---

### Task 20: CREATE `tests/test_beat_detection.py`

- **IMPLEMENT**:
  - `test_detect_beats_click_track()`:
    - Generate synthetic audio: silence with impulses every `sample_rate * 60 / bpm` samples at exactly 120 BPM
    - Run `detect_beats()`, verify detected BPM within 2% of 120
    - Verify beat count within ±2 of expected
  - `test_beat_grid_quarter()`:
    - Given known beats at samples [0, 48000, 96000], quarter subdivision → grid = [0, 48000, 96000]
  - `test_beat_grid_eighth()`:
    - Same beats → grid = [0, 24000, 48000, 72000, 96000]
  - `test_beat_grid_sixteenth()`:
    - Same beats → grid = [0, 12000, 24000, 36000, 48000, 60000, 72000, 84000, 96000]
  - `test_beat_grid_monotonic()`:
    - Verify all grid positions strictly increasing
  - `test_detect_beats_returns_python_int()`:
    - Verify all values in `beat_samples` are `isinstance(x, int)`, not numpy int
- **VALIDATE**: `uv run pytest tests/test_beat_detection.py -v`

---

### Task 21: CREATE `tests/test_beat_quantize.py`

- **IMPLEMENT**:
  - `test_quantize_snaps_to_nearest_grid()`:
    - Syllable at sample 1050, grid at [1000, 2000], strength=1.0 → target=1000
  - `test_quantize_strength_interpolation()`:
    - Syllable at 1000, nearest grid at 1200, strength=0.5 → target=1100
  - `test_quantize_strength_zero_no_change()`:
    - strength=0.0 → target=human_anchor (no movement)
  - `test_quantize_output_format()`:
    - Verify output dict has all fields that `create_edit_plan()` needs: `sample_rate`, `anchor_strategy`, `syllable_count`, `anchors[]` with `guide_anchor_sample`, `human_anchor_sample`, `guide_start_sample`, `guide_end_sample`, `human_start_sample`, `human_end_sample`, `delta_samples`
  - `test_quantize_monotonic_output()`:
    - Verify output anchors sorted by guide_anchor_sample
  - `test_quantize_resolves_duplicate_targets()`:
    - Two syllables near same grid line → they get different targets
  - `test_quantize_feeds_edit_planner()`:
    - Full integration: quantize → group_syllables → create_edit_plan → verify no errors
    - Uses the existing `create_edit_plan()` from `edit/planner.py` to prove format compatibility
- **IMPORTS**: `rapmap.beat.quantize`, `rapmap.align.base.AlignmentResult`, `rapmap.align.base.SyllableTimestamp`, `rapmap.align.base.PhoneTimestamp`, `rapmap.config.BeatDetectionConfig`, `rapmap.edit.planner.create_edit_plan`, `rapmap.config.RenderingConfig`
- **VALIDATE**: `uv run pytest tests/test_beat_quantize.py -v`

---

### Task 22: CREATE `tests/test_editor_api.py`

- **IMPLEMENT**: Test the Flask API using Flask's test client (no browser needed):
  - `test_get_state()`:
    - Set up a tmp project dir with required JSON files + dummy WAVs
    - Create Flask test client from `create_app(tmp_dir)`
    - GET `/api/state` → verify response has `anchor_map`, `canonical_syllables`, `audio_urls`
  - `test_save_anchor_map()`:
    - POST `/api/anchor_map` with a valid anchor_map dict
    - Verify `timing/anchor_map.json` on disk was updated
  - `test_save_anchor_map_rejects_non_monotonic()`:
    - POST with anchors where guide_anchor_sample is not monotonic
    - Verify 400 response with error message
  - `test_serve_audio_file()`:
    - GET `/audio/backing.wav` → verify 200 response with audio content
- **VALIDATE**: `uv run pytest tests/test_editor_api.py -v`

---

### Task 23: UPDATE `CLAUDE.md` — Document new modules and commands

- **IMPLEMENT**: Update project structure, commands section, and pipeline phases table:
  - Add `beat/` module description
  - Add `editor/` module description
  - Add commands: `detect-beats`, `editor`, `grab-audio`
  - Add `--mode beat-only` to `run` command docs
  - Add beat detection to pipeline phases table (Phase 4 alternate)
  - Note: "Beat detection requires `uv sync --extra beat`. Editor requires `uv sync --extra editor`."
- **VALIDATE**: Manual review

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
ruff check src/ tests/
ruff format src/ tests/
```

### Level 2: Import Check

```bash
uv run python -c "from rapmap.beat.detect import detect_beats; from rapmap.beat.grid import build_beat_grid; from rapmap.beat.quantize import quantize_anchors; print('Beat OK')"
uv run python -c "from rapmap.editor.server import create_app; print('Editor OK')"
uv run python -c "from rapmap.studio.launcher import launch_studio; from rapmap.studio.window_manager import focus_audacity; print('Studio OK')"
```

### Level 3: New Tests

```bash
uv run pytest tests/test_beat_detection.py tests/test_beat_quantize.py tests/test_editor_api.py -v
```

### Level 4: Regression Tests

```bash
uv run pytest tests/ -v
```

### Level 5: Manual Validation

1. Generate a test backing track with known BPM (e.g., click at 120 BPM):
   ```bash
   uv run python -c "
   import numpy as np; import soundfile as sf
   sr=48000; bpm=120; dur=10; audio=np.zeros(sr*dur, dtype=np.float32)
   for i in range(int(bpm*dur/60)): audio[int(i*sr*60/bpm):int(i*sr*60/bpm)+100]=0.8
   sf.write('/tmp/test_beat.wav', audio, sr)
   "
   ```
2. Run beat detection: `uv run rapmap detect-beats --project <test_workdir>`
3. Launch editor: `uv run rapmap editor --project <test_workdir>`
4. Verify native window: waveform renders, beat grid lines visible, syllable blocks draggable, save works
5. Launch studio: `uv run rapmap studio --project <test_workdir>`
6. Verify: Audacity opens, editor window opens, both arranged on screen
7. Click "Switch to Audacity" — verify Audacity comes to front
8. Click "Grab Audio" — verify tracks exported (if audio loaded in Audacity)
9. Drag syllables, click "Render + Apply" — verify corrected clips appear in Audacity

---

## ACCEPTANCE CRITERIA

- [ ] `detect_beats()` extracts BPM from backing track within 2% of actual
- [ ] `build_beat_grid()` produces correct subdivision positions
- [ ] `quantize_anchors()` outputs valid anchor_map consumable by `create_edit_plan()` unchanged
- [ ] `rapmap run --mode beat-only` completes full pipeline without AI guide
- [ ] `rapmap grab-audio` exports tracks from Audacity via pipe
- [ ] `rapmap editor` opens native window (pywebview) with waveform display
- [ ] `rapmap studio` launches Audacity + editor side-by-side
- [ ] "Switch to Audacity" button brings Audacity to front
- [ ] "Grab Audio" button exports tracks from Audacity into project dir
- [ ] "Render + Apply" button runs pipeline and imports clips back to Audacity
- [ ] Beat grid lines overlay on waveform at correct positions
- [ ] Syllable blocks are draggable and snap to beat grid
- [ ] Save button writes modified anchor_map to disk
- [ ] After save, `rapmap render` + `rapmap audacity` produce corrected output using edited timing
- [ ] All new tests pass
- [ ] All existing 112 tests still pass
- [ ] CLAUDE.md updated

---

## COMPLETION CHECKLIST

- [ ] All 23 tasks completed in order
- [ ] Each task validation passed
- [ ] All validation commands pass
- [ ] Manual editor test successful
- [ ] Ready for `/commit`

---

## NOTES

### pywebview + Flask: native feel without desktop framework complexity

pywebview opens a native OS webview window (WebKit on macOS, EdgeChromium on Windows, GTK WebKit on Linux) — no browser chrome, no URL bar, no tabs. It looks and feels like a desktop app. Flask runs in a daemon thread, serving the same HTML/JS/CSS. This gives us:
- wavesurfer.js for waveform rendering (battle-tested, used by SoundCloud)
- Native drag-and-drop and canvas support from the browser engine
- No PyQt, no Electron, no Tauri, no Rust toolchain
- Cross-platform: pywebview handles platform differences
- `--browser` flag as escape hatch if pywebview has issues on a specific platform

### Studio launcher: one command, two windows, seamless switching

`rapmap studio` launches Audacity as a subprocess, opens the editor in pywebview, and arranges both windows side-by-side using OS-level window management (AppleScript on macOS, wmctrl on Linux, PowerShell on Windows). The editor's "Switch to Audacity" button brings Audacity to front via the same mechanism. The user never alt-tabs or manages windows manually.

Window arrangement is best-effort — if the OS-level commands fail (wmctrl not installed, Audacity not found), it degrades gracefully: both windows still open, just not auto-arranged.

### "guide_*" field reuse in beat-only mode

The beat-quantized anchor_map uses `guide_anchor_sample`, `guide_start_sample`, etc. even though there's no AI guide. These fields hold beat-grid target positions. This is intentional — the planner/renderer/validator read these fields by name. The `"source": "beat_grid"` metadata field disambiguates.

### Editor JS complexity

Task 15 (editor.js) is the largest and hardest task. The drag-snap-constrain logic for syllable blocks requires careful coordinate math between sample space (integers) and pixel space (floats). Sync between two waveform views adds complexity. Estimate ~300-500 lines of JS. The wavesurfer.js Regions plugin could simplify some of this if it supports custom snap behavior — check before implementing from scratch.

### "Render + Apply" replaces manual CLI steps

The editor's "Render + Apply" button replaces the old workflow of: save → switch to terminal → run `rapmap render` → run `rapmap audacity` → switch to Audacity. Now it's one click: the server saves the anchor_map, runs the edit planner, renders clips, and imports them into Audacity via pipe. The user drags syllables, clicks "Render + Apply," clicks "Switch to Audacity," and hits play.

### Future: real-time preview

Currently there's no stretched audio preview in the editor — "Play Original" plays the unmodified vocal. Real-time stretched preview would require WebAudio time-stretching (SoundTouch.js or phase vocoder). For now, the fast path is "Render + Apply" → listen in Audacity. Real-time preview is a future enhancement.

### Platform dependencies for window management

- **macOS**: AppleScript (`osascript`) — built in, always works
- **Linux**: `wmctrl` — may need `sudo apt install wmctrl`. Degrades gracefully if missing.
- **Windows**: PowerShell `AppActivate` — built in on Windows 10+
- **pywebview**: Uses WebKit (macOS), EdgeChromium (Windows), GTK WebKit (Linux). Install is `pip install pywebview`. On Linux may need `sudo apt install python3-gi gir1.2-webkit2-4.0`.
