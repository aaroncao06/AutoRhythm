from pathlib import Path

import numpy as np

from rapmap.audio.io import audio_info, read_audio, write_audio
from rapmap.audio.normalize import normalize_project
from rapmap.config import ProjectConfig


def _make_test_wav(path: Path, sr: int = 48000, duration_s: float = 1.0, channels: int = 1):
    samples = int(sr * duration_s)
    if channels == 1:
        data = np.random.randn(samples).astype(np.float32) * 0.1
    else:
        data = np.random.randn(samples, channels).astype(np.float32) * 0.1
    write_audio(path, data, sr)
    return data


def test_read_write_roundtrip(tmp_path: Path):
    original = np.array([0.1, -0.2, 0.3, 0.0, -0.5], dtype=np.float32)
    wav_path = tmp_path / "test.wav"
    write_audio(wav_path, original, 48000)
    loaded, sr = read_audio(wav_path)
    assert sr == 48000
    np.testing.assert_allclose(loaded, original, atol=1e-6)


def test_stereo_to_mono(tmp_path: Path):
    wav_path = tmp_path / "stereo.wav"
    _make_test_wav(wav_path, channels=2)
    data, sr = read_audio(wav_path, mono=True)
    assert data.ndim == 1
    assert sr == 48000


def test_audio_info(tmp_path: Path):
    wav_path = tmp_path / "info_test.wav"
    _make_test_wav(wav_path, sr=48000, duration_s=0.5)
    info = audio_info(wav_path)
    assert info["sample_rate"] == 48000
    assert info["channels"] == 1
    assert info["frames"] == 24000
    assert "duration_seconds" in info


def test_normalize_project(tmp_path: Path):
    backing = tmp_path / "backing.wav"
    human = tmp_path / "human.wav"
    lyrics = tmp_path / "lyrics.txt"

    _make_test_wav(backing, sr=48000, duration_s=1.0)
    _make_test_wav(human, sr=48000, duration_s=1.0)
    lyrics.write_text("I got money on my mind")

    out_dir = tmp_path / "workdir"
    config = ProjectConfig()
    metadata = normalize_project(backing, human, lyrics, out_dir, config)

    assert (out_dir / "audio" / "backing.wav").exists()
    assert (out_dir / "audio" / "human_rap.wav").exists()
    assert (out_dir / "lyrics" / "lyrics.raw.txt").exists()
    assert (out_dir / "project.json").exists()
    assert metadata["sample_rate"] == 48000
    assert isinstance(metadata["backing_duration_samples"], int)
    assert isinstance(metadata["human_duration_samples"], int)
    assert metadata["backing_path"] == "audio/backing.wav"
    assert metadata["human_path"] == "audio/human_rap.wav"


def test_normalize_project_preserves_stereo_human_take(tmp_path: Path):
    backing = tmp_path / "backing.wav"
    human = tmp_path / "human.wav"
    lyrics = tmp_path / "lyrics.txt"

    _make_test_wav(backing, sr=48000, duration_s=1.0)
    stereo_human = _make_test_wav(human, sr=48000, duration_s=1.0, channels=2)
    lyrics.write_text("I got money on my mind")

    out_dir = tmp_path / "workdir"
    config = ProjectConfig(vocal_analysis_mono=True)
    metadata = normalize_project(backing, human, lyrics, out_dir, config)

    stored_human, sr = read_audio(out_dir / "audio" / "human_rap.wav")
    analysis_human, analysis_sr = read_audio(out_dir / "audio" / "human_rap_analysis.wav")

    assert sr == analysis_sr == 48000
    assert stored_human.ndim == 2
    assert stored_human.shape == stereo_human.shape
    assert analysis_human.ndim == 1
    np.testing.assert_allclose(analysis_human, stored_human.mean(axis=1), atol=1e-6)
    assert metadata["human_channels"] == 2
    assert metadata["human_analysis_path"] == "audio/human_rap_analysis.wav"


def test_normalize_project_honors_internal_audio_format(tmp_path: Path):
    backing = tmp_path / "backing.wav"
    human = tmp_path / "human.wav"
    lyrics = tmp_path / "lyrics.txt"

    _make_test_wav(backing, sr=48000, duration_s=1.0)
    _make_test_wav(human, sr=48000, duration_s=1.0, channels=2)
    lyrics.write_text("I got money on my mind")

    out_dir = tmp_path / "workdir"
    config = ProjectConfig(internal_audio_format="flac", vocal_analysis_mono=True)
    metadata = normalize_project(backing, human, lyrics, out_dir, config)

    assert (out_dir / "audio" / "backing.flac").exists()
    assert (out_dir / "audio" / "human_rap.flac").exists()
    assert (out_dir / "audio" / "human_rap_analysis.flac").exists()
    assert audio_info(out_dir / "audio" / "backing.flac")["sample_rate"] == 48000
    assert metadata["backing_path"] == "audio/backing.flac"
    assert metadata["human_path"] == "audio/human_rap.flac"
    assert metadata["human_analysis_path"] == "audio/human_rap_analysis.flac"


def test_resample(tmp_path: Path):
    wav_path = tmp_path / "sr44100.wav"
    _make_test_wav(wav_path, sr=44100, duration_s=1.0)

    out_dir = tmp_path / "workdir"
    human = tmp_path / "human.wav"
    lyrics = tmp_path / "lyrics.txt"
    _make_test_wav(human, sr=44100, duration_s=1.0)
    lyrics.write_text("test")

    config = ProjectConfig(sample_rate=48000)
    normalize_project(wav_path, human, lyrics, out_dir, config)

    resampled_info = audio_info(out_dir / "audio" / "backing.wav")
    assert resampled_info["sample_rate"] == 48000
    expected_len = int(44100 * 48000 / 44100)
    assert abs(resampled_info["frames"] - expected_len) <= 10
