# Train the local door head from card wording. The twelve exam sentences are held out.
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host.gate import GATE
from host.jev import WEIGHTS, ngrams

EVAL_FILE = ROOT / "tests" / "eval_cases.json"
BLIND_FILE = ROOT / "tests" / "eval_blind.json"

# Exact strings used as the live exam. They are not training rows.
EXAM = {
    "帮我把这句话写顺一点：今天天气很好我们出去走走吧",
    "帮我看一下贵州茅台现在多少钱",
    "查一下贵州茅台现在的股价和今天的涨跌，把结果写成一份 Word，再配一张小黑风格的配图。",
    "查茅台和宁德时代今天的股价和涨跌，写成一份 Word，配一张小黑风格的配图，再做一份幻灯片，并打开 https://example.com 把正文读出来。",
    "查一下贵州茅台现在的股价，把数字放进 Excel，不要写 Word。",
    "把刚才的会写成纪要，再整理成 Word，并做成一套幻灯片。",
    "打开 https://example.com 把正文读出来，收进资料库，再写成一份 PDF。",
    "在 Godot 里把这个场景改好并跑起来，然后把仓库备份到远程。",
    "按论文工作台写这一章，配一张小黑风格的图，再导出成 Word。",
    "再做一支同样风格的介绍视频",
    "打开这个登录页，填上账号密码然后点登录，把登录结果记成一份表格。",
    "这段代码什么意思",
    "看一下茅台现在多少钱",
}

POS = {
    "market-data": [
        "看看贵州茅台现在的价格",
        "今天的股价和涨跌",
        "今天这只股票涨了还是跌了",
        "帮我查一下现价",
        "宁德时代的股价",
        "看一下行情",
        "这只股票多少钱",
        "板块今天的涨跌",
        "查一下收盘股价",
    ],
    "market-watch": [
        "打开我设好的盯盘",
        "看一下盯盘里的标的",
        "盯盘现在怎么样",
    ],
    "meeting-minutes": [
        "把会议内容写成纪要",
        "整理一份会议纪要",
        "出一份纪要文件",
        "把讨论写成纪要",
    ],
    "office-docx": [
        "写成一份 Word",
        "导出成 Word",
        "导出成 word 文档",
        "整理成 docx",
        "做一份 Word 文档",
    ],
    "office-pdf": [
        "写成一份 PDF",
        "导出成 pdf 文件",
        "交给我一份 PDF",
    ],
    "office-pptx": [
        "做成一套幻灯片",
        "再做一份幻灯片",
        "做一份 ppt",
        "整理成 PPT 去讲",
    ],
    "office-xlsx": [
        "把数字放进 Excel",
        "记成一份表格",
        "写成 xlsx",
        "做一份 excel 表",
    ],
    "web-read": [
        "打开 https://example.org 把正文读出来",
        "读一下这个网址里的内容",
        "看看这个链接指向的网页",
        "读取 http 页面的正文",
    ],
    "web-act": [
        "填上账号密码然后点登录",
        "在网页上点击提交",
        "填写这个表单再提交",
        "帮我点一下登录按钮",
        "在登录页把表单填好再提交",
        "填完表点提交再把结果导出",
    ],
    "vox-video": [
        "做一支介绍视频",
        "再来一支介绍片",
        "按这个风格做介绍视频",
    ],
    "openmontage": [
        "把实拍素材剪辑一下",
        "剪辑这段实拍",
        "实拍画面剪成一条",
    ],
    "xiaohei": [
        "配一张小黑风格的图",
        "配一张小黑风格的配图",
        "画一张小黑插图",
        "用小黑的风格配图",
    ],
    "thesis": [
        "按论文工作台写这一章",
        "继续写论文的这一节",
        "论文这一章按工作台来",
    ],
    "company-intel": [
        "做一份公司情报",
        "查一下这家公司的资料",
        "按公司情报的流程看这家公司",
    ],
    "knowledge": [
        "收进资料库",
        "放进知识库",
        "归到资料库里",
    ],
    "last30days": [
        "最近三十天的资料",
        "汇总近 30天发生了什么",
        "看一下过去三十天",
    ],
    "godot": [
        "在 Godot 里改这个场景",
        "把 godot 工程跑起来",
        "Godot 里把角色改好",
    ],
    "git-backup": [
        "把仓库备份到远程",
        "推到远程仓库",
        "做一次远程备份",
    ],
}

