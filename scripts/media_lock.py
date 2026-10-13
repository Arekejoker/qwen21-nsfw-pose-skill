#!/usr/bin/env python3
"""Shared media task lock: video rendering is exclusive, image gen is shared.

Policy (see /home/zjh/switch-model.sh + pixelle-local-llm.service):
- Video asset rendering owns the GPU: it takes an EXCLUSIVE lock AND stops the
  local LLM for the duration (LLM must be restored afterwards).
- Image generation may run concurrently with the LLM, but must WAIT while a
  video render holds the exclusive lock.

Usage:
    from media_lock import media_lock
    with media_lock(exclusive=True, wait_timeout=3600):   # video render
        ...
    with media_lock(exclusive=False, wait_timeout=1800):  # image gen
        ...
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import time
from pathlib import Path

LOCK_FILE = Path(os.environ.get("MEDIA_LOCK_FILE", "/tmp/media-task.lock"))


class MediaLockError(RuntimeError):
    """Raised when the media lock cannot be acquired in time."""


@contextlib.contextmanager
def media_lock(exclusive: bool, wait_timeout: int = 3600):
    """Acquire the media lock.

    exclusive=True  -> video render (blocks all image gen until finished)
    exclusive=False -> image gen (shared; multiple concurrent images allowed)

    Blocks up to wait_timeout seconds; raises MediaLockError on timeout.
    """
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    mode = os.O_RDWR | os.O_CREAT
    f = os.open(LOCK_FILE, mode, 0o644)
    try:
        flags = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        deadline = time.monotonic() + wait_timeout
        while True:
            try:
                fcntl.flock(f, flags | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise MediaLockError(
                        f"media lock busy (exclusive={exclusive}): another "
                        f"video/image task is running — waited {wait_timeout}s"
                    ) from None
                time.sleep(2)
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        os.close(f)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Test the media lock")
    ap.add_argument("--exclusive", action="store_true", help="Take exclusive lock")
    ap.add_argument("--hold", type=float, default=5.0, help="Hold time (s)")
    args = ap.parse_args()
    with media_lock(exclusive=args.exclusive, wait_timeout=10):
        print(f"held exclusive={args.exclusive} for {args.hold}s")
        time.sleep(args.hold)
    print("released")
