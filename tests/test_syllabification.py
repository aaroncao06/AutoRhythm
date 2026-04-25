import importlib.resources
from pathlib import Path

import pytest

from rapmap.config import SyllableDetectionConfig
from rapmap.lyrics import pronunciations
from rapmap.lyrics.overrides import load_overrides
from rapmap.lyrics.parser import parse_lyrics
from rapmap.lyrics.pronunciations import lookup_pronunciation
from rapmap.lyrics.syllabify import (
    _derive_syllable_texts,
    build_canonical_syllables,
    is_vowel,
    syllabify_phones,
)


def test_is_vowel():
    assert is_vowel("AH1") is True
    assert is_vowel("IY0") is True
    assert is_vowel("AO2") is True
    assert is_vowel("M") is False
    assert is_vowel("T") is False
    assert is_vowel("") is False


def test_syllabify_monosyllable():
    phones, _ = lookup_pronunciation("got")
    result = syllabify_phones(phones)
    assert len(result) == 1


def test_syllabify_two_syllables():
    phones, _ = lookup_pronunciation("money")
    result = syllabify_phones(phones)
    assert len(result) == 2


def test_syllabify_three_syllables():
    phones, _ = lookup_pronunciation("beautiful")
    result = syllabify_phones(phones)
    assert len(result) == 3


def test_cmudict_lookup():
    phones, source = lookup_pronunciation("money")
    assert source == "cmudict"
    assert len(phones) > 0


def test_g2p_fallback():
    phones, source = lookup_pronunciation("xyzzyplugh")
    assert source == "g2p"
    assert len(phones) > 0


def test_lookup_pronunciation_respects_disabled_g2p():
    with pytest.raises(ValueError, match="g2p_fallback is disabled"):
        lookup_pronunciation("xyzzyplugh", g2p_fallback=False)


def test_override_applied():
    overrides = {
        "tryna": {
            "phones": ["T", "R", "AY1", "N", "AH0"],
            "syllables": [
                {"text": "try", "phones": ["T", "R", "AY1"]},
                {"text": "na", "phones": ["N", "AH0"]},
            ],
        }
    }
    phones, source = lookup_pronunciation("tryna", overrides)
    assert source == "override"
    assert phones == ["T", "R", "AY1", "N", "AH0"]


def test_build_canonical_syllables():
    lyrics = parse_lyrics("I got money on my mind")
    config = SyllableDetectionConfig()
    result = build_canonical_syllables(lyrics, None, config)
    assert len(result["syllables"]) > 0
    # "money" has 2 syllables, rest are monosyllabic → 7 total
    assert len(result["syllables"]) == 7


def test_canonical_syllable_indices_contiguous():
    lyrics = parse_lyrics("I got money on my mind")
    config = SyllableDetectionConfig()
    result = build_canonical_syllables(lyrics, None, config)
    indices = [s["syllable_index"] for s in result["syllables"]]
    assert indices == list(range(len(indices)))


def test_word_boundary_flags():
    lyrics = parse_lyrics("I got money")
    config = SyllableDetectionConfig()
    result = build_canonical_syllables(lyrics, None, config)
    syls = result["syllables"]

    # "I" → 1 syllable: word_initial=True, word_final=True
    assert syls[0]["is_word_initial"] is True
    assert syls[0]["is_word_final"] is True

    # "money" → 2 syllables: first is word_initial, second is word_final
    money_syls = [s for s in syls if s["word_text"] == "money"]
    assert len(money_syls) == 2
    assert money_syls[0]["is_word_initial"] is True
    assert money_syls[0]["is_word_final"] is False
    assert money_syls[1]["is_word_initial"] is False
    assert money_syls[1]["is_word_final"] is True


def test_line_final_flag():
    lyrics = parse_lyrics("I got money")
    config = SyllableDetectionConfig()
    result = build_canonical_syllables(lyrics, None, config)
    syls = result["syllables"]
    finals = [s for s in syls if s["is_line_final"]]
    assert len(finals) == 1
    assert finals[0]["word_text"] == "money"


