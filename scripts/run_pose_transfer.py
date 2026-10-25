#!/usr/bin/env python3
"""Route ③: scripted pose transfer from a 3D mannequin render (no browser).

Verified recipe (2026-10-16, see SKILL.md §6):
  image 1 = 3D mannequin render (pose source). It must be a textureless 3D
            render such as a VNCCS PoseStudio doll capture — photo or
            illustration references bleed the reference person's features
            into the output.
  image 2 = the character to keep (identity).
  prompt  = "replace the pose of <image 2> with the pose of <image 1>.
             keep the character of <image 2>"
  LoRA    = VNCCS PoseStudio LoRA @ 1.0 (mandatory — without it the mannequin
            is ignored), 25 steps, cfg 1, euler/simple.

Mannequin renders come from a route-④ browser run (run_vnccs_ui.py saves the
doll capture as `doll_*.png` under the ComfyUI output directory) or from any
other 3D poser render of the target pose.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qwen_pose_test import run, upload_image, MediaLockError  # noqa: E402

DEFAULT_PROMPT = ("replace the pose of <image 2> with the pose of <image 1>. "
                  "keep the character of <image 2>")
# VNCCS_LORA swaps the PoseStudio LoRA file (e.g. V2) without editing the script; --lora still wins
DEFAULT_LORA = os.environ.get("VNCCS_LORA", "VNCCS_QI2_PoseStudioV1.1.safetensors")


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Route ③: pose transfer from a 3D mannequin render (script, no browser)")
    p.add_argument("--char", required=True, help="character image (identity to keep)")
    p.add_argument("--pose-ref", required=True,
                   help="3D mannequin render of the target pose (pose source; NOT a photo)")
    p.add_argument("--out", required=True, help="output PNG path")
    p.add_argument("--name", help="run name / ComfyUI subfolder (default: from --out stem)")
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    p.add_argument("--negative", default="")
    p.add_argument("--seed", type=int, default=424242)
    p.add_argument("--steps", type=int, default=25)
    p.add_argument("--cfg", type=float, default=1.0)
    p.add_argument("--sampler", default="euler")
    p.add_argument("--scheduler", default="simple")
    p.add_argument("--resolution", type=int, default=1024)
    p.add_argument("--lora", default=DEFAULT_LORA)
    p.add_argument("--lora-strength", type=float, default=1.0)
    return p.parse_args()


def main() -> int:
    a = _parse()
    char = Path(a.char)
    pose_ref = Path(a.pose_ref)
    for label, path in (("character", char), ("pose reference", pose_ref)):
        if not path.is_file():
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            return 2

    name = a.name or f"posetransfer_{Path(a.out).stem}"
    cfg = dict(
        mode="edit", name=name, prompt=a.prompt, negative=a.negative,
        seed=a.seed, steps=a.steps, cfg=a.cfg, sampler=a.sampler,
        scheduler=a.scheduler, denoise=1.0, resolution=a.resolution, out=a.out,
        image_name=upload_image(pose_ref), source=str(pose_ref),   # image 1 = pose source
        image2_name=upload_image(char), source2=str(char),         # image 2 = character
        lora=a.lora, lora_strength=a.lora_strength,
    )
    try:
        res = run(cfg)
    except (MediaLockError, TimeoutError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"out": res["out"], "seconds": res["seconds"], "ok": res["ok"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
