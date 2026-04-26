from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_cmudict():
    import rapmap.lyrics.pronunciations as mod

    mod._cmudict = None
    yield
    mod._cmudict = None


def test_lookup_all_returns_multiple_for_common_word():
    from rapmap.lyrics.pronunciations import lookup_all_pronunciations

    results = lookup_all_pronunciations("the")
    assert len(results) >= 2
    for phones, source in results:
        assert len(phones) > 0
        assert source == "cmudict"


def test_lookup_all_returns_single_for_override():
    from rapmap.lyrics.pronunciations import lookup_all_pronunciations

    overrides = {"yo": {"phones": ["Y", "OW1"]}}
    results = lookup_all_pronunciations("yo", overrides=overrides)
    assert len(results) == 1
    assert results[0] == (["Y", "OW1"], "override")


def test_lookup_all_g2p_fallback():
    from rapmap.lyrics.pronunciations import lookup_all_pronunciations

    results = lookup_all_pronunciations("xyzzyplugh")
    assert len(results) == 1
    phones, source = results[0]
    assert source == "g2p"
    assert len(phones) > 0


def test_lookup_all_raises_without_g2p_fallback():
    from rapmap.lyrics.pronunciations import lookup_all_pronunciations

    with pytest.raises(ValueError, match="not in CMUdict"):
        lookup_all_pronunciations("xyzzyplugh", g2p_fallback=False)


def test_dictionary_generation_multi():
    from rapmap.align.mfa import _generate_dictionary

    canonical = {
        "syllables": [
            {"word_text": "the", "word_index": 0},
            {"word_text": "cat", "word_index": 1},
        ]
    }
    result = _generate_dictionary(canonical, None, multi_pronunciation=True)
    lines = [line for line in result.strip().split("\n") if line]

    the_lines = [line for line in lines if line.startswith("the\t")]
    assert len(the_lines) >= 2, f"Expected >=2 pronunciations for 'the', got {the_lines}"


def test_dictionary_generation_single():
    from rapmap.align.mfa import _generate_dictionary

    canonical = {
        "syllables": [
            {"word_text": "the", "word_index": 0},
        ]
    }
    result = _generate_dictionary(canonical, None, multi_pronunciation=False)
    lines = [line for line in result.strip().split("\n") if line]

    the_lines = [line for line in lines if line.startswith("the\t")]
    assert len(the_lines) == 1
