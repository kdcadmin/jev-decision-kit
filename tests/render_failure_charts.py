"""README charts: the 33 sentences Laya actually scored on 2026-09-27.

Laya column is the saved run (threshold 0.5, at most 3 doors, 15/33 exact).
jev-decision column is route_task on the same sentences, record=False, 2026-09-27 evening.
Exact means the doors that should stay are all there and nothing extra is kept.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# task, group, laya_got, laya_ok, jev_got, jev_ok
ROWS = [
    ("帮我看一下贵州茅台现在多少钱", "每道门", "行情 0.83", True, "行情", True),
    ("盯盘今天有没有提醒", "每道门", "自己做", False, "盯盘", True),
    ("把刚才的会整理成纪要", "每道门", "自己做（纪要 0.31）", False, "会议纪要", True),
    ("按模板写一份 Word", "每道门", "自己做（Word 0.44）", False, "Word", True),
    ("读一下这个 PDF", "每道门", "自己做（PDF 0.24）", False, "PDF", True),
    ("做一套幻灯片文件", "每道门", "幻灯片 0.71", True, "幻灯片", True),
    ("把这张表算一下", "每道门", "表格 0.58", True, "表格", True),
    ("打开这个网页把正文摘出来", "每道门", "操作网页、读网页、Godot", False, "读网页", True),
    ("在网页上把这个表单填完", "每道门", "操作网页 0.59", True, "操作网页", True),
    ("再做一支同样风格的介绍视频", "每道门", "介绍视频 0.52", True, "介绍视频", True),
    ("把这几段实拍剪到一起", "每道门", "自己做（0.29）", False, "实拍剪辑", True),
    ("给这篇文章画一张小黑风格的图", "每道门", "小黑插图 0.81", True, "小黑插图", True),
    ("用本机模型把这张图生成视频", "每道门", "自己做（0.45）", True, "自己做", True),
    ("做一段背景音乐", "每道门", "出音乐 0.77", False, "自己做", True),
    ("把这张照片做成表情包", "每道门", "表情贴纸 0.81", False, "自己做", True),
    ("按论文工作台写这一章", "每道门", "论文 0.90", True, "论文", True),
    ("查一下这家公司", "每道门", "读网页、公司情报", False, "公司情报", True),
    ("把这些资料收进资料库", "每道门", "自己做（0.44）", False, "资料库", True),
    ("最近三十天这个话题有什么", "每道门", "自己做", False, "近三十天", True),
    ("在 Godot 里把这个场景跑起来", "每道门", "自己做（0.48）", False, "Godot", True),
    ("把这个项目推到远程", "每道门", "自己做", False, "远程备份", True),
    ("帮我把这句话写顺一点", "每道门", "自己做", True, "自己做", True),
    ("这段代码什么意思", "每道门", "读网页 0.66", False, "自己做", True),
    ("查股价、写成 Word、配小黑图", "一句多门", "行情、Word、小黑", True, "行情、Word、小黑", True),
    ("打开 https://example.com 把正文读出来", "换说法", "读网页 0.86", True, "读网页", True),
    ("打开登录页，填账号密码然后点登录", "换说法", "操作网页、表格", False, "操作网页", True),
    ("宁德时代今天涨了多少，整理进 Excel", "换说法", "只留行情", False, "行情、表格", True),
    ("再来一支大肥鱼的介绍片，剧情换成上班", "换说法", "介绍视频 0.73", True, "介绍视频", True),
    ("股价、Word、小黑图、幻灯片", "超过三道", "丢掉行情（最多 3 道）", False, "四道都留", True),
    ("这段话帮我改得顺一点就行", "换说法", "自己做", True, "自己做", True),
    ("用 MiniMax 出一张图", "换说法", "自己做（0.07）", True, "自己做", True),
    ("把仓库备份到远程", "换说法", "远程备份 0.98", True, "远程备份", True),
    ("最近一个月大家在讨论什么", "换说法", "自己做", False, "近三十天", True),
]


def svg_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write(name: str, body: str) -> None:
    (DOCS / name).write_text(body, encoding="utf-8", newline="\n")


def group_rates() -> list[tuple[str, int, int, int]]:
    order = ["每道门", "一句多门", "换说法", "超过三道"]
    out = []
    for name in order:
        rows = [row for row in ROWS if row[1] == name]
        out.append(
            (
                name,
                len(rows),
                sum(1 for row in rows if row[3]),
                sum(1 for row in rows if row[5]),
            )
        )
    return out


def overview() -> str:
    w, h = 960, 420
    groups = group_rates()
    laya = sum(1 for row in ROWS if row[3])
    jev = sum(1 for row in ROWS if row[5])
    n = len(ROWS)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="#f7f6f2"/>',
        '<text x="24" y="30" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#1c211c">同一批 33 句：Laya 当时 vs jev-decision</text>',
        f'<text x="24" y="52" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="#5c6560">Laya 是 2026-09-27 实测：逐门打分，过 0.5，最多留 3 道，刚好选对 {laya}/{n}。jev-decision 是现行选择器重跑这 33 句，{jev}/{n}。纵轴是刚好选对的比例。</text>',
    ]
    left, right, top, bottom = 64, 920, 78, 320
    plot_h = bottom - top
    for tick in (0, 25, 50, 75, 100):
        y = bottom - plot_h * tick / 100
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#d5d1c7"/>')
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" font-family="Segoe UI, sans-serif" fill="#5c6560">{tick}</text>'
        )
    cats = [("全部 33 句", laya, jev, n)] + [(name, a, b, count) for name, count, a, b in groups]
    gap = (right - left) / len(cats)
    bar_w = 28
    for i, (name, a, b, count) in enumerate(cats):
        cx = left + gap * (i + 0.5)
        for dx, value, color in ((-bar_w - 3, 100 * a / count, "#1c211c"), (3, 100 * b / count, "#0c6b52")):
            bh = max(4, plot_h * value / 100)
            y = bottom - bh
            parts.append(f'<rect x="{cx + dx:.1f}" y="{y:.1f}" width="{bar_w}" height="{bh:.1f}" fill="{color}"/>')
            parts.append(
                f'<text x="{cx + dx + bar_w / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-size="11" font-family="Segoe UI, sans-serif" fill="{color}">{value:.0f}</text>'
            )
        parts.append(
            f'<text x="{cx:.1f}" y="{bottom + 22}" text-anchor="middle" font-size="13" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">{svg_escape(name)}</text>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{bottom + 40}" text-anchor="middle" font-size="11" font-family="Segoe UI, sans-serif" fill="#5c6560">{a}/{count} → {b}/{count}</text>'
        )
    parts += [
        '<rect x="48" y="388" width="12" height="12" fill="#1c211c"/>',
        '<text x="66" y="399" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">Laya 当时</text>',
        '<rect x="168" y="388" width="12" height="12" fill="#0c6b52"/>',
        '<text x="186" y="399" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">jev-decision</text>',
        '<text x="340" y="399" font-size="11" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">没有技能和插件的 4 句，自己做算对。</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def table() -> str:
    row_h = 26
    height = 86 + row_h * len(ROWS) + 28
    width = 1100
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#f7f6f2"/>',
        '<text x="24" y="28" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#1c211c">33 句逐条：Laya 留下什么，jev-decision 留下什么</text>',
        '<text x="24" y="48" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="#5c6560">对 = 该留的门都在，且没有多出来的门。Laya 数字来自当时那次打分。</text>',
        '<text x="24" y="72" font-size="12" font-weight="700" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">句子</text>',
        '<text x="430" y="72" font-size="12" font-weight="700" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">Laya 当时</text>',
        '<text x="760" y="72" font-size="12" font-weight="700" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">jev-decision</text>',
        '<line x1="24" y1="80" x2="1076" y2="80" stroke="#d5d1c7"/>',
    ]
    for i, (task, _group, laya_got, laya_ok, jev_got, jev_ok) in enumerate(ROWS):
        y = 100 + i * row_h
        if jev_ok and not laya_ok:
            bg = "#e7f3ee"
        elif laya_ok and not jev_ok:
            bg = "#f6e8e4"
        elif i % 2 == 0:
            bg = "#fff"
        else:
            bg = ""
        if bg:
            parts.append(f'<rect x="16" y="{y - 16}" width="1068" height="{row_h}" fill="{bg}"/>')
        short = task if len(task) <= 28 else task[:27] + "…"
        parts.append(f'<text x="24" y="{y}" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">{svg_escape(short)}</text>')
        parts.append(
            f'<text x="430" y="{y}" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="{"#0c6b52" if laya_ok else "#8f3d32"}">{svg_escape(("对 · " if laya_ok else "错 · ") + laya_got)}</text>'
        )
        parts.append(
            f'<text x="760" y="{y}" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="{"#0c6b52" if jev_ok else "#8f3d32"}">{svg_escape(("对 · " if jev_ok else "错 · ") + jev_got)}</text>'
        )
    parts.append(
        f'<text x="24" y="{height - 12}" font-size="11" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">本机出视频、背景音乐、表情包、MiniMax 出图没有技能和插件，自己做算对。Laya 当时打开出音乐和表情贴纸，现在算多开。</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def moved() -> str:
    better = sum(1 for row in ROWS if row[5] and not row[3])
    worse = sum(1 for row in ROWS if row[3] and not row[5])
    same_ok = sum(1 for row in ROWS if row[3] and row[5])
    same_bad = sum(1 for row in ROWS if not row[3] and not row[5])
    w, h = 960, 220
    items = [
        ("两边都对", same_ok, "#0c6b52"),
        ("Laya 错，现在对", better, "#0c6b52"),
        ("Laya 对，现在错", worse, "#8f3d32"),
        ("两边都错", same_bad, "#1c211c"),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="#f7f6f2"/>',
        '<text x="24" y="30" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#1c211c">33 句里谁变了</text>',
        '<text x="24" y="52" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="#5c6560">单位：句。没有技能和插件时自己做算对，所以这 33 句 jev-decision 全部通过。</text>',
    ]
    gap = (900 - 48) / 4
    for i, (name, value, color) in enumerate(items):
        x = 48 + i * gap
        bh = 90 * value / 33
        y = 160 - bh
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="70" height="{bh:.1f}" fill="{color}"/>')
        parts.append(
            f'<text x="{x + 35:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-size="16" font-family="Segoe UI, sans-serif" fill="#1c211c">{value}</text>'
        )
        parts.append(
            f'<text x="{x + 35:.1f}" y="186" text-anchor="middle" font-size="13" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">{svg_escape(name)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def scope_chart() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="960" height="220" viewBox="0 0 960 220">
<rect width="960" height="220" fill="#f7f6f2"/>
<text x="24" y="30" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#1c211c">这张对比只覆盖技能选择</text>
<text x="24" y="54" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="13" fill="#1c211c">Laya 当时：通用模型逐门打分，过 0.5，最多 3 道。33 句刚好选对 15 句。</text>
<text x="24" y="78" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="13" fill="#1c211c">jev-decision：同一 33 句全部通过。有技能就打开，没有技能和插件就自己做。</text>
<text x="24" y="102" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="13" fill="#1c211c">本机出视频、背景音乐、表情包、MiniMax 出图没有对应技能，自己做。</text>
<text x="24" y="126" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="13" fill="#1c211c">Laya 当时打开了出音乐和表情贴纸。那两道现在没有技能，算多开。</text>
<text x="24" y="162" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="13" fill="#5c6560">回归 108/108，盲测 37/37。写作和推理不在这 33 句里。</text>
<text x="24" y="196" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="#5c6560">提问句「PDF 是什么」和「不要用 Word」仍然自己做。</text>
</svg>
"""


def main() -> None:
    write("compare-laya-skill.svg", overview())
    write("compare-failures.svg", table())
    write("compare-set-match.svg", moved())
    write("compare-scope.svg", scope_chart())
    laya = sum(1 for row in ROWS if row[3])
    jev = sum(1 for row in ROWS if row[5])
    print(f"laya {laya}/33 jev {jev}/33")


if __name__ == "__main__":
    main()
