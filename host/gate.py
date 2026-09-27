# The door JEV scores. The rest of the cabinet stays browsable.
from __future__ import annotations

from pathlib import Path
import re

MARKER = "【技能柜】"
SKILL_TEXT_LIMIT = 8000
PREFACE_TEXT_LIMIT = 24000

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
    {"id": "code-build", "label": "编程", "blurb": "通过测试驱动实现程序、脚本或爬虫。", "ask": "是否要编写代码或开发程序？", "skills": ("test-driven-development",), "category": "code"},
    {"id": "backend-build", "label": "后端开发", "blurb": "实现后端服务和 API 接口。", "ask": "是否要开发后端或 API？", "skills": ("fullstack-dev",), "category": "code"},
    {"id": "frontend-build", "label": "前端开发", "blurb": "实现网页和前端界面。", "ask": "是否要开发前端页面？", "skills": ("frontend-dev",), "category": "web"},
    {"id": "android-build", "label": "Android 开发", "blurb": "实现 Android 应用。", "ask": "是否要开发 Android 应用？", "skills": ("android-native-dev",), "category": "code"},
    {"id": "ios-build", "label": "iOS 开发", "blurb": "实现 iOS 应用。", "ask": "是否要开发 iOS 应用？", "skills": ("ios-application-dev",), "category": "code"},
    {"id": "flutter-build", "label": "Flutter 开发", "blurb": "实现 Flutter 应用。", "ask": "是否要开发 Flutter 应用？", "skills": ("flutter-dev",), "category": "code"},
    {"id": "react-native-build", "label": "React Native 开发", "blurb": "实现 React Native 应用。", "ask": "是否要开发 React Native 应用？", "skills": ("react-native-dev",), "category": "code"},
    {"id": "code-debug", "label": "调试", "blurb": "定位并修复程序错误。", "ask": "是否要调试或修复程序错误？", "skills": ("systematic-debugging",), "category": "code"},
    {"id": "code-refactor", "label": "代码重构", "blurb": "重构代码并保持原有行为。", "ask": "是否要重构代码？", "skills": ("code-refactoring",), "category": "code"},
)

YES_LINE = 0.4
NEGATION = ("不要", "别", "不用", "勿", "不是", "不需要")
_NEGATION_FALSE = ("特别", "分别", "别的", "别人", "别处", "别家", "别管", "别名")
_ASK = (
    "什么意思",
    "是什么意思",
    "区别",
    "不同",
    "差异",
    "对比",
    "解释",
    "为什么叫",
    "变量",
    "是什么",
    "是什么东西",
    "怎么用",
    "怎么办",
    "哪个好",
    "哪个好用",
    "能不能",
    "可以吗",
    "如何",
    "为什么",
    "什么是",
    "干嘛的",
    "干什么用",
    "有什么用",
    "怎么",
)
_MAKE = (
    "制作",
    "做一份",
    "做一页",
    "做成",
    "做一个",
    "做张",
    "做一张",
    "改成",
    "写成",
    "整理成",
    "整理一下",
    "导出",
    "生成",
    "给我一份",
)
_TURN = ("还是", "改成", "换成", "改为")
# A door counts only when the sentence itself names that job.
WORDS = {
    "market-data": ("股价", "涨跌", "行情", "多少钱", "现价", "股票", "涨了多少"),
    "market-watch": ("盯盘", "盯着", "自选股"),
    "meeting-minutes": ("纪要", "会议"),
    "office-docx": ("Word", "word", "docx"),
    "office-pdf": ("PDF", "pdf"),
    "office-pptx": ("幻灯片", "ppt", "PPT", "pptx", "演示文稿"),
    "office-xlsx": ("表格", "Excel", "excel", "xlsx", "这张表"),
    "web-read": ("网页", "网址", "链接", "http", "https"),
    "web-act": ("点击", "填写", "填表", "提交", "登录", "表单"),
    "vox-video": ("介绍视频", "介绍片", "vox", "视频", "视频制作"),
    "openmontage": ("实拍", "剪辑"),
    "xiaohei": ("小黑",),
    "thesis": ("论文",),
    "company-intel": ("公司情报", "这家公司"),
    "knowledge": ("资料库", "知识库"),
    "last30days": ("三十天", "30天", "最近一个月"),
    "godot": ("Godot", "godot"),
    "git-backup": ("备份", "推到远程", "远程仓库"),
    "code-build": ("代码", "爬虫", "脚本", "程序", "编程", "Python", "JavaScript", "TypeScript", "算法"),
    "backend-build": ("API", "后端", "全栈"),
    "frontend-build": ("前端", "开发网页", "做一个网页", "做个网页", "开发网站", "做一个网站", "做个网站", "React", "Vue", "HTML", "CSS"),
    "android-build": ("Android", "安卓"),
    "ios-build": ("iOS",),
    "flutter-build": ("Flutter",),
    "react-native-build": ("React Native", "react-native"),
    "code-debug": ("代码的错误", "修复代码", "调试", "debug", "bug", "报错"),
    "code-refactor": ("重构", "refactor"),
}

