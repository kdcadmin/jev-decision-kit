# Read installed plugin names. JEV can score the ones that name a job.
# MCP stays in host/mcp_inventory.py and is not turned into a door.
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path

from host.gate import WORDS

_TAKEN = {word.casefold() for values in WORDS.values() for word in values}
_SLUG = re.compile(r"[^a-z0-9]+")

# The cabinet hook and the product shell are not jobs. codex-app-tools is an MCP wrapper.
_SKIP_SELECT = {
    "jev-skill-kit",
    "codex-app-tools",
    "unified-computer-use",
    "@deepseek-ai/dsh-base",
    "@deepseek-ai/dsh-web-app",
    "dsh-base",
    "dsh-web-app",
}

# Short job names. These words are not already used by a skill door.
_JOBS = {
    "planning-with-files": ("规划文件", ("规划文件", "计划文件"), "把计划写进可持续的规划文件。"),
    "weixin_memory": ("微信记忆", ("微信记忆", "微信记录"), "把微信对话记进本机记忆。"),
    "browser": ("应用内浏览器", ("应用内浏览器",), "用应用内浏览器打开并查看页面。"),
    "chrome": ("Chrome", ("Chrome", "chrome"), "用已经登录的 Chrome 做自动化。"),
    "computer-use": ("电脑操作", ("电脑操作",), "在本机桌面里操作软件。"),
    "latex": ("LaTeX", ("LaTeX", "latex"), "编译一份 LaTeX 文稿。"),
    "visualize": ("可视化", ("可视化",), "做图表、示意或可交互的可视化。"),
    "hyperframes": ("HyperFrames", ("HyperFrames", "hyperframes"), "用 HyperFrames 做网页式视频。"),
    "remotion": ("Remotion", ("Remotion", "remotion"), "用 Remotion 做程序化视频。"),
    "openai-templates": ("官方模板", ("官方模板",), "套用官方的文档、演示或表格模板。"),
    "plugin-management": ("管理插件", ("管理插件",), "查看或管理已经安装的插件。"),
    "product-design": ("产品原型", ("产品原型",), "把想法收成可以评审的产品原型。"),
    "sites": ("建站", ("建站",), "搭建并发布一个网站。"),
    "documents": ("文档插件", ("文档插件",), "用文档插件写或改一份文档。"),
    "pdf": ("PDF插件", ("PDF插件", "pdf插件"), "用 PDF 插件读或做 PDF。"),
    "presentations": ("简报插件", ("简报插件",), "用简报插件做一套演示。"),
    "spreadsheets": ("工作簿插件", ("工作簿插件",), "用工作簿插件做表。"),
    "template-creator": ("个人模板", ("个人模板",), "从现有材料做成个人模板。"),
    "datadog": ("Datadog", ("Datadog", "datadog"), "查 Datadog 里的日志、指标或追踪。"),
    "figma": ("Figma", ("Figma", "figma"), "在 Figma 里做界面。"),
    "notion-workspace": ("Notion", ("Notion", "notion"), "在 Notion 里读或写页面。"),
    "@deepseek-ai/dsh-experimental-agent-team-profile": ("智能体团队", ("智能体团队",), "用一组智能体分工做这件事。"),
    "@deepseek-ai/dsh-experimental-auto-review": ("自动审查", ("自动审查",), "在改动落地前做自动审查。"),
    "@deepseek-ai/dsh-experimental-voice-input-bundle": ("语音输入", ("语音输入",), "用语音把这句话送进去。"),
}


def door_id(name: str) -> str:
    slug = _SLUG.sub("-", (name or "").lower()).strip("-")
    return "plugin-" + (slug or "unnamed")


