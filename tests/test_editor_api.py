from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest


def _make_wav(path: Path, duration_samples: int = 48000, sr: int = 48000) -> None:
    num_samples = duration_samples
    data_size = num_samples * 4
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))
        f.write(struct.pack("<HHIIHH", 3, 1, sr, sr * 4, 4, 32))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)


def _setup_project(tmp_path: Path) -> Path:
    proj = tmp_path / "test_project"
    proj.mkdir()

    (proj / "project.json").write_text(json.dumps({
        "sample_rate": 48000,
        "human_path": "audio/human_rap.wav",
    }))

    _make_wav(proj / "audio" / "backing.wav")
    _make_wav(proj / "audio" / "human_rap.wav")

    anchor_map = {
        "sample_rate": 48000,
        "anchor_strategy": "onset",
        "syllable_count": 2,
        "anchors": [
            {
                "syllable_index": 0,
                "human_anchor_sample": 1000,
                "guide_anchor_sample": 1000,
                "delta_samples": 0,
                "human_start_sample": 1000,
                "human_end_sample": 1500,
                "guide_start_sample": 1000,
                "guide_end_sample": 1500,
                "confidence": 1.0,
            },
            {
                "syllable_index": 1,
                "human_anchor_sample": 2000,
                "guide_anchor_sample": 2000,
                "delta_samples": 0,
                "human_start_sample": 2000,
                "human_end_sample": 2500,
                "guide_start_sample": 2000,
                "guide_end_sample": 2500,
                "confidence": 1.0,
            },
        ],
    }
    (proj / "timing").mkdir()
    (proj / "timing" / "anchor_map.json").write_text(json.dumps(anchor_map))

    canonical = {
        "syllables": [
            {"text": "hel", "word_index": 0},
            {"text": "lo", "word_index": 0},
        ],
    }
    (proj / "lyrics").mkdir()
    (proj / "lyrics" / "canonical_syllables.json").write_text(json.dumps(canonical))

    return proj


@pytest.fixture
def project_dir(tmp_path):
    return _setup_project(tmp_path)


