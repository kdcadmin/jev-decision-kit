"""Version-guarded, reversible local Hermes per-child reasoning extension."""
from __future__ import annotations

import argparse
import py_compile
from pathlib import Path

MARKER = "# JEV_CHILD_REASONING_V1"


def _replace_once(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise RuntimeError(f"Hermes version differs at anchor: {before[:80]!r}")
    return source.replace(before, after, 1)


def install(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        return False
    changed = source
    changed = _replace_once(changed, "    override_max_tokens: Optional[int] = None,\n", "    override_max_tokens: Optional[int] = None,\n    override_reasoning_effort: Optional[str] = None,  " + MARKER + "\n")
    changed = _replace_once(changed, "    if override_request_overrides is not None:\n", "    if override_reasoning_effort is not None:\n        from hermes_constants import parse_reasoning_effort\n        parsed_effort = parse_reasoning_effort(override_reasoning_effort)\n        if parsed_effort is None:\n            raise ValueError(f\"Invalid child reasoning_effort: {override_reasoning_effort}\")\n        rt[\"reasoning_config\"] = parsed_effort\n    if override_request_overrides is not None:\n")
    changed = _replace_once(changed, "                parent_agent=parent_agent, role=_normalize_role(t.get(\"role\") or top_role), **overrides,\n", "                parent_agent=parent_agent, role=_normalize_role(t.get(\"role\") or top_role),\n                override_reasoning_effort=t.get(\"reasoning_effort\"), **overrides,\n")
    changed = _replace_once(changed, "            child_role=effective_role, child_goal=goal,\n", "            child_role=effective_role, child_goal=goal,\n            child_reasoning_effort=(getattr(child, \"reasoning_config\", None) or {}).get(\"effort\", \"none\"),\n            child_model=getattr(child, \"model\", \"\"),\n")
    changed = _replace_once(changed, "                        \"output_schema\": _p(\n", "                        \"reasoning_effort\": _p(\"string\", \"Reasoning effort for this child only.\", enum=[\"none\", \"minimal\", \"low\", \"medium\", \"high\", \"xhigh\", \"max\", \"ultra\"]),\n                        \"output_schema\": _p(\n")
    backup = path.with_name(path.name + ".jev.bak")
    if backup.exists() and backup.read_bytes() != path.read_bytes():
        raise RuntimeError("Existing backup differs; refusing to overwrite")
    if not backup.exists():
        backup.write_bytes(path.read_bytes())
    temporary = path.with_name(path.name + ".jev.tmp")
    temporary.write_bytes(changed.encode("utf-8"))
    try:
        py_compile.compile(str(temporary), doraise=True)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def undo(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    backup = path.with_name(path.name + ".jev.bak")
    if MARKER not in source or not backup.exists():
        return False
    backup.replace(path)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--undo", action="store_true")
    args = parser.parse_args()
    print(undo(args.path) if args.undo else install(args.path))
