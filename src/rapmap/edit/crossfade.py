from __future__ import annotations

import numpy as np


def compute_crossfade(
    left: np.ndarray,
    right: np.ndarray,
    crossfade_samples: int,
) -> np.ndarray:
    if crossfade_samples <= 0 or len(left) == 0 or len(right) == 0:
        return np.concatenate([left, right])
    xf = min(crossfade_samples, len(left), len(right))
    fade_out = np.sqrt(np.linspace(1.0, 0.0, xf)).astype(np.float32)
    fade_in = np.sqrt(np.linspace(0.0, 1.0, xf)).astype(np.float32)
    return np.concatenate([
        left[:-xf],
        left[-xf:] * fade_out + right[:xf] * fade_in,
        right[xf:],
    ])
