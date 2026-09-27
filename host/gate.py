# The door JEV scores. The rest of the cabinet stays browsable.
from __future__ import annotations

from pathlib import Path

MARKER = "【技能柜】"
SKILL_TEXT_LIMIT = 8000

GATE = (
    {
        "id": "market-data",
        "label": "行情",
        "blurb": "用本机行情接口查股价、板块或资金。",
        "ask": "这句话里是不是要查股价、涨跌或行情？",
        "skills": ("china-stock-data",),
        "category": "market",
    },
    {
        "id": "market-watch",
        "label": "盯盘",
        "blurb": "用本机盯盘看已经设好的标的。",
        "ask": "这句话里是不是要看已经设好的盯盘？",
        "skills": ("stock-watch",),
        "category": "market",
    },
    {
        "id": "meeting-minutes",
        "label": "会议纪要",
        "blurb": "把会议内容写成一份纪要文件。",
        "ask": "这句话里是不是要把会议写成纪要？",
        "skills": ("meeting-minutes",),
        "category": "docs",
    },
    {
        "id": "office-docx",
        "label": "Word",
        "blurb": "按本机方式读写 Word 文档。",
        "ask": "这句话里是不是要一份 Word 文档？",
        "skills": ("docx",),
        "category": "docs",
    },
    {
        "id": "office-pdf",
        "label": "PDF",
        "blurb": "按本机方式读写 PDF。",
        "ask": "这句话里是不是要一份 PDF？",
        "skills": ("pdf",),
        "category": "docs",
    },
    {
        "id": "office-pptx",
        "label": "幻灯片",
        "blurb": "按本机方式做幻灯片文件。",
        "ask": "这句话里是不是要一份幻灯片？",
        "skills": ("pptx",),
        "category": "docs",
    },
    {
        "id": "office-xlsx",
        "label": "表格",
        "blurb": "按本机方式读写表格。",
        "ask": "这句话里是不是要一份表格？",
        "skills": ("xlsx",),
        "category": "docs",
    },
    {
        "id": "web-read",
        "label": "读网页",
        "blurb": "用本机浏览器打开网页并读取内容。",
        "ask": "Does the user give a URL and ask to read that page?",
        "skills": ("web-access",),
        "category": "web",
    },
    {
        "id": "web-act",
        "label": "操作网页",
        "blurb": "用本机浏览器在网页上点击、填写、按步骤操作。",
        "ask": "Does the user ask to click buttons, fill a form, or submit on a web page?",
        "skills": ("agent-browser",),
        "category": "web",
    },
    {
        "id": "vox-video",
        "label": "介绍视频",
        "blurb": "用固定的大肥鱼纸片人，按给定剧情做一支介绍视频。",
        "ask": "这句话里是不是要一支介绍视频或介绍片？",
        "skills": ("vox-style-intro-video",),
        "category": "media",
    },
    {
        "id": "openmontage",
        "label": "实拍剪辑",
        "blurb": "把实拍素材剪成一支视频。",
        "ask": "这句话里是不是要把实拍素材剪成视频？",
        "skills": ("openmontage",),
        "category": "media",
    },
    {
        "id": "xiaohei",
        "label": "小黑插图",
        "blurb": "按小黑怪诞风格画文章插图。",
        "ask": "这句话里是不是要一张小黑风格的配图？",
        "skills": ("xiaohei-illustration",),
        "category": "media",
    },
    {
        "id": "thesis",
        "label": "论文",
        "blurb": "按本机论文工作台的步骤写论文。",
        "ask": "这句话里是不是要按论文工作台写一章？",
        "skills": ("chinese-thesis-workbench",),
        "category": "thesis",
    },
    {
        "id": "company-intel",
        "label": "公司情报",
        "blurb": "按本机流程查公司或人物资料。",
        "ask": "这句话里是不是要一份公司情报？",
        "skills": ("company-intelligence-research",),
        "category": "research",
    },
    {
        "id": "knowledge",
        "label": "资料库",
        "blurb": "把资料收进本机资料库。",
        "ask": "这句话里是不是要把资料收进知识库？",
        "skills": ("knowledge-pipeline",),
        "category": "research",
    },
    {
        "id": "last30days",
        "label": "近三十天",
        "blurb": "检索最近三十天的外部资料。",
        "ask": "这句话里是不是要最近三十天的研究汇总？",
        "skills": ("last30days",),
        "category": "research",
    },
    {
        "id": "godot",
        "label": "Godot",
        "blurb": "在本机 Godot 里改游戏并跑起来。",
        "ask": "这句话里是不是要改 Godot 游戏？",
        "skills": ("godot-gamedev", "godot-ai-mcp"),
        "category": "code",
    },
    {
        "id": "git-backup",
        "label": "远程备份",
        "blurb": "把当前项目推到已经配置的远程仓库。",
        "ask": "这句话里是不是要把仓库备份到远程？",
        "skills": ("git-remote-backup",),
        "category": "code",
    },
)

