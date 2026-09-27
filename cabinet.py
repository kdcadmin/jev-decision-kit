# Shared skill cabinet. Web page and MCP both call this module.
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("USE_TF", "0")

ROOT = Path(__file__).resolve().parent
SKILLS = ROOT / "skills"
CATALOG_PATH = ROOT / "catalog.json"
CONFIG_PATH = ROOT / "config.json"
CALLS_PATH = ROOT / "calls.json"
LAYA_REPO = "https://github.com/NandhaKishorM/laya"
LAYA_WEIGHTS = "https://huggingface.co/convaiinnovations/laya-multilingual"
LAYA_HF_REPO = "convaiinnovations/laya-multilingual"
BUNDLED_MODEL = ROOT / "models" / "laya"

GUESS_RULES = (
    ("router", ("aas", "skill-router", "skill-creator", "find-skills", "using-agent")),
    ("prompts", ("prompt",)),
    ("thesis", ("thesis", "lunwen", "literature", "humanizer", "peer-review")),
    ("market", ("stock", "ticker", "market-watch")),
    ("docs", ("meeting", "minutes", "docx", "pdf", "pptx", "xlsx", "word-doc")),
    ("web", ("browser", "web-", "frontend", "html", "figma", "landing")),
    ("media", ("video", "montage", "remotion", "music", "gif", "illustration", "audio", "song")),
    ("design", ("design", "canvas", "diagram", "poster")),
    ("research", ("research", "intelligence", "knowledge", "arxiv")),
    ("planning", ("plan", "okr", "brainstorm")),
    ("product", ("prd", "product", "pricing", "gtm", "persona", "monetiz", "swot", "roadmap")),
    ("code", ("code", "debug", "test", "git", "api", "mcp", "dev", "review", "tdd", "react", "python")),
)

LABELS = {
    "code": "代码",
    "web": "网页",
    "prompts": "提示词",
    "thesis": "论文",
    "research": "调研",
    "design": "设计",
    "docs": "文档",
    "market": "行情",
    "media": "媒体",
    "planning": "规划",
    "product": "产品",
    "router": "路由",
    "other": "其他",
}

CRITERIA = {
    "code": "写代码、改 bug、审查、测试、重构、脚本",
    "web": "网页、浏览器、抓取页面、前端界面",
    "prompts": "提示词、系统提示、写作指令",
    "thesis": "论文、学位论文、文献格式",
    "research": "调研、检索资料、公司或文献情报",
    "design": "视觉设计、配色、界面稿、海报",
    "docs": "文档、会议纪要、说明、幻灯片文稿",
    "market": "股票、行情、交易、金融数据",
    "media": "图片、视频、音频、动画、剪辑",
    "planning": "规划、任务拆解、执行计划、日程",
    "product": "产品、商业、增长、运营、定价",
    "router": "决定下一步该用哪类技能",
    "other": "上面都不合适",
}

lock = threading.Lock()
_model_lock = threading.Lock()
agent = None


def load_catalog() -> dict:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("skills"), list):
        raise ValueError("catalog.json is missing a skills list")
    return data


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def save_catalog(data: dict) -> None:
    _atomic_write(CATALOG_PATH, json.dumps(data, ensure_ascii=False, indent=2))


def safe_name(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}", name):
        raise ValueError("bad skill name")
    return name


def known_categories(data: dict) -> list[str]:
    found = {item.get("category") for item in data["skills"] if item.get("category")}
    ordered = [key for key in LABELS if key in found or (SKILLS / key).is_dir()]
    extra = sorted(found - set(ordered))
    return ordered + extra


def skill_dir(item: dict) -> Path:
    path = Path(item["path"]).resolve()
    root = SKILLS.resolve()
    if path != root and root not in path.parents:
        raise ValueError("skill path is outside the kit")
    if not path.is_dir():
        raise FileNotFoundError(str(path))
    return path


def find_skill(data: dict, name: str) -> dict:
    for item in data["skills"]:
        if item.get("name") == name:
            return item
    raise KeyError(name)


def frontmatter_description(text: str) -> str:
    match = re.match(r"^---\s*\r?\n(.*?)\r?\n---", text, re.S)
    if not match:
        return ""
    block = match.group(1)
    lines = block.splitlines()
    for index, line in enumerate(lines):
        found = re.match(r"^description:\s*(.*)$", line)
        if not found:
            continue
        rest = found.group(1).strip()
        if rest in {">", "|", ">-", "|-"}:
            chunks = []
            for follow in lines[index + 1 :]:
                if follow.startswith("  ") or follow.startswith("\t"):
                    chunks.append(follow.strip())
                elif follow.strip() == "":
                    continue
                else:
                    break
            return " ".join(chunks)[:240]
        return rest.strip("\"'")[:240]
    return ""


def list_scripts(directory: Path) -> list[str]:
    scripts = directory / "scripts"
    if not scripts.is_dir():
        return []
    found = []
    for path in scripts.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".py", ".ps1", ".sh", ".js", ".mjs", ".bat", ".cmd"}:
            found.append(str(path.relative_to(directory)).replace("\\", "/"))
    return sorted(found)


def read_skill_text(directory: Path) -> str:
    path = directory / "SKILL.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def body_excerpt(text: str, limit: int = 400) -> str:
    body = re.sub(r"^---\s*\r?\n.*?\r?\n---\s*", "", text, count=1, flags=re.S)
    body = re.sub(r"[#>*_`]+", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return body[:limit]


def skill_changed(item: dict) -> bool:
    stored = item.get("origin")
    if not stored:
        return False
    origin = Path(stored) / "SKILL.md"
    try:
        kit = skill_dir(item) / "SKILL.md"
    except (OSError, ValueError, FileNotFoundError, KeyError):
        return False
    if not origin.is_file() or not kit.is_file():
        return False
    try:
        return hashlib.sha256(origin.read_bytes()).digest() != hashlib.sha256(kit.read_bytes()).digest()
    except OSError:
        return False


def public_skill(item: dict) -> dict:
    scripts = item.get("scripts") or []
    if isinstance(scripts, dict):
        scripts = []
    return {
        "name": item.get("name"),
        "category": item.get("category"),
        "source": item.get("source"),
        "summary": item.get("summary") or "",
        "scripts": scripts,
        "path": item.get("path") or "",
    }


def catalog_view() -> dict:
    with lock:
        data = load_catalog()
        filled = False
        for item in data["skills"]:
            if (item.get("summary") or "").strip():
                continue
            try:
                excerpt = body_excerpt(read_skill_text(skill_dir(item)), 160)
            except (OSError, ValueError, FileNotFoundError, KeyError):
                excerpt = ""
            if excerpt:
                item["summary"] = excerpt
                filled = True
        if filled:
            save_catalog(data)
    categories = []
    for key in known_categories(data):
        count = sum(1 for item in data["skills"] if item.get("category") == key)
        categories.append({"id": key, "label": LABELS.get(key, key), "count": count})
    skills = []
    for item in data["skills"]:
        public = public_skill(item)
        try:
            public["excerpt"] = body_excerpt(read_skill_text(skill_dir(item)))
        except (OSError, ValueError, FileNotFoundError, KeyError):
            public["excerpt"] = ""
        public["changed"] = skill_changed(item)
        public["origin"] = item.get("origin") or ""
        skills.append(public)
    skills.sort(key=lambda item: item["name"] or "")
    return {"categories": categories, "skills": skills, "total": len(skills)}


def read_skill(name: str) -> dict:
    name = safe_name(name)
    with lock:
        data = load_catalog()
        item = find_skill(data, name)
        directory = skill_dir(item)
    skill_file = directory / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8") if skill_file.is_file() else ""
    payload = public_skill(item)
    payload["content"] = content
    payload["scripts"] = list_scripts(directory)
    payload["path"] = str(directory)
    payload["excerpt"] = body_excerpt(content)
    payload["changed"] = skill_changed(item)
    return payload


def move_skill(name: str, category: str) -> dict:
    name = safe_name(name)
    if category not in LABELS and not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", category):
        raise ValueError("bad category")
    with lock:
        data = load_catalog()
        item = find_skill(data, name)
        source = skill_dir(item)
        if item.get("category") == category and source.parent.name == category:
            return {"ok": True, "category": category, "path": str(source)}
        dest = (SKILLS / category / name).resolve()
        if SKILLS.resolve() not in dest.parents:
            raise ValueError("destination escaped the kit")
        if dest.exists():
            raise FileExistsError("destination already exists")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))
        item["category"] = category
        item["path"] = str(dest)
        item["scripts"] = list_scripts(dest)
        save_catalog(data)
    return {"ok": True, "category": category, "path": str(dest)}


