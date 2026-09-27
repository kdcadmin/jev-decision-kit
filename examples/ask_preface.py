# Minimal preface client. Copy this file, keep the same header name.
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT_FILE = ROOT / "runtime" / "preface.port"
TOKEN_FILE = ROOT / "runtime" / "preface.token"


def preface(task: str, source: str = "example") -> str:
    port = PORT_FILE.read_text(encoding="utf-8").strip()
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    payload = json.dumps({"task": task, "source": source}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/preface",
        data=payload,
        headers={"Content-Type": "application/json", "X-Kit-Token": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SystemExit("preface refused: " + str(exc.code)) from exc
    return str(body.get("preface") or "")


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "用Word写一份报告"
    print(preface(text))
