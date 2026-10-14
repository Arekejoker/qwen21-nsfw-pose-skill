#!/usr/bin/env python3
"""Standalone CDP browser fallback for the route ④ scripts.

Used only when the OpenClaw/shared-browser adapter
(`~/.openclaw/tools/browser/browser_client.py`) is not installed, so the
scripts keep working on standalone hosts. It connects to an existing CDP
endpoint when one is reachable and otherwise launches Playwright's bundled
Chromium headless with a throwaway temporary profile (no logins, no cookies)
and connects to that.

Requirements: `pip install playwright && playwright install chromium`.

Environment:
    COMFY_BROWSER_CDP   CDP endpoint to reuse (default http://127.0.0.1:18800)
    COMFY_BROWSER_PORT  Port for the launched Chromium (default 18800)
    COMFY_BROWSER_MODE  auto (default) | attach (never launch) | launch (always)
"""
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request

PORT = int(os.environ.get("COMFY_BROWSER_PORT", "18800"))
CDP = os.environ.get("COMFY_BROWSER_CDP", f"http://127.0.0.1:{PORT}").rstrip("/")
MODE = os.environ.get("COMFY_BROWSER_MODE", "auto").strip().lower()

_proc: subprocess.Popen | None = None


def _cdp_up() -> bool:
    try:
        with urllib.request.urlopen(f"{CDP}/json/version", timeout=2):
            return True
    except Exception:
        return False


def _launch(playwright) -> None:
    global _proc
    exe = playwright.chromium.executable_path
    profile = tempfile.mkdtemp(prefix="comfy-browser-")
    args = [
        exe,
        f"--remote-debugging-port={PORT}",
        "--headless=new",
        # Ubuntu 23.10+ AppArmor blocks the setuid sandbox in many setups
        "--no-sandbox",
        "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader",
        "--disable-dev-shm-usage",
        "--mute-audio",
        f"--user-data-dir={profile}",
    ]
    _proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _cleanup() -> None:
        if _proc and _proc.poll() is None:
            _proc.terminate()
        shutil.rmtree(profile, ignore_errors=True)

    atexit.register(_cleanup)
    deadline = time.time() + 30
    while time.time() < deadline:
        if _cdp_up():
            return
        if _proc.poll() is not None:
            raise RuntimeError(
                f"fallback Chromium exited early (status {_proc.returncode}); "
                "is Chromium installed for playwright? `playwright install chromium`"
            )
        time.sleep(0.5)
    raise RuntimeError(f"fallback Chromium did not expose CDP at {CDP} within 30s")


def connect_sync(playwright):
    """Return a connected sync Browser (same contract as browser_client.connect_sync)."""
    if MODE != "launch" and _cdp_up():
        return playwright.chromium.connect_over_cdp(CDP)
    if MODE == "attach":
        raise RuntimeError(f"no CDP endpoint reachable at {CDP} (COMFY_BROWSER_MODE=attach)")
    _launch(playwright)
    return playwright.chromium.connect_over_cdp(CDP)
