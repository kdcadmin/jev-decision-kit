"""Hermes hook: ensure the workspace protocol exists, inject a short hint once."""
from __future__ import annotations

from pathlib import Path

from host.preface_client import message_text
from host.writer_protocol import already_hinted, session_hint


def pre_llm_call(user_message="", **_kwargs):
    text = message_text(user_message)
    if already_hinted(text):
        return None
    hint = session_hint(Path.cwd())
    return {"context": hint}
