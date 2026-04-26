from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory


def _validate_anchor_map(data: dict | None) -> str | None:
    if not data or "anchors" not in data:
        return "Missing anchors in request body"

    for top_key in ("sample_rate", "anchor_strategy", "syllable_count"):
        if top_key not in data:
            return f"Missing required field: {top_key}"

    anchors = data["anchors"]
    if data["syllable_count"] != len(anchors):
        return (
            f"syllable_count ({data['syllable_count']}) "
            f"!= len(anchors) ({len(anchors)})"
        )

    required_anchor_fields = (
        "syllable_index",
        "human_anchor_sample",
        "guide_anchor_sample",
        "delta_samples",
        "human_start_sample",
        "human_end_sample",
        "guide_start_sample",
        "guide_end_sample",
        "confidence",
    )
    sample_fields = (
        "human_anchor_sample",
        "guide_anchor_sample",
        "human_start_sample",
        "human_end_sample",
        "guide_start_sample",
        "guide_end_sample",
    )
    for i, a in enumerate(anchors):
        for field in required_anchor_fields:
            if field not in a:
                return f"Anchor {i} missing required field: {field}"
        for field in sample_fields:
            if a[field] < 0:
                return f"Anchor {i} has negative {field}: {a[field]}"

    for i in range(1, len(anchors)):
        if anchors[i]["guide_anchor_sample"] <= anchors[i - 1]["guide_anchor_sample"]:
            return (
                f"Non-monotonic guide_anchor_sample at index {i}: "
                f"{anchors[i]['guide_anchor_sample']} <= "
                f"{anchors[i - 1]['guide_anchor_sample']}"
            )

    return None


