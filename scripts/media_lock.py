#!/usr/bin/env python3
"""Shared media task lock: video rendering is exclusive, image gen is shared.

Policy (see the deployment's model-switching script/service):
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

POSIX uses fcntl.flock. On native Windows (no fcntl) it falls back to an
atomic O_EXCL lock-file: there is no shared-lock primitive there, so shared
callers also take the file; ComfyUI serialises queued jobs anyway, so this
only adds a wait, never a conflict.
"""
from __future__ import annotations

import contextlib
import os
import tempfile
import time
from pathlib import Path

try:
    import fcntl  # POSIX flock; absent on native Windows
except ImportError:  # pragma: no cover - Windows
    fcntl = None

_DEFAULT_LOCK = os.path.join(tempfile.gettempdir(), "media-task.lock")
LOCK_FILE = Path(os.environ.get("MEDIA_LOCK_FILE", _DEFAULT_LOCK))


class MediaLockError(RuntimeError):
    """Raised when the media lock cannot be acquired in time."""


def _busy_error(exclusive: bool) -> MediaLockError:
    return MediaLockError(
        f"media lock busy (exclusive={exclusive}): another "
        f"video/image task is running"
    )


@contextlib.contextmanager
def media_lock(exclusive: bool, wait_timeout: int = 3600):
    """Acquire the media lock.

    exclusive=True  -> video render (blocks all image gen until finished)
    exclusive=False -> image gen (shared; multiple concurrent images allowed
                       on POSIX; serialised on Windows, see module docstring)

    Blocks up to wait_timeout seconds; raises MediaLockError on timeout.
    """
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_timeout

    if fcntl is None:  # Windows fallback: atomic lock-file creation
        handle = None
        while True:
            try:
                handle = os.open(
                    LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644
                )
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise _busy_error(exclusive) from None
                time.sleep(2)
        try:
            yield
        finally:
            if handle is not None:
                os.close(handle)
                with contextlib.suppress(OSError):
                    os.unlink(LOCK_FILE)
        return

    mode = os.O_RDWR | os.O_CREAT
    f = os.open(LOCK_FILE, mode, 0o644)
    try:
        flags = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        while True:
            try:
                fcntl.flock(f, flags | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise _busy_error(exclusive) from None
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