def save_skill(name: str, content: str) -> dict:
    name = safe_name(name)
    if not isinstance(content, str):
        raise ValueError("content must be text")
    if len(content) > 1_000_000:
        raise ValueError("content too large")
    with lock:
        data = load_catalog()
        item = find_skill(data, name)
        directory = skill_dir(item)
        (directory / "SKILL.md").write_bytes(content.encode("utf-8"))
        summary = frontmatter_description(content)
        if summary:
            item["summary"] = summary
        save_catalog(data)
    return {"ok": True, "summary": item.get("summary") or ""}


def default_config() -> dict:
    from host.board import empty_board

    return {
        "selectorEnabled": True,
        "layaModelDir": "",
        "extraScanRoots": [],
        "board": empty_board(),
    }


def load_config() -> dict:
    data = default_config()
    if CONFIG_PATH.is_file():
        stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        if isinstance(stored, dict):
            data.update({key: stored[key] for key in data if key in stored and key != "board"})
            if isinstance(stored.get("board"), dict):
                data["board"] = stored["board"]
    if not str(data.get("layaModelDir") or "").strip():
        data["layaModelDir"] = str(BUNDLED_MODEL)
    return data


def save_config(updates: dict) -> dict:
    global agent, _loaded_from
    data = load_config()
    if "selectorEnabled" in updates:
        data["selectorEnabled"] = bool(updates["selectorEnabled"])
    if "layaModelDir" in updates:
        data["layaModelDir"] = str(updates["layaModelDir"] or "").strip()
        agent = None
        _loaded_from = None
    if "extraScanRoots" in updates and isinstance(updates["extraScanRoots"], list):
        data["extraScanRoots"] = [str(item).strip() for item in updates["extraScanRoots"] if str(item).strip()]
    _atomic_write(CONFIG_PATH, json.dumps(data, ensure_ascii=False, indent=2))
    from hosts import sync_hosts

    hosts = sync_hosts(bool(data["selectorEnabled"]))
    return {"config": public_config(data), "hosts": hosts}


def weights_ready(directory: Path) -> bool:
    return (directory / "model.safetensors").is_file() and (directory / "rl_agent_config.json").is_file()


def pick_model_dir(configured: str, bundled: Path = BUNDLED_MODEL) -> Path:
    text = (configured or "").strip()
    if text:
        path = Path(text)
        if weights_ready(path):
            return path
    return bundled


def public_config(data: dict | None = None) -> dict:
    from host.jev import WEIGHTS

    data = data or load_config()
    directory = pick_model_dir(str(data.get("layaModelDir") or ""))
    ready = weights_ready(directory)
    return {
        "selectorEnabled": bool(data["selectorEnabled"]),
        "jevWeights": str(WEIGHTS),
        "layaModelDir": str(directory),
        "layaReady": ready,
        "layaRepo": LAYA_REPO,
        "layaWeights": LAYA_WEIGHTS,
        "skillDir": str(SKILLS),
        "extraScanRoots": data.get("extraScanRoots") or [],
        "project": str(ROOT),
    }


def model_dir() -> Path:
    return pick_model_dir(str(load_config().get("layaModelDir") or ""))


def ensure_laya_weights() -> Path:
    directory = model_dir()
    if weights_ready(directory):
        return directory
    directory = BUNDLED_MODEL
    directory.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id=LAYA_HF_REPO, local_dir=str(directory))
    except Exception as exc:
        raise FileNotFoundError(
            "项目里还没有 Laya 权重，自动下载也失败了。需要能访问 "
            + LAYA_WEIGHTS
            + " 。"
            + str(exc)
        ) from exc
    if not weights_ready(directory):
        raise FileNotFoundError("下载结束了，但项目里的 models/laya 仍缺少 model.safetensors 或 rl_agent_config.json。")
    stored = load_config()
    if not weights_ready(Path(str(stored.get("layaModelDir") or ""))):
        stored["layaModelDir"] = str(directory)
        _atomic_write(CONFIG_PATH, json.dumps(stored, ensure_ascii=False, indent=2))
    return directory


