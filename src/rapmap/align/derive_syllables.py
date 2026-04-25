from __future__ import annotations

import logging
from pathlib import Path

from rapmap.align.base import (
    AlignmentResult,
    PhoneTimestamp,
    SyllableTimestamp,
    WordTimestamp,
)
from rapmap.align.textgrid import parse_textgrid
from rapmap.lyrics.syllabify import is_vowel, syllabify_phones

logger = logging.getLogger(__name__)


def _seconds_to_samples(seconds: float, sample_rate: int) -> int:
    return int(round(seconds * sample_rate))


def _compute_anchor(phones: list[PhoneTimestamp], strategy: str) -> int:
    if strategy == "onset":
        return phones[0].start_sample
    if strategy == "end":
        return phones[-1].end_sample
    if strategy == "vowel_nucleus":
        for p in phones:
            if is_vowel(p.phone):
                return (p.start_sample + p.end_sample) // 2
        return phones[0].start_sample
    return phones[0].start_sample


def _phone_confidence(phones: list[PhoneTimestamp], sample_rate: int) -> float:
    if not phones:
        return 0.0
    min_duration = min(p.end_sample - p.start_sample for p in phones)
    min_duration_ms = min_duration * 1000 / sample_rate
    return min(1.0, max(0.0, min_duration_ms / 30.0))


def derive_syllable_timestamps(
    textgrid_path: Path,
    canonical_syllables: dict,
    sample_rate: int,
    role: str,
    audio_path: str,
    anchor_strategy: str = "onset",
) -> AlignmentResult:
    tiers = parse_textgrid(textgrid_path)
    assert "words" in tiers, f"TextGrid missing 'words' tier, found: {list(tiers.keys())}"
    assert "phones" in tiers, f"TextGrid missing 'phones' tier, found: {list(tiers.keys())}"

    word_tier = tiers["words"]
    phone_tier = tiers["phones"]

    tg_words = [iv for iv in word_tier.intervals if iv.text]
    tg_phones = [iv for iv in phone_tier.intervals if iv.text]

    canonical_syls = canonical_syllables["syllables"]
    canonical_words: list[dict] = []
    seen_word_indices: set[int] = set()
    for syl in canonical_syls:
        wi = syl["word_index"]
        if wi not in seen_word_indices:
            seen_word_indices.add(wi)
            canonical_words.append({"word_index": wi, "text": syl["word_text"]})

    assert len(tg_words) == len(canonical_words), (
        f"Word count mismatch: TextGrid has {len(tg_words)} words, "
        f"canonical has {len(canonical_words)} words"
    )

    phone_start = [_seconds_to_samples(p.xmin, sample_rate) for p in tg_phones]
    phone_end = [_seconds_to_samples(p.xmax, sample_rate) for p in tg_phones]
    phone_labels = [p.text for p in tg_phones]

    word_starts = [_seconds_to_samples(w.xmin, sample_rate) for w in tg_words]
    word_ends = [_seconds_to_samples(w.xmax, sample_rate) for w in tg_words]

    all_words: list[WordTimestamp] = []
    all_syllables: list[SyllableTimestamp] = []
    global_syl_idx = 0

    for word_pos, cw in enumerate(canonical_words):
        w_start = word_starts[word_pos]
        w_end = word_ends[word_pos]

        word_phones: list[PhoneTimestamp] = []
        for pi in range(len(tg_phones)):
            if phone_start[pi] >= w_start and phone_end[pi] <= w_end:
                word_phones.append(
                    PhoneTimestamp(
                        phone=phone_labels[pi],
                        start_sample=phone_start[pi],
                        end_sample=phone_end[pi],
                    )
                )

        all_words.append(
            WordTimestamp(
                word_index=cw["word_index"],
                text=cw["text"],
                start_sample=w_start,
                end_sample=w_end,
                phones=word_phones,
            )
        )

        word_phone_labels = [p.phone for p in word_phones]
        canonical_syl_count = sum(
            1 for s in canonical_syls if s["word_index"] == cw["word_index"]
        )
        vowel_count = sum(1 for p in word_phone_labels if is_vowel(p))

        if vowel_count == canonical_syl_count and vowel_count > 0:
            syl_groups = syllabify_phones(word_phone_labels)
            phone_idx = 0
            for syl_phones_list in syl_groups:
                syl_phone_timestamps = word_phones[phone_idx : phone_idx + len(syl_phones_list)]
                phone_idx += len(syl_phones_list)
                anchor = _compute_anchor(syl_phone_timestamps, anchor_strategy)
                all_syllables.append(
                    SyllableTimestamp(
                        syllable_index=global_syl_idx,
                        word_index=cw["word_index"],
                        word_text=cw["text"],
                        start_sample=syl_phone_timestamps[0].start_sample,
                        end_sample=syl_phone_timestamps[-1].end_sample,
                        anchor_sample=anchor,
                        phones=syl_phone_timestamps,
                        confidence=_phone_confidence(syl_phone_timestamps, sample_rate),
                    )
                )
                global_syl_idx += 1
        elif vowel_count == 0 and canonical_syl_count > 0:
            logger.warning(
                "Word '%s': no vowels detected by MFA, fabricating %d "
                "syllable boundaries by equal division (confidence=0.1)",
                cw["text"],
                canonical_syl_count,
            )
            total_dur = w_end - w_start
            chunk = total_dur // canonical_syl_count if canonical_syl_count > 0 else total_dur
            for si in range(canonical_syl_count):
                s_start = w_start + si * chunk
                s_end = w_start + (si + 1) * chunk if si < canonical_syl_count - 1 else w_end
                all_syllables.append(
                    SyllableTimestamp(
                        syllable_index=global_syl_idx,
                        word_index=cw["word_index"],
                        word_text=cw["text"],
                        start_sample=s_start,
                        end_sample=s_end,
                        anchor_sample=s_start,
                        phones=word_phones if si == 0 else [],
                        confidence=0.1,
                    )
                )
                global_syl_idx += 1
        else:
            logger.warning(
                "Word '%s': MFA detected %d vowels but canonical has %d "
                "syllables, fabricating boundaries by equal division "
                "(confidence=0.3)",
                cw["text"],
                vowel_count,
                canonical_syl_count,
            )
            total_dur = w_end - w_start
            chunk = total_dur // canonical_syl_count if canonical_syl_count > 0 else total_dur
            for si in range(canonical_syl_count):
                s_start = w_start + si * chunk
                s_end = w_start + (si + 1) * chunk if si < canonical_syl_count - 1 else w_end
                all_syllables.append(
                    SyllableTimestamp(
                        syllable_index=global_syl_idx,
                        word_index=cw["word_index"],
                        word_text=cw["text"],
                        start_sample=s_start,
                        end_sample=s_end,
                        anchor_sample=s_start,
                        phones=[],
                        confidence=0.3,
                    )
                )
                global_syl_idx += 1

    assert len(all_syllables) == len(canonical_syls), (
        f"Derived syllable count {len(all_syllables)} != "
        f"canonical count {len(canonical_syls)}"
    )

    total_dur = 0
    if tg_words:
        total_dur = _seconds_to_samples(
            max(iv.xmax for iv in word_tier.intervals), sample_rate
        )

    return AlignmentResult(
        sample_rate=sample_rate,
        role=role,
        audio_path=audio_path,
        total_duration_samples=total_dur,
        words=all_words,
        syllables=all_syllables,
    )
