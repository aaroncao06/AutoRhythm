from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PhoneTimestamp:
    phone: str
    start_sample: int
    end_sample: int


@dataclass
class WordTimestamp:
    word_index: int
    text: str
    start_sample: int
    end_sample: int
    phones: list[PhoneTimestamp] = field(default_factory=list)


@dataclass
class SyllableTimestamp:
    syllable_index: int
    word_index: int
    word_text: str
    start_sample: int
    end_sample: int
    anchor_sample: int
    phones: list[PhoneTimestamp] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class AlignmentResult:
    sample_rate: int
    role: str
    audio_path: str
    total_duration_samples: int
    words: list[WordTimestamp] = field(default_factory=list)
    syllables: list[SyllableTimestamp] = field(default_factory=list)


def alignment_to_dict(result: AlignmentResult) -> dict:
    return {
        "sample_rate": result.sample_rate,
        "role": result.role,
        "audio_path": result.audio_path,
        "total_duration_samples": result.total_duration_samples,
        "words": [
            {
                "word_index": w.word_index,
                "text": w.text,
                "start_sample": w.start_sample,
                "end_sample": w.end_sample,
                "phones": [
                    {
                        "phone": p.phone,
                        "start_sample": p.start_sample,
                        "end_sample": p.end_sample,
                    }
                    for p in w.phones
                ],
            }
            for w in result.words
        ],
        "syllables": [
            {
                "syllable_index": s.syllable_index,
                "word_index": s.word_index,
                "word_text": s.word_text,
                "start_sample": s.start_sample,
                "end_sample": s.end_sample,
                "anchor_sample": s.anchor_sample,
                "phones": [
                    {
                        "phone": p.phone,
                        "start_sample": p.start_sample,
                        "end_sample": p.end_sample,
                    }
                    for p in s.phones
                ],
                "confidence": s.confidence,
            }
            for s in result.syllables
        ],
    }


def alignment_from_dict(data: dict) -> AlignmentResult:
    words = []
    for wd in data.get("words", []):
        phones = [
            PhoneTimestamp(
                phone=p["phone"],
                start_sample=p["start_sample"],
                end_sample=p["end_sample"],
            )
            for p in wd.get("phones", [])
        ]
        words.append(
            WordTimestamp(
                word_index=wd["word_index"],
                text=wd["text"],
                start_sample=wd["start_sample"],
                end_sample=wd["end_sample"],
                phones=phones,
            )
        )
    syllables = []
    for sd in data.get("syllables", []):
        phones = [
            PhoneTimestamp(
                phone=p["phone"],
                start_sample=p["start_sample"],
                end_sample=p["end_sample"],
            )
            for p in sd.get("phones", [])
        ]
        syllables.append(
            SyllableTimestamp(
                syllable_index=sd["syllable_index"],
                word_index=sd["word_index"],
                word_text=sd["word_text"],
                start_sample=sd["start_sample"],
                end_sample=sd["end_sample"],
                anchor_sample=sd["anchor_sample"],
                phones=phones,
                confidence=sd.get("confidence", 1.0),
            )
        )
    return AlignmentResult(
        sample_rate=data["sample_rate"],
        role=data["role"],
        audio_path=data["audio_path"],
        total_duration_samples=data["total_duration_samples"],
        words=words,
        syllables=syllables,
    )