def load_memory() -> dict:
    if not CALLS_PATH.is_file():
        return {"calls": [], "rules": {}}
    try:
        data = json.loads(CALLS_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {"calls": [], "rules": {}}
    if not isinstance(data, dict):
        return {"calls": [], "rules": {}}
    data.setdefault("calls", [])
    data.setdefault("rules", {})
    return data


def save_memory(data: dict) -> None:
    _atomic_write(CALLS_PATH, json.dumps(data, ensure_ascii=False, indent=2))


def record_call(task: str, category: str, skills: list[dict], source: str, method: str = "skill", passed: list | None = None, label: str | None = None) -> dict:
    with lock:
        memory = load_memory()
        shown = label or ("自主思考" if method == "think" else LABELS.get(category, category))
        entry = {
            "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "task": task,
            "method": method,
            "category": category,
            "label": shown,
            "skills": [item["name"] for item in skills],
            "source": source,
        }
        if passed:
            entry["passed"] = [
                {"name": item.get("name"), "probability": item.get("probability")}
                for item in passed
                if item.get("name")
            ]
        memory["calls"].insert(0, entry)
        memory["calls"] = memory["calls"][:200]
        save_memory(memory)
    return entry


def mcp_snippet() -> dict:
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    command = str(python if python.is_file() else Path(sys.executable))
    script = str((ROOT / "mcp_server.py").resolve())
    block = {
        "mcpServers": {
            "jev-skill-kit": {
                "command": command,
                "args": [script],
                "env": {"USE_TF": "0", "PYTHONUTF8": "1"},
            }
        }
    }
    return {"name": "jev-skill-kit", "configText": json.dumps(block, ensure_ascii=False, indent=2)}


SOURCE_LABELS = {"web": "网页", "mcp": "MCP", "hermes": "Hermes", "openclaw": "龙虾"}
TASK_MATCH = 0.5


def normalize_task(task: str) -> str:
    return re.sub(r"\s+", "", (task or "").strip().lower())


def task_similarity(left: str, right: str) -> float:
    a = normalize_task(left)
    b = normalize_task(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    def grams(text: str) -> set[str]:
        if len(text) < 2:
            return {text}
        return {text[i : i + 2] for i in range(len(text) - 1)}

    ga, gb = grams(a), grams(b)
    return len(ga & gb) / len(ga | gb)


def task_rule_list(memory: dict) -> list:
    rules = memory.get("rules")
    if isinstance(rules, list):
        return rules
    memory["rules"] = []
    return memory["rules"]


SEMANTIC_MATCH = 0.75


def _cosine(left, right) -> float:
    dot = norm_left = norm_right = 0.0
    for a, b in zip(left, right):
        x, y = float(a), float(b)
        dot += x * y
        norm_left += x * x
        norm_right += y * y
    if norm_left <= 0 or norm_right <= 0:
        return 0.0
    return dot / ((norm_left ** 0.5) * (norm_right ** 0.5))


def best_task_rule(task: str, category: str, memory: dict, embed=None) -> dict | None:
    candidates = [rule for rule in task_rule_list(memory) if rule.get("category") == category and (rule.get("task") or "").strip()]
    if not candidates:
        return None
    vectors = None
    if embed is not None:
        try:
            vectors = embed([task] + [rule["task"] for rule in candidates])
        except Exception:
            vectors = None
    best = None
    best_rank = -1.0
    for index, rule in enumerate(candidates):
        lexical = task_similarity(task, rule.get("task") or "")
        cosine = 0.0
        if vectors is not None and len(vectors) == len(candidates) + 1:
            cosine = _cosine(vectors[0], vectors[index + 1])
        if lexical < TASK_MATCH and cosine < SEMANTIC_MATCH:
            continue
        rank = max(lexical, cosine)
        if rank > best_rank:
            best = rule
            best_rank = rank
    return best


def best_matching_rule(task: str, memory: dict, embed=None) -> dict | None:
    candidates = [rule for rule in task_rule_list(memory) if (rule.get("task") or "").strip()]
    if not candidates:
        return None
    vectors = None
    if embed is not None:
        try:
            vectors = embed([task] + [rule["task"] for rule in candidates])
        except Exception:
            vectors = None
    best = None
    best_rank = -1.0
    for index, rule in enumerate(candidates):
        lexical = task_similarity(task, rule.get("task") or "")
        cosine = 0.0
        if vectors is not None and len(vectors) == len(candidates) + 1:
            cosine = _cosine(vectors[0], vectors[index + 1])
        if lexical < TASK_MATCH and cosine < SEMANTIC_MATCH:
            continue
        rank = max(lexical, cosine)
        if rank > best_rank:
            best = rule
            best_rank = rank
    return best


def calls_view() -> dict:
    memory = load_memory()
    calls = []
    for call in memory["calls"][:80]:
        item = dict(call)
        source = call.get("source") or ""
        item["sourceLabel"] = SOURCE_LABELS.get(source, source)
        calls.append(item)
    return {"calls": calls, "rules": task_rule_list(memory), "mcp": mcp_snippet()}


def delete_call(call_id: str) -> dict:
    call_id = str(call_id or "").strip()
    if not call_id:
        raise ValueError("missing call")
    with lock:
        memory = load_memory()
        kept = [call for call in memory["calls"] if call.get("id") != call_id]
        if len(kept) == len(memory["calls"]):
            raise KeyError("call not found")
        memory["calls"] = kept
        save_memory(memory)
    return {"ok": True}


def update_rule(body: dict) -> dict:
    task = str(body.get("task") or "").strip()
    category = str(body.get("category") or "").strip()
    if not task:
        raise ValueError("需要任务原文")
    if category not in LABELS and not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", category):
        raise ValueError("bad category")
    with lock:
        memory = load_memory()
        rules = task_rule_list(memory)
        rule = None
        for item in rules:
            if item.get("category") == category and normalize_task(item.get("task") or "") == normalize_task(task):
                rule = item
                break
        if rule is None:
            rule = {"task": task, "category": category, "add": [], "remove": []}
            rules.append(rule)
        rule.setdefault("add", [])
        rule.setdefault("remove", [])

        def add_unique(key: str, name: str) -> None:
            safe_name(name)
            if name not in rule[key]:
                rule[key].append(name)

        added = str(body.get("add") or "")
        removed = str(body.get("remove") or "")
        if added:
            add_unique("add", added)
            rule["remove"] = [name for name in rule["remove"] if name != added]
        if removed:
            add_unique("remove", removed)
            rule["add"] = [name for name in rule["add"] if name != removed]
        restore = str(body.get("unremove") or "")
        dropped = str(body.get("unadd") or "")
        if dropped:
            rule["add"] = [name for name in rule["add"] if name != dropped]
        if restore:
            rule["remove"] = [name for name in rule["remove"] if name != restore]
        if not rule["add"] and not rule["remove"]:
            rules.remove(rule)
        catalog = load_catalog()
        known = {item["name"]: item for item in catalog["skills"]}
        for call in memory["calls"]:
            if call.get("category") != category or normalize_task(call.get("task") or "") != normalize_task(task):
                continue
            names = [name for name in (call.get("skills") or []) if name not in set(rule.get("remove") or []) and name != dropped]
            for name in rule.get("add") or []:
                if name not in names and name in known:
                    names.append(name)
            if restore and restore in known and restore not in names and restore not in set(rule.get("remove") or []):
                names.append(restore)
            call["skills"] = names
        save_memory(memory)
        shown = []
        for call in memory["calls"]:
            if call.get("category") == category and normalize_task(call.get("task") or "") == normalize_task(task):
                shown = call.get("skills") or []
                break
        skills = [skill_record(known[name]) for name in shown if name in known]
    return {"rule": rule if rule.get("add") or rule.get("remove") else None, "skills": skills}


def skill_record(item: dict, probability=None) -> dict:
    return {
        "name": item.get("name"),
        "summary": (item.get("summary") or "")[:160],
        "path": item.get("path") or "",
        "probability": probability,
    }


def pick_close_skills(skill_answer: dict, remaining: dict, by_name: dict, ratio: float = 0.6, limit: int = 3) -> tuple[list[dict], list[dict]]:
    probs = skill_answer.get("probabilities") or {}
    ranked: list[tuple[str, float | None]] = []
    for name, value in probs.items():
        if name not in remaining or value is None:
            continue
        try:
            ranked.append((name, float(value)))
        except (TypeError, ValueError):
            continue
    ranked.sort(key=lambda item: item[1], reverse=True)
    choice = skill_answer.get("choice")
    if choice in remaining and not any(name == choice for name, _prob in ranked):
        ranked.insert(0, (choice, None))
    if not ranked and choice in remaining:
        ranked = [(choice, None)]
    picked = []
    passed = []
    if not ranked:
        return picked, passed
    top = ranked[0][1]
    stopped = False
    for name, prob in ranked:
        item = by_name.get(name, {})
        shown = round(prob, 4) if isinstance(prob, float) else prob
        close = not picked or top is None or top <= 0 or prob is None or prob >= ratio * top
        if stopped or len(picked) >= limit or not close:
            stopped = True
            if len(passed) < 8:
                passed.append({"name": name, "probability": shown})
            continue
        picked.append(
            {
                "name": name,
                "summary": remaining.get(name, ""),
                "path": item.get("path") or "",
                "probability": prob,
                "confidence": skill_answer.get("answer_confidence") if name == choice else None,
            }
        )
    return picked, passed


def apply_rules(category: str, ranked: list[dict], catalog: dict, task: str = "", rule: dict | None = None) -> list[dict]:
    if rule is None:
        rule = best_task_rule(task, category, load_memory()) or {}
    removed = set(rule.get("remove") or [])
    added = [name for name in (rule.get("add") or []) if name not in removed]
    by_name = {item["name"]: item for item in catalog["skills"]}
    final: list[dict] = []
    seen = set()
    for item in ranked:
        name = item["name"]
        if name in removed or name in seen:
            continue
        final.append(item)
        seen.add(name)
    for name in added:
        if name in seen:
            continue
        item = by_name.get(name)
        if item:
            final.append(skill_record(item))
            seen.add(name)
    return final


def guess_category(name: str) -> str:
    lowered = name.lower()
    for category, keys in GUESS_RULES:
        if any(key in lowered for key in keys):
            return category
    return "other"


def is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = os.lstat(path).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & 0x400)


def known_scan_roots() -> list[tuple[str, Path]]:
    home = Path.home()
    named = [
        ("cursor", home / ".cursor" / "skills"),
        ("openclaw-workspace", home / ".openclaw" / "workspace" / "skills"),
        ("agents", home / ".agents" / "skills"),
        ("hermes", home / ".hermes" / "skills"),
        ("codex", home / ".codex" / "skills"),
        ("claude", home / ".claude" / "skills"),
        ("openclaw", home / ".openclaw" / "skills"),
    ]
    extra = [("extra", Path(item)) for item in load_config().get("extraScanRoots") or []]
    return [(source, path) for source, path in named + extra if path.is_dir()]


_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "AppData"}
# Dead MiniMax calls and skills that still point at the deleted video pipeline.
BLOCKED_SKILLS = {
    "minimax-multimodal-toolkit",
    "minimax-music-gen",
    "minimax-music-playlist",
    "minimax-docx",
    "minimax-pdf",
    "minimax-xlsx",
    "gif-sticker-maker",
    "mmx-cli",
    "vision-analysis",
    "buddy-sings",
    "web-animation-arsenal",
    "video-archive",
}


