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
    parser.add_argument(
        "--caption", default="rap, hip-hop, aggressive flow, male rapper, trap beat",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--offload", action="store_true")
    parser.add_argument("--task-type", default="text2music", choices=["text2music", "lego"])
    parser.add_argument("--src-audio", default=None, help="Backing track path (required for lego)")
    parser.add_argument("--global-caption", default="")
    args = parser.parse_args()

    project_root = args.project_root or os.environ.get(
        "ACESTEP_PROJECT_ROOT",
        str(Path(__file__).resolve().parents[5] / "ACE-Step-1.5"),
    )
    sys.path.insert(0, project_root)

    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler

    is_lego = args.task_type == "lego"
    config_path = "acestep-v15-base" if is_lego else "acestep-v15-turbo"

    dit_handler = AceStepHandler()
    dit_handler.initialize_service(
        project_root=project_root,
        config_path=config_path,
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

    default_steps = 50 if is_lego else 8
    steps = args.steps if args.steps is not None else default_steps

    if is_lego:
        assert args.src_audio and Path(args.src_audio).exists(), (
            f"--src-audio required for lego task, got: {args.src_audio}"
        )
        params = GenerationParams(
            task_type="lego",
            src_audio=args.src_audio,
            instruction="Generate the vocals track based on the audio context:",
            caption=args.caption,
            global_caption=args.global_caption,
            lyrics=lyrics_formatted,
            vocal_language="en",
            bpm=args.bpm,
            timesignature=args.time_signature or "",
            repainting_start=0.0,
            repainting_end=-1,
            inference_steps=steps,
            guidance_scale=7.0,
            shift=3.0,
            seed=args.seed,
            thinking=True,
        )
    else:
        params = GenerationParams(
            task_type="text2music",
            caption=args.caption,
            lyrics=lyrics_formatted,
            vocal_language="en",
            bpm=args.bpm,
            timesignature=args.time_signature or "",
            duration=args.duration,
            inference_steps=steps,
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
