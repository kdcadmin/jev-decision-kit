"""Cursor beforeSubmitPrompt: run jev-decision on the user sentence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host.gate import already_prefaced
from host.preface_client import message_text, preface_for


def main() -> None:
    raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    text = message_text(payload.get("prompt") or "")
    reply = {"continue": True}
    if text and not already_prefaced(text):
        preface = preface_for(text, "cursor")
        if preface:
            runtime = ROOT / "runtime"
            runtime.mkdir(parents=True, exist_ok=True)
            (runtime / "cursor-preface.txt").write_text(preface, encoding="utf-8")
            reply["additional_context"] = preface
    sys.stdout.buffer.write(json.dumps(reply, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
