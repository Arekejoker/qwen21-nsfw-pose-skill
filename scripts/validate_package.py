#!/usr/bin/env python3
"""Offline integrity checks for the shareable Qwen-Image pose package."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


python_files = sorted((ROOT / "scripts").glob("*.py"))
for path in python_files:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path.relative_to(ROOT)))
    except (SyntaxError, UnicodeDecodeError) as exc:
        errors.append(f"Python syntax error in {path.relative_to(ROOT)}: {exc}")

json_dirs = (
    ROOT / "workflows",
    ROOT / "prompts",
    ROOT / "downloads" / "samples",
    ROOT / "pose_library" / "local_user_poses",
)
json_files = sorted(path for directory in json_dirs for path in directory.rglob("*.json"))
for path in json_files:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        errors.append(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}")

pose_dir = ROOT / "pose_library" / "local_user_poses" / "Uncategorized"
pose_jsons = sorted(pose_dir.glob("*.json"))
pose_previews = sorted(pose_dir.glob("*.webp"))
check(len(pose_jsons) == 55, f"expected 55 curated pose JSONs, found {len(pose_jsons)}")
check(len(pose_previews) == 55, f"expected 55 pose previews, found {len(pose_previews)}")
for path in pose_jsons:
    check(path.with_suffix(".webp").is_file(), f"missing pose preview for {path.name}")
for path in pose_previews:
    check(path.with_suffix(".json").is_file(), f"missing pose JSON for {path.name}")
    check(path.stat().st_size > 0, f"empty pose preview file: {path.name}")

readmes = [ROOT / "README.md", ROOT / "README.en.md"]
image_paths: list[str] = []
for readme in readmes:
    check(readme.is_file(), f"missing {readme.name}")
    if not readme.is_file():
        continue
    images = re.findall(r'<img\s+[^>]*src="([^"]+)"', readme.read_text(encoding="utf-8"))
    image_paths.extend(images)
    check(bool(images), f"{readme.name} has no embedded showcase images")
    for image_path in images:
        local_path = image_path.split("?", 1)[0]  # strip cache-busting query
        target = ROOT / local_path
        check(target.is_file(), f"README image does not exist: {local_path}")
        if target.is_file():
            check(target.stat().st_size > 0, f"empty README image: {local_path}")

for relative in (
    "LICENSE",
    "SKILL.md",
    "install/setup.md",
    "references/src_standing.png",
    "downloads/samples/phase5_meta.json",
):
    check((ROOT / relative).is_file(), f"missing required package file: {relative}")

if errors:
    for error in errors:
        print(f"FAIL: {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    f"OK: {len(python_files)} Python files, {len(json_files)} JSON files, "
    f"{len(pose_jsons)} pose JSON/preview pairs, {len(image_paths)} README images"
)
