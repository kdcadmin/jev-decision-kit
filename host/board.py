# Cabinet-only switches, hides, and added rows. Host config files stay untouched.
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"
HOST = "技能柜"
_KINDS = {"plugin": "plugin", "mcp": "mcp"}
_PACKAGE = re.compile(r"^(@[A-Za-z0-9._-]+/)?[A-Za-z0-9._-]+$")
_GITHUB = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def empty_board() -> dict:
    return {
        "mcpHidden": [],
        "mcpEnabled": {},
        "mcpAdded": [],
        "pluginHidden": [],
        "pluginEnabled": {},
        "pluginAdded": [],
    }


def _read_config() -> dict:
    if not CONFIG_PATH.is_file():
        return {}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_board() -> dict:
    board = empty_board()
    raw = _read_config().get("board")
    if not isinstance(raw, dict):
        return board
    for key, value in board.items():
        stored = raw.get(key)
        if isinstance(stored, type(value)):
            board[key] = stored
    return board


def save_board(board: dict) -> dict:
    data = _read_config()
    data["board"] = board
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return board


def row_key(host: str, name: str) -> str:
    return str(host or "") + "\t" + str(name or "")


def apply_rows(rows: list[dict], kind: str, board: dict | None = None) -> list[dict]:
    if kind not in _KINDS:
        raise ValueError("unknown list")
    state = board if board is not None else load_board()
    hidden = {str(item) for item in state.get(kind + "Hidden") or []}
    enabled = state.get(kind + "Enabled") if isinstance(state.get(kind + "Enabled"), dict) else {}
    kept = []
    for row in rows:
        ident = row_key(row.get("host"), row.get("name"))
        if ident in hidden:
            continue
        item = dict(row)
        if ident in enabled:
            item["enabled"] = bool(enabled[ident])
        if "canSelect" in item:
            item["selectable"] = bool(item.get("canSelect")) and bool(item.get("enabled"))
        kept.append(item)
    for added in state.get(kind + "Added") or []:
        if not isinstance(added, dict):
            continue
        name = str(added.get("name") or "").strip()
        if not name:
            continue
        ident = row_key(HOST, name)
        if ident in hidden:
            continue
        on = True if ident not in enabled else bool(enabled[ident])
        item = {
            "name": name,
            "host": HOST,
            "enabled": on,
            "source": str(added.get("source") or ""),
            "origin": str(added.get("kind") or ""),
            "added": True,
        }
        if kind == "plugin":
            from host.plugin_inventory import describe, door_id

            label, words, blurb, can_select = describe(name, str(added.get("blurb") or ""))
            item.update(
                {
                    "label": label,
                    "blurb": blurb,
                    "words": list(words),
                    "door": door_id(name),
                    "canSelect": can_select,
                    "selectable": can_select and on,
                }
            )
        kept.append(item)
    return kept


def _clean_source(text: str) -> str:
    source = " ".join((text or "").split())
    if not source or len(source) > 300:
        raise ValueError("先写来源，并且不要太长")
    return source


def plugin_from_source(kind: str, source: str) -> dict:
    text = _clean_source(source)
    mode = (kind or "").strip()
    if mode == "package":
        if not _PACKAGE.match(text):
            raise ValueError("包名写成 npm 那样，例如 @deepseek-ai/dsh-plugin")
        return {"name": text, "source": text, "kind": "package", "blurb": "从包名添加的插件。"}
    if mode == "github":
        match = _GITHUB.match(text)
        if not match:
            raise ValueError("插件的 GitHub 地址要写成 https://github.com/作者/仓库")
        return {"name": match.group(2), "source": text, "kind": "github", "blurb": "从 GitHub 添加的插件。"}
    if mode == "local":
        folder = Path(text)
        if not folder.is_dir():
            raise FileNotFoundError("这个本地目录不存在")
        name = _local_plugin_name(folder)
        return {"name": name, "source": str(folder), "kind": "local", "blurb": "从本地目录添加的插件。"}
    raise ValueError("选包名、GitHub 或本地目录")


def mcp_from_source(kind: str, source: str) -> dict:
    text = _clean_source(source)
    mode = (kind or "").strip()
    if mode == "link":
        if not text.startswith(("https://", "http://")) or " " in text:
            raise ValueError("链接要以 http:// 或 https:// 开头")
        name = text.rstrip("/").rsplit("/", 1)[-1] or "mcp"
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "mcp"
        return {"name": name[:80], "source": text, "kind": "link"}
    if mode == "github":
        match = _GITHUB.match(text)
        if not match:
            raise ValueError("MCP 的 GitHub 地址要写成 https://github.com/作者/仓库")
        return {"name": match.group(2), "source": text, "kind": "github"}
    if mode == "local":
        folder = Path(text)
        if not folder.exists():
            raise FileNotFoundError("这个本地路径不存在")
        return {"name": folder.name or "mcp", "source": str(folder), "kind": "local"}
    raise ValueError("选链接、GitHub 或本地路径")


def _local_plugin_name(folder: Path) -> str:
    for name in ("plugin.yaml", "plugin.json", "package.json"):
        path = folder / name
        if not path.is_file():
            nested = folder / ".cursor-plugin" / "plugin.json"
            path = nested if name == "plugin.json" and nested.is_file() else path
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if name.endswith(".json"):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("name"):
                return str(data["name"]).strip()
        for line in raw.splitlines():
            if line.startswith("name:"):
                title = line.split(":", 1)[1].strip().strip("\"'")
                if title:
                    return title
    return folder.name


def _mutate(kind: str, host: str, name: str) -> tuple[dict, str]:
    if kind not in _KINDS:
        raise ValueError("unknown list")
    title = (name or "").strip()
    where = (host or "").strip()
    if not title or not where:
        raise ValueError("缺少名称")
    return load_board(), row_key(where, title)


def set_enabled(kind: str, host: str, name: str, enabled: bool) -> dict:
    board, ident = _mutate(kind, host, name)
    flags = dict(board[kind + "Enabled"])
    flags[ident] = bool(enabled)
    board[kind + "Enabled"] = flags
    hidden = [item for item in board[kind + "Hidden"] if item != ident]
    board[kind + "Hidden"] = hidden
    return save_board(board)


def hide_row(kind: str, host: str, name: str) -> dict:
    board, ident = _mutate(kind, host, name)
    added_key = kind + "Added"
    before = len(board[added_key])
    board[added_key] = [
        item
        for item in board[added_key]
        if not (isinstance(item, dict) and item.get("name") == name and host == HOST)
    ]
    if len(board[added_key]) == before:
        hidden = list(board[kind + "Hidden"])
        if ident not in hidden:
            hidden.append(ident)
        board[kind + "Hidden"] = hidden
    flags = dict(board[kind + "Enabled"])
    flags.pop(ident, None)
    board[kind + "Enabled"] = flags
    return save_board(board)


def add_row(kind: str, spec: dict) -> dict:
    board = load_board()
    name = spec["name"]
    added = list(board[kind + "Added"])
    if any(isinstance(item, dict) and item.get("name") == name for item in added):
        raise FileExistsError("名单里已经有 " + name)
    hidden = [item for item in board[kind + "Hidden"] if item != row_key(HOST, name)]
    board[kind + "Hidden"] = hidden
    added.append(spec)
    board[kind + "Added"] = added
    return save_board(board)
