"""Tell a new Cursor session that jev-decision is wired for this workspace."""
from __future__ import annotations

import json
import sys

sys.stdout.buffer.write(
    json.dumps(
        {
            "additional_context": (
                "本工作区已接技能柜。你发出的每句原句会在提交前由本机 jev-decision 打分。"
                "若本轮出现以 jev-decision: 开头的文字，那是宿主决定：自己做就不要翻技能；"
                "列出了技能名就用 MCP get_skill 按名字读正文，读完照做，不要再挑选。"
            )
        },
        ensure_ascii=False,
    ).encode("utf-8")
)
sys.stdout.buffer.flush()
