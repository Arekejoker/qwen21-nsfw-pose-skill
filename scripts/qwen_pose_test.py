#!/usr/bin/env python3
"""pose-lab: Qwen-Image 2.1 LoRA test harness (T2I + edit).

Runs against the production ComfyUI service on 127.0.0.1:8188 and takes the
shared media lock (image-gen shared mode) so it never fights openclaw tasks.

Everything is applied to an in-memory copy of the production workflow;
no production workflow file is modified.

Usage (single run):
    qwen_pose_test.py --mode t2i --prompt "..." --seed 42 --steps 40 --cfg 1 \
        --sampler euler --scheduler simple --width 1344 --height 768 \
        --out outputs/x.png [--lora NAME --lora-strength 0.8]
    qwen_pose_test.py --mode edit --input inputs/src.png --prompt "..." \
        --out outputs/y.png [--lora NAME --lora-strength 0.8]
"""
from __future__ import annotations

import argparse
import copy
import json
import mimetypes
import os
import random
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # bundled media_lock.py
try:
    from media_lock import media_lock, MediaLockError  # noqa: E402
except ImportError:  # fall back to the shared-machine helper if present
    sys.path.insert(0, os.path.expanduser("~/.openclaw/tools"))
    from media_lock import media_lock, MediaLockError  # noqa: E402

_PKG_DIR = Path(__file__).resolve().parent.parent
COMFY_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
WORKFLOW_DIR = Path(os.environ.get("QWEN_POSE_WORKFLOWS", str(_PKG_DIR / "workflows")))
POSELAB = Path(os.environ.get("POSELAB", str(_PKG_DIR)))

WORKFLOWS = {
    "t2i": WORKFLOW_DIR / "qwen21_t2i.json",
    "edit": WORKFLOW_DIR / "qwen21_edit.json",
}
TIMEOUT = 900
POLL_INTERVAL = 2.0

# node ids are resolved by class_type (both bundled workflows use 1/2/3/4/5/6/7/8)
N_SAVE = "8"


def _http_json(method: str, url: str, payload: dict | None = None, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def upload_image(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"input image not found: {path}")
    boundary = f"----poselab{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    body = bytearray()
    body += f"--{boundary}\r\n".encode()
    body += (
        f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode()
    body += path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{COMFY_URL}/upload/image",
        data=bytes(body),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read())
    name = result.get("name")
    if not name:
        raise RuntimeError(f"/upload/image returned no name: {json.dumps(result)}")
    sub = result.get("subfolder", "")
    return f"{sub}/{name}" if sub else name


def queue_prompt(workflow: dict) -> str:
    payload = {"prompt": workflow, "client_id": f"poselab-{random.randint(0, 10**6)}"}
    result = _http_json("POST", f"{COMFY_URL}/prompt", payload, timeout=60)
    if result.get("error"):
        raise RuntimeError(f"ComfyUI rejected prompt: {json.dumps(result, ensure_ascii=False)[:800]}")
    pid = result.get("prompt_id")
    if not pid:
        raise RuntimeError(f"/prompt returned no prompt_id: {json.dumps(result)[:400]}")
    return pid


def wait_and_get_image(prompt_id: str) -> str:
    deadline = time.monotonic() + TIMEOUT
    last = ""
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL)
        try:
            hist = _http_json("GET", f"{COMFY_URL}/history/{prompt_id}", timeout=30)
        except Exception as exc:  # noqa: BLE001
            last = f"poll error: {exc}"
            continue
        entry = hist.get(prompt_id)
        if not entry:
            last = "no history entry yet"
            continue
        if entry.get("status", {}).get("status_str") == "error":
            msgs = entry.get("status", {}).get("messages", [])
            raise RuntimeError(f"ComfyUI prompt failed: {json.dumps(msgs, ensure_ascii=False)[:800]}")
        images = entry.get("outputs", {}).get(N_SAVE, {}).get("images", [])
        if images:
            img = images[0]
            sub = img.get("subfolder", "")
            return f"{sub}/{img['filename']}" if sub else img["filename"]
        last = "executing..."
    raise TimeoutError(f"prompt {prompt_id} did not finish in {TIMEOUT}s ({last})")