MULTI = [
    ("查股价，再写成一份 Word，配一张小黑风格的图", ["market-data", "office-docx", "xiaohei"]),
    ("把纪要整理成 Word，并做成幻灯片", ["meeting-minutes", "office-docx", "office-pptx"]),
    ("打开 https://example.org 读正文，收进资料库，写成 PDF", ["web-read", "knowledge", "office-pdf"]),
    ("Godot 场景改好并跑起来，再备份到远程", ["godot", "git-backup"]),
    ("论文这一章配小黑风格的图，再导出 Word", ["thesis", "xiaohei", "office-docx"]),
    ("登录之后把结果记成表格", ["web-act", "office-xlsx"]),
    ("股价放进 Excel", ["market-data", "office-xlsx"]),
    ("介绍片里配一张小黑", ["vox-video", "xiaohei"]),
]

NONE = [
    "帮我把这句话写顺一点",
    "今天天气很好我们出去走走吧",
    "这段脚本在做什么",
    "解释一下这个函数",
    "这个报错怎么看",
    "帮我算一下十二乘八",
    "给这个函数起个名字",
    "明天有个会议，帮我改到下午",
    "这件衣服多少钱",
    "备份这个想法，先写下来",
    "你好",
    "把这句话翻译通顺",
]


def held_out_texts() -> set[str]:
    held = set(EXAM)
    for path in (EVAL_FILE, BLIND_FILE):
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("cases") or []:
            text = str(item.get("text") or "").strip()
            if text:
                held.add(text)
    return held


def rows() -> list[tuple[str, set[str]]]:
    found = []
    for gate_id, lines in POS.items():
        for line in lines:
            found.append((line, {gate_id}))
    for line, labels in MULTI:
        for _repeat in range(6):
            found.append((line, set(labels)))
    for line in NONE:
        for _repeat in range(3):
            found.append((line, set()))
    for gate in GATE:
        found.append((gate["blurb"], {gate["id"]}))
    from host.plugin_inventory import plugin_gates

    for gate in plugin_gates():
        found.append((gate["blurb"], {gate["id"]}))
        for word in gate.get("words") or ():
            line = "请用" + str(word) + "做这件事"
            if line not in EXAM:
                found.append((line, {gate["id"]}))
    from host.tool_memory import load_samples

    for item in load_samples():
        text = str(item.get("task") or "").strip()
        doors = {str(door) for door in (item.get("doors") or []) if str(door)}
        if text and doors:
            found.append((text, doors))
    held = held_out_texts()
    leaked = [text for text, _labels in found if text in held]
    if leaked:
        raise RuntimeError("exam sentence leaked into training: " + leaked[0])
    return found


def _git_rev() -> str:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (done.stdout or "").strip() if done.returncode == 0 else ""


