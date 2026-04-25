import numpy as np
import soundfile as sf

from rapmap.config import ProjectConfig
from rapmap.guide.manual import load_manual_guide


def test_load_manual_guide(tmp_path):
    guide = tmp_path / "guide.wav"
    sr = 48000
    data = np.random.randn(sr * 2).astype(np.float32)
    sf.write(str(guide), data, sr, subtype="FLOAT")

    project = tmp_path / "project"
    project.mkdir()

    result = load_manual_guide(guide, project, ProjectConfig())
    assert result.path.exists()
    assert result.sample_rate == 48000
    assert result.source == "manual"
    assert result.duration_samples == sr * 2


def test_guide_resampled(tmp_path):
    guide = tmp_path / "guide_44k.wav"
    data = np.random.randn(44100).astype(np.float32)
    sf.write(str(guide), data, 44100, subtype="FLOAT")

    project = tmp_path / "project"
    project.mkdir()

    result = load_manual_guide(guide, project, ProjectConfig(sample_rate=48000))
    assert result.sample_rate == 48000
    assert result.duration_samples == 48000


def test_guide_result_metadata(tmp_path):
    guide = tmp_path / "guide.wav"
    sf.write(str(guide), np.zeros(4800, dtype=np.float32), 48000, subtype="FLOAT")

    project = tmp_path / "project"
    project.mkdir()

    result = load_manual_guide(guide, project, ProjectConfig())
    assert result.duration_samples == 4800
    assert result.path.name == "ai_guide_vocal.wav"
