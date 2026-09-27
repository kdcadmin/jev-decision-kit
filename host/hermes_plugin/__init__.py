from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host.preface_client import message_text, preface_for


def pre_llm_call(user_message="", **_kwargs):
    text = message_text(user_message)
    if not text or "【技能柜】" in text:
        return None
    preface = preface_for(text, "hermes")
    if not preface:
        return None
    return {"context": preface}


def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", pre_llm_call)
