from __future__ import annotations

import re

from rapmap.lyrics.normalize import normalize_word


def parse_lyrics(lyrics_text: str) -> dict:
    raw_bars = re.split(r"\n\s*\n", lyrics_text.strip())
    bars = []
    for bar_idx, raw_bar in enumerate(raw_bars):
        lines = []
        for line_idx, raw_line in enumerate(
            line for line in raw_bar.split("\n") if line.strip()
        ):
            words = []
            for token in raw_line.split():
                if not token.strip():
                    continue
                normalized = normalize_word(token)
                if not normalized:
                    continue
                words.append(
                    {
                        "word_index": len(words),
                        "text": token,
                        "normalized": normalized,
                    }
                )
            if words:
                lines.append({"line_index": line_idx, "text": raw_line.strip(), "words": words})
        if lines:
            bars.append({"bar_index": bar_idx, "lines": lines})

    assert len(bars) > 0, "Lyrics contain no bars"
    assert any(line["words"] for bar in bars for line in bar["lines"]), "Lyrics contain no words"
    return {"bars": bars}
