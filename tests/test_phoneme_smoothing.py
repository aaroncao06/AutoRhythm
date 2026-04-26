from __future__ import annotations

from rapmap.align.base import PhoneTimestamp
from rapmap.align.derive_syllables import _smooth_phones


def _phone(label: str, start: int, end: int) -> PhoneTimestamp:
    return PhoneTimestamp(phone=label, start_sample=start, end_sample=end)


def test_smooth_merges_short_phone():
    phones = [
        _phone("K", 0, 100),
        _phone("AH", 100, 110),
        _phone("T", 110, 300),
    ]
    result = _smooth_phones(phones, min_duration_samples=50)
    assert len(result) == 2
    assert result[0].start_sample == 0
    assert result[-1].end_sample == 300


def test_smooth_preserves_long_phones():
    phones = [
        _phone("K", 0, 200),
        _phone("AE1", 200, 500),
        _phone("T", 500, 700),
    ]
    result = _smooth_phones(phones, min_duration_samples=50)
    assert len(result) == 3
    for orig, smoothed in zip(phones, result):
        assert orig.start_sample == smoothed.start_sample
        assert orig.end_sample == smoothed.end_sample


def test_smooth_merges_into_longer_neighbor():
    phones = [
        _phone("S", 0, 100),
        _phone("T", 100, 105),
        _phone("AE1", 105, 400),
    ]
    result = _smooth_phones(phones, min_duration_samples=50)
    assert len(result) == 2
    assert result[1].phone == "AE1"
    assert result[1].start_sample == 100
    assert result[1].end_sample == 400


def test_smooth_first_phone_merges_into_next():
    phones = [
        _phone("HH", 0, 5),
        _phone("AE1", 5, 300),
        _phone("T", 300, 500),
    ]
    result = _smooth_phones(phones, min_duration_samples=50)
    assert len(result) == 2
    assert result[0].phone == "AE1"
    assert result[0].start_sample == 0
    assert result[0].end_sample == 300


def test_smooth_last_phone_merges_into_previous():
    phones = [
        _phone("K", 0, 200),
        _phone("AE1", 200, 500),
        _phone("T", 500, 505),
    ]
    result = _smooth_phones(phones, min_duration_samples=50)
    assert len(result) == 2
    assert result[-1].phone == "AE1"
    assert result[-1].start_sample == 200
    assert result[-1].end_sample == 505


def test_smooth_single_phone_unchanged():
    phones = [_phone("AH", 0, 10)]
    result = _smooth_phones(phones, min_duration_samples=50)
    assert len(result) == 1
    assert result[0].start_sample == 0
    assert result[0].end_sample == 10


def test_smooth_empty_list():
    result = _smooth_phones([], min_duration_samples=50)
    assert result == []


def test_smooth_contiguity_preserved():
    phones = [
        _phone("K", 0, 100),
        _phone("R", 100, 108),
        _phone("AE1", 108, 400),
        _phone("SH", 400, 405),
        _phone("T", 405, 600),
    ]
    result = _smooth_phones(phones, min_duration_samples=50)
    for i in range(1, len(result)):
        assert result[i].start_sample == result[i - 1].end_sample, (
            f"Gap at index {i}: prev_end={result[i-1].end_sample}, "
            f"this_start={result[i].start_sample}"
        )
