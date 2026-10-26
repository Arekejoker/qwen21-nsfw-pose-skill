#!/usr/bin/env python3
"""Run the official VNCCS Pose Studio workflow through the ComfyUI web UI.

VNCCS_PoseStudio needs the frontend's live capture at execution time, so we
load the graph in the shared browser (our own tab), set the character image and
the pose preset, queue from the UI, then collect the outputs from disk.

Usage:
    run_vnccs_ui.py --pose crawling [--char /path/to/face.png] [--timeout 900]
    run_vnccs_ui.py --pose "squatting leaning back" --prompt "on a rooftop at night"
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # bundled media_lock.py
try:
    from media_lock import media_lock  # noqa: E402
except ImportError:  # fall back to the shared-machine helper if present
    sys.path.insert(0, os.path.expanduser("~/.openclaw/tools"))
    from media_lock import media_lock  # noqa: E402

# route ④ needs a CDP browser; keep --list-poses usable without one
try:
    sys.path.insert(0, os.path.expanduser("~/.openclaw/tools/browser"))
    from browser_client import connect_sync  # noqa: E402
except ImportError:  # standalone hosts: bundled CDP fallback
    try:
        from browser_fallback import connect_sync  # noqa: E402
    except ImportError:
        connect_sync = None
try:
    from playwright.sync_api import sync_playwright  # noqa: E402
except ImportError:
    sync_playwright = None

# ComfyUI-side paths default to $COMFY (or ~/ComfyUI); override individually if needed
_COMFY = Path(os.environ.get("COMFY") or (Path.home() / "ComfyUI"))
WF_FILE = Path(os.environ.get("VNCCS_WF_FILE", str(_PKG_DIR / "workflows" / "VNCCS_PoseStudio_QI2.1.json")))
VNCCS_LIB = Path(os.environ.get("VNCCS_POSELIB", str(_COMFY / "custom_nodes" / "ComfyUI_VNCCS_Utils" / "PoseLibrary")))
COMFY_INPUT = Path(os.environ.get("COMFYUI_INPUT", str(_COMFY / "input")))
COMFY_OUTPUT = Path(os.environ.get("COMFYUI_OUTPUT", str(_COMFY / "output")))
OUT = Path(os.environ.get("VNCCS_UI_OUT", str(_PKG_DIR / "outputs" / "vnccs_ui")))
VNCCS_LORA = os.environ.get("VNCCS_LORA", "VNCCS_QI2_PoseStudioV1.1.safetensors")
URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")

# aliases used by the phase4b runs, kept so old commands still work
LEGACY = {
    "crawling": "Crawling",
    "kneel_side": "Kneeling - Side View",
    "lean_back": "Leaning Back",
    "sit_side": "Sitting - Side View",
}


def _slug(s: str) -> str:
    return "_".join("".join(ch if ch.isalnum() else " " for ch in s.lower()).split())


def build_pose_index() -> dict[str, Path]:
    """Index every pose JSON shipped in the VNCCS PoseLibrary (136 as of 2026-10-12).

    Keys: "<repo_slug>/<category_slug>/<pose_slug>" for every pose, plus a bare
    "<pose_slug>" alias when that name is unique across the library (9 pose names
    such as "Standing A" exist in more than one repository).
    """
    idx: dict[str, Path] = {}
    counts: dict[str, int] = {}
    if VNCCS_LIB.is_dir():
        for p in sorted(VNCCS_LIB.rglob("*.json")):
            s = p.as_posix()  # Windows str(path) uses backslashes; normalize
            if "/poses/" not in s and "/local_user_poses/" not in s:
                continue
            rel = p.relative_to(VNCCS_LIB).parts
            repo, category, name = _slug(rel[0]), _slug(rel[1]), _slug(p.stem)
            if category == "poses":  # local_user_poses nests one level shallower
                category = _slug(rel[2])
            idx[f"{repo}/{category}/{name}"] = p
            counts[name] = counts.get(name, 0) + 1
    for key, path in list(idx.items()):
        if key.count("/") != 2:
            continue
        name = key.rsplit("/", 1)[1]
        if counts.get(name) == 1:
            idx[name] = path
    for alias, stem in LEGACY.items():
        for key, path in idx.items():
            if key.count("/") == 2 and key.rsplit("/", 1)[1] == _slug(stem):
                idx.setdefault(alias, path)
                break
    return idx


def resolve_pose(name: str, idx: dict[str, Path]) -> Path:
    if name in idx:
        return idx[name]
    key = _slug(name)
    if key in idx:
        return idx[key]
    hits = sorted({p for k, p in idx.items() if key in k or k in key})
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise KeyError(f"unknown pose '{name}' — run with --list-poses to see the {len(idx)} available poses")
    raise KeyError(f"pose '{name}' is ambiguous: {[p.stem for p in hits][:6]} — disambiguate with <repo>/<category>/<name>")


def prep_workflow(pose_json: str, char_name: str, prefix: str, user_prompt: str = "") -> dict:
    wf = json.loads(WF_FILE.read_text(encoding="utf-8"))
    by_id = {n["id"]: n for n in wf["nodes"]}

    # drop the rgthree comparer (only a viewer node; its inputs are decorative here)
    drop = [nid for nid, n in by_id.items() if n["type"].startswith("Image Comparer")]
    wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in drop]
    wf["links"] = [l for l in wf["links"] if l[1] not in drop and l[3] not in drop]

    # character image + save prefix on the existing LoadImage / SaveImage nodes
    for n in wf["nodes"]:
        if n["type"] == "LoadImage" and isinstance(n.get("widgets_values"), list):
            n["widgets_values"][0] = char_name
        if n["type"] == "SaveImage" and isinstance(n.get("widgets_values"), list):
            n["widgets_values"][0] = prefix
        if n["type"] == "VNCCS_PoseStudio" and isinstance(n.get("widgets_values"), list):
            value = pose_json
            if user_prompt:
                # The frontend rebuilds the capture prompt from the scene document's
                # export block (prompt_template "Draw character from image2\n
                # <lighting>\n<user_prompt>"), where <user_prompt> comes from the
                # per-pose prompt. Library pose files carry empty prompt/pose_prompts
                # fields and no export block, so set all three hydration paths:
                # pose.prompt (per-tab), pose_prompts[0] (hydrated array) and
                # export.user_prompt (legacy global default).
                scene = json.loads(pose_json)
                scene["prompt"] = user_prompt
                scene["pose_prompts"] = [user_prompt]
                try:
                    export = dict(json.loads(n["widgets_values"][0]).get("export") or {})
                except (TypeError, ValueError):
                    export = {}
                export["user_prompt"] = user_prompt
                scene["export"] = export
                value = json.dumps(scene)
            n["widgets_values"][0] = value
        if n["type"] == "LoraLoaderModelOnly" and isinstance(n.get("widgets_values"), list):
            n["widgets_values"][0] = VNCCS_LORA
    return wf


def find_new_outputs(prefix: str, since: float) -> list[Path]:
    hits = []
    for p in COMFY_OUTPUT.rglob(f"{prefix}*.png"):
        try:
            if p.stat().st_mtime >= since - 1:
                hits.append(p)
        except OSError:
            pass
    return sorted(hits)


def settle(page, ms: int) -> None:
    """Sleep without relying on the CDP channel staying idle."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        time.sleep(0.5)
        try:
            page.evaluate("1")
        except Exception:
            pass


