# Compare rule-only, rules+JEV, and rules+JEV+fixed-memory. Does not read this machine's live memory.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host.gate import available_gates, decision_from_votes, sentence_names
from host.tool_memory import remembered_doors
import cabinet

EVAL_FILE = ROOT / "tests" / "eval_cases.json"
BLIND_FILE = ROOT / "tests" / "eval_blind.json"
MEMORY_FILE = ROOT / "tests" / "memory_fixture.json"


def _names(decided: dict) -> list[str]:
    return [str(item.get("name") or "") for item in (decided.get("skills") or []) if item.get("name")]


def _rules_only(task: str, gates: list[dict]) -> list[str]:
    votes = {gate["id"]: (1.0 if sentence_names(task, gate) else 0.0) for gate in gates}
    return _names(decision_from_votes(votes, gates, None, {}, task))


def _route(task: str) -> list[str]:
    return _names(cabinet.route_task(task, "eval", record=False))


def _same(got: list[str], expect: list[str]) -> tuple[bool, bool]:
    miss = [name for name in expect if name not in got]
    extra = [name for name in got if name not in expect]
    return got == expect, not miss and not extra


def jev_case_rows(head_path: Path | None = None) -> list[dict]:
    import host.jev as jev

    saved = jev.WEIGHTS
    payload = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    rows = []
    if head_path is not None:
        jev.WEIGHTS = Path(head_path)
        jev.cache_clear()
    try:
        with patch("host.tool_memory.remembered_doors", return_value=set()), patch(
            "cabinet.load_memory", return_value={"rules": []}
        ):
            for item in cases:
                text = str(item.get("text") or "")
                expect = [str(name) for name in (item.get("expect") or [])]
                got = _route(text)
                _exact, ok = _same(got, expect)
                rows.append({"text": text, "expect": expect, "got": got, "ok": ok, "scores": jev.score_task(text)})
    finally:
        if head_path is not None:
            jev.WEIGHTS = saved
            jev.cache_clear()
    return rows


def jev_set_ok(path: Path | None = None) -> tuple[int, int]:
    rows = jev_case_rows(path)
    return sum(int(row["ok"]) for row in rows), len(rows)


def _run(name: str, cases: list[dict], gates: list[dict], samples: list[dict]) -> None:
    modes = ("rules", "rules_jev", "rules_jev_memory")
    tally = {mode: {"exact": 0, "ok": 0, "miss": 0, "extra": 0} for mode in modes}
    print("set", name, "n", len(cases))
    for item in cases:
        task = str(item.get("text") or "")
        expect = [str(label) for label in (item.get("expect") or [])]
        with patch("host.tool_memory.remembered_doors", return_value=set()), patch(
            "cabinet.load_memory", return_value={"rules": []}
        ):
            jev = _route(task)
        with patch(
            "host.tool_memory.remembered_doors",
            lambda text, samples_arg=None, line=0.72: remembered_doors(text, samples, line),
        ), patch("cabinet.load_memory", return_value={"rules": []}):
            memory = _route(task)
        scored = {"rules": _rules_only(task, gates), "rules_jev": jev, "rules_jev_memory": memory}
        for mode, got in scored.items():
            exact, ok = _same(got, expect)
            tally[mode]["exact"] += int(exact)
            tally[mode]["ok"] += int(ok)
            if not ok:
                miss = [label for label in expect if label not in got]
                extra = [label for label in got if label not in expect]
                tally[mode]["miss"] += len(miss)
                tally[mode]["extra"] += len(extra)
                print(mode, task, "got", got, "expect", expect, "miss", miss, "extra", extra)
    total = len(cases) or 1
    for mode in modes:
        row = tally[mode]
        print(
            name,
            mode,
            "exact",
            str(row["exact"]) + "/" + str(len(cases)),
            "set",
            str(row["ok"]) + "/" + str(len(cases)),
            "miss",
            row["miss"],
            "extra",
            row["extra"],
        )
    del total
    jev_ok = tally["rules_jev"]["ok"]
    mem_ok = tally["rules_jev_memory"]["ok"]
    print(name, "memory_delta", mem_ok - jev_ok)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blind", action="store_true")
    args = parser.parse_args()
    catalog = cabinet.load_catalog()
    from host.plugin_inventory import plugin_gates

    gates = available_gates(catalog) + plugin_gates()
    samples = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    payload = json.loads((BLIND_FILE if args.blind else EVAL_FILE).read_text(encoding="utf-8"))
    _run("blind" if args.blind else "regression", payload.get("cases") or [], gates, samples)


if __name__ == "__main__":
    main()
