#!/usr/bin/env python3
"""Environment self-check for the qwen21-nsfw-pose package.

Read-only by design: every check either inspects this package's own files or
sends a GET request to the local ComfyUI HTTP API. It never writes files,
changes ComfyUI state, installs anything, launches a browser, or takes the
media lock — safe to run on any machine, at any time.

Degradation: each check is independently guarded; any failure becomes a
WARN/SKIP line with an install hint instead of a crash. Exit code is non-zero
only for FAIL lines (package files missing or ComfyUI unreachable). All
WARN-level findings still leave exit code 0, because they describe an
environment that may not have installed the optional parts yet.

Usage:
    python3 scripts/doctor.py            # human-readable report
    python3 scripts/doctor.py --json     # machine-readable report
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PKG_DIR = SCRIPT_DIR.parent
COMFY_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
HTTP_TIMEOUT = 6.0

EXPECTED = {
    "unet": "qwen_image_2.1_int8_convrot.safetensors",
    "clip": "qwen3vl_8b_int8_convrot.safetensors",
    "vae": "qwen_image_2.1_vae_bf16.safetensors",
    "default_lora": "qwen2_1-femaledVaginus-nsfw-v1_3-fine_L22-31.safetensors",
}
KNOWN_LORAS = [
    "qwen2_1-femaledVaginus-nsfw-v1_3-fine_L22-31.safetensors",
    "qwen2_1-femaledVaginus-nsfw-v1.3-fine.safetensors",
    "thesealpacas-nsfw-v2.safetensors",
    "nsfw-posture-v3.safetensors",
    "qwen21-nsfw-image-edit.safetensors",
    os.environ.get("VNCCS_LORA", "VNCCS_QI2_PoseStudioV1.1.safetensors"),
]
PACKAGE_FILES = [
    "workflows/qwen21_t2i.json",
    "workflows/qwen21_edit.json",
    "workflows/VNCCS_PoseStudio_QI2.1.json",
    "scripts/qwen_pose_test.py",
    "scripts/run_vnccs_ui.py",
    "scripts/media_lock.py",
]


class Report:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, level: str, text: str, hint: str = "") -> None:
        self.rows.append({"level": level, "text": text, "hint": hint})

    def ok(self, text: str) -> None:
        self.add("OK", text)

    def warn(self, text: str, hint: str = "") -> None:
        self.add("WARN", text, hint)

    def skip(self, text: str, hint: str = "") -> None:
        self.add("SKIP", text, hint)

    def fail(self, text: str, hint: str = "") -> None:
        self.add("FAIL", text, hint)

    @property
    def failed(self) -> bool:
        return any(r["level"] == "FAIL" for r in self.rows)


def http_json(path: str, timeout: float = HTTP_TIMEOUT):
    req = urllib.request.Request(f"{COMFY_URL}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def node_options(node: str, section: str, field: str) -> list[str] | None:
    """Return a COMBO option list from /object_info/<node>, or None if absent."""
    try:
        data = http_json(f"/object_info/{node}")
    except Exception:  # noqa: BLE001
        return None
    info = data.get(node)
    if not info:
        return None
    try:
        return list(info["input"][section][field][0])
    except (KeyError, TypeError, IndexError):
        return None


def check_python(r: Report) -> None:
    v = sys.version_info
    if v >= (3, 10):
        r.ok(f"Python {v.major}.{v.minor}.{v.micro} (>= 3.10)")
    else:
        r.fail(f"Python {v.major}.{v.minor} is older than 3.10",
               "install Python 3.10+ (the scripts use modern type syntax)")


def check_package_files(r: Report) -> None:
    missing = [f for f in PACKAGE_FILES if not (PKG_DIR / f).exists()]
    if missing:
        r.fail(f"package files missing: {', '.join(missing)}",
               "re-clone the repository or re-download the release archive")
    else:
        r.ok(f"package files present ({len(PACKAGE_FILES)} checked)")


def check_comfy(r: Report) -> bool:
    try:
        stats = http_json("/system_stats")
    except Exception as exc:  # noqa: BLE001
        r.fail(f"ComfyUI not reachable at {COMFY_URL} ({exc.__class__.__name__})",
               "start ComfyUI, or set COMFYUI_URL (install/setup.md §1)")
        return False
    system = stats.get("system", {})
    version = system.get("comfyui_version", "?")
    py = str(system.get("python_version", "?")).split(" ")[0]
    ram = system.get("ram_total")
    ram_txt = f", RAM {round(ram / 2**30)} GiB" if isinstance(ram, (int, float)) and ram else ""
    r.ok(f"ComfyUI {version} reachable at {COMFY_URL} (python {py}{ram_txt})")
    devices = stats.get("devices", [])
    if devices:
        d = devices[0]
        vram = d.get("vram_total")
        vram_txt = f", VRAM {round(vram / 2**30)} GiB" if isinstance(vram, (int, float)) and vram else ""
        name = d.get("name") or d.get("type") or "device"
        r.ok(f"device: {name}{vram_txt}")
    return True


def check_base_models(r: Report) -> None:
    found = {}
    for key, node, section, field in [
        ("unet", "UNETLoader", "required", "unet_name"),
        ("clip", "CLIPLoader", "required", "clip_name"),
        ("vae", "VAELoader", "required", "vae_name"),
    ]:
        opts = node_options(node, section, field)
        if opts is None:
            r.warn(f"{node} not available — cannot verify {key}",
                   "is this a stock ComfyUI 0.3x install? (install/setup.md §1)")
            return
        found[key] = EXPECTED[key] in opts
        if found[key]:
            r.ok(f"base {key}: {EXPECTED[key]}")
        else:
            r.warn(f"base {key} missing: {EXPECTED[key]}",
                   f"download it into the ComfyUI model dirs (install/setup.md §2)")


def check_loras(r: Report) -> None:
    opts = node_options("LoraLoaderModelOnly", "required", "lora_name")
    if opts is None:
        r.warn("LoraLoaderModelOnly not available — cannot verify LoRAs",
               "is this a stock ComfyUI install? (install/setup.md §1)")
        return
    have = [n for n in KNOWN_LORAS if n in opts]
    default_ok = EXPECTED["default_lora"] in opts
    if default_ok:
        r.ok(f"default LoRA present ({len(have)}/{len(KNOWN_LORAS)} known LoRAs installed)")
    elif have:
        r.warn(f"default LoRA missing: {EXPECTED['default_lora']}",
               f"route ① needs it; {len(have)} other known LoRA(s) found (install/setup.md §2)")
    else:
        r.warn("no known NSFW/pose LoRAs found in models/loras",
               "download at least the default LoRA (install/setup.md §2)")


def check_vnccs_node(r: Report) -> bool:
    try:
        data = http_json("/object_info/VNCCS_PoseStudio")
    except Exception as exc:  # noqa: BLE001
        r.skip(f"VNCCS node check skipped ({exc.__class__.__name__})")
        return False
    if data.get("VNCCS_PoseStudio"):
        r.ok("VNCCS_PoseStudio node available (route ④ usable)")
        return True
    r.warn("VNCCS_PoseStudio node not found — route ④ unavailable",
           "install ComfyUI_VNCCS_Utils (install/setup.md §4) and restart ComfyUI")
    return False


def check_pose_library(r: Report) -> None:
    try:
        data = http_json("/vnccs/pose_library/list")
        poses = data.get("poses", [])
    except Exception as exc:  # noqa: BLE001
        r.warn(f"pose library endpoint not reachable ({exc.__class__.__name__})",
               "route ④ needs VNCCS_Utils + at least one pose repository (install/setup.md §4)")
        return
    if not poses:
        r.warn("pose library is empty",
               "add pose repositories (install/setup.md §4) — a full setup has 136 poses")
        return
    repos: dict[str, int] = {}
    for p in poses:
        repos[p.get("repository", "?")] = repos.get(p.get("repository", "?"), 0) + 1
    detail = ", ".join(f"{k} ({v})" for k, v in sorted(repos.items()))
    r.ok(f"pose library: {len(poses)} poses — {detail}")


def check_browser_stack(r: Report) -> None:
    playwright = importlib.util.find_spec("playwright") is not None
    openclaw = (Path.home() / ".openclaw" / "tools" / "browser" / "browser_client.py").exists()
    fallback = (SCRIPT_DIR / "browser_fallback.py").exists()
    if playwright and (openclaw or fallback):
        which = "shared-browser adapter" if openclaw else "bundled fallback launcher"
        r.ok(f"route ④ browser stack ready (playwright + {which})")
    elif not playwright:
        r.warn("playwright not installed — route ④ unavailable",
               "pip install playwright && playwright install chromium")
    else:
        r.warn("no browser client found for route ④",
               "keep browser_client.py or the bundled browser_fallback.py next to this script")


def run(json_out: bool) -> int:
    r = Report()
    check_python(r)
    check_package_files(r)
    if check_comfy(r):
        check_base_models(r)
        check_loras(r)
        vnccs = check_vnccs_node(r)
        if vnccs:
            check_pose_library(r)
        else:
            r.skip("pose library check skipped (VNCCS_Utils not installed)")
    else:
        for name in ("base models", "LoRAs", "VNCCS node", "pose library"):
            r.skip(f"{name} check skipped (ComfyUI unreachable)")
    check_browser_stack(r)

    if json_out:
        print(json.dumps({"ok": not r.failed, "checks": r.rows}, indent=2, ensure_ascii=False))
    else:
        print(f"qwen21-nsfw-pose doctor — {PKG_DIR}")
        print(f"ComfyUI: {COMFY_URL}\n")
        for row in r.rows:
            line = f"[{row['level']:4}] {row['text']}"
            print(line)
            if row["hint"] and row["level"] != "OK":
                print(f"       hint: {row['hint']}")
        bad = sum(1 for x in r.rows if x["level"] == "FAIL")
        warn = sum(1 for x in r.rows if x["level"] == "WARN")
        print(f"\n{len(r.rows)} checks: {len(r.rows) - bad - warn} OK, {warn} WARN, {bad} FAIL")
    return 1 if r.failed else 0


def main() -> int:
    # Windows cp1252 consoles cannot print the ①②③④ glyphs used in check text.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Read-only environment self-check (never writes anything)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()
    return run(a.json)


if __name__ == "__main__":
    sys.exit(main())
