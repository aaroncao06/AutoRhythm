from pathlib import Path

from rapmap.align.textgrid import parse_textgrid

FIXTURE = """\
File type = "ooTextFile"
Object class = "TextGrid"

xmin = 0.0
xmax = 1.52
tiers? <exists>
size = 2
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
        xmin = 0.0
        xmax = 1.52
        intervals: size = 4
            intervals [1]:
                xmin = 0.0
                xmax = 0.28
                text = ""
            intervals [2]:
                xmin = 0.28
                xmax = 0.72
                text = "i"
            intervals [3]:
                xmin = 0.72
                xmax = 1.20
                text = "got"
            intervals [4]:
                xmin = 1.20
                xmax = 1.52
                text = ""
    item [2]:
        class = "IntervalTier"
        name = "phones"
        xmin = 0.0
        xmax = 1.52
        intervals: size = 5
            intervals [1]:
                xmin = 0.0
                xmax = 0.28
                text = ""
            intervals [2]:
                xmin = 0.28
                xmax = 0.72
                text = "AY1"
            intervals [3]:
                xmin = 0.72
                xmax = 0.85
                text = "G"
            intervals [4]:
                xmin = 0.85
                xmax = 1.05
                text = "AA1"
            intervals [5]:
                xmin = 1.05
                xmax = 1.20
                text = "T"
"""


def _write_fixture(tmp_path: Path) -> Path:
    p = tmp_path / "test.TextGrid"
    p.write_text(FIXTURE)
    return p


def test_parse_two_tiers(tmp_path):
    tiers = parse_textgrid(_write_fixture(tmp_path))
    assert "words" in tiers
    assert "phones" in tiers


def test_parse_word_intervals(tmp_path):
    tiers = parse_textgrid(_write_fixture(tmp_path))
    words = [iv for iv in tiers["words"].intervals if iv.text]
    assert len(words) == 2
    assert words[0].text == "i"
    assert words[1].text == "got"


def test_parse_phone_intervals(tmp_path):
    tiers = parse_textgrid(_write_fixture(tmp_path))
    phones = [iv for iv in tiers["phones"].intervals if iv.text]
    assert len(phones) == 4
    assert phones[0].text == "AY1"
    assert phones[3].text == "T"


def test_parse_includes_silence(tmp_path):
    tiers = parse_textgrid(_write_fixture(tmp_path))
    all_words = tiers["words"].intervals
    silence = [iv for iv in all_words if iv.text == ""]
    assert len(silence) == 2


def test_parse_timestamps(tmp_path):
    tiers = parse_textgrid(_write_fixture(tmp_path))
    phones = tiers["phones"].intervals
    ay = [iv for iv in phones if iv.text == "AY1"][0]
    assert abs(ay.xmin - 0.28) < 1e-6
    assert abs(ay.xmax - 0.72) < 1e-6