_DEVELOPMENT_GATES = {
    "code-build", "backend-build", "frontend-build", "android-build",
    "ios-build", "flutter-build", "react-native-build", "code-debug", "code-refactor",
}
_ACTION = re.compile(r"编写|开发|实现|修复|修一下|排查|调试|重构|优化|制作|生成|搭建|写|做|改|build|implement|create|fix|debug|refactor", re.I)


def _operation_request(clause: str) -> bool:
    return bool(_ACTION.search(clause))


def _resolve(skills: list, name: str, category: str | None) -> dict | None:
    matches = []
    for item in skills:
        if item.get("name") != name:
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


def named_skill_gates(catalog: dict, task: str, gates: list[dict]) -> list[dict]:
    """Let installed skills be explicitly addressed without a hardcoded door.

    Only names are aliases here; descriptions are not executable routing rules.
    Existing doors gain the full skill name, so they aren't selected twice.
    """
    covered = set()
    for gate in gates:
        names = [item['name'] for item in gate['items'] if item.get('kind', 'skill') == 'skill']
        covered.update(names)
        gate['words'] = tuple(dict.fromkeys((*_terms(gate), *names)))
    extra = []
    for item in catalog.get('skills') or []:
        name = str(item.get('name') or '')
        if not name or name in covered or _named(task, name) < 0:
            continue
        resolved = _resolve(catalog['skills'], name, None)
        if resolved is None:
            continue
        covered.add(name)
        extra.append({'id': 'skill:' + name, 'label': name,
                      'blurb': str(item.get('summary') or name),
                      'ask': '是否明确要求使用 ' + name + '？',
                      'words': (name,), 'items': [resolved]})
    return extra


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


def _cjk(ch: str) -> bool:
    return bool(ch) and "\u4e00" <= ch <= "\u9fff"


def _named(task: str, word: str) -> int:
    text = task or ""
    if not word.isascii():
        return text.find(word)
    hay = text.lower()
    needle = word.lower()
    index = 0
    while True:
        pos = hay.find(needle, index)
        if pos < 0:
            return -1
        before = hay[pos - 1] if pos else ""
        after = hay[pos + len(needle)] if pos + len(needle) < len(hay) else ""
        if before.isalnum() and not _cjk(text[pos - 1] if pos else ""):
            index = pos + 1
            continue
        if after.isalnum() and not _cjk(text[pos + len(word)] if pos + len(word) < len(text) else ""):
            index = pos + 1
            continue
        return pos


def _false_negation(text: str, index: int) -> bool:
    for phrase in _NEGATION_FALSE:
        start = text.find(phrase)
        while start >= 0:
            if start <= index < start + len(phrase):
                return True
            start = text.find(phrase, start + 1)
    return False


def _other_named(between: str, skip_at: int) -> bool:
    del skip_at
    blob = between or ""
    if not blob.strip():
        return False
    for words in WORDS.values():
        for word in words:
            if word and word in blob:
                return True
    return False


