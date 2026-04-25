from __future__ import annotations

from pathlib import Path

import yaml


def load_overrides(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    with open(path) as f:
        raw = yaml.safe_load(f)
    if not raw:
        return None
    overrides = {}
    for word, entry in raw.items():
        key = word.lower()
        if not isinstance(entry, dict) or "phones" not in entry:
            raise ValueError(
                f"Override '{word}': must be a dict with a 'phones' key, got {type(entry).__name__}"
            )
        phones = entry["phones"]
        if not isinstance(phones, list) or not phones:
            raise ValueError(f"Override '{word}': 'phones' must be a non-empty list")
        if "syllables" in entry:
            syls = entry["syllables"]
            if not isinstance(syls, list) or not syls:
                raise ValueError(
                    f"Override '{word}': 'syllables' must be a non-empty list if present"
                )
            for i, syl in enumerate(syls):
                if not isinstance(syl, dict) or "text" not in syl or "phones" not in syl:
                    raise ValueError(
                        f"Override '{word}', syllable {i}: must have 'text' and 'phones' keys"
                    )
        overrides[key] = entry
    return overrides
