from __future__ import annotations

_cmudict: dict[str, list[list[str]]] | None = None
_g2p = None


def _require_nltk_resource(resource_path: str, install_hint: str) -> None:
    import nltk

    try:
        nltk.data.find(resource_path)
    except LookupError as exc:
        raise RuntimeError(
            f"Missing NLTK resource '{resource_path}'. Install it before running RapMap: "
            f"`python -m nltk.downloader {install_hint}`"
        ) from exc


def _ensure_cmudict() -> dict[str, list[list[str]]]:
    global _cmudict
    if _cmudict is None:
        _require_nltk_resource("corpora/cmudict", "cmudict")
        from nltk.corpus import cmudict

        _cmudict = cmudict.dict()
    return _cmudict


def _ensure_g2p():
    global _g2p
    if _g2p is None:
        _require_nltk_resource(
            "taggers/averaged_perceptron_tagger_eng", "averaged_perceptron_tagger_eng"
        )
        from g2p_en import G2p

        _g2p = G2p()
    return _g2p


def lookup_pronunciation(
    word: str, overrides: dict | None = None, g2p_fallback: bool = True
) -> tuple[list[str], str]:
    key = word.lower()

    if overrides and key in overrides:
        entry = overrides[key]
        phones = entry["phones"]
        assert len(phones) > 0, f"Override for '{word}' has empty phone list"
        return phones, "override"

    d = _ensure_cmudict()
    if key in d:
        phones = d[key][0]
        assert len(phones) > 0, f"CMUdict entry for '{word}' has empty phone list"
        return phones, "cmudict"

    if not g2p_fallback:
        raise ValueError(
            f"Word '{word}' not in CMUdict and g2p_fallback is disabled; add an override instead"
        )

    g2p = _ensure_g2p()
    phones_raw = g2p(key)
    phones = [p for p in phones_raw if p.strip() and p not in ".,!?;:"]
    if phones:
        return phones, "g2p"

    raise ValueError(f"Word '{word}' not in CMUdict and G2P produced no phones")


def lookup_all_words(
    words: list[str], overrides: dict | None = None, g2p_fallback: bool = True
) -> list[dict]:
    return [
        {"word": w, "phones": phones, "source": source}
        for w in words
        for phones, source in [lookup_pronunciation(w, overrides, g2p_fallback=g2p_fallback)]
    ]
