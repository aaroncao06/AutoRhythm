import numpy as np
import pytest

from rapmap.align.base import AlignmentResult, PhoneTimestamp, SyllableTimestamp
from rapmap.config import ClipGroupingConfig, SafeBoundaryConfig
from rapmap.edit.grouping import group_syllables
from rapmap.edit.safe_boundaries import score_boundaries


def _make_canonical(syllable_data):
    syllables = []
    for i, (text, word_idx, word_text, is_word_final, is_line_final) in enumerate(
        syllable_data
    ):
        syllables.append(
            {
                "syllable_index": i,
                "syllable_text": text,
                "word_index": word_idx,
                "word_text": word_text,
                "line_index": 0,
                "bar_index": 0,
                "is_word_final": is_word_final,
                "is_line_final": is_line_final,
            }
        )
    return {"syllables": syllables}


def _make_anchor_map(n, sr=48000, guide_offset=0, human_offset=500):
    anchors = []
    for i in range(n):
        g_start = guide_offset + i * 4800
        g_end = g_start + 3600
        h_start = human_offset + i * 5000
        h_end = h_start + 3800
        anchors.append(
            {
                "syllable_index": i,
                "guide_anchor_sample": g_start,
                "human_anchor_sample": h_start,
                "guide_start_sample": g_start,
                "guide_end_sample": g_end,
                "human_start_sample": h_start,
                "human_end_sample": h_end,
                "delta_samples": h_start - g_start,
            }
        )
    return {"sample_rate": sr, "anchor_strategy": "onset", "anchors": anchors}


def _make_alignment(n, sr=48000, offset=500):
    syllables = []
    for i in range(n):
        start = offset + i * 5000
        end = start + 3800
        syllables.append(
            SyllableTimestamp(
                syllable_index=i,
                word_index=i,
                word_text=f"w{i}",
                start_sample=start,
                end_sample=end,
                anchor_sample=start,
                phones=[
                    PhoneTimestamp(phone="AH1", start_sample=start, end_sample=end)
                ],
                confidence=0.9,
            )
        )
    return AlignmentResult(
        sample_rate=sr,
        role="human",
        audio_path="test.wav",
        total_duration_samples=offset + n * 5000,
        syllables=syllables,
    )


class TestGroupingModes:
    def test_strict_syllable_one_per_clip(self):
        n = 4
        canonical = _make_canonical(
            [
                ("I", 0, "I", True, False),
                ("got", 1, "got", True, False),
                ("mon", 2, "money", False, False),
                ("ey", 2, "money", True, True),
            ]
        )
        anchor_map = _make_anchor_map(n)
        config = ClipGroupingConfig()
        result = group_syllables(
            canonical, anchor_map, None, None, 48000, config, mode="strict_syllable"
        )
        assert result["clip_count"] == n
        for clip in result["clips"]:
            assert len(clip["syllable_indices"]) == 1

    def test_syllable_with_handles_one_per_clip(self):
        n = 3
        canonical = _make_canonical(
            [
                ("I", 0, "I", True, False),
                ("got", 1, "got", True, False),
                ("it", 2, "it", True, True),
            ]
        )
        anchor_map = _make_anchor_map(n)
        config = ClipGroupingConfig()
        result = group_syllables(
            canonical,
            anchor_map,
            None,
            None,
            48000,
            config,
            mode="syllable_with_handles",
        )
        assert result["clip_count"] == n

    def test_word_boundary_grouping(self):
        canonical = _make_canonical(
            [
                ("mon", 0, "money", False, False),
                ("ey", 0, "money", True, False),
                ("in", 1, "in", True, False),
                ("the", 2, "the", True, False),
                ("bank", 3, "bank", True, True),
            ]
        )
        anchor_map = _make_anchor_map(5)
        config = ClipGroupingConfig()
        result = group_syllables(
            canonical, anchor_map, None, None, 48000, config, mode="word"
        )
        assert result["clip_count"] == 4
        assert result["clips"][0]["syllable_indices"] == [0, 1]
        assert result["clips"][1]["syllable_indices"] == [2]

    def test_phrase_grouping_single_line(self):
        canonical = _make_canonical(
            [
                ("I", 0, "I", True, False),
                ("got", 1, "got", True, False),
                ("it", 2, "it", True, True),
            ]
        )
        anchor_map = _make_anchor_map(3)
        config = ClipGroupingConfig()
        result = group_syllables(
            canonical, anchor_map, None, None, 48000, config, mode="phrase"
        )
        assert result["clip_count"] == 1
        assert result["clips"][0]["syllable_indices"] == [0, 1, 2]

    def test_bar_grouping(self):
        syls = [
            ("I", 0, "I", True, False),
            ("got", 1, "got", True, False),
            ("it", 2, "it", True, False),
        ]
        canonical = _make_canonical(syls)
        canonical["syllables"][2]["bar_index"] = 1
        anchor_map = _make_anchor_map(3)
        config = ClipGroupingConfig()
        result = group_syllables(
            canonical, anchor_map, None, None, 48000, config, mode="bar"
        )
        assert result["clip_count"] == 2
        assert result["clips"][0]["syllable_indices"] == [0, 1]
        assert result["clips"][1]["syllable_indices"] == [2]

    def test_unknown_mode_fails(self):
        canonical = _make_canonical([("I", 0, "I", True, True)])
        anchor_map = _make_anchor_map(1)
        config = ClipGroupingConfig()
        with pytest.raises(ValueError, match="Unknown grouping mode"):
            group_syllables(
                canonical, anchor_map, None, None, 48000, config, mode="nonexistent"
            )


