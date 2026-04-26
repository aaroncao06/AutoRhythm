from __future__ import annotations

SUBDIVISION_UNITS = {
    "quarter": 1,
    "eighth": 2,
    "sixteenth": 4,
    "triplet": 3,
}


def build_beat_grid(
    beat_info: dict, subdivision: str, total_duration_samples: int
) -> dict:
    assert subdivision in SUBDIVISION_UNITS, f"Unknown subdivision: {subdivision}"
    units_per_beat = SUBDIVISION_UNITS[subdivision]
    beats = beat_info["beat_samples"]

    grid: list[int] = []
    for i in range(len(beats) - 1):
        span = beats[i + 1] - beats[i]
        for s in range(units_per_beat):
            pos = beats[i] + int(round(span * s / units_per_beat))
            grid.append(pos)
    if beats:
        grid.append(beats[-1])

    grid = sorted(set(grid))

    return {
        "bpm": beat_info["bpm"],
        "subdivision": subdivision,
        "units_per_beat": units_per_beat,
        "grid_samples": grid,
        "beat_samples": beat_info["beat_samples"],
        "sample_rate": beat_info["sample_rate"],
        "total_grid_points": len(grid),
    }