def test_build_with_overrides():
    lyrics = parse_lyrics("I tryna get it")
    overrides = {
        "tryna": {
            "phones": ["T", "R", "AY1", "N", "AH0"],
            "syllables": [
                {"text": "try", "phones": ["T", "R", "AY1"]},
                {"text": "na", "phones": ["N", "AH0"]},
            ],
        }
    }
    config = SyllableDetectionConfig()
    result = build_canonical_syllables(lyrics, overrides, config)
    tryna_syls = [s for s in result["syllables"] if s["word_text"] == "tryna"]
    assert len(tryna_syls) == 2
    assert tryna_syls[0]["syllable_text"] == "try"
    assert tryna_syls[0]["source"] == "override"


def test_bundled_override_matches_apostrophized_input():
    bundled_ref = importlib.resources.files("rapmap.configs").joinpath(
        "pronunciation_overrides.yaml"
    )
    overrides = load_overrides(Path(str(bundled_ref)))
    lyrics = parse_lyrics("ain't")
    config = SyllableDetectionConfig()

    result = build_canonical_syllables(lyrics, overrides, config)

    assert len(result["syllables"]) == 1
    assert result["syllables"][0]["source"] == "override"
    assert result["syllables"][0]["syllable_text"] == "ain't"


def test_build_canonical_syllables_respects_disabled_g2p():
    lyrics = parse_lyrics("xyzzyplugh")
    config = SyllableDetectionConfig(g2p_fallback=False)

    with pytest.raises(ValueError, match="g2p_fallback is disabled"):
        build_canonical_syllables(lyrics, None, config)


def test_missing_nltk_resource_raises_setup_error(monkeypatch):
    pronunciations._cmudict = None
    pronunciations._g2p = None

    class FakeNltk:
        class data:
            @staticmethod
            def find(_path: str):
                raise LookupError("missing")

    monkeypatch.setitem(__import__("sys").modules, "nltk", FakeNltk)

    with pytest.raises(RuntimeError, match="python -m nltk.downloader cmudict"):
        pronunciations._ensure_cmudict()


def test_syllabify_consecutive_vowels():
    """F1 regression: adjacent vowel phones must produce separate syllables."""
    # going: G OW1 IH0 NG → 2 syllables
    phones, _ = lookup_pronunciation("going")
    result = syllabify_phones(phones)
    vowel_count = sum(1 for p in phones if is_vowel(p))
    assert len(result) == vowel_count == 2

    # fire: F AY1 ER0 → 2 syllables
    phones, _ = lookup_pronunciation("fire")
    result = syllabify_phones(phones)
    assert len(result) == 2

    # power: P AW1 ER0 → 2 syllables
    phones, _ = lookup_pronunciation("power")
    result = syllabify_phones(phones)
    assert len(result) == 2


def test_syllabify_hiatus_words():
    """F1 regression: words with vowel hiatus (idea, radio, area)."""
    for word, expected in [("idea", 3), ("radio", 3), ("area", 3), ("piano", 3)]:
        phones, _ = lookup_pronunciation(word)
        result = syllabify_phones(phones)
        assert len(result) == expected, f"{word}: expected {expected}, got {len(result)}"


def test_syllabify_empty_input():
    assert syllabify_phones([]) == []


def test_syllable_count_equals_vowel_count():
    """The invariant: syllable count must always equal vowel count in phones."""
    words = [
        "money",
        "beautiful",
        "going",
        "fire",
        "higher",
        "power",
        "literally",
        "idea",
        "creating",
        "radio",
        "I",
        "got",
        "the",
    ]
    for word in words:
        phones, _ = lookup_pronunciation(word)
        result = syllabify_phones(phones)
        vowel_count = sum(1 for p in phones if is_vowel(p))
        assert len(result) == vowel_count, (
            f"{word}: {len(result)} syllables != {vowel_count} vowels, phones={phones}"
        )


def test_derive_syllable_texts_short_word():
    """F5 regression: no empty strings when word is shorter than syllable count."""
    result = _derive_syllable_texts("I", 2)
    assert len(result) == 2
    assert all(len(t) > 0 for t in result)

    result = _derive_syllable_texts("go", 3)
    assert len(result) == 3
    assert all(len(t) > 0 for t in result)

    result = _derive_syllable_texts("", 1)
    assert result == [""]