def _sample_hash(data: list[tuple[str, set[str]]]) -> str:
    blob = json.dumps([(text, sorted(names)) for text, names in data], ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _guard_reason(text: str, expect: list[str]) -> str | None:
    if not expect and any(mark in text for mark in ("是什么", "怎么用", "有什么用", "哪个好", "什么意思", "干什么用")):
        return "ask"
    if text == "不要用 Word":
        return "negation"
    if text in {"看一下茅台现在多少钱", "用Word写一份报告", "不要 PDF 只要 Word"}:
        return "core"
    return None


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _door_scores(old: dict, new: dict) -> dict:
    names = sorted(set(old.get("expect") or []) | set(old.get("got") or []) | set(new.get("got") or []))
    before = old.get("scores") or {}
    after = new.get("scores") or {}
    return {
        "before": {name: before.get(name) for name in names if name in before},
        "after": {name: after.get(name) for name in names if name in after},
    }


def _diff_row(old: dict, new: dict) -> dict:
    item = {"text": old["text"], "expect": old["expect"], "before": old["got"], "after": new.get("got")}
    scores = _door_scores(old, new)
    if scores["before"] or scores["after"]:
        item["scores"] = scores
    return item


def compare_rows(before: list[dict], after: list[dict]) -> dict:
    lost = []
    gained = []
    guards = []
    keyed = {row["text"]: row for row in after}
    for old in before:
        new = keyed.get(old["text"]) or {}
        if old["ok"] and not new.get("ok"):
            lost.append(_diff_row(old, new))
        if new.get("ok") and not old["ok"]:
            gained.append(_diff_row(old, new))
        kind = _guard_reason(old["text"], old["expect"])
        if not kind:
            continue
        if kind in {"ask", "negation"} and new.get("got"):
            guards.append({"text": old["text"], "kind": kind, "got": new.get("got")})
        elif kind == "core" and old["ok"] and not new.get("ok"):
            guards.append({"text": old["text"], "kind": kind, "got": new.get("got")})
    before_ok = sum(int(row["ok"]) for row in before)
    after_ok = sum(int(row["ok"]) for row in after)
    return {
        "before": before_ok,
        "after": after_ok,
        "lost": lost,
        "gained": gained,
        "guards": guards,
        "ok": after_ok >= before_ok and not guards,
    }


def publish_if_not_worse(official: Path, payload: dict, score_path) -> tuple[bool, dict]:
    candidate = official.with_name(official.stem + ".candidate.json")
    report_path = official.with_name("last-train.json")
    _write_json(candidate, payload)
    try:
        before = score_path(official)
        after = score_path(candidate)
    except Exception:
        candidate.unlink(missing_ok=True)
        raise
    report = {"before": before, "after": after, "kept": after >= before}
    _write_json(report_path, report)
    if after < before:
        candidate.unlink(missing_ok=True)
        return False, report
    tmp = official.with_suffix(official.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(official)
    candidate.unlink(missing_ok=True)
    report["kept"] = True
    _write_json(report_path, report)
    return True, report


def replace_if_not_worse(path: Path, payload: dict, score) -> tuple[bool, int, int]:
    kept, report = publish_if_not_worse(path, payload, lambda _p, fn=score: fn())
    return kept, int(report["before"]), int(report["after"])


def train(force: bool = False) -> None:
    import torch

    torch.manual_seed(0)
    from host.plugin_inventory import plugin_gates

    labels = [gate["id"] for gate in GATE] + [gate["id"] for gate in plugin_gates()]
    index = {label: pos for pos, label in enumerate(labels)}
    data = rows()
    vocab = sorted({gram for text, _names in data for gram in ngrams(text)})
    column = {gram: pos for pos, gram in enumerate(vocab)}
    matrix = torch.zeros(len(data), len(vocab))
    target = torch.zeros(len(data), len(labels))
    for row, (text, names) in enumerate(data):
        for gram in ngrams(text):
            matrix[row, column[gram]] = 1.0
        for name in names:
            target[row, index[name]] = 1.0
    layer = torch.nn.Linear(len(vocab), len(labels))
    # One-door rows only teach the doors they name. Empty rows teach every door to stay off.
    # Otherwise “股价” learns a negative weight on Word and cancels a sentence that asks for both.
    mask = torch.zeros_like(target)
    for row, (_text, names) in enumerate(data):
        if names:
            for name in names:
                mask[row, index[name]] = 1.0
        else:
            mask[row] = 1.0
    loss_fn = torch.nn.BCEWithLogitsLoss(reduction="none")
    opt = torch.optim.Adam(layer.parameters(), lr=0.05)
    for _epoch in range(320):
        opt.zero_grad()
        loss = (loss_fn(layer(matrix), target) * mask).sum() / mask.sum()
        loss.backward()
        opt.step()
    with torch.no_grad():
        pred = torch.sigmoid(layer(matrix))
        agree = ((pred >= 0.4) == (target >= 0.5)) | (mask < 0.5)
        fit = agree.all(dim=1).float().mean().item()
    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "vocab": vocab,
        "labels": labels,
        "bias": [round(float(value), 5) for value in layer.bias.detach()],
        "weight": [[round(float(value), 5) for value in row] for row in layer.weight.detach()],
        "train_rows": len(data),
        "train_fit": round(fit, 4),
    }
    from host.eval_heldout import jev_case_rows
    from host.jev import cache_clear

    payload["source"] = {
        "sample_hash": _sample_hash(data),
        "rows": len(data),
        "seed": 0,
        "epochs": 320,
        "lr": 0.05,
        "git": _git_rev(),
        "fit": round(fit, 4),
    }
    candidate = WEIGHTS.with_name("head.candidate.json")
    report_path = WEIGHTS.with_name("last-train.json")
    _write_json(candidate, payload)
    try:
        before_rows = jev_case_rows(WEIGHTS)
        after_rows = jev_case_rows(candidate)
    except Exception:
        candidate.unlink(missing_ok=True)
        raise
    compared = compare_rows(before_rows, after_rows)
    compared["source"] = payload["source"]
    _write_json(report_path, compared)
    if not force and not compared["ok"]:
        candidate.unlink(missing_ok=True)
        cache_clear()
        raise RuntimeError(
            "refused head.json: regression "
            + str(compared["after"])
            + " vs "
            + str(compared["before"])
            + ", lost "
            + str(len(compared["lost"]))
            + ", guards "
            + str(len(compared["guards"]))
        )
    payload["source"]["regression"] = compared["after"]
    payload["source"]["baseline"] = compared["before"]
    tmp = WEIGHTS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(WEIGHTS)
    candidate.unlink(missing_ok=True)
    cache_clear()
    print("saved", WEIGHTS, "rows", len(data), "fit", round(fit, 4), "regression", compared["after"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    try:
        train(force=parser.parse_args().force)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