class TestSafeBoundaryGrouping:
    def _setup(self, n):
        syl_data = [
            (f"s{i}", i, f"w{i}", True, i == n - 1) for i in range(n)
        ]
        canonical = _make_canonical(syl_data)
        anchor_map = _make_anchor_map(n)
        alignment = _make_alignment(n)
        audio = np.random.randn(n * 6000).astype(np.float32) * 0.01
        return canonical, anchor_map, alignment, audio

    def test_safe_boundary_produces_valid_clips(self):
        canonical, anchor_map, alignment, audio = self._setup(6)
        config = ClipGroupingConfig()
        result = group_syllables(
            canonical, anchor_map, alignment, audio, 48000, config, mode="safe_boundary"
        )
        assert result["clip_count"] >= 1
        all_indices = []
        for clip in result["clips"]:
            all_indices.extend(clip["syllable_indices"])
        assert sorted(all_indices) == list(range(6))

    def test_safe_boundary_single_syllable(self):
        canonical, anchor_map, alignment, audio = self._setup(1)
        config = ClipGroupingConfig()
        result = group_syllables(
            canonical, anchor_map, alignment, audio, 48000, config, mode="safe_boundary"
        )
        assert result["clip_count"] == 1
        assert result["clips"][0]["syllable_indices"] == [0]

    def test_safe_boundary_requires_alignment(self):
        canonical = _make_canonical([("I", 0, "I", True, True)])
        anchor_map = _make_anchor_map(1)
        config = ClipGroupingConfig()
        with pytest.raises(AssertionError, match="safe_boundary mode requires human_alignment"):
            group_syllables(
                canonical, anchor_map, None, None, 48000, config, mode="safe_boundary"
            )


class TestAllSyllablesAssigned:
    def test_every_syllable_in_exactly_one_clip(self):
        n = 5
        canonical = _make_canonical(
            [(f"s{i}", i, f"w{i}", True, i == n - 1) for i in range(n)]
        )
        anchor_map = _make_anchor_map(n)
        for mode in ["strict_syllable", "syllable_with_handles", "word"]:
            result = group_syllables(
                canonical, anchor_map, None, None, 48000, ClipGroupingConfig(), mode=mode
            )
            all_indices = []
            for clip in result["clips"]:
                all_indices.extend(clip["syllable_indices"])
            assert sorted(all_indices) == list(range(n)), f"Failed for mode={mode}"


class TestClipMetadata:
    def test_clip_ids_sequential(self):
        canonical = _make_canonical(
            [
                ("I", 0, "I", True, False),
                ("got", 1, "got", True, False),
                ("it", 2, "it", True, True),
            ]
        )
        anchor_map = _make_anchor_map(3)
        result = group_syllables(
            canonical,
            anchor_map,
            None,
            None,
            48000,
            ClipGroupingConfig(),
            mode="strict_syllable",
        )
        for i, clip in enumerate(result["clips"]):
            assert clip["clip_index"] == i
            assert clip["clip_id"].startswith(f"clip_{i:04d}_")

    def test_clip_source_target_samples(self):
        canonical = _make_canonical([("I", 0, "I", True, True)])
        anchor_map = _make_anchor_map(1, human_offset=1000)
        result = group_syllables(
            canonical,
            anchor_map,
            None,
            None,
            48000,
            ClipGroupingConfig(),
            mode="strict_syllable",
        )
        clip = result["clips"][0]
        assert clip["source_start_sample"] == anchor_map["anchors"][0]["human_start_sample"]
        assert clip["source_end_sample"] == anchor_map["anchors"][0]["human_end_sample"]
        assert clip["target_start_sample"] == anchor_map["anchors"][0]["guide_start_sample"]
        assert clip["target_end_sample"] == anchor_map["anchors"][0]["guide_end_sample"]


class TestBoundaryScoring:
    def test_score_count(self):
        canonical = _make_canonical(
            [
                ("I", 0, "I", True, False),
                ("got", 1, "got", True, False),
                ("it", 2, "it", True, True),
            ]
        )
        alignment = _make_alignment(3)
        audio = np.random.randn(20000).astype(np.float32) * 0.01
        config = SafeBoundaryConfig()
        scores = score_boundaries(canonical, alignment, audio, 48000, config)
        assert len(scores) == 2

    def test_single_syllable_no_boundaries(self):
        canonical = _make_canonical([("I", 0, "I", True, True)])
        alignment = _make_alignment(1)
        audio = np.random.randn(5000).astype(np.float32)
        scores = score_boundaries(canonical, alignment, audio, 48000, SafeBoundaryConfig())
        assert len(scores) == 0

    def test_word_boundary_bonus(self):
        canonical = _make_canonical(
            [
                ("mon", 0, "money", False, False),
                ("ey", 0, "money", True, False),
                ("in", 1, "in", True, True),
            ]
        )
        alignment = _make_alignment(3)
        audio = np.zeros(20000, dtype=np.float32)
        config = SafeBoundaryConfig()
        scores = score_boundaries(canonical, alignment, audio, 48000, config)
        assert scores[1] > scores[0]
