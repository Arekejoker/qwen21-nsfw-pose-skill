#!/usr/bin/env python3
"""Optional Wan 2.7 image generation through Monid; prints provider output JSON.

Usage: MONID_API_KEY=... python3 scripts/monid_image_example.py --prompt "A forest"
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


class MonidProviderError(RuntimeError):
    """Preserve the vendor status and error separately from Monid errors."""

    def __init__(self, status: int, error):
        self.status, self.error = status, error
        super().__init__(f"Alibaba Cloud rejected request ({status}): "
                         f"{json.dumps(error, ensure_ascii=False)}")


def generate_image(prompt: str, *, timeout: float = 300):
    key = os.environ.get("MONID_API_KEY")
    if not key:
        raise RuntimeError("Set MONID_API_KEY to run this optional example.")
    headers = {"Authorization": f"Bearer {key}"}
    payload = {
        "provider": "alibaba",
        "endpoint": "/v1/image/wan2.7-image",
        "input": {"queryParams": {}, "body": {"prompt": prompt}, "pathParams": {}},
    }
    deadline = time.monotonic() + timeout

    def request(url, data=None):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Monid run timed out")
        req = urllib.request.Request(url, data=data, headers=headers)
        if data is not None:
            req.add_header("Content-Type", "application/json; charset=utf-8")
        with urllib.request.urlopen(req, timeout=min(60, remaining)) as resp:
            return resp.status, json.loads(resp.read())

    status, run = request(
        "https://api.monid.ai/v1/run",
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )
    if status == 202:
        run_id = urllib.parse.quote(run["runId"], safe="")
        while run.get("status") not in (
            "COMPLETED", "FAILED", "TIMED_OUT", "STOPPED", "BLOCKED",
        ):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Monid run timed out")
            time.sleep(min(2, remaining))
            _, run = request(f"https://api.monid.ai/v1/runs/{run_id}")
    if run.get("status") not in (None, "COMPLETED"):
        raise RuntimeError(f"Monid run {run.get('status')}")
    provider = run.get("providerResponse") or {}
    if provider.get("httpStatus", 200) >= 400:
        raise MonidProviderError(provider["httpStatus"], provider.get("error"))
    return run["output"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()
    try:
        output = generate_image(args.prompt)
    except urllib.error.HTTPError as exc:
        parser.exit(1, f"Monid HTTP {exc.code}: {exc.read().decode('utf-8')}\n")
    except (RuntimeError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
