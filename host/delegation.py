"""Local delegation decisions and observed child-agent lifecycle events."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "runtime" / "delegation.json"
_SOURCES = {"web", "hermes", "openclaw", "harness", "codex", "cursor"}
_STATES = {"started", "completed", "error", "aborted"}
_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}


def effort_for_task(goal: str, context: str = "") -> str:
    """Initial conservative effort policy, independent of the skill-selection head."""
    text = f"{goal or ''} {context or ''}".lower()
    high = ("架构", "重构", "调试", "排查", "设计", "证明", "优化", "复杂", "debug", "refactor", "architecture", "investigate", "security")
    low = ("列出", "查找", "搜索", "汇总", "摘要", "翻译", "格式", "list", "find", "search", "summarize", "translate")
    if any(word in text for word in high) or len(text) > 600:
        return "high"
    if any(word in text for word in low) and len(text) < 220:
        return "low"
    return "medium"


def assign_task_efforts(tasks: list[dict]) -> list[dict]:
    """Fill only unspecified task efforts; explicit host/user choices win."""
    assigned = []
    for task in tasks:
        copy = dict(task)
        if str(copy.get("reasoning_effort") or "").lower() not in _EFFORTS:
            copy["reasoning_effort"] = effort_for_task(str(copy.get("goal") or ""), str(copy.get("context") or ""))
        assigned.append(copy)
    return assigned


def record_task_efforts(tasks: list[dict], source: str = "hermes") -> None:
    """Persist the proposed effort separately from the child-start observation."""
    for task in tasks:
        goal = str(task.get("goal") or "")[:500]
        effort = str(task.get("reasoning_effort") or "")
        if not goal or not effort:
            continue
        now = datetime.now().astimezone()
        if any(row.get("kind") == "effort-decision" and row.get("task") == goal and
               row.get("effort") == effort and
               abs((now - datetime.fromisoformat(row["at"])).total_seconds()) < 5
               for row in _read()[:8]):
            continue
        _append({"kind": "effort-decision", "source": source, "task": goal,
                 "effort": effort, "detail": "按任务规则补全，或沿用宿主已写的强度",
                 "reason": "per-task policy or explicit override"})


def _read() -> list[dict]:
    try:
        rows = json.loads(LOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return rows if isinstance(rows, list) else []


def present(entry: dict) -> dict:
    """Fill display fields so the log never shows an empty model/effort/detail cell."""
    row = dict(entry)
    kind = str(row.get("kind") or "")
    source = str(row.get("source") or "")
    task = str(row.get("task") or "")
    model = str(row.get("model") or "").strip()
    effort = str(row.get("effort") or "").strip()
    detail = str(row.get("detail") or row.get("reason") or "").strip()
    if effort.lower() == "host-configured":
        effort = ""
    if kind in {"decision", "effort-decision"} and not effort:
        effort = effort_for_task(task)
    if not model:
        if source == "web":
            model = "网页试选，无模型"
        elif kind == "observed":
            model = "未上报模型"
        else:
            model = "尚未创建子代理"
    if kind == "observed" and not effort:
        effort = "未上报强度"
    if not detail:
        if kind == "observed":
            detail = "宿主未回报详情"
        elif kind == "effort-decision":
            detail = "按任务规则补全，或沿用宿主已写的强度"
        elif row.get("recommendation") == "delegate":
            detail = "明确要求并行或子代理；不强制创建进程"
        else:
            detail = "未要求并行，保持单代理"
    row["model"] = model[:120]
    row["effort"] = effort[:40]
    row["detail"] = detail[:500]
    return row


def entries() -> list[dict]:
    return [present(row) for row in _read()[:100]]


def _append(row: dict) -> dict:
    row = {"at": datetime.now().astimezone().isoformat(timespec="seconds"), **row}
    import cabinet

    with cabinet._config_lock():
        rows = [row, *_read()][:300]
        LOG.parent.mkdir(parents=True, exist_ok=True)
        tmp = LOG.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(LOG)
    return row


def decide(task: str, source: str, enabled: bool) -> dict:
    """Conservative initial policy; this is not a trained JEV dispatch head."""
    text = (task or "").strip()
    explicit = bool(re.search(r"子代理|子智能体|sub.?agent|并行|同时.*分别|分别.*同时", text, re.I))
    blocked = bool(re.search(r"(?:不要|别|无需|不需要).{0,5}(?:子代理|子智能体|并行)", text[:40]))
    count = 2 if enabled and explicit and not blocked else 0
    reason = "明确要求并行或子代理" if count else ("派遣已关闭" if not enabled else "保持单代理")
    decision = {
        "kind": "decision", "source": source, "task": text[:500],
        "recommendation": "delegate" if count else "solo", "agents": count,
        "model": "网页试选，无模型" if source == "web" else "尚未创建子代理",
        "effort": effort_for_task(text) if text else "medium",
        "detail": reason + ("；不强制创建进程" if count else ""),
        "policy": "initial-rules", "reason": reason,
    }
    if text and source not in {"test", "eval"}:
        _append(decision)
    return decision


def observed(source: str, state: str, child_id: str = "", task: str = "", model: str = "", effort: str = "", detail: str = "") -> dict:
    if source not in _SOURCES or state not in _STATES:
        raise ValueError("invalid delegation event")
    if not child_id.strip():
        raise ValueError("missing child id")
    # Plugin and shell hooks can both see one lifecycle event on some surfaces.
    if any(row.get("kind") == "observed" and row.get("source") == source and
           row.get("state") == state and row.get("childId") == child_id
           for row in _read()[:12]):
        return next(row for row in _read()[:12] if row.get("kind") == "observed" and
                    row.get("source") == source and row.get("state") == state and row.get("childId") == child_id)
    return _append({
        "kind": "observed", "source": source, "state": state,
        "childId": child_id[:160], "task": task[:500], "model": model[:120],
        "effort": effort[:40], "detail": detail[:500],
    })