def _copy_skill(source_dir: Path, category: str, name: str) -> Path:
    dest = SKILLS / category / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source_dir,
        dest,
        ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", ".venv", "venv", ".env", ".env.*"),
        dirs_exist_ok=False,
    )
    return dest


def _fingerprint(root: Path) -> dict[str, str]:
    found = {}
    if not root.is_dir():
        return found
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        parts = path.relative_to(root).parts
        if any(part in _SKIP_DIRS or part.startswith(".env") for part in parts):
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        found["/".join(parts)] = digest
    return found


def _find_named_skill(root: Path, name: str, depth: int) -> Path | None:
    direct = root / name
    if (direct / "SKILL.md").is_file() and not is_reparse(direct):
        try:
            return direct.resolve()
        except OSError:
            return direct
    if depth <= 0 or not root.is_dir() or is_reparse(root):
        return None
    try:
        children = list(root.iterdir())
    except OSError:
        return None
    for child in children:
        if not child.is_dir() or child.name in _SKIP_DIRS or child.name.startswith("."):
            continue
        if is_reparse(child):
            continue
        found = _find_named_skill(child, name, depth - 1)
        if found is not None:
            return found
    return None


def locate_origin(item: dict) -> Path | None:
    name = item.get("name") or ""
    kit = SKILLS.resolve()
    stored = item.get("origin")
    if stored:
        path = Path(stored)
        if path.name == name and (path / "SKILL.md").is_file():
            try:
                real = path.resolve()
            except OSError:
                real = path
            if real != kit and kit not in real.parents:
                return real
    matches = []
    for label, root in known_scan_roots():
        try:
            if root.resolve() == kit or kit in root.resolve().parents:
                continue
        except OSError:
            continue
        found = _find_named_skill(root, name, 4)
        if found is None or found == kit or kit in found.parents:
            continue
        matches.append((label, found))
    source = item.get("source")
    for label, found in matches:
        if label == source:
            return found
    return matches[0][1] if matches else None


def _child(root: Path, rel: str) -> Path:
    root_real = root.resolve()
    target = (root_real / rel).resolve()
    if target != root_real and root_real not in target.parents:
        raise ValueError("path escaped")
    return target


def _mirror(source: Path, dest: Path, delete_extra: bool = False) -> bool:
    if not source.is_dir():
        raise FileNotFoundError(str(source))
    dest.mkdir(parents=True, exist_ok=True)
    current = _fingerprint(dest)
    wanted = _fingerprint(source)
    if current == wanted:
        return False
    for rel, digest in wanted.items():
        if current.get(rel) == digest:
            continue
        target = _child(dest, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_child(source, rel), target)
    if delete_extra:
        for rel in current:
            if rel not in wanted:
                target = _child(dest, rel)
                if target.is_file():
                    target.unlink()
    return True