def create_app(project_dir: Path) -> Flask:
    app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"))
    app.config["PROJECT_DIR"] = project_dir

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/static/<path:filename>")
    def serve_static(filename):
        return send_from_directory(app.static_folder, filename)

    @app.route("/audio/<path:filename>")
    def serve_audio(filename):
        audio_dir = Path(app.config["PROJECT_DIR"]) / "audio"
        return send_from_directory(audio_dir, filename)

    @app.route("/api/state")
    def get_state():
        proj = Path(app.config["PROJECT_DIR"])

        anchor_map = None
        anchor_path = proj / "timing" / "anchor_map.json"
        if anchor_path.exists():
            with open(anchor_path) as f:
                anchor_map = json.load(f)

        beat_grid = None
        grid_path = proj / "timing" / "beat_grid.json"
        if grid_path.exists():
            with open(grid_path) as f:
                beat_grid = json.load(f)

        canonical = None
        canon_path = proj / "lyrics" / "canonical_syllables.json"
        if canon_path.exists():
            with open(canon_path) as f:
                canonical = json.load(f)

        proj_meta = {}
        proj_json = proj / "project.json"
        if proj_json.exists():
            with open(proj_json) as f:
                proj_meta = json.load(f)

        audio_urls = {}
        audio_dir = proj / "audio"
        if (audio_dir / "backing.wav").exists():
            audio_urls["backing"] = "/audio/backing.wav"
        if (audio_dir / "human_rap.wav").exists():
            audio_urls["human"] = "/audio/human_rap.wav"

        return jsonify({
            "sample_rate": proj_meta.get("sample_rate", 48000),
            "anchor_map": anchor_map,
            "beat_grid": beat_grid,
            "canonical_syllables": canonical,
            "audio_urls": audio_urls,
        })

    @app.route("/api/anchor_map", methods=["POST"])
    def save_anchor_map():
        proj = Path(app.config["PROJECT_DIR"])
        data = request.get_json()
        error = _validate_anchor_map(data)
        if error:
            return jsonify({"error": error}), 400

        timing_dir = proj / "timing"
        timing_dir.mkdir(parents=True, exist_ok=True)
        with open(timing_dir / "anchor_map.json", "w") as f:
            json.dump(data, f, indent=2)

        return jsonify({"ok": True})

    @app.route("/api/focus-audacity", methods=["POST"])
    def focus_audacity():
        from rapmap.studio.window_manager import focus_audacity as _focus

        ok = _focus()
        return jsonify({"ok": ok})

    @app.route("/api/grab-audio", methods=["POST"])
    def grab_audio():
        proj = Path(app.config["PROJECT_DIR"])
        body = request.get_json(silent=True) or {}
        backing_track = body.get("backing_track", 0)
        vocal_track = body.get("vocal_track", 1)

        from rapmap.audacity.script_pipe import AudacityPipe

        pipe = AudacityPipe()
        if not pipe.connect():
            return jsonify({"error": "Could not connect to Audacity"}), 503

        audio_dir = proj / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        tracks = [
            (backing_track, "backing.wav"),
            (vocal_track, "human_rap.wav"),
        ]
        exported = 0
        try:
            for track_idx, filename in tracks:
                pipe.solo_track(track_idx, True)
                pipe.select_all()
                if pipe.export_audio(audio_dir / filename):
                    exported += 1
                pipe.solo_track(track_idx, False)
        finally:
            for track_idx, _ in tracks:
                pipe.solo_track(track_idx, False)
            pipe.close()

        return jsonify({"ok": True, "tracks_exported": exported})

    @app.route("/api/render-apply", methods=["POST"])
    def render_apply():
        proj = Path(app.config["PROJECT_DIR"])
        timing_dir = proj / "timing"
        anchor_map_path = timing_dir / "anchor_map.json"

        previous_anchor_map = None
        if anchor_map_path.exists():
            with open(anchor_map_path) as f:
                previous_anchor_map = f.read()

        body = request.get_json(silent=True)
        if body and "anchor_map" in body:
            error = _validate_anchor_map(body["anchor_map"])
            if error:
                return jsonify({"error": error}), 400
            timing_dir.mkdir(parents=True, exist_ok=True)
            with open(anchor_map_path, "w") as f:
                json.dump(body["anchor_map"], f, indent=2)

        try:
            from rapmap.audio.io import read_audio
            from rapmap.audio.render import render_clips
            from rapmap.config import load_config as _load_config
            from rapmap.edit.grouping import group_syllables
            from rapmap.edit.operations import edit_plan_to_dict
            from rapmap.edit.planner import create_edit_plan

            config = _load_config()

            with open(proj / "project.json") as f:
                proj_meta = json.load(f)
            sr = proj_meta["sample_rate"]

            with open(proj / "lyrics" / "canonical_syllables.json") as f:
                canonical = json.load(f)
            with open(anchor_map_path) as f:
                anchor_map = json.load(f)

            human_path = proj / proj_meta.get(
                "human_analysis_path",
                proj_meta.get("human_path", "audio/human_rap.wav"),
            )
            human_audio, _ = read_audio(human_path, mono=True)

            clip_groups = group_syllables(
                canonical, anchor_map, None, None, sr,
                config.clip_grouping, "word",
            )
            edit_plan = create_edit_plan(clip_groups, anchor_map, config.rendering)

            edit_dir = proj / "edit"
            edit_dir.mkdir(parents=True, exist_ok=True)
            with open(edit_dir / "edit_plan.json", "w") as f:
                json.dump(edit_plan_to_dict(edit_plan), f, indent=2)

            result = render_clips(
                edit_plan, human_audio, sr, proj, config.rendering, anchor_map,
                fail_on_anchor_error=config.validation.require_zero_sample_anchor_error,
            )

            from rapmap.audacity.import_project import build_audacity_session

            build_audacity_session(proj, config.audacity)

            return jsonify({
                "ok": True,
                "report": result["report"],
            })
        except Exception as e:
            if previous_anchor_map is not None:
                with open(anchor_map_path, "w") as f:
                    f.write(previous_anchor_map)
            elif anchor_map_path.exists():
                anchor_map_path.unlink()
            return jsonify({"error": str(e)}), 500

    return app


def launch_editor(project_dir: Path, port: int = 8765, use_webview: bool = True) -> None:
    app = create_app(project_dir)
    if use_webview:
        import threading

        import webview

        server_thread = threading.Thread(
            target=lambda: app.run(port=port, debug=False, use_reloader=False),
            daemon=True,
        )
        server_thread.start()
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
