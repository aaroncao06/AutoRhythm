from __future__ import annotations

from rapmap.align.base import AlignmentResult
from rapmap.config import AlignmentConfig


def validate_alignment(
    alignment: AlignmentResult,
    canonical_syllables: dict,
    config: AlignmentConfig,
) -> dict:
    checks: dict[str, bool] = {}
    errors: list[str] = []
    low_confidence: list[int] = []

    canonical_count = len(canonical_syllables["syllables"])
    actual_count = len(alignment.syllables)
    checks["syllable_count_match"] = actual_count == canonical_count
    if not checks["syllable_count_match"]:
        errors.append(
            f"Syllable count mismatch: alignment has {actual_count}, "
            f"canonical has {canonical_count}"
        )

    checks["non_negative_samples"] = True
    for s in alignment.syllables:
        if s.start_sample < 0 or s.end_sample <= s.start_sample:
            checks["non_negative_samples"] = False
            errors.append(
                f"Syllable {s.syllable_index}: invalid range "
                f"[{s.start_sample}, {s.end_sample}]"
            )
            break

    checks["anchor_within_bounds"] = True
    for s in alignment.syllables:
        if not (s.start_sample <= s.anchor_sample <= s.end_sample):
            checks["anchor_within_bounds"] = False
            errors.append(
                f"Syllable {s.syllable_index}: anchor {s.anchor_sample} "
                f"outside [{s.start_sample}, {s.end_sample}]"
            )
            break

    checks["monotonic_starts"] = True
    for i in range(1, len(alignment.syllables)):
        if alignment.syllables[i].start_sample < alignment.syllables[i - 1].start_sample:
            checks["monotonic_starts"] = False
            errors.append(
                f"Non-monotonic start at syllable {i}: "
                f"{alignment.syllables[i].start_sample} < "
                f"{alignment.syllables[i - 1].start_sample}"
            )
            break

    for s in alignment.syllables:
        if s.confidence < config.min_syllable_confidence:
            low_confidence.append(s.syllable_index)

    if actual_count > 0:
        lc_fraction = len(low_confidence) / actual_count
        checks["confidence_acceptable"] = (
            lc_fraction <= config.max_low_confidence_fraction
        )
        if not checks["confidence_acceptable"]:
            errors.append(
                f"Low-confidence syllables: {len(low_confidence)}/{actual_count} "
                f"({lc_fraction:.0%}) exceeds max allowed "
                f"{config.max_low_confidence_fraction:.0%}"
            )

    passed = all(checks.values())
    result = {
        "passed": passed,
        "checks": checks,
        "errors": errors,
        "low_confidence_syllables": low_confidence,
        "low_confidence_count": len(low_confidence),
    }

    if not checks.get("syllable_count_match") and config.fail_on_missing_syllables:
        raise ValueError(
            f"Alignment validation failed: {errors[0] if errors else 'syllable count mismatch'}"
        )
    if not passed and config.fail_on_alignment_error:
        raise ValueError(f"Alignment validation failed: {'; '.join(errors)}")

    return result
