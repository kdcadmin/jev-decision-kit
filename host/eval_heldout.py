# Compare rule-only, rules+JEV, and rules+JEV+memory on the frozen eval file.
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host.gate import available_gates, decision_from_votes, sentence_names
import cabinet

EVAL_FILE = ROOT / "tests" / "eval_cases.json"


def _names(decided: dict) -> list[str]:
    return [str(item.get("name") or "") for item in (decided.get("skills") or []) if item.get("name")]


def _rules_only(task: str, gates: list[dict]) -> list[str]:
    votes = {gate["id"]: (1.0 if sentence_names(task, gate) else 0.0) for gate in gates}
    return _names(decision_from_votes(votes, gates, None, {}, task))


def _route(task: str) -> list[str]:
    return _names(cabinet.route_task(task, "eval", record=False))


def _same(got: list[str], expect: list[str]) -> tuple[bool, bool]:
    exact = got == expect
    miss = [name for name in expect if name not in got]
    extra = [name for name in got if name not in expect]
    return exact, not miss and not extra


def main() -> None:
    payload = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    catalog = cabinet.load_catalog()
    from host.plugin_inventory import plugin_gates

    gates = available_gates(catalog) + plugin_gates()
    modes = ("rules", "rules_jev", "rules_jev_memory")
    tally = {mode: {"exact": 0, "ok": 0, "miss": 0, "extra": 0} for mode in modes}
    print("n", len(cases))
    for item in cases:
        task = str(item.get("text") or "")
        expect = [str(name) for name in (item.get("expect") or [])]
        with patch("host.tool_memory.remembered_doors", return_value=set()), patch(
            "cabinet.load_memory", return_value={"rules": []}
        ):
            jev = _route(task)
        memory = _route(task)
        scored = {
            "rules": _rules_only(task, gates),
            "rules_jev": jev,
            "rules_jev_memory": memory,
        }
        for mode, got in scored.items():
            exact, ok = _same(got, expect)
            tally[mode]["exact"] += int(exact)
            tally[mode]["ok"] += int(ok)
            if not ok:
                miss = [name for name in expect if name not in got]
                extra = [name for name in got if name not in expect]
                tally[mode]["miss"] += len(miss)
                tally[mode]["extra"] += len(extra)
                print(mode, task, "got", got, "expect", expect, "miss", miss, "extra", extra)
    total = len(cases)
    for mode in modes:
        row = tally[mode]
        print(
            mode,
            "exact",
            str(row["exact"]) + "/" + str(total),
            "set",
            str(row["ok"]) + "/" + str(total),
            "miss",
            row["miss"],
            "extra",
            row["extra"],
        )


if __name__ == "__main__":
    main()
