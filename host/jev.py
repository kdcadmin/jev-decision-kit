# Local door scores. One linear head per door, trained in host/train_jev.py.
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "models" / "jev" / "head.json"


def ngrams(text: str) -> list[str]:
    raw = (text or "").strip().lower()
    found = []
    for size in (2, 3, 4):
        if len(raw) < size:
            continue
        for index in range(len(raw) - size + 1):
            found.append(raw[index : index + size])
    return found


def _sigmoid(value: float) -> float:
    if value >= 20:
        return 1.0
    if value <= -20:
        return 0.0
    return 1.0 / (1.0 + math.exp(-value))


_HEAD = None
_HEAD_STAMP = None


def load_head() -> dict:
    global _HEAD, _HEAD_STAMP
    stamp = WEIGHTS.stat().st_mtime_ns if WEIGHTS.is_file() else 0
    if _HEAD is None or stamp != _HEAD_STAMP:
        _HEAD = json.loads(WEIGHTS.read_text(encoding="utf-8"))
        _HEAD_STAMP = stamp
    return _HEAD


def cache_clear() -> None:
    global _HEAD, _HEAD_STAMP
    _HEAD = None
    _HEAD_STAMP = None


def score_task(task: str, gate_ids: list[str] | None = None) -> dict[str, float]:
    head = load_head()
    labels = list(head["labels"])
    wanted = set(gate_ids) if gate_ids is not None else set(labels)
    index = {gram: pos for pos, gram in enumerate(head["vocab"])}
    present = {index[gram] for gram in ngrams(task) if gram in index}
    bias = head["bias"]
    rows = head["weight"]
    scores = {}
    for label_index, label in enumerate(labels):
        if label not in wanted:
            continue
        logit = float(bias[label_index])
        row = rows[label_index]
        for key in present:
            logit += float(row[key])
        scores[label] = round(_sigmoid(logit), 4)
    for label in wanted:
        scores.setdefault(label, 0.0)
    return scores