def _clause_span(text: str, index: int) -> tuple[int, int]:
    start = 0
    end = len(text)
    for mark in ("，", ",", "。", "；", ";", "！", "!", "？", "?", "、"):
        left = text.rfind(mark, 0, index)
        if left >= start:
            start = left + 1
        right = text.find(mark, index)
        if right >= 0 and right < end:
            end = right
    return start, end


def _hits(task: str, gate: dict) -> list[tuple[int, int]]:
    found = []
    text = task or ""
    for word in _terms(gate):
        start = 0
        while True:
            piece = text[start:]
            relative = _named(piece, word)
            if relative < 0:
                break
            index = start + relative
            found.append((index, len(word)))
            start = index + max(len(word), 1)
    found.sort()
    uniq = []
    seen = set()
    for index, length in found:
        if (index, length) in seen:
            continue
        seen.add((index, length))
        uniq.append((index, length))
    return uniq


def _item_negated(text: str, index: int, length: int) -> bool:
    if _false_negation(text, index):
        return False
    left = text[max(0, index - 6) : index]
    cut = max(left.rfind(ch) for ch in "，,。；;！!？?")
    if cut >= 0:
        left = left[cut + 1 :]
    if "只要" in left or "就用" in left or "还是用" in left:
        return False
    right = text[index + length : min(len(text), index + length + 4)]
    rcut = min((i for i, ch in enumerate(right) if ch in "，,。；;！!？?"), default=-1)
    if rcut >= 0:
        right = right[:rcut]
    for flag in NEGATION:
        if flag in left and not _false_negation(text, max(0, index - 6)):
            between = left[left.rfind(flag) + len(flag) :]
            if "只要" in between:
                continue
            if between.strip() and _other_named(between, skip_at=index):
                continue
            return True
        if flag in right and not _false_negation(text, index + length):
            return True
    return False


def _later_reclaim(text: str, gate: dict, index: int) -> bool:
    for later, length in _hits(text, gate):
        if later <= index:
            continue
        before = text[max(0, later - 8) : later]
        if any(mark in before for mark in _TURN) and not _item_negated(text, later, length):
            return True
    return False


def _item_asking(text: str, index: int, length: int) -> bool:
    start, end = _clause_span(text, index)
    clause = text[start:end]
    local = text[max(0, index - 8) : min(len(text), index + length + 8)]
    word = text[index : index + length]
    # Polite requests are actions, while "怎么写" and "是什么" remain questions.
    questions = [mark for mark in _ASK if mark in clause]
    if questions and all(mark in {"能不能", "可以吗"} for mark in questions) and _operation_request(clause):
        return False
    # A capability name may itself contain 制作; that is not an action verb
    # when the user is asking what it means.
    if any(mark in clause for mark in ("是什么意思", "什么意思", "是什么", "什么是", "有什么用", "干嘛的")):
        outside_name = text[start:index] + text[index + length:end]
        if not any(mark in outside_name for mark in _MAKE):
            return True
    contrast = any(mark in clause for mark in ("区别", "不同", "差异", "对比")) or any(
        mark in local for mark in ("区别", "不同", "差异", "对比")
    )
    export = any(mark in local for mark in ("导出", "写成", "改成", "只要"))
    if contrast and not export and word.lower() in {"word", "pdf", "docx", "ppt", "pptx"}:
        return True
    if word.lower() in {"表格", "excel", "xlsx"}:
        before = text[max(0, index - 10) : index]
        if any(mark in before for mark in _MAKE):
            return False
    if any(mark in local for mark in _MAKE) and not contrast:
        return False
    if any(mark in clause for mark in _MAKE) and not any(mark in clause for mark in _ASK):
        return False
    return any(mark in clause for mark in _ASK) or any(mark in local for mark in _ASK)


