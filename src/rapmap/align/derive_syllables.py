from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

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


def _smooth_phones(phones: list[PhoneTimestamp], min_duration_samples: int) -> list[PhoneTimestamp]:
    if len(phones) <= 1:
        return phones
    result = list(phones)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(result):
            dur = result[i].end_sample - result[i].start_sample
            if dur < min_duration_samples and len(result) > 1:
                if i == 0:
                    result[1] = PhoneTimestamp(
                        phone=result[1].phone,
                        start_sample=result[0].start_sample,
                        end_sample=result[1].end_sample,
                    )
                    result.pop(0)
                elif i == len(result) - 1:
                    result[-2] = PhoneTimestamp(
                        phone=result[-2].phone,
                        start_sample=result[-2].start_sample,
                        end_sample=result[-1].end_sample,
                    )
                    result.pop(-1)
                else:
                    prev_dur = result[i - 1].end_sample - result[i - 1].start_sample
                    next_dur = result[i + 1].end_sample - result[i + 1].start_sample
                    if prev_dur >= next_dur:
                        result[i - 1] = PhoneTimestamp(
                            phone=result[i - 1].phone,
                            start_sample=result[i - 1].start_sample,
                            end_sample=result[i].end_sample,
                        )
                    else:
                        result[i + 1] = PhoneTimestamp(
                            phone=result[i + 1].phone,
                            start_sample=result[i].start_sample,
                            end_sample=result[i + 1].end_sample,
                        )
                    result.pop(i)
                changed = True
                continue
            i += 1
    return result


def _energy_split(
    audio_segment: np.ndarray,
    num_syllables: int,
    sample_rate: int,
    word_start_sample: int,
) -> list[tuple[int, int]]:
    if len(audio_segment) < num_syllables * 2:
        return []

    win_samples = max(1, int(0.010 * sample_rate))
    hop = max(1, win_samples // 2)
    n_frames = (len(audio_segment) - win_samples) // hop + 1
    if n_frames < num_syllables:
        return []

    rms = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        start = i * hop
        frame = audio_segment[start : start + win_samples]
        rms[i] = np.sqrt(np.mean(frame**2))

    from scipy.signal import find_peaks

    min_distance = max(1, n_frames // (num_syllables * 2))
    peaks, _ = find_peaks(rms, distance=min_distance, prominence=np.max(rms) * 0.05)

    if len(peaks) != num_syllables:
        return []

    boundaries_frames = [0]
    for i in range(len(peaks) - 1):
        valley_region = rms[peaks[i] : peaks[i + 1]]
        valley_offset = np.argmin(valley_region)
        boundaries_frames.append(peaks[i] + valley_offset)
    boundaries_frames.append(n_frames)

    result = []
    for i in range(num_syllables):
        s_start = int(word_start_sample + boundaries_frames[i] * hop)
        s_end = int(word_start_sample + boundaries_frames[i + 1] * hop)
        if i == num_syllables - 1:
            s_end = int(word_start_sample + len(audio_segment))
        result.append((s_start, s_end))

    return result


def derive_syllable_timestamps(
    textgrid_path: Path,
    canonical_syllables: dict,
    sample_rate: int,
    role: str,
    audio_path: str,
    anchor_strategy: str = "onset",
    smoothing_min_ms: float = 0.0,
    audio_data: np.ndarray | None = None,
    canonical_word_indices: list[int] | None = None,
) -> AlignmentResult:
    tiers = parse_textgrid(textgrid_path)
    assert "words" in tiers, f"TextGrid missing 'words' tier, found: {list(tiers.keys())}"
    assert "phones" in tiers, f"TextGrid missing 'phones' tier, found: {list(tiers.keys())}"

    word_tier = tiers["words"]
    phone_tier = tiers["phones"]

    tg_words = [iv for iv in word_tier.intervals if iv.text]
    tg_phones = [iv for iv in phone_tier.intervals if iv.text]

    if canonical_word_indices is not None:
        assert all(0 <= i < len(tg_words) for i in canonical_word_indices), (
            f"canonical_word_indices out of range: max="
            f"{max(canonical_word_indices) if canonical_word_indices else 'n/a'}, "
            f"tg_words count={len(tg_words)}"
        )
        tg_words = [tg_words[i] for i in canonical_word_indices]

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

        if smoothing_min_ms > 0:
            min_dur = int(smoothing_min_ms * sample_rate / 1000)
            word_phones = _smooth_phones(word_phones, min_dur)

        word_phone_labels = [p.phone for p in word_phones]
        canonical_syl_count = sum(1 for s in canonical_syls if s["word_index"] == cw["word_index"])
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
                "syllable boundaries (confidence=0.1-0.5)",
                cw["text"],
                canonical_syl_count,
            )
            energy_boundaries: list[tuple[int, int]] = []
            if audio_data is not None:
                word_audio = audio_data[w_start:w_end]
                energy_boundaries = _energy_split(
                    word_audio,
                    canonical_syl_count,
                    sample_rate,
                    w_start,
                )

            if energy_boundaries:
                for si, (s_start, s_end) in enumerate(energy_boundaries):
                    all_syllables.append(
                        SyllableTimestamp(
                            syllable_index=global_syl_idx,
                            word_index=cw["word_index"],
                            word_text=cw["text"],
                            start_sample=s_start,
                            end_sample=s_end,
                            anchor_sample=s_start,
                            phones=word_phones if si == 0 else [],
                            confidence=0.5,
                        )
                    )
                    global_syl_idx += 1
            else:
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
                "syllables, fabricating boundaries (confidence=0.3-0.5)",
                cw["text"],
                vowel_count,
                canonical_syl_count,
            )
            energy_boundaries_2: list[tuple[int, int]] = []
            if audio_data is not None:
                word_audio_2 = audio_data[w_start:w_end]
                energy_boundaries_2 = _energy_split(
                    word_audio_2,
                    canonical_syl_count,
                    sample_rate,
                    w_start,
                )

            if energy_boundaries_2:
                for si, (s_start, s_end) in enumerate(energy_boundaries_2):
                    all_syllables.append(
                        SyllableTimestamp(
                            syllable_index=global_syl_idx,
                            word_index=cw["word_index"],
                            word_text=cw["text"],
                            start_sample=s_start,
                            end_sample=s_end,
                            anchor_sample=s_start,
                            phones=word_phones if si == 0 else [],
                            confidence=0.5,
                        )
                    )
                    global_syl_idx += 1
            else:
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
        f"Derived syllable count {len(all_syllables)} != canonical count {len(canonical_syls)}"
    )

    total_dur = 0
    if tg_words:
        total_dur = _seconds_to_samples(max(iv.xmax for iv in word_tier.intervals), sample_rate)

    return AlignmentResult(
        sample_rate=sample_rate,
        role=role,
        audio_path=audio_path,
        total_duration_samples=total_dur,
        words=all_words,
        syllables=all_syllables,
    )
