from __future__ import annotations

from rapmap.config import SyllableDetectionConfig
from rapmap.lyrics.pronunciations import lookup_pronunciation


def is_vowel(phone: str) -> bool:
    return len(phone) > 0 and phone[-1] in ("0", "1", "2")


def syllabify_phones(phones: list[str]) -> list[list[str]]:
    if not phones:
        return []

    syllables: list[list[str]] = []
    current: list[str] = []

    for i, phone in enumerate(phones):
        if is_vowel(phone):
            if current and any(is_vowel(p) for p in current):
                syllables.append(current)
                current = [phone]
            else:
                current.append(phone)
        else:
            if current and any(is_vowel(p) for p in current):
                remaining = phones[i:]
                if any(is_vowel(p) for p in remaining):
                    syllables.append(current)
                    current = [phone]
                else:
                    current.append(phone)
            else:
                current.append(phone)
    if current:
        syllables.append(current)

    expected = sum(1 for p in phones if is_vowel(p))
    assert len(syllables) == expected, (
        f"Syllable count {len(syllables)} != vowel count {expected} for phones {phones}"
    )
    return syllables


def _derive_syllable_texts(word_text: str, syllable_count: int) -> list[str]:
    if syllable_count <= 1:
        return [word_text]
    if len(word_text) < syllable_count:
        return [word_text] + [word_text] * (syllable_count - 1)
    chunk = len(word_text) // syllable_count
    parts = []
    for i in range(syllable_count):
        start = i * chunk
        end = (i + 1) * chunk if i < syllable_count - 1 else len(word_text)
        parts.append(word_text[start:end])
    return parts


def build_canonical_syllables(
    lyrics_normalized: dict,
    overrides: dict | None,
    config: SyllableDetectionConfig,
) -> dict:
    syllables = []
    global_idx = 0
    sources: dict[str, int] = {"cmudict": 0, "g2p": 0, "override": 0}

    for bar in lyrics_normalized["bars"]:
        bar_idx = bar["bar_index"]
        for line in bar["lines"]:
            line_idx = line["line_index"]
            words = line["words"]
            for word_pos, word_entry in enumerate(words):
                word_text = word_entry["text"]
                normalized = word_entry["normalized"]
                is_last_word_in_line = word_pos == len(words) - 1

                if overrides and normalized in overrides and "syllables" in overrides[normalized]:
                    override_entry = overrides[normalized]
                    syl_defs = override_entry["syllables"]
                    source = "override"
                    sources[source] += 1
                    for syl_pos, syl_def in enumerate(syl_defs):
                        syllables.append(
                            {
                                "syllable_index": global_idx,
                                "bar_index": bar_idx,
                                "line_index": line_idx,
                                "word_index": word_entry["word_index"],
                                "word_text": word_text,
                                "syllable_text": syl_def["text"],
                                "phones": syl_def["phones"],
                                "source": source,
                                "is_word_initial": syl_pos == 0,
                                "is_word_final": syl_pos == len(syl_defs) - 1,
                                "is_line_final": is_last_word_in_line
                                and syl_pos == len(syl_defs) - 1,
                            }
                        )
                        global_idx += 1
                else:
                    phones, source = lookup_pronunciation(
                        normalized,
                        overrides,
                        g2p_fallback=config.g2p_fallback,
                    )
                    sources[source] += 1
                    phone_syllables = syllabify_phones(phones)
                    syl_texts = _derive_syllable_texts(word_text, len(phone_syllables))

                    for syl_pos, syl_phones in enumerate(phone_syllables):
                        syllables.append(
                            {
                                "syllable_index": global_idx,
                                "bar_index": bar_idx,
                                "line_index": line_idx,
                                "word_index": word_entry["word_index"],
                                "word_text": word_text,
                                "syllable_text": syl_texts[syl_pos],
                                "phones": syl_phones,
                                "source": source,
                                "is_word_initial": syl_pos == 0,
                                "is_word_final": syl_pos == len(phone_syllables) - 1,
                                "is_line_final": is_last_word_in_line
                                and syl_pos == len(phone_syllables) - 1,
                            }
                        )
                        global_idx += 1

    word_count = sum(
        len(line["words"]) for bar in lyrics_normalized["bars"] for line in bar["lines"]
    )
    assert len(syllables) > 0, f"No syllables detected from lyrics with {word_count} words"
    for syl in syllables:
        assert any(is_vowel(p) for p in syl["phones"]), (
            f"Syllable {syl['syllable_index']} ('{syl['syllable_text']}') "
            f"has no vowel phone: {syl['phones']}"
        )

    return {"syllables": syllables, "sources": sources}