def main() -> int:
    # Windows cp1252 consoles cannot print the route glyphs or non-ASCII pose
    # names; reconfigure both streams (stdout carries the list, stderr the notes).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pose", default="crawling",
                    help="pose name/slug from the PoseLibrary (see --list-poses)")
    ap.add_argument("--char", default=str(_PKG_DIR / "references" / "src_standing.png"))
    ap.add_argument("--prompt", default="",
                    help="scene prompt for the capture: sets the pose prompt + export.user_prompt (overrides the workflow default)")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--list-poses", action="store_true", help="print all available pose names and exit")
    a = ap.parse_args()

    idx = build_pose_index()
    if a.list_poses:
        for slug, path in sorted(idx.items()):
            print(f"{slug}\t{path}")
        counts = sum(1 for k in idx if k.count("/") == 2)
        print(f"# {counts} poses (bare aliases not counted)", file=sys.stderr)
        if counts == 0:
            print(f"# nothing under {VNCCS_LIB} — set VNCCS_POSELIB or $COMFY (see install/setup.md §0/§4)",
                  file=sys.stderr)
        return 0
    if connect_sync is None or sync_playwright is None:
        print("ERROR: route ④ needs a CDP browser client and playwright; install playwright "
              "(`pip install playwright && playwright install chromium`) or keep the OpenClaw "
              "adapter at ~/.openclaw/tools/browser/browser_client.py", file=sys.stderr)
        return 2
    try:
        pose_path = resolve_pose(a.pose, idx)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    tag = _slug(a.pose)  # filesystem-safe tag for output names
    OUT.mkdir(parents=True, exist_ok=True)
    COMFY_INPUT.mkdir(parents=True, exist_ok=True)
    char_src = Path(a.char)
    if not char_src.exists():
        print(f"ERROR: character not found: {char_src}", file=sys.stderr)
        return 1
    char_name = char_src.name
    shutil.copy2(char_src, COMFY_INPUT / char_name)

    pose_json = pose_path.read_text(encoding="utf-8")
    # unique prefix per run — never clobber a previous result
    stamp = int(time.time())
    prefix = f"poselab/vnccs_ui_{tag}_{stamp}"
    wf = prep_workflow(pose_json, char_name, prefix, a.prompt)

    with media_lock(exclusive=False, wait_timeout=a.timeout + 300):
      with sync_playwright() as pw:
        browser = connect_sync(pw)
        page = browser.contexts[0].new_page()
        logs: list[str] = []
        try:
            page.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
            page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
            def _on_resp(r):
                if "/prompt" in r.url and r.status >= 400:
                    try:
                        logs.append(f"HTTP {r.status} /prompt: {r.text()[:1500]}")
                    except Exception as e:
                        logs.append(f"HTTP {r.status} /prompt body unreadable: {e}")
            page.on("response", _on_resp)
        except Exception:
            pass
        try:
            page.goto(URL, timeout=30000)
            settle(page, 4000)
            page.evaluate("(wf) => window.app.loadGraphData(wf)", wf)
            settle(page, 3000)
            # drop QwenImage21Cache (aimdo error on this box) and wire LoRA -> KSampler
            page.evaluate("""() => {
                const g = window.app.graph;
                const nodes = g._nodes;
                const lora = nodes.find(n => n.type === 'LoraLoaderModelOnly');
                const ks = nodes.find(n => n.type === 'KSampler');
                const cache = nodes.find(n => n.type === 'QwenImage21Cache');
                if (lora && ks) {
                    const slot = ks.inputs.findIndex(i => i.name === 'model');
                    lora.connect(0, ks, slot);
                }
                if (cache) g.remove(cache);
                return true;
            }""")
            settle(page, 1500)
            # also persist the rendered pose figure (doll) for comparison
            page.evaluate("""(prefix) => {
                try {
                    const g = window.app.graph;
                    const ps = g._nodes.find(n => n.type === 'VNCCS_PoseStudio');
                    if (!ps || !window.LiteGraph) return false;
                    const sv = window.LiteGraph.createNode('SaveImage');
                    sv.widgets[0].value = prefix;
                    g.add(sv);
                    ps.connect(0, sv, 0);
                    return true;
                } catch (e) { return 'ERR:' + e.message; }
            }""", f"poselab/vnccs_ui_doll_{tag}_{stamp}")
            # confirm widgets landed
            info = page.evaluate("""() => {
                const g = window.app.graph._nodes;
                const li = g.find(n => n.type === 'LoadImage');
                const ps = g.find(n => n.type === 'VNCCS_PoseStudio');
                return {
                    nodes: g.length,
                    loadImage: li ? li.widgets.find(w=>w.name==='image').value : null,
                    poseLen: ps ? String(ps.widgets.find(w=>w.name==='pose_data').value).length : null,
                };
            }""")
            print(f"[vnccs-ui] graph: {info}")
            page.screenshot(path=str(OUT / f"_ui_{tag}_loaded.png"))

            t0 = time.time()
            page.evaluate("() => window.app.queuePrompt()")
            print("[vnccs-ui] queued from UI; waiting for outputs...")
            deadline = time.time() + a.timeout
            got: list[Path] = []
            while time.time() < deadline:
                settle(page, 5000)
                got = find_new_outputs(prefix, t0)
                if got:
                    break
            if not got:
                page.screenshot(path=str(OUT / f"_ui_{tag}_timeout.png"))
                print("[vnccs-ui] TIMEOUT; console tail:")
                for line in logs[-12:]:
                    print("   ", line)
                return 1
            settle(page, 2000)
            saved: list[str] = []
            for i, p in enumerate(got, 1):
                dst = OUT / f"result_{tag}{('' if i == 1 else f'_{i}')}.png"
                shutil.copy2(p, dst)
                saved.append(dst.name)
                print(f"[vnccs-ui] saved {dst.name} ({p.name})")
            page.screenshot(path=str(OUT / f"_ui_{tag}_done.png"))
        finally:
            page.close()
    (OUT / f"{tag}_{stamp}.meta.json").write_text(json.dumps({
        "pose": a.pose, "resolved": str(pose_path), "char": char_name,
        "comfy_prefix": prefix, "seconds": round(time.time() - t0, 1),
        "outputs": saved, "lora": VNCCS_LORA,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[vnccs-ui] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