YES_LINE = 0.4
NEGATION = ("不要", "别", "不用", "勿")
# A door counts only when the sentence itself names that job.
WORDS = {
    "market-data": ("股价", "涨跌", "行情", "多少钱", "现价", "股票"),
    "market-watch": ("盯盘",),
    "meeting-minutes": ("纪要", "会议"),
    "office-docx": ("Word", "word", "docx"),
    "office-pdf": ("PDF", "pdf"),
    "office-pptx": ("幻灯片", "ppt", "PPT"),
    "office-xlsx": ("表格", "Excel", "excel", "xlsx"),
    "web-read": ("网页", "网址", "链接", "http", "https"),
    "web-act": ("点击", "填写", "填表", "提交", "登录"),
    "vox-video": ("介绍视频", "介绍片"),
    "openmontage": ("实拍", "剪辑"),
    "xiaohei": ("小黑",),
    "thesis": ("论文",),
    "company-intel": ("公司情报", "这家公司"),
    "knowledge": ("资料库", "知识库"),
    "last30days": ("三十天", "30天"),
    "godot": ("Godot", "godot"),
    "git-backup": ("备份", "推到远程", "远程仓库"),
}


def _resolve(skills: list, name: str, category: str | None) -> dict | None:
    matches = []
    for item in skills:
        if item.get("name") != name:
            continue
        if category and item.get("category") != category:
            continue
        path = Path(item.get("path") or "")
        if (path / "SKILL.md").is_file():
            matches.append(item)
    if not matches:
        return None
    matches.sort(key=lambda item: str(item.get("path") or "").count("\\") + str(item.get("path") or "").count("/"))
    return matches[0]


def available_gates(catalog: dict) -> list[dict]:
    skills = catalog.get("skills") or []
    ready = []
    for entry in GATE:
        items = []
        for name in entry["skills"]:
            item = _resolve(skills, name, entry.get("category"))
            if item is not None:
                items.append(item)
        if not items:
            continue
        ready.append(
            {
                "id": entry["id"],
                "label": entry["label"],
                "blurb": entry["blurb"],
                "ask": entry["ask"],
                "items": items,
            }
        )
    return ready


def noul_questions(gates: list[dict]) -> dict:
    questions = {}
    for gate in gates:
        questions[gate["id"]] = {
            "type": "noul",
            "instructions": gate["ask"],
        }
    return questions


def gate_labels(gates: list[dict]) -> dict:
    labels = {"think": "自主思考"}
    for gate in gates:
        labels[gate["id"]] = gate["label"]
    return labels


def _vote(probabilities: dict, gate_id: str) -> float:
    try:
        return float(probabilities.get(gate_id) or 0)
    except (TypeError, ValueError):
        return 0.0


def _terms(gate: dict) -> tuple:
    return tuple(gate.get("words") or WORDS.get(gate["id"], ()))


def _named(task: str, word: str) -> int:
    if word.isascii():
        return task.lower().find(word.lower())
    return task.find(word)