def sync_skills(direction: str, name: str | None = None, preview: bool = False) -> dict:
    if direction not in {"push", "revert"}:
        raise ValueError("bad direction")
    if name:
        name = safe_name(name)
    updated = []
    unchanged = 0
    missing = []
    with lock:
        data = load_catalog()
        items = [find_skill(data, name)] if name else list(data["skills"])
        for item in items:
            skill_name = item.get("name") or ""
            origin = locate_origin(item)
            if origin is None:
                missing.append(skill_name)
                continue
            category = item.get("category") or "other"
            kit_dir = (SKILLS / category / skill_name).resolve()
            if kit_dir != SKILLS.resolve() and SKILLS.resolve() not in kit_dir.parents:
                raise ValueError("skill path is outside the kit")
            if not preview:
                item["origin"] = str(origin)
            if preview:
                changed = _fingerprint(kit_dir if direction == "push" else origin) != _fingerprint(origin if direction == "push" else kit_dir)
            elif direction == "push":
                changed = _mirror(kit_dir, origin, delete_extra=False)
            else:
                changed = _mirror(origin, kit_dir, delete_extra=True)
                skill_file = kit_dir / "SKILL.md"
                text = skill_file.read_text(encoding="utf-8", errors="replace") if skill_file.is_file() else ""
                item["summary"] = frontmatter_description(text)
                item["scripts"] = list_scripts(kit_dir)
            if not preview:
                item["path"] = str(kit_dir)
            if changed:
                updated.append({"name": skill_name, "category": category, "origin": str(origin)})
            else:
                unchanged += 1
        if not preview:
            data["count"] = len(data["skills"])
            data["generatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            save_catalog(data)
    return {
        "direction": direction,
        "preview": preview,
        "updated": updated,
        "unchanged": unchanged,
        "missingCount": len(missing),
        "missing": missing[:40],
    }


def _write_roots(paths: list[str]) -> list[str]:
    data = load_config()
    data["extraScanRoots"] = paths
    _atomic_write(CONFIG_PATH, json.dumps(data, ensure_ascii=False, indent=2))
    return paths


def remember_root(path: str) -> list[str]:
    folder = Path(path)
    if not folder.is_dir():
        raise FileNotFoundError("这个文件夹不存在：" + str(folder))
    text = str(folder)
    current = [str(item) for item in load_config().get("extraScanRoots") or []]
    if text not in current:
        current.append(text)
    return _write_roots(current)


def forget_root(path: str) -> list[str]:
    text = str(Path(path))
    current = [item for item in load_config().get("extraScanRoots") or [] if str(Path(item)) != text and item != path]
    return _write_roots(current)


def pick_folder() -> str:
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$dialog.Description = '选择技能文件夹'; "
        "$dialog.ShowNewFolderButton = $false; "
        "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $dialog.SelectedPath }"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return (completed.stdout or "").strip().splitlines()[-1].strip() if (completed.stdout or "").strip() else ""


def scan_skills(roots: list[tuple[str, Path]] | None = None, home_walk: bool = True) -> dict:
    copied = []
    skipped = []
    seen_real: set[Path] = set()
    with lock:
        data = load_catalog() if CATALOG_PATH.is_file() else {"skills": [], "generatedAt": "", "root": str(SKILLS), "count": 0}
        have = {item.get("name") for item in data["skills"]}

        def consider(directory: Path, source: str) -> None:
            skill_file = directory / "SKILL.md"
            if not skill_file.is_file():
                return
            try:
                real = directory.resolve()
            except OSError:
                return
            if real in seen_real or SKILLS.resolve() in real.parents or real == SKILLS.resolve():
                return
            seen_real.add(real)
            name = directory.name
            try:
                safe_name(name)
            except ValueError:
                skipped.append({"name": name, "reason": "name"})
                return
            if name in BLOCKED_SKILLS:
                skipped.append({"name": name, "reason": "blocked"})
                return
            if name in have:
                skipped.append({"name": name, "reason": "duplicate"})
                return
            category = guess_category(name)
            try:
                dest = _copy_skill(real, category, name)
            except OSError as exc:
                skipped.append({"name": name, "reason": str(exc)})
                return
            text = skill_file.read_text(encoding="utf-8", errors="replace")
            data["skills"].append(
                {
                    "name": name,
                    "category": category,
                    "source": source,
                    "origin": str(real),
                    "path": str(dest),
                    "summary": frontmatter_description(text),
                    "scripts": list_scripts(dest),
                }
            )
            have.add(name)
            copied.append({"name": name, "category": category, "source": source})

        def walk(root: Path, source: str, depth_left: int) -> None:
            if depth_left < 0 or not root.is_dir() or is_reparse(root):
                return
            try:
                children = list(root.iterdir())
            except OSError:
                return
            if (root / "SKILL.md").is_file():
                consider(root, source)
                return
            for child in children:
                if not child.is_dir():
                    continue
                if child.name in {".git", "node_modules", "__pycache__", ".venv", "venv", "AppData"}:
                    continue
                if is_reparse(child):
                    try:
                        target = child.resolve()
                    except OSError:
                        continue
                    if (target / "SKILL.md").is_file():
                        consider(target, source)
                    continue
                walk(child, source, depth_left - 1)

        chosen = roots if roots is not None else known_scan_roots()
        for source, root in chosen:
            walk(root, source, 6)
        if home_walk:
            home = Path.home()
            for child in home.iterdir() if home.is_dir() else []:
                if not child.is_dir() or child.name.startswith(".") or child.name in {"AppData", "Application Data"}:
                    continue
                try:
                    resolved = child.resolve()
                    if resolved == ROOT.resolve() or ROOT.resolve() in resolved.parents or SKILLS.resolve() in resolved.parents:
                        continue
                except OSError:
                    continue
                walk(child, "found", 5)
        data["count"] = len(data["skills"])
        data["generatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        data["root"] = str(SKILLS)
        save_catalog(data)
    return {"copied": copied, "skippedDuplicates": sum(1 for item in skipped if item["reason"] == "duplicate"), "skipped": skipped[:40]}


def import_folder(path: str) -> dict:
    roots = remember_root(path)
    report = scan_skills(roots=[("chosen", Path(path))], home_walk=False)
    report["extraScanRoots"] = roots
    return report


_loaded_from: str | None = None


def get_agent():
    global agent, _loaded_from
    directory = ensure_laya_weights()
    with _model_lock:
        if agent is not None and _loaded_from == str(directory):
            return agent
        import laya

        agent = laya.load(str(directory), device="cpu")
        _loaded_from = str(directory)
        return agent


def predict_choice(model, task: str, key: str, instructions: str, criteria: dict) -> dict:
    result = model.predict(
        task,
        {
            key: {
                "type": "choice",
                "instructions": instructions,
                "criteria": criteria,
            }
        },
        max_len=1024,
    )
    return result["answers"][key]


def method_probabilities(answer: dict) -> dict:
    raw = answer.get("probabilities") or {}
    think_p = float(raw.get("think") or 0)
    skill_p = float(raw.get("skill") or 0)
    if skill_p <= 0 and think_p > 0:
        skill_p = max(0.0, 1.0 - think_p)
    return {"think": round(think_p, 4), "skill": round(skill_p, 4)}


def _gate_method_probabilities(votes: dict) -> dict:
    values = []
    for value in votes.values():
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    top = max(values) if values else 0.0
    kept = [value for value in values if value >= 0.5]
    skill_p = max(kept) if kept else top
    return {"think": round(max(0.0, 1.0 - skill_p), 4), "skill": round(skill_p, 4)}


def route_task(task: str, source: str = "web", model=None, record: bool = True) -> dict:
    from host.gate import available_gates, decision_from_votes, gate_labels, sentence_names

    task = task.strip()
    original_length = len(task)
    clipped = False
    if not task:
        raise ValueError("task is empty")
    if len(task) > 2000:
        task = task[:2000]
        clipped = True
    config = load_config()
    if not config["selectorEnabled"]:
        return {
            "enabled": False,
            "message": "技能选择器已关闭。打开后，宿主会在模型开口前用 JEV 选技能。",
        }
    del model
    from host.jev import load_head, score_task

    data = load_catalog()
    from host.plugin_inventory import plugin_gates

    gates = available_gates(data) + plugin_gates()
    from host.tool_memory import remembered_doors

    probabilities = score_task(task, [gate["id"] for gate in gates])
    trained = set(load_head().get("labels") or [])
    habits = remembered_doors(task)
    for gate in gates:
        named = sentence_names(task, gate)
        if not named:
            probabilities[gate["id"]] = 0.0
            continue
        if gate["id"] in habits:
            probabilities[gate["id"]] = max(float(probabilities.get(gate["id"]) or 0), 0.75)
            continue
        if gate["id"] not in trained:
            probabilities[gate["id"]] = max(float(probabilities.get(gate["id"]) or 0), 0.75)
    memory = load_memory()
    matched = best_matching_rule(task, memory, None)
    by_name = {item["name"]: item for item in data["skills"] if item.get("name")}
    decided = decision_from_votes(probabilities, gates, matched, by_name, task, habits)
    remembered = {"task": matched["task"]} if matched else None
    call = None
    if record:
        call = record_call(
            task,
            decided["gate"],
            decided["skills"],
            source,
            decided["method"],
            decided["passed"],
            decided["label"],
        )
    kinds = {str(item.get("kind") or "skill") for item in decided["skills"]}
    if decided["method"] == "think":
        message = "JEV 判断这次自己做。不要套技能，直接完成任务。"
    elif kinds == {"plugin"}:
        message = "JEV 已选定插件。按插件做，不要再挑选。"
    elif "plugin" in kinds:
        message = "JEV 已选定技能和插件。读完照做，不要再挑选。"
    else:
        message = "JEV 已选定技能。读完照做，不要再挑选。"
    return {
        "enabled": True,
        "method": decided["method"],
        "methodProbabilities": _gate_method_probabilities(probabilities),
        "methodConfidence": None,
        "message": message,
        "category": decided["gate"],
        "label": decided["label"],
        "categoryProbabilities": probabilities,
        "categoryConfidence": None,
        "gateLabels": gate_labels(gates),
        "skills": decided["skills"],
        "passed": decided["passed"],
        "reasons": decided.get("reasons") or [],
        "model": "jev",
        "task": task,
        "remembered": remembered,
        "decisionId": call["id"] if record else None,
        "clipped": clipped,
        "originalLength": original_length if clipped else None,
    }


def host_preface(task: str, source: str = "host") -> str:
    from host.gate import format_preface

    text = (task or "").strip()
    if not text or "【技能柜】" in text:
        return ""
    routed = route_task(text, source)
    texts = {}
    for skill in routed.get("skills") or []:
        name = skill.get("name") or ""
        path = skill.get("path") or ""
        if not name:
            continue
        if path:
            try:
                texts[name] = read_skill(name).get("content") or ""
            except (OSError, ValueError, FileNotFoundError, KeyError):
                texts[name] = ""
    preface = format_preface(routed, texts)
    decision = routed.get("decisionId") or ""
    if decision and preface:
        preface += "\n\ndecision_id=" + str(decision)
    if routed.get("clipped") and preface:
        preface += "\n原句超过 2000 字，已截断后再选。"
    return preface


LIBRARY_PATH = ROOT / "library.json"
_GITHUB_PART = re.compile(r"^[A-Za-z0-9_.-]+$")
_ZH_CACHE: dict[str, str] = {}


def _cjk_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def _needs_zh(text: str) -> bool:
    letters = len(re.findall(r"[A-Za-z]", text or ""))
    cjk = _cjk_count(text)
    return letters > 12 and cjk < letters * 0.3


def _translate_piece(text: str) -> str:
    chunk = (text or "").strip()
    if not chunk or not _needs_zh(chunk):
        return chunk
    cached = _ZH_CACHE.get(chunk)
    if cached:
        return cached
    query = urllib.parse.urlencode({"q": chunk[:450], "langpair": "en|zh-CN"})
    request = urllib.request.Request(
        "https://api.mymemory.translated.net/get?" + query,
        headers={"User-Agent": "jev-skill-kit"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        translated = _polish_zh(str((payload.get("responseData") or {}).get("translatedText") or "").strip())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, UnicodeError):
        return chunk
    if not translated or "MYMEMORY WARNING" in translated.upper() or payload.get("quotaFinished"):
        return chunk
    if _cjk_count(translated) <= _cjk_count(chunk):
        return chunk
    _ZH_CACHE[chunk] = translated
    return translated


def _polish_zh(text: str) -> str:
    for source, target in (
        ("座席技能", "智能体技能"),
        ("人工智能代理", "智能体"),
        ("编码代理", "编程智能体"),
        ("代理技能", "智能体技能"),
        ("人工智能生成", "机器生成"),
    ):
        text = text.replace(source, target)
    return text


def _translate_zh(text: str) -> str:
    source = (text or "").strip()
    if not source or not _needs_zh(source):
        return source
    cached = _ZH_CACHE.get(source)
    if cached:
        return cached
    pieces = []
    for paragraph in source.split("\n\n"):
        if len(paragraph.encode("utf-8")) <= 450:
            pieces.append(_translate_piece(paragraph))
            continue
        buf = ""
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            trial = (buf + " " + sentence).strip()
            if buf and len(trial.encode("utf-8")) > 450:
                pieces.append(_translate_piece(buf))
                buf = sentence
            else:
                buf = trial
        if buf:
            pieces.append(_translate_piece(buf))
    joined = _polish_zh("\n\n".join(part for part in pieces if part))
    if joined and not _needs_zh(joined):
        _ZH_CACHE[source] = joined
    return joined or source


def _zh_items(items: list[dict]) -> bool:
    pending = [item for item in items if _needs_zh(item.get("description") or "")]
    if not pending:
        return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        translated = list(pool.map(lambda item: _translate_zh(item.get("description") or ""), pending))
    changed = False
    for item, text in zip(pending, translated):
        if text and text != item.get("description"):
            item["description"] = text
            changed = True
    return changed


def _day_key(stamp: str) -> str:
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return datetime.now().astimezone().date().isoformat()
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return moment.astimezone().date().isoformat()


def _upsert_day(days: list, stamp: str, items: list) -> list:
    if not stamp or not items:
        return days
    key = _day_key(stamp)
    kept = [day for day in days if not (isinstance(day, dict) and day.get("date") == key)]
    kept.append({"date": key, "fetchedAt": stamp, "items": items})
    kept.sort(key=lambda day: str(day.get("date") or ""), reverse=True)
    return kept[:366]


def _archive_current(data: dict) -> bool:
    raw = data.get("days")
    days = [day for day in raw if isinstance(day, dict)] if isinstance(raw, list) else []
    changed = not isinstance(raw, list)
    stamp = data.get("fetchedAt") or ""
    items = data.get("items") or []
    if stamp and items and not any(day.get("date") == _day_key(stamp) for day in days):
        days = _upsert_day(days, stamp, items)
        changed = True
    if changed:
        data["days"] = days
    elif "days" not in data:
        data["days"] = days
        changed = True
    return changed


def library_view() -> dict:
    if not LIBRARY_PATH.is_file():
        return {"fetchedAt": "", "items": [], "days": [], "note": "还没有推荐。打开这一页时会去 GitHub 取一次。"}
    data = json.loads(LIBRARY_PATH.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        return {"fetchedAt": "", "items": [], "days": []}
    data.setdefault("items", [])
    data.setdefault("fetchedAt", "")
    changed = _zh_items(data["items"])
    for item in data["items"]:
        polished = _polish_zh(item.get("description") or "")
        if polished != item.get("description"):
            item["description"] = polished
            changed = True
    if _archive_current(data):
        changed = True
    for day in data.get("days") or []:
        if _zh_items(day.get("items") or []):
            changed = True
    if changed:
        LIBRARY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def library_is_stale(hours: int = 20) -> bool:
    if not LIBRARY_PATH.is_file():
        return True
    try:
        fetched = library_view().get("fetchedAt") or ""
        if not fetched:
            return True
        moment = datetime.fromisoformat(fetched)
        if moment.tzinfo is None:
            moment = moment.astimezone()
        age = datetime.now().astimezone() - moment
        return age.total_seconds() > hours * 3600
    except (OSError, ValueError, TypeError):
        return True


def _repo_items(payload: dict) -> list[dict]:
    items = []
    for repo in payload.get("items") or []:
        items.append(
            {
                "name": repo.get("name") or "",
                "fullName": repo.get("full_name") or "",
                "url": repo.get("html_url") or "",
                "description": (repo.get("description") or "")[:180],
                "stars": repo.get("stargazers_count") or 0,
            }
        )
    return items


def _search_repos(query: str) -> list[dict]:
    target = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": query, "sort": "stars", "order": "desc", "per_page": "10"}
    )
    return _repo_items(_github_json(target))[:10]


def search_library(query: str) -> dict:
    text = " ".join((query or "").split())
    if not text:
        raise ValueError("先写要找什么")
    if len(text) > 80:
        raise ValueError("搜索太长")
    safe = re.sub(r"[^\w\u4e00-\u9fff.+# -]", " ", text).strip()
    if not safe:
        raise ValueError("先写要找什么")
    items = _search_repos(f"{safe} topic:agent-skills")
    note = f"在话题 agent-skills 里搜「{text}」。不会自动装进柜。"
    if not items:
        items = _search_repos(f"{safe} skill")
        note = f"话题里没有「{text}」，改在带 skill 的仓库里搜了。不会自动装进柜。"
    if not items:
        note = f"没有搜到「{text}」。"
    _zh_items(items)
    return {"query": text, "items": items, "note": note, "fetchedAt": ""}


def refresh_library() -> dict:
    items = _search_repos("topic:agent-skills")
    _zh_items(items)
    previous: dict = {}
    if LIBRARY_PATH.is_file():
        try:
            loaded = json.loads(LIBRARY_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                previous = loaded
        except (OSError, json.JSONDecodeError):
            previous = {}
    days = previous.get("days") if isinstance(previous.get("days"), list) else []
    if previous.get("items") and previous.get("fetchedAt"):
        days = _upsert_day(days, previous["fetchedAt"], previous["items"])
    fetched = datetime.now().astimezone().isoformat(timespec="seconds")
    days = _upsert_day(days, fetched, items[:10])
    data = {
        "fetchedAt": fetched,
        "items": items[:10],
        "days": days,
        "note": "按 GitHub 星标，话题是 agent-skills 的仓库。每天留一份，以前的推荐还能翻。不会自动装进柜。",
    }
    LIBRARY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def parse_github(url: str) -> tuple[str, str, str | None, str]:
    text = (url or "").strip().split("?")[0].split("#")[0].rstrip("/")
    if text.endswith(".git"):
        text = text[:-4]
    prefix = "https://github.com/"
    if not text.startswith(prefix):
        raise ValueError("只接受 github.com 上的仓库链接")
    parts = [part for part in text[len(prefix):].split("/") if part != ""]
    if len(parts) < 2 or not _GITHUB_PART.match(parts[0]) or not _GITHUB_PART.match(parts[1]):
        raise ValueError("只接受 github.com 上的仓库链接")
    owner, repo = parts[0], parts[1]
    branch = None
    path = ""
    if len(parts) > 2:
        if parts[2] not in ("tree", "blob") or len(parts) < 4 or not _GITHUB_PART.match(parts[3]):
            raise ValueError("只接受仓库首页，或 tree、blob 里的目录")
        if parts[3].startswith("-"):
            raise ValueError("链接里的路径不能用")
        branch = parts[3]
        path = "/".join(parts[4:])
    if path.endswith("SKILL.md"):
        path = path.rsplit("/", 1)[0]
    if ".." in path.replace("\\", "/").split("/"):
        raise ValueError("链接里的路径不能用")
    return owner, repo, branch, path


def _skill_dirs(root: Path) -> list[Path]:
    found = []
    if (root / "SKILL.md").is_file():
        return [root]
    for path in root.rglob("SKILL.md"):
        if any(part in _SKIP_DIRS or part == ".git" for part in path.parts):
            continue
        try:
            if len(path.relative_to(root).parts) > 4:
                continue
        except ValueError:
            continue
        found.append(path.parent)
        if len(found) >= 80:
            break
    return found


def _github_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "jev-skill-kit", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {403, 429}:
            raise RuntimeError("GitHub 今天的查询次数用完了，过一会儿再打开。") from exc
        raise RuntimeError("GitHub 没有这个仓库。") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("连不上 GitHub。") from exc


def _safe_skill_path(path: str) -> str:
    text = (path or "").strip().lstrip("/")
    parts = text.split("/")
    if not text.endswith("SKILL.md") or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("只能打开仓库里的 SKILL.md")
    return text


def _skill_name_from_path(path: str, repo: str) -> str:
    if path == "SKILL.md":
        return repo
    return path[: -len("/SKILL.md")].rsplit("/", 1)[-1]


_PEEK_CACHE: dict[str, dict] = {}
_README_STOP = re.compile(
    r"^(disclaimer|license|licence|contributing|installation|install|usage|getting started|"
    r"contents|table of contents|available skills|skill list|目录|免责声明)\b",
    re.I,
)
_README_BADGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_README_LINK_ITEM = re.compile(r"^[-*]\s+\[[^\]]+\]\([^)]+\)\s*$")


def _readme_text(owner: str, repo: str, branch: str) -> str:
    for name in ("README.md", "README.MD", "readme.md", "README"):
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{urllib.parse.quote(branch)}/{name}"
        request = urllib.request.Request(raw_url, headers={"User-Agent": "jev-skill-kit"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            return ""
        except urllib.error.URLError:
            return ""
    return ""


def _project_intro(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    paragraphs: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        chunk = " ".join(part.strip() for part in buf if part.strip())
        buf.clear()
        if not chunk or _README_LINK_ITEM.match(chunk):
            return
        plain = _README_BADGE.sub("", chunk)
        plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
        plain = re.sub(r"[*_`>]+", "", plain)
        plain = re.sub(r"\s+", " ", plain).strip(" -")
        if len(plain) < 40:
            return
        paragraphs.append(plain)

    for raw in text.splitlines():
        line = raw.strip()
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            flush()
            if _README_STOP.match(heading.group(1).strip()):
                break
            continue
        if not line:
            flush()
            continue
        if _README_BADGE.search(line) and len(_README_BADGE.sub("", line).strip()) < 12:
            continue
        if _README_LINK_ITEM.match(line):
            continue
        if line.startswith(">"):
            line = line.lstrip("> ").strip()
        buf.append(line)
    flush()
    chosen: list[str] = []
    total = 0
    for paragraph in paragraphs:
        if chosen and total + len(paragraph) > 1000:
            break
        chosen.append(paragraph)
        total += len(paragraph)
        if len(chosen) >= 4:
            break
    return "\n\n".join(chosen)


def peek_github(url: str) -> dict:
    owner, repo, branch, subpath = parse_github(url)
    prefix = (subpath or "").strip("/")
    key = f"{owner}/{repo}@{branch or ''}:{prefix}"
    cached = _PEEK_CACHE.get(key)
    if cached:
        return cached
    if not branch:
        try:
            meta = _github_json(f"https://api.github.com/repos/{owner}/{repo}")
            branch = meta.get("default_branch") or "main"
        except RuntimeError:
            branch = "main"
    about = _translate_zh(_project_intro(_readme_text(owner, repo, branch)))
    if not about and branch == "main":
        master = _translate_zh(_project_intro(_readme_text(owner, repo, "master")))
        if master:
            branch = "master"
            about = master
    try:
        tree = _github_json(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{urllib.parse.quote(branch)}?recursive=1"
        )
    except RuntimeError as exc:
        return {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "url": f"https://github.com/{owner}/{repo}",
            "about": about,
            "skills": [],
            "total": 0,
            "truncated": False,
            "error": str(exc),
        }
    found = []
    for node in tree.get("tree") or []:
        path = node.get("path") or ""
        if node.get("type") != "blob" or not path.endswith("SKILL.md"):
            continue
        if prefix and path != f"{prefix}/SKILL.md" and not path.startswith(prefix + "/"):
            continue
        if len(path.split("/")) > 6:
            continue
        found.append(
            {
                "name": _skill_name_from_path(path, repo),
                "path": path,
                "url": f"https://github.com/{owner}/{repo}/blob/{branch}/{path}",
            }
        )
    found.sort(key=lambda item: (item["name"], item["path"]))
    payload = {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "url": f"https://github.com/{owner}/{repo}",
        "about": about,
        "skills": found[:60],
        "total": len(found),
        "truncated": bool(tree.get("truncated")) or len(found) > 60,
        "error": "",
    }
    _PEEK_CACHE[key] = payload
    return payload


def read_github_skill(url: str, path: str) -> dict:
    owner, repo, branch, _subpath = parse_github(url)
    path = _safe_skill_path(path)
    if not branch:
        meta = _github_json(f"https://api.github.com/repos/{owner}/{repo}")
        branch = meta.get("default_branch") or "main"
    quoted = "/".join(urllib.parse.quote(part) for part in path.split("/"))
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{urllib.parse.quote(branch)}/{quoted}"
    request = urllib.request.Request(raw_url, headers={"User-Agent": "jev-skill-kit"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError("读不到这个技能的介绍。") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("连不上 GitHub。") from exc
    summary = frontmatter_description(text) or body_excerpt(text, 360)
    return {
        "name": _skill_name_from_path(path, repo),
        "summary": summary,
        "url": f"https://github.com/{owner}/{repo}/blob/{branch}/{path}",
        "path": path,
        "installUrl": f"https://github.com/{owner}/{repo}/tree/{branch}/{path[: -len('/SKILL.md')]}" if path != "SKILL.md" else f"https://github.com/{owner}/{repo}",
    }


def install_github(url: str) -> dict:
    owner, repo, branch, subpath = parse_github(url)
    clone_url = f"https://github.com/{owner}/{repo}.git"
    command = ["git", "clone", "--depth", "1"]
    if branch:
        command.extend(["--branch", branch])
    temp = Path(tempfile.mkdtemp(prefix="jev-skill-"))
    command.extend([clone_url, str(temp)])
    copied = []
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            raise RuntimeError(detail[-1] if detail else "git clone 失败")
        base = temp / subpath if subpath else temp
        if not base.is_dir():
            raise FileNotFoundError("链接里的目录不存在")
        dirs = _skill_dirs(base)
        if not dirs:
            raise FileNotFoundError("这个链接里没有 SKILL.md")
        with lock:
            data = load_catalog()
            have = {item.get("name") for item in data["skills"]}
            for directory in dirs:
                name = repo if directory.resolve() == temp.resolve() else directory.name
                try:
                    safe_name(name)
                except ValueError:
                    continue
                if name in have or (SKILLS / guess_category(name) / name).exists():
                    copied.append({"name": name, "skipped": "柜里已经有同名技能"})
                    continue
                category = guess_category(name)
                dest = _copy_skill(directory, category, name)
                text = (dest / "SKILL.md").read_text(encoding="utf-8", errors="replace")
                summary = frontmatter_description(text) or body_excerpt(text, 160)
                data["skills"].append(
                    {
                        "name": name,
                        "category": category,
                        "source": "github",
                        "origin": f"https://github.com/{owner}/{repo}",
                        "path": str(dest),
                        "summary": summary,
                        "scripts": list_scripts(dest),
                    }
                )
                have.add(name)
                copied.append({"name": name, "category": category, "skipped": ""})
            data["count"] = len(data["skills"])
            save_catalog(data)
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    installed = [item for item in copied if not item.get("skipped")]
    if not installed and copied:
        raise FileExistsError("柜里已经有同名技能")
    if not installed:
        raise FileNotFoundError("没有装进新的技能")
    connected = bool(load_config().get("selectorEnabled"))
    message = "已复制进技能柜，没有运行里面的脚本。"
    if len(installed) >= 80:
        message += "这个仓库太大，先装了 80 个。"
    if connected:
        message += "龙虾和 Hermes 已经接在这个柜上，下次任务直接用，不用再让它们单独下载。"
    return {"copied": installed, "skipped": [item for item in copied if item.get("skipped")], "message": message}


def install_local(path: str) -> dict:
    folder = Path((path or "").strip())
    if not folder.is_dir():
        raise FileNotFoundError("这个文件夹不存在")
    dirs = _skill_dirs(folder)
    if not dirs:
        raise FileNotFoundError("这个文件夹里没有 SKILL.md")
    copied = []
    with lock:
        data = load_catalog()
        have = {item.get("name") for item in data["skills"]}
        for directory in dirs:
            name = directory.name
            try:
                safe_name(name)
            except ValueError:
                continue
            if name in have or (SKILLS / guess_category(name) / name).exists():
                copied.append({"name": name, "skipped": "柜里已经有同名技能"})
                continue
            category = guess_category(name)
            dest = _copy_skill(directory, category, name)
            text = (dest / "SKILL.md").read_text(encoding="utf-8", errors="replace")
            summary = frontmatter_description(text) or body_excerpt(text, 160)
            data["skills"].append(
                {
                    "name": name,
                    "category": category,
                    "source": "local",
                    "origin": str(folder),
                    "path": str(dest),
                    "summary": summary,
                    "scripts": list_scripts(dest),
                }
            )
            have.add(name)
            copied.append({"name": name, "category": category, "skipped": ""})
        data["count"] = len(data["skills"])
        save_catalog(data)
    installed = [item for item in copied if not item.get("skipped")]
    if not installed and copied:
        raise FileExistsError("柜里已经有同名技能")
    if not installed:
        raise FileNotFoundError("没有装进新的技能")
    message = "已从本地文件夹复制进技能柜，没有运行里面的脚本。"
    if len(installed) >= 80:
        message += "这个文件夹太大，先装了 80 个。"
    return {"copied": installed, "skipped": [item for item in copied if item.get("skipped")], "message": message}
