import pytest

from rapmap.align.base import AlignmentResult, PhoneTimestamp, SyllableTimestamp
from rapmap.align.validate import validate_alignment
from rapmap.config import AlignmentConfig, AnchorStrategyConfig
from rapmap.timing.anchor_map import build_anchor_map
from rapmap.timing.anchors import extract_anchor


def _make_alignment(syllables_data, sample_rate=48000, role="guide"):
    syllables = []
    for i, (start, end, word) in enumerate(syllables_data):
        syllables.append(
            SyllableTimestamp(
                syllable_index=i,
                word_index=i,
                word_text=word,
                start_sample=start,
                end_sample=end,
                anchor_sample=start,
                phones=[PhoneTimestamp(phone="AH1", start_sample=start, end_sample=end)],
                confidence=0.9,
            )
        )
    return AlignmentResult(
        sample_rate=sample_rate,
        role=role,
        audio_path="test.wav",
        total_duration_samples=syllables_data[-1][1] if syllables_data else 0,
        words=[],
        syllables=syllables,
    )


def test_onset_anchor_extraction():
    syl = SyllableTimestamp(
        syllable_index=0, word_index=0, word_text="test",
        start_sample=100, end_sample=200, anchor_sample=100,
        phones=[PhoneTimestamp(phone="AH1", start_sample=100, end_sample=200)],
    )
    assert extract_anchor(syl, "onset") == 100


def test_end_anchor_extraction():
    syl = SyllableTimestamp(
        syllable_index=0, word_index=0, word_text="test",
        start_sample=100, end_sample=200, anchor_sample=100,
        phones=[PhoneTimestamp(phone="AH1", start_sample=100, end_sample=200)],
    )
    assert extract_anchor(syl, "end") == 200


def test_vowel_nucleus_anchor():
    syl = SyllableTimestamp(
        syllable_index=0, word_index=0, word_text="test",
        start_sample=100, end_sample=300, anchor_sample=100,
        phones=[
            PhoneTimestamp(phone="T", start_sample=100, end_sample=150),
            PhoneTimestamp(phone="AH1", start_sample=150, end_sample=250),
            PhoneTimestamp(phone="S", start_sample=250, end_sample=300),
        ],
    )
    assert extract_anchor(syl, "vowel_nucleus") == 200


def test_anchor_map_construction():
    guide = _make_alignment([(1000, 2000, "I"), (3000, 4000, "got")], role="guide")
    human = _make_alignment([(1500, 2500, "I"), (3500, 4500, "got")], role="human")
    config = AnchorStrategyConfig(default="onset")

    result = build_anchor_map(guide, human, config)
    assert result["syllable_count"] == 2
    assert result["anchors"][0]["guide_anchor_sample"] == 1000
    assert result["anchors"][0]["human_anchor_sample"] == 1500
    assert result["anchors"][0]["delta_samples"] == 500


def test_anchor_map_monotonic():
    guide = _make_alignment(
        [(1000, 2000, "I"), (3000, 4000, "got"), (5000, 6000, "it")], role="guide"
    )
    human = _make_alignment(
        [(1500, 2500, "I"), (3500, 4500, "got"), (5500, 6500, "it")], role="human"
    )
    config = AnchorStrategyConfig(default="onset")
    result = build_anchor_map(guide, human, config)
    anchors = [a["guide_anchor_sample"] for a in result["anchors"]]
    assert anchors == sorted(anchors)
    assert len(set(anchors)) == len(anchors)


def test_anchor_map_non_monotonic_fails():
    guide_syls = [
        SyllableTimestamp(
            syllable_index=0, word_index=0, word_text="a",
            start_sample=2000, end_sample=3000, anchor_sample=2000,
            phones=[PhoneTimestamp(phone="AH1", start_sample=2000, end_sample=3000)],
        ),
        SyllableTimestamp(
            syllable_index=1, word_index=1, word_text="b",
            start_sample=1000, end_sample=2000, anchor_sample=1000,
            phones=[PhoneTimestamp(phone="AH1", start_sample=1000, end_sample=2000)],
        ),
    ]
    guide = AlignmentResult(
        sample_rate=48000, role="guide", audio_path="g.wav",
        total_duration_samples=3000, syllables=guide_syls,
    )
    human = _make_alignment([(500, 1500, "a"), (2000, 3000, "b")], role="human")
    config = AnchorStrategyConfig(default="onset")
    with pytest.raises(AssertionError, match="Non-monotonic"):
        build_anchor_map(guide, human, config)


def test_syllable_count_mismatch_fails():
    guide = _make_alignment([(1000, 2000, "I")], role="guide")
    human = _make_alignment([(1000, 2000, "I"), (3000, 4000, "got")], role="human")
    config = AnchorStrategyConfig(default="onset")
    with pytest.raises(AssertionError, match="Syllable count mismatch"):
        build_anchor_map(guide, human, config)


def test_removed_strategies_rejected():
    syl = SyllableTimestamp(
        syllable_index=0, word_index=0, word_text="test",
        start_sample=100, end_sample=200, anchor_sample=100,
        phones=[PhoneTimestamp(phone="AH1", start_sample=100, end_sample=200)],
    )
    for strategy in ["onset_and_end", "hybrid", "nonexistent"]:
        with pytest.raises(ValueError, match="Unknown anchor strategy"):
            extract_anchor(syl, strategy)


def test_validate_low_confidence_fraction_fails():
    alignment = _make_alignment(
        [(1000, 2000, "a"), (3000, 4000, "b"), (5000, 6000, "c")],
        role="human",
    )
    for s in alignment.syllables:
        s.confidence = 0.1
    canonical = {
        "syllables": [
            {"syllable_index": i, "word_index": i, "word_text": w}
            for i, w in enumerate(["a", "b", "c"])
        ]
    }
    config = AlignmentConfig(
        fail_on_alignment_error=True,
        min_syllable_confidence=0.7,
        max_low_confidence_fraction=0.2,
    )
    with pytest.raises(ValueError, match="Low-confidence syllables"):
        validate_alignment(alignment, canonical, config)


def test_validate_low_confidence_within_threshold_passes():
    alignment = _make_alignment(
        [(1000, 2000, "a"), (3000, 4000, "b"), (5000, 6000, "c"),
         (7000, 8000, "d"), (9000, 10000, "e")],
        role="human",
    )
    alignment.syllables[0].confidence = 0.1
    canonical = {
        "syllables": [
            {"syllable_index": i, "word_index": i, "word_text": w}
            for i, w in enumerate(["a", "b", "c", "d", "e"])
        ]
    }
    config = AlignmentConfig(
        fail_on_alignment_error=True,
        min_syllable_confidence=0.7,
        max_low_confidence_fraction=0.2,
    )
    result = validate_alignment(alignment, canonical, config)
    assert result["low_confidence_count"] == 1
    assert result["passed"]
