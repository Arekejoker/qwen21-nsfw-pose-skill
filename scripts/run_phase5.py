#!/usr/bin/env python3
"""Phase 5: reproduce author sample prompts/params to isolate what drives the look.

Cases:
  A1: taws shower prompt + v1.3b @1.0, author params (50s, cfg2.5, er_sde/beta, seed 80964)
  A2: taws massage prompt + v1.3b @1.0, 30s, same as above
  B1: thesealpacas selfie prompt + v2 @0.8, author params (50s, cfg4, er_sde/beta)
  C1: control — shower prompt, NO lora, same sampler params (isolates prompt effect)
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qwen_pose_test import run, MediaLockError

META = json.load(open(Path(__file__).parent.parent / "downloads/samples/phase5_meta.json"))
OUT = Path(__file__).parent.parent / "outputs/phase5"
OUT.mkdir(parents=True, exist_ok=True)

TAWS = "qwen2_1-femaledVaginus-nsfw-v1_3-fine_L22-31.safetensors"
SEAL = "thesealpacas-nsfw-v2.safetensors"

CASES = [
    {"key": "A1_shower_v13b", "src": "taws_v13_shower", "lora": TAWS, "strength": 1.0,
     "seed": 80964, "steps": 50, "cfg": 2.5, "w": 1152, "h": 1728, "refine": False},
    {"key": "A2_massage_v13b", "src": "taws_v13_massage", "lora": TAWS, "strength": 1.0,
     "seed": 80964, "steps": 30, "cfg": 2.5, "w": 1152, "h": 1728},
    {"key": "B1_selfie_seal", "src": "thesealpacas_v2_selfie", "lora": SEAL, "strength": 0.8,
     "seed": 124880844757561, "steps": 50, "cfg": 4.0, "w": 1152, "h": 1728},
    {"key": "C1_shower_no_lora", "src": "taws_v13_shower", "lora": None, "strength": None,
     "seed": 80964, "steps": 50, "cfg": 2.5, "w": 1152, "h": 1728},
]

results = []
for c in CASES:
    out = OUT / f"{c['key']}.png"
    if out.exists() and out.stat().st_size > 0:
        print(f"[skip] {c['key']} exists", flush=True)
        results.append({"key": c["key"], "ok": True, "out": str(out), "seconds": 0})
        continue
    meta = META[c["src"]]
    cfg = dict(mode="t2i", name=c["key"],
               prompt=meta["prompt"], negative=meta.get("negative", ""),
               out=str(out), seed=c["seed"], steps=c["steps"], cfg=c["cfg"],
               sampler="er_sde", scheduler="beta",
               width=c["w"], height=c["h"], resolution=1024,
               lora=c["lora"], lora_strength=c["strength"])
    try:
        r = run(cfg, keep_meta=True)
        r["key"] = c["key"]
        results.append(r)
        print(f"[ok] {c['key']} {r['seconds']}s", flush=True)
    except (MediaLockError, Exception) as e:
        print(f"[fail] {c['key']}: {e}", flush=True)
        results.append({"key": c["key"], "ok": False, "error": str(e)})

json.dump(results, open(OUT / "_results.json", "w"), ensure_ascii=False, indent=1)
print("done")