def sentence_names(task: str, gate: dict) -> bool:
    """True when the sentence names this job and does not tell us to skip it."""
    text = task or ""
    found = False
    for word in _terms(gate):
        index = _named(text, word)
        if index < 0:
            continue
        window = text[max(0, index - 8) : index]
        if any(flag in window for flag in NEGATION):
            return False
        found = True
    return found


def decision_from_votes(
    probabilities: dict,
    gates: list[dict],
    rule: dict | None,
    by_name: dict,
    task: str = "",
    remembered: set[str] | None = None,
) -> dict:
    rule = rule or {}
    removed = {str(name) for name in (rule.get("remove") or [])}
    added = [str(name) for name in (rule.get("add") or []) if str(name) not in removed]
    ranked = [(_vote(probabilities, gate["id"]), index, gate) for index, gate in enumerate(gates)]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    remembered = remembered or set()
    chosen = [
        gate
        for vote, _index, gate in ranked
        if vote >= YES_LINE and (sentence_names(task, gate) or gate["id"] in remembered)
    ]
    chosen_ids = {gate["id"] for gate in chosen}
    ordered = []
    seen = set()
    for gate in chosen:
        prob = round(_vote(probabilities, gate["id"]), 4)
        for item in gate["items"]:
            name = item.get("name") or ""
            if not name or name in removed or name in seen:
                continue
            seen.add(name)
            ordered.append(
                {
                    "name": name,
                    "summary": gate["blurb"],
                    "path": item.get("path") or "",
                    "probability": prob,
                    "kind": item.get("kind") or "skill",
                    "host": item.get("host") or "",
                }
            )
    for name in added:
        if name in seen or name not in by_name:
            continue
        item = by_name[name]
        seen.add(name)
        ordered.append(
            {
                "name": name,
                "summary": ((item.get("summary") or "")[:160]),
                "path": item.get("path") or "",
                "probability": None,
            }
        )
    method = "skill" if ordered else "think"
    passed = []
    for vote, _index, gate in ranked:
        if gate["id"] in chosen_ids:
            continue
        passed.append({"name": gate["label"], "probability": round(vote, 4)})
        if len(passed) >= 4:
            break
    if method != "skill" or not chosen:
        label = "技能" if method == "skill" else "自主思考"
        gate_id = ""
    elif len(chosen) == 1:
        label = chosen[0]["label"]
        gate_id = chosen[0]["id"]
    else:
        label = "、".join(gate["label"] for gate in chosen)
        gate_id = chosen[0]["id"]
    return {
        "method": method,
        "gate": gate_id,
        "label": label,
        "skills": ordered,
        "passed": passed,
    }


def format_preface(routed: dict, texts: dict[str, str]) -> str:
    if not routed.get("enabled", True):
        return ""
    if routed.get("method") != "skill":
        return MARKER + "JEV 已选定：自己做。不要读取技能，不要再挑选。"
    chosen = routed.get("skills") or []
    kinds = {str(item.get("kind") or "skill") for item in chosen}
    if kinds == {"plugin"}:
        lead = "JEV 已选定下面这些插件。按插件做，不要再挑选。"
    elif "plugin" in kinds:
        lead = "JEV 已选定下面这些技能和插件。读完照做，不要再挑选，也不要改用别的技能。"
    else:
        lead = "JEV 已选定下面这些技能。读完照做，不要再挑选，也不要改用别的技能。"
    chunks = [MARKER + lead]
    remembered = (routed.get("remembered") or {}).get("task")
    if remembered:
        chunks.append("沿用了你对「" + str(remembered) + "」的调整。")
    for skill in chosen:
        name = str(skill.get("name") or "")
        body = (texts.get(name) or "").strip()
        if not body and skill.get("kind") == "plugin":
            host = str(skill.get("host") or "").strip()
            where = host + " 上的" if host else ""
            body = "使用" + where + "插件 " + name + "。" + str(skill.get("summary") or "")
        if len(body) > SKILL_TEXT_LIMIT:
            body = body[:SKILL_TEXT_LIMIT] + "\n…（后面已截断）"
        title = "插件 " + name if skill.get("kind") == "plugin" else name
        chunks.append("## " + title + "\n" + body)
    return "\n\n".join(chunks)
