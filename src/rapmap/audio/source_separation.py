from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from rapmap.audio.io import read_audio, write_audio


def separate_vocals(
    audio_path: Path,
    output_path: Path,
    model_name: str = "htdemucs",
) -> Path:
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    model = get_model(model_name)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    data, sr = read_audio(audio_path, mono=False)
    if data.ndim == 1:
        data = np.stack([data, data], axis=-1)

    waveform = torch.from_numpy(data.T).unsqueeze(0).to(device)

    if sr != model.samplerate:
        import torchaudio
        waveform = torchaudio.functional.resample(waveform.squeeze(0), sr, model.samplerate).unsqueeze(0)

    with torch.no_grad():
        sources = apply_model(model, waveform, device=device)

    vocal_idx = model.sources.index("vocals")
    vocals = sources[0, vocal_idx].cpu().numpy()
    vocals_mono = vocals.mean(axis=0).astype(np.float32)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_audio(output_path, vocals_mono, model.samplerate)
    return output_path