def sentence_names(task: str, gate: dict) -> bool:
    """True when the sentence names this job and the last mention still wants it."""
    text = task or ""
    explicit = any(_named(text, str(item.get("name") or "")) >= 0
                   for item in gate.get("items", []) if item.get("name"))
    if not explicit and gate['id'] in _DEVELOPMENT_GATES:
        # Mentioning a platform in conversation isn't a development request.
        active = False
        for index, _length in _hits(text, gate):
            start, end = _clause_span(text, index)
            if _operation_request(text[start:end]):
                active = True
        if not active:
            return False
        if gate['id'] == 'code-build':
            # Debugging/refactoring and frontend code have their own workflow.
            if not any(mark in text for mark in ('爬虫', '脚本')) and any(
                sentence_names(text, {'id': other, 'words': WORDS[other]})
                for other in ('code-debug', 'code-refactor', 'frontend-build')
            ):
                return False
    if not explicit and gate['id'] == 'vox-video' and _named(text, 'vox') < 0 and not any(
        word in text for word in ('介绍视频', '介绍片')
    ):
        if not _operation_request(text):
            return False
        if any(word in text for word in WORDS['openmontage']):
            return False
    if not explicit and gate['id'] == 'frontend-build' and 'React Native' in text:
        # React Native is a mobile framework, not the React web workflow.
        if not any(word in text for word in ('前端', '网页', '网站', 'HTML', 'CSS', 'Vue')):
            return False
    hits = _hits(text, gate)
    if not hits:
        return False
    last_index, last_length = hits[-1]
    if _item_negated(text, last_index, last_length) and not _later_reclaim(text, gate, last_index):
        return False
    if _item_asking(text, last_index, last_length):
        return False
    kept = False
    for index, length in hits:
        if _item_asking(text, index, length):
            continue
        if _item_negated(text, index, length):
            if _later_reclaim(text, gate, index):
                kept = True
            continue
        kept = True
    return kept


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
    chosen = []
    reasons = []
    for vote, _index, gate in ranked:
        named = sentence_names(task, gate)
        if named and vote >= YES_LINE:
            why = "点了名，分数 " + str(round(vote, 2))
            kept = True
        elif named:
            why = "点了名，分数 " + str(round(vote, 2)) + " 没过 0.4"
            kept = False
        else:
            why = "没点名" if vote < YES_LINE else "没点名，虽然分数 " + str(round(vote, 2))
            kept = False
        if kept:
            chosen.append(gate)
            reasons.append({"id": gate["id"], "label": gate["label"], "kept": True, "probability": round(vote, 4), "reason": why})
        else:
            reasons.append({"id": gate["id"], "label": gate["label"], "kept": False, "probability": round(vote, 4), "reason": why})
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
        "reasons": reasons,
    }


def format_preface(routed: dict, texts: dict[str, str]) -> str:
    if not routed.get("enabled", True):
        return ""
    if routed.get("method") != "skill":
        return MARKER + "JEV 已选定：自己做。不要读取技能，不要再挑选。"
    chosen = routed.get("skills") or []
    kinds = {str(item.get("kind") or "skill") for item in chosen}
    names = [str(skill.get("name") or "") for skill in chosen if skill.get("name")]
    lead = MARKER + "已选定：" + "、".join(names) + "。读完照做，不要再挑选。"
    if kinds == {"plugin"}:
        lead = MARKER + "已选定插件：" + "、".join(names) + "。按插件做，不要再挑选。"
    elif "plugin" in kinds:
        lead = MARKER + "已选定技能和插件：" + "、".join(names) + "。读完照做，不要再挑选。"
    chunks = [lead]
    if routed.get("clipped"):
        chunks.append("原句超过 2000 字，后面没参与选择。")
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
            body = body[:SKILL_TEXT_LIMIT] + "\n…（后面已截断，用 get_skill 按 offset 续读。）"
        title = "插件 " + name if skill.get("kind") == "plugin" else name
        chunks.append("## " + title + "\n" + body)
    joined = "\n\n".join(chunks)
    if len(joined) <= PREFACE_TEXT_LIMIT:
        return joined
    return joined[:PREFACE_TEXT_LIMIT] + "\n…（前言已截断，用 get_skill 续读选定技能。）"
