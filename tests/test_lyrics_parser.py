import pytest

from rapmap.lyrics.parser import parse_lyrics


def test_parse_single_bar():
    result = parse_lyrics("I got money on my mind")
    assert len(result["bars"]) == 1
    assert len(result["bars"][0]["lines"]) == 1
    words = result["bars"][0]["lines"][0]["words"]
    assert len(words) == 6
    assert words[0]["text"] == "I"
    assert words[2]["normalized"] == "money"


def test_parse_multi_bar():
    text = "I got money on my mind\n\nI been running through the night"
    result = parse_lyrics(text)
    assert len(result["bars"]) == 2
    assert result["bars"][0]["lines"][0]["words"][0]["text"] == "I"
    assert result["bars"][1]["lines"][0]["words"][0]["text"] == "I"


def test_parse_multi_line_single_bar():
    text = "I got money\non my mind"
    result = parse_lyrics(text)
    assert len(result["bars"]) == 1
    assert len(result["bars"][0]["lines"]) == 2


def test_parse_word_normalization():
    result = parse_lyrics('"Money," she said. Don\'t stop!')
    words = result["bars"][0]["lines"][0]["words"]
    assert words[0]["normalized"] == "money"
    assert words[2]["normalized"] == "said"
    assert words[3]["normalized"] == "don't"
    assert words[4]["normalized"] == "stop"


def test_parse_empty_lyrics_fails():
    with pytest.raises(AssertionError):
        parse_lyrics("")


def test_parse_whitespace_only_fails():
    with pytest.raises(AssertionError):
        parse_lyrics("   \n\n   ")


def test_parse_preserves_original_text():
    result = parse_lyrics("MONEY!!!")
    assert result["bars"][0]["lines"][0]["words"][0]["text"] == "MONEY!!!"
    assert result["bars"][0]["lines"][0]["words"][0]["normalized"] == "money"


def test_parse_bar_indices():
    text = "bar one\n\nbar two\n\nbar three"
    result = parse_lyrics(text)
    for i, bar in enumerate(result["bars"]):
        assert bar["bar_index"] == i


def test_parse_punctuation_only_tokens_skipped():
    """F2 regression: standalone punctuation must not produce word entries."""
    result = parse_lyrics("Real -- talk")
    words = result["bars"][0]["lines"][0]["words"]
    normalized = [w["normalized"] for w in words]
    assert normalized == ["real", "talk"]


def test_parse_dashes_and_ellipses():
    result = parse_lyrics("I -- got ... money")
    words = result["bars"][0]["lines"][0]["words"]
    assert len(words) == 3
    assert [w["normalized"] for w in words] == ["i", "got", "money"]


def test_parse_leading_trailing_punctuation_tokens():
    result = parse_lyrics("- I got money -")
    words = result["bars"][0]["lines"][0]["words"]
    assert [w["normalized"] for w in words] == ["i", "got", "money"]


def test_parse_word_indices_after_skipped_tokens():
    """Word indices should be contiguous even when tokens are skipped."""
    result = parse_lyrics("Real -- talk")
    words = result["bars"][0]["lines"][0]["words"]
    indices = [w["word_index"] for w in words]
    assert indices == [0, 1]


def test_parse_all_punctuation_line_skipped():
    """A line with only punctuation tokens produces no words, so no line entry."""
    result = parse_lyrics("I got money\n***\nreal talk")
    lines = result["bars"][0]["lines"]
    line_texts = [ln["text"] for ln in lines]
    assert "***" not in line_texts
