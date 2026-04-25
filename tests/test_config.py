from pathlib import Path

from rapmap.config import RapMapConfig, load_config


def test_default_config():
    config = RapMapConfig()
    assert config.project.sample_rate == 48000
    assert config.anchor_strategy.default == "onset"
    assert config.clip_grouping.default == "safe_boundary"
    assert config.rendering.preserve_pitch is True
    assert config.validation.require_zero_sample_anchor_error is True


def test_load_config_no_file():
    config = load_config(None)
    assert config.project.sample_rate == 48000


def test_load_config_yaml(tmp_path: Path):
    cfg_file = tmp_path / "test.yaml"
    cfg_file.write_text("project:\n  sample_rate: 44100\n")
    config = load_config(cfg_file)
    assert config.project.sample_rate == 44100
    assert config.rendering.backend == "rubberband"
