#!/usr/bin/env python3
"""Create a custom VNCCS pose from a library pose by rotating bones.

Loads the base pose into the PoseStudio editor in the shared browser, applies
the requested bone rotations, and saves through PoseStudio's own
saveToLibrary(), so the result is the same as the editor's Save dialog
(pose JSON + preview under PoseLibrary/local_user_poses/poses/<category>/).

loadFromLibrary() must get the /vnccs/pose_library/list entry (name,
repository, category), not the pose file content: a pose file has no name,
the fetch fails and the editor keeps its previous pose without raising.

Usage:
    make_custom_pose.py --base "Standing A" --list-bones
    make_custom_pose.py --base "MIUProject__VNCCS_PoseLibrary_Main/poses/Standing/Standing A" \
        --name "Arms Out" --rotate upperarm_l:1:90 --rotate upperarm_r:1:-90
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # bundled browser_fallback.py

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

WF_FILE = Path(os.environ.get("VNCCS_WF_FILE", str(_PKG_DIR / "workflows" / "VNCCS_PoseStudio_QI2.1.json")))
URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")


def list_poses() -> list[dict]:
    with urllib.request.urlopen(f"{URL}/vnccs/pose_library/list", timeout=30) as resp:
        return json.loads(resp.read())["poses"]


def resolve_base(base: str, poses: list[dict]) -> dict:
    exact = [p for p in poses if p["id"] == base]
    if exact:
        return exact[0]
    named = [p for p in poses if p["name"].lower() == base.lower()]
    if len(named) == 1:
        return named[0]
    if named:
        ids = "\n  ".join(p["id"] for p in named)
        raise KeyError(f"'{base}' matches {len(named)} poses; pass one of these ids:\n  {ids}")
    raise KeyError(f"no pose named '{base}' (see run_vnccs_ui.py --list-poses or {URL}/vnccs/pose_library/list)")


def parse_rotation(spec: str) -> tuple[str, int, float]:
    bone, axis, degrees = spec.split(":")
    if axis not in ("0", "1", "2"):
        raise ValueError(f"axis must be 0, 1 or 2: {spec}")
    return bone, int(axis), float(degrees)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="library pose id or unique name (see /vnccs/pose_library/list)")
    ap.add_argument("--name", help="name of the new pose (required unless --list-bones)")
    ap.add_argument("--category", default="Custom")
    ap.add_argument("--rotate", action="append", default=[], metavar="BONE:AXIS:DEG",
                    help="add DEG degrees to euler axis AXIS (0/1/2) of BONE; repeatable")
    ap.add_argument("--tags", default="", help="comma-separated tags")
    ap.add_argument("--prompt", default="", help="pose prompt stored with the pose")
    ap.add_argument("--no-preview", action="store_true", help="save without the .webp preview")
    ap.add_argument("--list-bones", action="store_true", help="print the base pose's bone rotations and exit")
    a = ap.parse_args()

    if not a.list_bones and not a.name:
        ap.error("--name is required unless --list-bones is given")
    if connect_sync is None or sync_playwright is None:
        print("ERROR: needs a CDP browser client and playwright; install playwright "
              "(`pip install playwright && playwright install chromium`) or keep the OpenClaw "
              "adapter at ~/.openclaw/tools/browser/browser_client.py", file=sys.stderr)
        return 2
    try:
        rotations = [parse_rotation(s) for s in a.rotate]
        entry = resolve_base(a.base, list_poses())
    except (KeyError, ValueError) as exc:
        print(f"ERROR: {exc.args[0]}", file=sys.stderr)
        return 2

    wf = json.loads(WF_FILE.read_text(encoding="utf-8"))
    with sync_playwright() as pw:
        browser = connect_sync(pw)
        page = browser.contexts[0].new_page()
        try:
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.goto(URL, timeout=30000)
            page.wait_for_timeout(5000)
            page.evaluate("(wf) => window.app.loadGraphData(wf)", wf)
            page.wait_for_timeout(6000)
            res = page.evaluate("""async ([entry, rotations, save]) => {
                const w = window.app.graph._nodes.find(n => n.type === 'VNCCS_PoseStudio')?.studioWidget;
                if (!w?.viewer) return {error: 'VNCCS_PoseStudio editor not found'};
                await w.loadFromLibrary(entry);
                await new Promise(r => setTimeout(r, 1500));
                const pose = JSON.parse(JSON.stringify(w.viewer.getPose()));
                if (!save) return {bones: pose.bones};
                for (const [bone, axis, deg] of rotations) {
                    if (!pose.bones[bone]) return {error: `unknown bone: ${bone}`};
                    pose.bones[bone][axis] += deg;
                }
                w.viewer.setPose(pose, true);
                w.commitViewerPoseToCurrentEditor();
                await new Promise(r => setTimeout(r, 1500));
                const ok = await w.saveToLibrary(save.name, save.preview, save.meta);
                return {ok, bones: w.viewer.getPose().bones};
            }""", [entry, rotations, None if a.list_bones else {
                "name": a.name, "preview": not a.no_preview,
                "meta": {"category": a.category, "tags": [t.strip() for t in a.tags.split(",") if t.strip()],
                         "prompt": a.prompt},
            }])
        finally:
            page.close()

    if res.get("error"):
        print(f"ERROR: {res['error']}", file=sys.stderr)
        return 1
    if a.list_bones:
        for bone, rot in res["bones"].items():
            print(f"{bone}\t" + "\t".join(f"{v:.1f}" for v in rot))
        return 0
    saved = [p for p in list_poses() if p["name"] == a.name and p["category"] == a.category
             and p["repository"] == "local_user_poses"]
    if not res.get("ok") or not saved:
        print("ERROR: save failed (check the ComfyUI browser console)", file=sys.stderr)
        return 1
    print(json.dumps({"base": entry["id"], "saved": saved[0]["id"], "rotations": rotations}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
