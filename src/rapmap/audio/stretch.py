from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf


def time_stretch(
    data: np.ndarray,
    sample_rate: int,
    ratio: float,
    preserve_pitch: bool = True,
) -> np.ndarray:
    if abs(ratio - 1.0) < 1e-6:
        return data.copy()
    assert ratio > 0, f"Stretch ratio must be positive, got {ratio}"
    assert len(data) > 0, "Cannot stretch empty audio"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        in_path = tmp / "input.wav"
        out_path = tmp / "output.wav"
        sf.write(str(in_path), data, sample_rate, subtype="FLOAT")

        cmd = ["rubberband", "-t", str(ratio), "--no-threads"]
        if not preserve_pitch:
            cmd.extend(["-p", "0"])
        cmd.extend([str(in_path), str(out_path)])

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except FileNotFoundError:
            raise RuntimeError(
                "rubberband CLI not found. Install: "
                "brew install rubberband (macOS) or apt install rubberband-cli (Linux)"
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"rubberband failed (exit {e.returncode}): {e.stderr}")

        stretched, _ = sf.read(str(out_path), dtype="float32")

    return stretched
