#!/usr/bin/env python3
"""Standalone ACE-Step generation script.

Runs inside the ACE-Step virtual environment. Called as a subprocess by the
RapMap acestep adapter. Outputs a single wav file.

Usage:
    python _acestep_generate.py --lyrics "..." --output /path/to/out.wav \
        --duration 15 --bpm 120 --caption "rap, hip-hop, male rapper"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lyrics", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--bpm", type=int, default=None)
    parser.add_argument("--time-signature", default="", help="Time signature: 2, 3, 4, or 6")
    parser.add_argument("--caption", default="rap, hip-hop, aggressive flow, male rapper, trap beat")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--offload", action="store_true")
    args = parser.parse_args()

    project_root = args.project_root or os.environ.get(
        "ACESTEP_PROJECT_ROOT",
        str(Path(__file__).resolve().parents[5] / "ACE-Step-1.5"),
    )
    sys.path.insert(0, project_root)

    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music

    dit_handler = AceStepHandler()
    dit_handler.initialize_service(
        project_root=project_root,
        config_path="acestep-v15-turbo",
        device="auto",
        offload_to_cpu=args.offload,
    )

    llm_handler = LLMHandler()
    available_lm = llm_handler.get_available_5hz_lm_models()
    if available_lm:
        lm_model = available_lm[0]
    else:
        from acestep.model_downloader import ensure_lm_model, get_checkpoints_dir
        ensure_lm_model(checkpoints_dir=str(get_checkpoints_dir()))
        available_lm = llm_handler.get_available_5hz_lm_models()
        lm_model = available_lm[0] if available_lm else "acestep-5Hz-lm-0.6B"

    from acestep.model_downloader import get_checkpoints_dir
    llm_handler.initialize(
        checkpoint_dir=str(get_checkpoints_dir()),
        lm_model_path=lm_model,
        backend="pytorch",
        device="auto",
        offload_to_cpu=args.offload,
    )

    lyrics_formatted = args.lyrics
    if not lyrics_formatted.startswith("["):
        lyrics_formatted = "[Verse]\n" + lyrics_formatted

    params = GenerationParams(
        task_type="text2music",
        caption=args.caption,
        lyrics=lyrics_formatted,
        vocal_language="en",
        bpm=args.bpm,
        timesignature=args.time_signature or "",
        duration=args.duration,
        inference_steps=args.steps,
        seed=args.seed,
        thinking=True,
    )
    config = GenerationConfig(
        batch_size=1,
        audio_format="wav",
    )

    output_dir = str(Path(args.output).parent)
    result = generate_music(dit_handler, llm_handler, params, config, save_dir=output_dir)

    if not result.success:
        print(json.dumps({"success": False, "error": result.error}))
        sys.exit(1)

    generated_path = None
    if result.audios:
        for audio_entry in result.audios:
            p = audio_entry.get("path")
            if p and Path(p).exists():
                generated_path = p
                break

    if generated_path is None:
        print(json.dumps({"success": False, "error": "No audio file produced"}))
        sys.exit(1)

    target = Path(args.output)
    if Path(generated_path) != target:
        import shutil
        shutil.copy2(generated_path, target)

    print(json.dumps({"success": True, "path": str(target)}))


if __name__ == "__main__":
    main()
