from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.eval_heldout import MEMORY_FILE, _route, _rules_only, _same
from host.gate import available_gates
from host.plugin_inventory import plugin_gates
from host.tool_memory import remembered_doors
import cabinet

INCIDENTS = [
    ("提问误开技能", "PDF 是什么", "把「是什么」当成导出 PDF"),
    ("不要 Word 仍打开", "不要用 Word", "否定被习惯盖掉"),
    ("WordPress 当成 Word", "我说的是WordPress建站，不是Word文档", "排除句被当成建站/Word"),
    ("只要一个赢家", "把刚才的会写成纪要，再整理成 Word，并做成一套幻灯片。", "纪要+Word+幻灯片收成一门"),
    ("否定 PDF 要论文", "不要用 PDF，给我论文", "关掉 PDF 后论文也没了"),
    ("网页操作漏选", "填表提交之后导出成 PDF", "只开 PDF，漏掉填表提交"),
    ("多门并列股价", "查一下贵州茅台现在的股价，把数字放进 Excel，不要写 Word。", "要 Excel 时仍打开 Word"),
    ("登录页换说法", "在登录页填完再点提交", "盲测：换一种说法就没了"),
]


def got_for(text: str) -> dict[str, list[str]]:
    catalog = cabinet.load_catalog()
    gates = available_gates(catalog) + plugin_gates()
    samples = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    rules = _rules_only(text, gates)
    with patch("host.tool_memory.remembered_doors", return_value=set()), patch(
        "cabinet.load_memory", return_value={"rules": []}
    ):
        jev = _route(text)
    with patch(
        "host.tool_memory.remembered_doors",
        lambda value, samples_arg=None, line=0.72: remembered_doors(value, samples, line),
    ), patch("cabinet.load_memory", return_value={"rules": []}):
        memory = _route(text)
    return {"rules": rules, "jev": jev, "memory": memory}


def mark(got: list[str], expect: list[str]) -> str:
    exact, ok = _same(got, expect)
    if ok:
        return "过"
    miss = [name for name in expect if name not in got]
    extra = [name for name in got if name not in expect]
    bits = []
    if miss:
        bits.append("漏 " + "、".join(miss))
    if extra:
        bits.append("误开 " + "、".join(extra))
    return "；".join(bits) or "错"


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main() -> None:
    cases = {item["text"]: item for item in json.loads((ROOT / "tests" / "eval_cases.json").read_text(encoding="utf-8"))["cases"]}
    cases.update({item["text"]: item for item in json.loads((ROOT / "tests" / "eval_blind.json").read_text(encoding="utf-8"))["cases"]})
    rows = []
    for title, text, was in INCIDENTS:
        expect = list(cases[text]["expect"])
        got = got_for(text)
        row = {
            "title": title,
            "was": was,
            "text": text,
            "expect": expect,
            "rules": mark(got["rules"], expect),
            "jev": mark(got["jev"], expect),
            "memory": mark(got["memory"], expect),
            "got": got,
        }
        rows.append(row)
        print(title, "expect", expect, "rules", got["rules"], "jev", got["jev"], "memory", got["memory"])

    height = 64 + 36 * len(rows) + 48
    width = 1100
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#f7f6f2"/>',
        '<text x="24" y="32" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#1c211c">以前选错的那些句，现在还错不错</text>',
        '<text x="24" y="52" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="#5c6560">纵列是同一评测句。过=集合匹配。漏=该开没开。误开=不该开却开了。</text>',
    ]
    headers = [("24", "以前的坑"), ("220", "例句"), ("560", "规则"), ("740", "JEV"), ("920", "JEV+记忆")]
    y0 = 78
    for x, label in headers:
        parts.append(
            f'<text x="{x}" y="{y0}" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" font-weight="700" fill="#5c6560">{label}</text>'
        )
    parts.append(f'<line x1="24" y1="{y0 + 8}" x2="{width - 24}" y2="{y0 + 8}" stroke="#d5d1c7"/>')

    def cell_color(flag: str) -> str:
        if flag == "过":
            return "#0c6b52"
        return "#8f3d32"

    for i, row in enumerate(rows):
        y = y0 + 28 + i * 36
        if i % 2 == 0:
            parts.append(f'<rect x="16" y="{y - 18}" width="{width - 32}" height="36" fill="#e7f3ee"/>')
        short = row["text"] if len(row["text"]) <= 22 else row["text"][:21] + "…"
        parts.append(
            f'<text x="24" y="{y}" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="13" fill="#1c211c">{esc(row["title"])}</text>'
        )
        parts.append(
            f'<text x="220" y="{y}" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="#5c6560">{esc(short)}</text>'
        )
        for x, key in (("560", "rules"), ("740", "jev"), ("920", "memory")):
            flag = row[key]
            shown = flag if len(flag) <= 16 else flag[:15] + "…"
            parts.append(
                f'<text x="{x}" y="{y}" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="{cell_color(flag)}">{esc(shown)}</text>'
            )
    parts.append(
        f'<text x="24" y="{height - 14}" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="11" fill="#5c6560">来源：回归集与盲测原句。登录页换说法仍漏 agent-browser。JEV 单独漏论文和填表；记忆补上这两句。</text>'
    )
    parts.append("</svg>")
    (ROOT / "docs" / "compare-failures.svg").write_text("".join(parts), encoding="utf-8")

    # counts of those 8 incidents passing
    def count_pass(key: str) -> int:
        return sum(1 for row in rows if row[key] == "过")

    n = len(rows)
    # reuse simple bar svg
    W, H = 920, 360
    left, top, plot_h = 70, 64, 220
    cats = ["这 8 类旧事故现在过了几条"]
    series = [
        ("规则", count_pass("rules"), "#1c211c"),
        ("JEV", count_pass("jev"), "#5c6560"),
        ("JEV+记忆", count_pass("memory"), "#0c6b52"),
    ]
    bar_w = 140
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="#f7f6f2"/>',
        '<text x="24" y="32" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#1c211c">旧事故覆盖（8 条代表句）</text>',
        '<text x="24" y="52" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="#5c6560">提问误开、否定、WordPress、多门并列、论文/网页操作、股价不要 Word、登录页换说法。</text>',
    ]
    for i in range(0, n + 1):
        y = top + plot_h * (1 - i / n)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{W - 24}" y2="{y:.1f}" stroke="#d5d1c7"/>')
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" font-family="Segoe UI" fill="#5c6560">{i}/{n}</text>'
        )
    gx = 160
    for i, (name, value, color) in enumerate(series):
        h = plot_h * value / n
        x = gx + i * (bar_w + 48)
        y = top + plot_h - h
        parts.append(f'<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" fill="{color}"/>')
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-size="14" font-family="Segoe UI" fill="#1c211c">{value}/{n}</text>'
        )
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h + 24}" text-anchor="middle" font-size="13" font-family="Noto Sans SC, Segoe UI" fill="#1c211c">{name}</text>'
        )
    parts.append(
        f'<text x="24" y="{H - 16}" font-size="11" font-family="Noto Sans SC, Segoe UI" fill="#5c6560">满分 8。JEV 单独会漏「不要 PDF，给我论文」和「填表提交之后导出成 PDF」。记忆补上。登录页盲测三列都还漏。</text>'
    )
    parts.append("</svg>")
    (ROOT / "docs" / "compare-errors.svg").write_text("".join(parts), encoding="utf-8")
    print("wrote charts")


if __name__ == "__main__":
    main()