def download_view(image_rel: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    parts = image_rel.split("/")
    query = urllib.parse.urlencode({"filename": parts[-1], "type": "output"})
    if len(parts) > 1:
        query += "&" + urllib.parse.urlencode({"subfolder": "/".join(parts[:-1])})
    with urllib.request.urlopen(f"{COMFY_URL}/view?{query}", timeout=120) as resp:
        output.write_bytes(resp.read())


def inject_lora_model_only(wf: dict, lora_name: str, strength: float) -> int:
    """Insert LoraLoaderModelOnly after UNETLoader; rewire model consumers.

    DiT-only LoRAs (civitai NSFW/pose loras) are trained on the transformer, so
    the text-encoder path is intentionally left untouched.
    """
    unet_id = next((k for k, v in wf.items() if isinstance(v, dict) and v.get("class_type") == "UNETLoader"), None)
    if unet_id is None:
        raise RuntimeError("workflow has no UNETLoader")
    wf["99"] = {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {"lora_name": lora_name, "strength_model": strength, "model": [unet_id, 0]},
    }
    for k, v in wf.items():
        if k == "99" or not isinstance(v, dict):
            continue
        for iname, val in v.get("inputs", {}).items():
            if isinstance(val, list) and len(val) == 2 and val[0] == unet_id and val[1] == 0:
                v["inputs"][iname] = ["99", 0]
    return 1


def build_workflow(mode: str, cfg: dict) -> tuple[dict, dict]:
    wf = copy.deepcopy(json.loads(WORKFLOWS[mode].read_text(encoding="utf-8")))
    applied: dict = {"mode": mode}

    save_id = next(k for k, v in wf.items() if isinstance(v, dict) and v.get("class_type") == "SaveImage")
    wf[save_id]["inputs"]["filename_prefix"] = f"poselab/{cfg['name']}"

    if mode == "t2i":
        text_id = next(k for k, v in wf.items() if isinstance(v, dict) and v.get("class_type") == "TextEncodeQwenImage21")
        latent_id = next(k for k, v in wf.items() if isinstance(v, dict) and v.get("class_type") == "EmptyLatentImage")
        wf[text_id]["inputs"]["prompt"] = cfg["prompt"]
        wf[text_id]["inputs"]["negative_prompt"] = cfg.get("negative") or ""
        wf[text_id]["inputs"]["resolution"] = cfg.get("resolution", 1024)
        wf[latent_id]["inputs"]["width"] = cfg["width"]
        wf[latent_id]["inputs"]["height"] = cfg["height"]
        wf[latent_id]["inputs"]["batch_size"] = 1
        applied.update(prompt=cfg["prompt"], negative=cfg.get("negative") or "",
                       resolution=cfg.get("resolution", 1024), width=cfg["width"], height=cfg["height"])
    else:
        image_id = next(k for k, v in wf.items() if isinstance(v, dict) and v.get("class_type") == "LoadImage")
        text_id = next(k for k, v in wf.items() if isinstance(v, dict) and v.get("class_type") == "TextEncodeQwenImage21")
        wf[image_id]["inputs"]["image"] = cfg["image_name"]
        wf[text_id]["inputs"]["prompt"] = cfg["prompt"]
        wf[text_id]["inputs"]["negative_prompt"] = cfg.get("negative") or ""
        wf[text_id]["inputs"]["resolution"] = cfg.get("resolution", 1024)
        applied.update(prompt=cfg["prompt"], negative=cfg.get("negative") or "",
                       resolution=cfg.get("resolution", 1024), image=cfg["image_name"],
                       source=cfg.get("source"))
        if cfg.get("image2_name"):
            wf["90"] = {"class_type": "LoadImage", "inputs": {"image": cfg["image2_name"]}}
            wf[text_id]["inputs"]["images.image_2"] = ["90", 0]
            applied.update(image2=cfg["image2_name"], source2=cfg.get("source2"))

    ks = next(k for k, v in wf.items() if isinstance(v, dict) and v.get("class_type") == "KSampler")
    wf[ks]["inputs"]["seed"] = cfg["seed"]
    wf[ks]["inputs"]["steps"] = cfg["steps"]
    wf[ks]["inputs"]["cfg"] = cfg["cfg"]
    wf[ks]["inputs"]["sampler_name"] = cfg["sampler"]
    wf[ks]["inputs"]["scheduler"] = cfg["scheduler"]
    wf[ks]["inputs"]["denoise"] = cfg.get("denoise", 1.0)
    applied.update(seed=cfg["seed"], steps=cfg["steps"], cfg=cfg["cfg"],
                   sampler=cfg["sampler"], scheduler=cfg["scheduler"], denoise=cfg.get("denoise", 1.0))

    if cfg.get("lora"):
        inject_lora_model_only(wf, cfg["lora"], cfg["lora_strength"])
        applied.update(lora=cfg["lora"], lora_strength=cfg["lora_strength"])
    else:
        applied.update(lora=None, lora_strength=None)
    return wf, applied


def run(cfg: dict, *, keep_meta: bool = True) -> dict:
    """Execute one generation. Returns result dict; raises on failure."""
    mode = cfg["mode"]
    out = Path(cfg["out"])
    wf, applied = build_workflow(mode, cfg)
    result = {"name": cfg["name"], "config": applied, "out": str(out), "started": time.time()}
    with media_lock(exclusive=False, wait_timeout=1800):
        t0 = time.monotonic()
        pid = queue_prompt(wf)
        image_rel = wait_and_get_image(pid)
        result["seconds"] = round(time.monotonic() - t0, 1)
        result["comfy_output"] = image_rel
        download_view(image_rel, out)
    result["finished"] = time.time()
    result["ok"] = out.exists() and out.stat().st_size > 0
    if keep_meta:
        meta = out.with_suffix(out.suffix + ".json")
        meta.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="pose-lab Qwen-Image 2.1 LoRA test run")
    p.add_argument("--mode", choices=["t2i", "edit"], required=True)
    p.add_argument("--name", required=True, help="run name (used for ComfyUI subfolder + output)")
    p.add_argument("--prompt", required=True)
    p.add_argument("--negative", default="")
    p.add_argument("--input", help="source image (edit mode)")
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=424242)
    p.add_argument("--steps", type=int, default=40)
    p.add_argument("--cfg", type=float, default=1.0)
    p.add_argument("--sampler", default="euler")
    p.add_argument("--scheduler", default="simple")
    p.add_argument("--denoise", type=float, default=1.0)
    p.add_argument("--width", type=int, default=1344)
    p.add_argument("--height", type=int, default=768)
    p.add_argument("--resolution", type=int, default=1024)
    p.add_argument("--lora")
    p.add_argument("--lora-strength", type=float, default=0.8)
    return p.parse_args()


def main() -> int:
    a = _parse()
    cfg = dict(a.__dict__)
    if a.mode == "edit":
        if not a.input:
            print("ERROR: --input required for edit mode", file=sys.stderr)
            return 2
        cfg["image_name"] = upload_image(Path(a.input))
        cfg["source"] = a.input
    try:
        res = run(cfg)
    except (MediaLockError, TimeoutError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"out": res["out"], "seconds": res["seconds"], "ok": res["ok"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