@pytest.fixture
def client(project_dir):
    from rapmap.editor.server import create_app

    app = create_app(project_dir)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestEditorAPI:
    def test_get_state(self, client):
        resp = client.get("/api/state")
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["sample_rate"] == 48000
        assert data["anchor_map"] is not None
        assert data["anchor_map"]["syllable_count"] == 2
        assert data["canonical_syllables"] is not None
        assert "backing" in data["audio_urls"]
        assert "human" in data["audio_urls"]

    def test_save_anchor_map(self, client, project_dir):
        anchor_map = {
            "sample_rate": 48000,
            "anchor_strategy": "onset",
            "syllable_count": 2,
            "anchors": [
                {
                    "syllable_index": 0,
                    "human_anchor_sample": 1000,
                    "guide_anchor_sample": 1100,
                    "delta_samples": -100,
                    "human_start_sample": 1000,
                    "human_end_sample": 1500,
                    "guide_start_sample": 1100,
                    "guide_end_sample": 1600,
                    "confidence": 1.0,
                },
                {
                    "syllable_index": 1,
                    "human_anchor_sample": 2000,
                    "guide_anchor_sample": 2200,
                    "delta_samples": -200,
                    "human_start_sample": 2000,
                    "human_end_sample": 2500,
                    "guide_start_sample": 2200,
                    "guide_end_sample": 2700,
                    "confidence": 1.0,
                },
            ],
        }

        resp = client.post(
            "/api/anchor_map",
            data=json.dumps(anchor_map),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

        saved = json.loads((project_dir / "timing" / "anchor_map.json").read_text())
        assert saved["anchors"][0]["guide_anchor_sample"] == 1100

    def test_save_anchor_map_rejects_non_monotonic(self, client):
        anchor_map = {
            "sample_rate": 48000,
            "anchor_strategy": "onset",
            "syllable_count": 2,
            "anchors": [
                {
                    "syllable_index": 0,
                    "guide_anchor_sample": 2000,
                    "human_anchor_sample": 1000,
                    "delta_samples": -1000,
                    "human_start_sample": 1000,
                    "human_end_sample": 1500,
                    "guide_start_sample": 2000,
                    "guide_end_sample": 2500,
                    "confidence": 1.0,
                },
                {
                    "syllable_index": 1,
                    "guide_anchor_sample": 1500,
                    "human_anchor_sample": 2000,
                    "delta_samples": 500,
                    "human_start_sample": 2000,
                    "human_end_sample": 2500,
                    "guide_start_sample": 1500,
                    "guide_end_sample": 2000,
                    "confidence": 1.0,
                },
            ],
        }

        resp = client.post(
            "/api/anchor_map",
            data=json.dumps(anchor_map),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "Non-monotonic" in data["error"]

    def test_save_anchor_map_rejects_missing_top_fields(self, client):
        anchor_map = {
            "anchors": [
                {
                    "syllable_index": 0,
                    "guide_anchor_sample": 1000,
                    "human_anchor_sample": 1000,
                    "delta_samples": 0,
                    "human_start_sample": 1000,
                    "human_end_sample": 1500,
                    "guide_start_sample": 1000,
                    "guide_end_sample": 1500,
                    "confidence": 1.0,
                },
            ],
        }
        resp = client.post(
            "/api/anchor_map",
            data=json.dumps(anchor_map),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "Missing required field" in resp.get_json()["error"]

    def test_save_anchor_map_rejects_missing_anchor_fields(self, client):
        anchor_map = {
            "sample_rate": 48000,
            "anchor_strategy": "onset",
            "syllable_count": 1,
            "anchors": [
                {
                    "syllable_index": 0,
                    "guide_anchor_sample": 1000,
                },
            ],
        }
        resp = client.post(
            "/api/anchor_map",
            data=json.dumps(anchor_map),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "missing required field" in resp.get_json()["error"].lower()

    def test_save_anchor_map_rejects_count_mismatch(self, client):
        anchor_map = {
            "sample_rate": 48000,
            "anchor_strategy": "onset",
            "syllable_count": 5,
            "anchors": [
                {
                    "syllable_index": 0,
                    "guide_anchor_sample": 1000,
                    "human_anchor_sample": 1000,
                    "delta_samples": 0,
                    "human_start_sample": 1000,
                    "human_end_sample": 1500,
                    "guide_start_sample": 1000,
                    "guide_end_sample": 1500,
                    "confidence": 1.0,
                },
            ],
        }
        resp = client.post(
            "/api/anchor_map",
            data=json.dumps(anchor_map),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "syllable_count" in resp.get_json()["error"]

    def test_save_anchor_map_rejects_negative_samples(self, client):
        anchor_map = {
            "sample_rate": 48000,
            "anchor_strategy": "onset",
            "syllable_count": 1,
            "anchors": [
                {
                    "syllable_index": 0,
                    "human_anchor_sample": 1000,
                    "guide_anchor_sample": -50,
                    "delta_samples": 1050,
                    "human_start_sample": 1000,
                    "human_end_sample": 1500,
                    "guide_start_sample": -50,
                    "guide_end_sample": 450,
                    "confidence": 1.0,
                },
            ],
        }
        resp = client.post(
            "/api/anchor_map",
            data=json.dumps(anchor_map),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "negative" in resp.get_json()["error"].lower()

    def test_render_apply_rejects_invalid_anchor_map(self, client):
        bad_anchor_map = {
            "anchors": [{"syllable_index": 0, "guide_anchor_sample": 1000}],
        }
        resp = client.post(
            "/api/render-apply",
            data=json.dumps({"anchor_map": bad_anchor_map}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "Missing required field" in resp.get_json()["error"]

    def test_render_apply_rejects_negative_samples(self, client):
        anchor_map = {
            "sample_rate": 48000,
            "anchor_strategy": "onset",
            "syllable_count": 1,
            "anchors": [
                {
                    "syllable_index": 0,
                    "human_anchor_sample": 1000,
                    "guide_anchor_sample": -10,
                    "delta_samples": 1010,
                    "human_start_sample": 1000,
                    "human_end_sample": 1500,
                    "guide_start_sample": -10,
                    "guide_end_sample": 490,
                    "confidence": 1.0,
                },
            ],
        }
        resp = client.post(
            "/api/render-apply",
            data=json.dumps({"anchor_map": anchor_map}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "negative" in resp.get_json()["error"].lower()

    def test_serve_audio_file(self, client):
        resp = client.get("/audio/backing.wav")
        assert resp.status_code == 200
        assert resp.content_type in ("audio/wav", "audio/x-wav")
