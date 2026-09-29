"""Hermes shell-hook wire adapter for GUI/TUI surfaces."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host import hermes_plugin


def handle(payload: dict) -> dict | None:
    event = payload.get("hook_event_name")
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    if event == "pre_llm_call":
        # Only the GUI/TUI session family needs this bridge. Other surfaces use the plugin.
        if str(extra.get("platform") or "").lower() not in {"desktop", "tui"}:
            return None
        return hermes_plugin.pre_llm_call(user_message=extra.get("user_message") or "")
    if event == "pre_tool_call":
        return hermes_plugin.pre_tool_call(tool_name=payload.get("tool_name"), args=payload.get("tool_input"))
    if event == "subagent_start":
        hermes_plugin.subagent_start(**extra)
    elif event == "subagent_stop":
        hermes_plugin.subagent_stop(**extra)
    return None


if __name__ == "__main__":
    result = handle(json.load(sys.stdin))
    if result is not None:
        print(json.dumps(result, ensure_ascii=False))
