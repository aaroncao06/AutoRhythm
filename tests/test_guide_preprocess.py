from rapmap.guide.preprocess import (
    _levenshtein_ratio,
    match_words,
)


class TestLevenshteinRatio:
    def test_identical(self):
        assert _levenshtein_ratio("hello", "hello") == 1.0

    def test_empty(self):
        assert _levenshtein_ratio("", "hello") == 0.0
        assert _levenshtein_ratio("hello", "") == 0.0

    def test_similar(self):
        ratio = _levenshtein_ratio("sittin", "sitting")
        assert ratio > 0.75

    def test_different(self):
        ratio = _levenshtein_ratio("yo", "yeah")
        assert ratio < 0.75


class TestMatchWords:
    def test_exact_match_no_extras(self):
        stt = ["yeah", "load", "up"]
        canonical = ["yeah", "load", "up"]
        result = match_words(stt, canonical)
        assert result.all_matched
        assert len(result.extra_indices) == 0
        assert len(result.matches) == 3

    def test_extras_at_start(self):
        stt = ["yo", "what", "up", "yeah", "load"]
        canonical = ["yeah", "load"]
        result = match_words(stt, canonical)
        assert result.all_matched
        assert result.extra_indices == [0, 1, 2]
        assert len(result.matches) == 2
        assert result.matches[0].stt_index == 3
        assert result.matches[1].stt_index == 4

    def test_extras_at_end(self):
        stt = ["yeah", "load", "peace", "out"]
        canonical = ["yeah", "load"]
        result = match_words(stt, canonical)
        assert result.all_matched
        assert result.extra_indices == [2, 3]

    def test_extras_in_middle(self):
        stt = ["yeah", "uh", "huh", "load"]
        canonical = ["yeah", "load"]
        result = match_words(stt, canonical)
        assert result.all_matched
        assert result.extra_indices == [1, 2]

    def test_extras_everywhere(self):
        stt = ["yo", "yeah", "uh", "load", "peace"]
        canonical = ["yeah", "load"]
        result = match_words(stt, canonical)
        assert result.all_matched
        assert result.extra_indices == [0, 2, 4]

    def test_fuzzy_match(self):
        stt = ["sittin", "on"]
        canonical = ["sitting", "on"]
        result = match_words(stt, canonical, threshold=0.75)
        assert result.all_matched

    def test_canonical_not_found(self):
        stt = ["yo", "what", "up"]
        canonical = ["yeah", "load"]
        result = match_words(stt, canonical)
        assert not result.all_matched

    def test_repeated_word_correct_matching(self):
        stt = ["up", "yeah", "load", "up"]
        canonical = ["yeah", "load", "up"]
        result = match_words(stt, canonical)
        assert result.all_matched
        assert result.extra_indices == [0]
        assert result.matches[0].stt_index == 1
        assert result.matches[2].stt_index == 3

    def test_canonical_word_to_stt_mapping(self):
        stt = ["intro", "yeah", "load"]
        canonical = ["yeah", "load"]
        result = match_words(stt, canonical)
        assert result.canonical_word_to_stt == {0: 1, 1: 2}
        assert result.stt_to_canonical_word == {1: 0, 2: 1}

    def test_empty_canonical(self):
        stt = ["yo", "what"]
        canonical: list[str] = []
        result = match_words(stt, canonical)
        assert result.all_matched
        assert result.extra_indices == [0, 1]

    def test_empty_stt(self):
        stt: list[str] = []
        canonical = ["yeah"]
        result = match_words(stt, canonical)
        assert not result.all_matched

    def test_punctuation_handling(self):
        stt = ["yeah,", "load!"]
        canonical = ["yeah", "load"]
        result = match_words(stt, canonical)
        assert result.all_matched
