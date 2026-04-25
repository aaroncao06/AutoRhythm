from rapmap.align.base import AlignmentResult, PhoneTimestamp, SyllableTimestamp
from rapmap.audacity.labels import generate_all_labels, generate_label_track


def _make_alignment(syllable_data, role="guide"):
    syllables = []
    for i, (start, end, word) in enumerate(syllable_data):
        syllables.append(
            SyllableTimestamp(
                syllable_index=i,
                word_index=i,
                word_text=word,
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
        sample_rate=48000,
        role=role,
        audio_path="test.wav",
        total_duration_samples=syllable_data[-1][1] if syllable_data else 0,
        syllables=syllables,
    )


class TestLabelTrackFormat:
    def test_tsv_format(self):
        entries = [
            {"start_sample": 0, "end_sample": 48000, "text": "hello"},
            {"start_sample": 48000, "end_sample": 96000, "text": "world"},
        ]
        result = generate_label_track(entries, 48000)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        parts = lines[0].split("\t")
        assert len(parts) == 3
        assert parts[2] == "hello"

    def test_sample_to_seconds_conversion(self):
        entries = [{"start_sample": 24000, "end_sample": 72000, "text": "test"}]
        result = generate_label_track(entries, 48000)
        line = result.strip()
        parts = line.split("\t")
        assert abs(float(parts[0]) - 0.5) < 1e-5
        assert abs(float(parts[1]) - 1.5) < 1e-5

    def test_trailing_newline(self):
        entries = [{"start_sample": 0, "end_sample": 1000, "text": "x"}]
        result = generate_label_track(entries, 48000)
        assert result.endswith("\n")

    def test_empty_entries(self):
        result = generate_label_track([], 48000)
        assert result == "\n"


class TestGenerateAllLabels:
    def _canonical(self):
        return {
            "syllables": [
                {
                    "syllable_index": 0,
                    "syllable_text": "I",
                    "word_index": 0,
                    "word_text": "I",
                },
                {
                    "syllable_index": 1,
                    "syllable_text": "got",
                    "word_index": 1,
                    "word_text": "got",
                },
            ]
        }

    def test_canonical_only(self, tmp_path):
        written = generate_all_labels(
            self._canonical(), None, None, None, None, 48000, tmp_path
        )
        assert len(written) == 1
        assert written[0].name == "labels_canonical.txt"
        assert written[0].exists()

    def test_all_label_types(self, tmp_path):
        guide = _make_alignment([(1000, 2000, "I"), (3000, 4000, "got")], role="guide")
        human = _make_alignment(
            [(1500, 2500, "I"), (3500, 4500, "got")], role="human"
        )
        anchor_map = {
            "anchors": [
                {
                    "syllable_index": 0,
                    "guide_anchor_sample": 1000,
                    "delta_samples": 500,
                },
                {
                    "syllable_index": 1,
                    "guide_anchor_sample": 3000,
                    "delta_samples": 500,
                },
            ]
        }
        clip_groups = {
            "clips": [
                {
                    "clip_id": "clip_0000_i",
                    "target_start_sample": 1000,
                    "target_end_sample": 2000,
                },
                {
                    "clip_id": "clip_0001_got",
                    "target_start_sample": 3000,
                    "target_end_sample": 4000,
                },
            ]
        }
        written = generate_all_labels(
            self._canonical(),
            guide,
            human,
            anchor_map,
            clip_groups,
            48000,
            tmp_path,
        )
        assert len(written) == 5
        names = {p.name for p in written}
        assert "labels_canonical.txt" in names
        assert "labels_guide.txt" in names
        assert "labels_human.txt" in names
        assert "labels_anchors.txt" in names
        assert "labels_clips.txt" in names

    def test_labels_dir_created(self, tmp_path):
        generate_all_labels(
            self._canonical(), None, None, None, None, 48000, tmp_path
        )
        assert (tmp_path / "labels").is_dir()

    def test_guide_label_content(self, tmp_path):
        guide = _make_alignment([(4800, 9600, "hello")], role="guide")
        written = generate_all_labels(
            {
                "syllables": [
                    {
                        "syllable_index": 0,
                        "syllable_text": "hel",
                        "word_index": 0,
                        "word_text": "hello",
                    }
                ]
            },
            guide,
            None,
            None,
            None,
            48000,
            tmp_path,
        )
        guide_file = [p for p in written if p.name == "labels_guide.txt"][0]
        content = guide_file.read_text().strip()
        parts = content.split("\t")
        assert abs(float(parts[0]) - 0.1) < 1e-5
        assert abs(float(parts[1]) - 0.2) < 1e-5
        assert "hello" in parts[2]
