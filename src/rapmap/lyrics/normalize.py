from __future__ import annotations

import re


def normalize_word(word: str) -> str:
    lowered = word.lower()
    return re.sub(r"^[^\w']+|[^\w']+$", "", lowered)