def _enabled(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    return str(value).strip().lower() not in {"false", "0", "no", "off"}


def _clean(text: str, limit: int = 160) -> str:
    piece = " ".join((text or "").split())
    if len(piece) > limit:
        piece = piece[:limit].rstrip() + "…"
    return piece


def describe(name: str, description: str) -> tuple[str, tuple, str, bool]:
    if name in _SKIP_SELECT:
        return name, (), _clean(description) or name, False
    known = _JOBS.get(name)
    if known:
        label, words, blurb = known
        return label, words, blurb, True
    label = name.split("/")[-1] or name
    words = tuple(word for word in (label, name) if word and word.casefold() not in _TAKEN and len(word) >= 3)
    return label, words, _clean(description) or label, bool(words)


def _entry(host: str, name: str, description: str, enabled: bool = True) -> dict | None:
    title = (name or "").strip()
    if not title:
        return None
    label, words, blurb, can_select = describe(title, description)
    return {
        "name": title,
        "host": host,
        "enabled": enabled,
        "label": label,
        "blurb": blurb,
        "words": list(words),
        "door": door_id(title),
        "canSelect": can_select,
        "selectable": can_select and enabled,
    }


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None


def _yaml_fields(text: str) -> dict:
    raw = text or ""
    if not raw.lstrip().startswith("name:"):
        try:
            raw = base64.b64decode(raw.strip()).decode("utf-8")
        except (ValueError, UnicodeError):
            return {}
    found = {}
    for line in raw.splitlines():
        if line.startswith("name:"):
            found["name"] = line.split(":", 1)[1].strip().strip("\"'")
        elif line.startswith("description:"):
            found["description"] = line.split(":", 1)[1].strip().strip("\"'")
    return found


def _from_plugin_json(host: str, path: Path) -> dict | None:
    data = _read_json(path)
    if not isinstance(data, dict):
        return None
    return _entry(
        host,
        str(data.get("name") or data.get("displayName") or ""),
        str(data.get("description") or ""),
        _enabled(data.get("enabled")),
    )


def _newest(paths: list[Path]) -> list[Path]:
    grouped: dict[str, Path] = {}
    for path in paths:
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        name = str(data.get("name") or data.get("displayName") or "")
        if not name:
            continue
        previous = grouped.get(name)
        if previous is None or str(path) > str(previous):
            grouped[name] = path
    return list(grouped.values())


def _scan_json_plugins(root: Path, host: str, marker: str) -> list[dict]:
    if not root.is_dir():
        return []
    paths = [path for path in root.rglob("plugin.json") if marker in path.parts]
    found = []
    for path in _newest(paths):
        item = _from_plugin_json(host, path)
        if item is not None:
            found.append(item)
    return found


def _scan_hermes(root: Path) -> list[dict]:
    folder = root / "plugins"
    if not folder.is_dir():
        return []
    found = []
    for path in sorted(folder.glob("*/plugin.yaml")):
        try:
            fields = _yaml_fields(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        item = _entry("Hermes", fields.get("name") or path.parent.name, fields.get("description") or "")
        if item is not None:
            found.append(item)
    return found


def _scan_harness(root: Path | None) -> list[dict]:
    if root is None or not (root / "profiles").is_dir():
        return []
    found = []
    seen = set()
    for package in sorted((root / "profiles").glob("*/package.json")):
        data = _read_json(package)
        if not isinstance(data, dict):
            continue
        profile = data.get("dsh") if isinstance(data.get("dsh"), dict) else {}
        block = profile.get("profile") if isinstance(profile.get("profile"), dict) else {}
        bundles = block.get("bundles") if isinstance(block.get("bundles"), list) else []
        for name in bundles:
            title = str(name).strip()
            if not title or title in seen:
                continue
            seen.add(title)
            item = _entry("Harness", title, "")
            if item is not None:
                found.append(item)
    return found


def default_harness_home() -> Path | None:
    preferred = os.environ.get("DSH_HOME")
    if preferred:
        return Path(preferred)
    local = Path.home() / ".dsh"
    if local.is_dir():
        return local
    fallback = Path("D:/dsh")
    if fallback.is_dir():
        return fallback
    return None


def list_plugins(home: Path | None = None, harness_home: Path | None = None) -> dict:
    root = home or Path.home()
    plugins = []
    plugins.extend(_scan_hermes(root / ".hermes"))
    plugins.extend(_scan_json_plugins(root / ".codex" / "plugins", "Codex", ".codex-plugin"))
    # Cursor leaves uninstalled marketplace plugins in plugins/cache. Only local installs count.
    plugins.extend(_scan_json_plugins(root / ".cursor" / "plugins" / "local", "Cursor", ".cursor-plugin"))
    plugins.extend(_scan_harness(harness_home if harness_home is not None else default_harness_home()))
    plugins.sort(key=lambda item: (item["host"], item["name"]))
    if home is None:
        from host.board import apply_rows

        plugins = apply_rows(plugins, "plugin")
        plugins.sort(key=lambda item: (item["host"], item["name"]))
    return {
        "note": "这些插件和技能一起交给 JEV。只有这句话点了名、并且分数过线的才会留下。MCP 仍只查看，不参与选择。",
        "plugins": plugins,
    }


def plugin_gates(home: Path | None = None, harness_home: Path | None = None) -> list[dict]:
    grouped: dict[str, dict] = {}
    for item in list_plugins(home, harness_home)["plugins"]:
        if not item.get("selectable"):
            continue
        door = grouped.get(item["door"])
        piece = {"name": item["name"], "path": "", "kind": "plugin", "host": item["host"]}
        if door is None:
            grouped[item["door"]] = {
                "id": item["door"],
                "label": item["label"],
                "blurb": item["blurb"],
                "ask": "这句话里是不是要用" + item["label"] + "？",
                "words": tuple(item["words"]),
                "items": [piece],
            }
            continue
        door["items"].append(piece)
    return [grouped[key] for key in sorted(grouped)]
