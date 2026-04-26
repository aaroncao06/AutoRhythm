from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProjectConfig:
    sample_rate: int = 48000
    internal_audio_format: str = "wav"
    vocal_analysis_mono: bool = True


@dataclass
class GuideGenerationConfig:
    mode: str = "manual"
    model: str = "songgeneration"
    allow_full_mix: bool = True
    source_separate_if_needed: bool = True
    fallback_manual_guide: bool = True


@dataclass
class SyllableDetectionConfig:
    mode: str = "auto"
    manual_overrides: str = "optional"
    pronunciation_dictionary: str = "cmudict"
    g2p_fallback: bool = True
    preserve_bars_from_newlines: bool = True


@dataclass
class AlignmentConfig:
    primary_backend: str = "mfa"
    fallback_backend: str = "whisperx"
    require_exact_syllable_count: bool = True
    min_syllable_confidence: float = 0.70
    fail_on_missing_syllables: bool = True
    fail_on_alignment_error: bool = True
    max_low_confidence_fraction: float = 0.2
    phoneme_smoothing_min_ms: float = 15.0
    energy_fallback: bool = True
    multi_pronunciation: bool = True


@dataclass
class AnchorStrategyConfig:
    default: str = "onset"


@dataclass
class BeatDetectionConfig:
    subdivision: str = "eighth"
    quantize_strength: float = 1.0
    min_bpm: int = 60
    max_bpm: int = 200
    hop_length: int = 512


@dataclass
class SafeBoundaryConfig:
    min_silence_ms: float = 20
    low_energy_window_ms: float = 12
    zero_crossing_search_ms: float = 4
    min_clip_duration_ms: float = 80
    max_clip_duration_ms: float = 2500
    max_syllables_per_clip: int = 8
    prefer_word_boundaries: bool = True
    prefer_line_boundaries: bool = True
    avoid_inside_words: bool = True
    avoid_vowel_cuts: bool = True
    allow_cut_before_plosives: bool = True


@dataclass
class ClipGroupingConfig:
    default: str = "safe_boundary"
    safe_boundary: SafeBoundaryConfig = field(default_factory=SafeBoundaryConfig)


@dataclass
class RenderingConfig:
    backend: str = "rubberband"
    preserve_pitch: bool = True
    deterministic: bool = True
    rendering_mode: str = "warp"
    crossfade_ms: float = 8
    pre_handle_ms: float = 20
    post_handle_ms: float = 20
    output_flattened_preview: bool = True
    output_individual_clips: bool = True
    min_stretch_ratio: float = 0.50
    max_stretch_ratio: float = 2.00
    fail_on_extreme_stretch: bool = False


@dataclass
class AudacityConfig:
    integration: str = "mod_script_pipe"
    create_label_tracks: bool = True
    import_grouped_clips: bool = True
    import_flattened_preview: bool = True
    open_after_render: bool = True


@dataclass
class ValidationConfig:
    require_zero_sample_anchor_error: bool = True
    fail_on_alignment_error: bool = True
    fail_on_render_mismatch: bool = True


@dataclass
class RapMapConfig:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    guide_generation: GuideGenerationConfig = field(default_factory=GuideGenerationConfig)
    syllable_detection: SyllableDetectionConfig = field(default_factory=SyllableDetectionConfig)
    alignment: AlignmentConfig = field(default_factory=AlignmentConfig)
    anchor_strategy: AnchorStrategyConfig = field(default_factory=AnchorStrategyConfig)
    beat_detection: BeatDetectionConfig = field(default_factory=BeatDetectionConfig)
    clip_grouping: ClipGroupingConfig = field(default_factory=ClipGroupingConfig)
    rendering: RenderingConfig = field(default_factory=RenderingConfig)
    audacity: AudacityConfig = field(default_factory=AudacityConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)


def load_config(config_path: Path | None = None) -> RapMapConfig:
    if config_path is None or not config_path.exists():
        return RapMapConfig()

    with open(config_path) as f:
        if config_path.suffix == ".json":
            raw = json.load(f)
        else:
            raw = yaml.safe_load(f) or {}

    return _merge_config(RapMapConfig(), raw)


def _merge_section(section: Any, overrides: dict[str, Any]) -> None:
    for key, value in overrides.items():
        if not hasattr(section, key):
            continue
        existing = getattr(section, key)
        if isinstance(value, dict) and dataclasses.is_dataclass(existing):
            _merge_section(existing, value)
        else:
            setattr(section, key, value)


def _merge_config(config: RapMapConfig, overrides: dict[str, Any]) -> RapMapConfig:
    for section_name, section_overrides in overrides.items():
        if not isinstance(section_overrides, dict):
            continue
        section = getattr(config, section_name, None)
        if section is None:
            continue
        _merge_section(section, section_overrides)
    return config
