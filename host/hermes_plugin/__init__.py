from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host.preface_client import message_text, preface_for, report_dispatch_event
from host.delegation import assign_task_efforts, record_task_efforts
import cabinet


def pre_llm_call(user_message="", **_kwargs):
    text = message_text(user_message)
    if not text or "【技能柜】" in text:
        return None
    preface = preface_for(text, "hermes")
    if not preface:
        return None
    return {"context": preface}


def pre_tool_call(tool_name="", args=None, **_kwargs):
    if tool_name != "delegate_task" or not isinstance(args, dict):
        return None
    if args.get("action") in {"list", "steer", "stop"}:
        return None
    if not cabinet.load_config().get("delegationEnabled", False):
        return None
    tasks = args.get("tasks")
    if isinstance(tasks, list) and tasks and all(isinstance(task, dict) for task in tasks):
        assigned = assign_task_efforts(tasks)
        record_task_efforts(assigned)
        if assigned != tasks:
            return {"action": "modify", "args": {"tasks": assigned}}
    elif isinstance(args.get("goal"), str) and args["goal"].strip():
        from host.delegation import effort_for_task
        assigned = [{"goal": args["goal"], "context": args.get("context"), "reasoning_effort": effort_for_task(args["goal"], str(args.get("context") or ""))}]
        record_task_efforts(assigned)
        return {"action": "modify", "args": {"tasks": assigned}}
    return None


def subagent_start(child_subagent_id="", child_session_id="", child_goal="", child_reasoning_effort="", child_model="", **_kwargs):
    child_id = str(child_session_id or child_subagent_id or "")
    if child_id:
        report_dispatch_event(source="hermes", state="started", child_id=child_id, task=str(child_goal), effort=str(child_reasoning_effort), model=str(child_model))


def subagent_stop(child_subagent_id="", child_session_id="", parent_session_id="", child_goal="", child_status="", **_kwargs):
    # Some Hermes versions omit child IDs from the stop hook. Keep the event,
    # but mark its identity as uncorrelated instead of inventing a child match.
    child_id = str(child_session_id or child_subagent_id or ("unknown:" + str(parent_session_id or "hermes")))
    state = "completed" if child_status in {"completed", "success", "ok"} else ("aborted" if child_status in {"interrupted", "cancelled", "aborted"} else "error")
    report_dispatch_event(source="hermes", state=state, child_id=child_id, task=str(child_goal), detail=str(child_status))


def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_hook("pre_tool_call", pre_tool_call)
    ctx.register_hook("subagent_start", subagent_start)
    ctx.register_hook("subagent_stop", subagent_stop)
