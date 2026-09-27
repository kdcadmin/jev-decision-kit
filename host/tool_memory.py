# Pull finished tool uses out of local agent logs and keep only the door they map to.
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from host.gate import GATE, NEGATION, WORDS
from host.jev import ngrams

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "runtime" / "tool-memory.json"
MAX_TASK = 280
MIN_TASK = 8
CODEX_FILE_LIMIT = 8_000_000

TOOL_DOORS = {
    "browser_navigate": "web-read",
    "browser_exec": "web-act",
    "browser_click": "web-act",
    "browser_fill": "web-act",
    "browser_type": "web-act",
}


def skill_doors() -> dict[str, str]:
    mapping = {}
    for gate in GATE:
        for name in gate["skills"]:
            mapping[name.lower()] = gate["id"]
    return mapping


def _text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
        return "\n".join(part.strip() for part in parts if part and part.strip()).strip()
    return ""


def usable_task(text: str) -> str:
    task = " ".join((text or "").split())
    if len(task) < MIN_TASK or len(task) > MAX_TASK:
        return ""
    if task.startswith("{") or task.startswith("["):
        return ""
    return task


def doors_from_tool(name: str, arguments) -> set[str]:
    found = set()
    key = (name or "").strip().lower()
    if key in TOOL_DOORS:
        found.add(TOOL_DOORS[key])
    skills = skill_doors()
    if key in skills:
        found.add(skills[key])
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
    if isinstance(arguments, dict):
        for raw in _strings(arguments):
            base = raw.strip().lower().split(":")[-1].split("/")[-1].split("\\")[-1]
            if base in skills:
                found.add(skills[base])
    return found


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        found = []
        for item in value.values():
            found.extend(_strings(item))
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(_strings(item))
        return found
    return []


def _negated(text: str, door: str) -> bool:
    for word in WORDS.get(door, ()):
        if word.isascii():
            index = text.lower().find(word.lower())
        else:
            index = text.find(word)
        if index < 0:
            continue
        window = text[max(0, index - 8) : index]
        if any(flag in window for flag in NEGATION):
            return True
    return False


def _failed(text: str) -> bool:
    head = (text or "").strip()[:80].lower()
    return head.startswith("error") or head.startswith("traceback") or '"is_error": true' in head


def _finish(task: str, doors: set[str], correction: str, failed: bool) -> tuple[str, set[str]] | None:
    if failed or not task or not doors:
        return None
    kept = {door for door in doors if not _negated(correction, door)}
    if not kept:
        return None
    return task, kept


def collect_turns(messages: list[dict]) -> list[tuple[str, set[str], str]]:
    """messages: role, content, tool_name, tool_calls, source."""
    samples = []
    task = ""
    doors: set[str] = set()
    failed = False
    saw_result = False
    source = ""

    def flush(correction: str) -> None:
        nonlocal task, doors, failed, saw_result
        if saw_result:
            done = _finish(task, doors, correction, failed)
            if done:
                samples.append((done[0], done[1], source))
        task = ""
        doors = set()
        failed = False
        saw_result = False

    for message in messages:
        role = message.get("role") or ""
        if role == "user":
            flush(_text(message.get("content")))
            task = usable_task(_text(message.get("content")))
            source = str(message.get("source") or "")
            continue
        if role == "assistant":
            calls = message.get("tool_calls") or []
            if isinstance(calls, str):
                try:
                    calls = json.loads(calls)
                except json.JSONDecodeError:
                    calls = []
            if isinstance(calls, dict):
                calls = [calls]
            if isinstance(calls, list):
                for call in calls:
                    if not isinstance(call, dict):
                        continue
                    function = call.get("function") if isinstance(call.get("function"), dict) else {}
                    name = str(call.get("name") or function.get("name") or message.get("tool_name") or "")
                    arguments = call.get("arguments") or function.get("arguments") or {}
                    doors.update(doors_from_tool(name, arguments))
            continue
        if role == "tool":
            if doors:
                saw_result = True
                if _failed(_text(message.get("content"))):
                    failed = True
    flush("")
    return samples


def _hermes_messages() -> list[dict]:
    database = Path.home() / ".hermes" / "state.db"
    if not database.is_file():
        return []
    uri = "file:" + str(database).replace("\\", "/") + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            "SELECT session_id, role, content, tool_name, tool_calls FROM messages WHERE active=1 ORDER BY session_id, id"
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "role": role,
            "content": content,
            "tool_name": tool_name,
            "tool_calls": tool_calls,
            "source": "hermes",
            "session": session_id,
        }
        for session_id, role, content, tool_name, tool_calls in rows
    ]


def _split_sessions(messages: list[dict]) -> list[list[dict]]:
    groups = []
    current = []
    session = None
    for message in messages:
        key = message.get("session")
        if current and key != session:
            groups.append(current)
            current = []
        session = key
        current.append(message)
    if current:
        groups.append(current)
    return groups


def _codex_messages() -> tuple[list[dict], int]:
    root = Path.home() / ".codex" / "sessions"
    if not root.is_dir():
        return [], 0
    skipped = 0
    messages = []
    for path in root.rglob("*.jsonl"):
        try:
            if path.stat().st_size > CODEX_FILE_LIMIT:
                skipped += 1
                continue
        except OSError:
            continue
        session = path.stem
        try:
            handle = path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line in handle:
                if "function_call" not in line and '"message"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = obj.get("payload") or {}
                if not isinstance(payload, dict):
                    continue
                item = payload.get("item") if isinstance(payload.get("item"), dict) else payload
                kind = item.get("type")
                if kind == "message" and item.get("role") == "user":
                    messages.append({"role": "user", "content": item.get("content"), "source": "codex", "session": session})
                elif kind == "function_call":
                    messages.append(
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_name": item.get("name") or "",
                            "tool_calls": [{"name": item.get("name") or "", "arguments": item.get("arguments") or {}}],
                            "source": "codex",
                            "session": session,
                        }
                    )
                elif kind == "function_call_output":
                    messages.append(
                        {
                            "role": "tool",
                            "content": item.get("output") or "",
                            "source": "codex",
                            "session": session,
                        }
                    )
    return messages, skipped


def extract_tool_memory() -> dict:
    hermes = _hermes_messages()
    codex, skipped = _codex_messages()
    samples = []
    seen = set()
    for group in _split_sessions(hermes + codex):
        for task, doors, source in collect_turns(group):
            key = (task, tuple(sorted(doors)))
            if key in seen:
                continue
            seen.add(key)
            samples.append({"task": task, "doors": sorted(doors), "source": source})
    STORE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"samples": samples, "skippedLargeCodexLogs": skipped}
    STORE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    for item in samples:
        sources[item["source"]] = sources.get(item["source"], 0) + 1
        for door in item["doors"]:
            counts[door] = counts.get(door, 0) + 1
    return {
        "kept": len(samples),
        "doors": counts,
        "sources": sources,
        "skippedLargeCodexLogs": skipped,
        "readHermes": len(hermes),
        "readCodexEvents": len(codex),
    }


def load_samples() -> list[dict]:
    if not STORE.is_file():
        return []
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("samples") if isinstance(data, dict) else None
    return items if isinstance(items, list) else []


def remembered_doors(task: str, samples: list[dict] | None = None, line: float = 0.72) -> set[str]:
    grams = set(ngrams(task))
    if not grams:
        return set()
    found = set()
    for item in samples if samples is not None else load_samples():
        proto = set(ngrams(str(item.get("task") or "")))
        if len(proto) < 6:
            continue
        if len(proto & grams) / len(proto) < line:
            continue
        for door in item.get("doors") or []:
            found.add(str(door))
    return found
