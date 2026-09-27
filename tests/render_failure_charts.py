"""Emit README charts from this week's skill-selection incidents.

Series are 踩坑当时 vs jev-decision. Do not invent Laya door scores.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# 这几天调试里实际出现过的技能选择事故。当时=踩到了（挡住=0）。现在=现行 jev-decision（含记忆）。
PITS = [
    ("提问误开", "PDF 是什么 / Codex 提问 8/10 误开", 0, 100),
    ("否定仍打开", "不要用 Word", 0, 100),
    ("未点名却开", "线性头 ~0.99 仍开门", 0, 100),
    ("赢家通吃", "纪要+Word+幻灯片只留一门", 0, 100),
    ("选错技能", "WordPress 当成 Word", 0, 100),
    ("否定后乱选", "不要 PDF，给我论文", 0, 100),
    ("漏掉操作门", "填表提交之后导出成 PDF", 0, 100),
    ("换说法漏召", "在登录页填完再点提交", 0, 0),
]


def svg_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write(name: str, body: str) -> None:
    (DOCS / name).write_text(body, encoding="utf-8", newline="\n")


def pits_chart() -> str:
    w, h = 960, 440
    top, bottom, left, right = 88, 348, 56, 932
    plot_h = bottom - top
    n = len(PITS)
    gap = (right - left) / n
    bar_w = 22
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="#f7f6f2"/>',
        '<text x="24" y="30" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#1c211c">这几天踩过的技能选择坑：当时 vs jev-decision</text>',
        '<text x="24" y="50" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="#5c6560">纵轴是这类事故有没有被挡住（100=挡住）。当时=调试时真实出现过的失败。现在=jev-decision。没有给 Laya 打柜门分。</text>',
    ]
    for i, tick in enumerate((0, 25, 50, 75, 100)):
        y = bottom - plot_h * tick / 100
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#d5d1c7"/>')
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" font-family="Segoe UI, sans-serif" fill="#5c6560">{tick}</text>'
        )
    for i, (name, _ex, then, now) in enumerate(PITS):
        cx = left + gap * (i + 0.5)
        for dx, value, color in ((-bar_w - 2, then, "#1c211c"), (2, now, "#0c6b52")):
            bh = max(4, plot_h * value / 100)
            y = bottom - bh
            parts.append(f'<rect x="{cx + dx:.1f}" y="{y:.1f}" width="{bar_w}" height="{bh:.1f}" fill="{color}"/>')
            parts.append(
                f'<text x="{cx + dx + bar_w / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-size="11" font-family="Segoe UI, sans-serif" fill="{color}">{value}</text>'
            )
        parts.append(
            f'<text x="{cx:.1f}" y="{bottom + 22}" text-anchor="middle" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">{svg_escape(name)}</text>'
        )
    parts += [
        '<rect x="48" y="404" width="12" height="12" fill="#1c211c"/>',
        '<text x="66" y="415" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">踩坑当时</text>',
        '<rect x="168" y="404" width="12" height="12" fill="#0c6b52"/>',
        '<text x="186" y="415" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">jev-decision</text>',
        '<text x="300" y="415" font-size="11" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">8 类里 7 类已挡住。换说法漏召仍是盲测登录页。</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def table_chart() -> str:
    rows = [
        ("提问误开", "PDF 是什么；Codex 试用提问 8/10 都开门", "当成导出/操作", "提问句自己做"),
        ("否定被盖", "不要用 Word", "习惯分把 Word 又打开", "不开 Word"),
        ("未点名却开", "句子没点名，头仍打到 ~0.99", "无名门也留下", "未点名清零"),
        ("赢家通吃", "纪要，再写成 Word，再做幻灯片", "YES_LIMIT / 只留一门", "点名的门都留"),
        ("选错技能", "WordPress 建站，不是 Word", "当成 Word 或建站", "不开 Word"),
        ("否定后乱选", "不要用 PDF，给我论文", "关掉 PDF，论文也没了", "留论文工作台"),
        ("漏掉操作门", "填表提交之后导出成 PDF", "只开 PDF", "填表 + PDF"),
        ("股价否定", "放进 Excel，不要写 Word", "仍打开 Word", "只开行情和表格"),
        ("换说法漏召", "在登录页填完再点提交", "对不上网页操作门", "仍漏（盲测）"),
        ("训差权重", "一次重训回归 106→99", "差点覆盖 head.json", "发布门拒绝，基线仍在"),
        ("评测句进训练", "用考卷原句修召回", "分数虚高", "训练拦截评测原句"),
        ("Harness 选门", "pre-step 返回数组", "宿主 TypeError", "PreStepDecision 追加"),
    ]
    row_h = 30
    height = 72 + row_h * len(rows) + 36
    width = 1100
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#f7f6f2"/>',
        '<text x="24" y="28" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#1c211c">这几天实际踩过的坑</text>',
        '<text x="24" y="48" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="#5c6560">来源：这几天试用和评测原句。不是 Laya 108 条打分。</text>',
        '<text x="24" y="70" font-size="12" font-weight="700" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">坑</text>',
        '<text x="150" y="70" font-size="12" font-weight="700" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">怎么踩的</text>',
        '<text x="560" y="70" font-size="12" font-weight="700" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">当时</text>',
        '<text x="820" y="70" font-size="12" font-weight="700" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">jev-decision</text>',
        '<line x1="24" y1="78" x2="1076" y2="78" stroke="#d5d1c7"/>',
    ]
    for i, (pit, how, then, now) in enumerate(rows):
        y = 98 + i * row_h
        if i % 2 == 0:
            parts.append(f'<rect x="16" y="{y - 18}" width="1068" height="{row_h}" fill="#e7f3ee"/>')
        now_color = "#8f3d32" if "仍漏" in now else "#0c6b52"
        parts.append(f'<text x="24" y="{y}" font-size="13" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">{svg_escape(pit)}</text>')
        parts.append(f'<text x="150" y="{y}" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">{svg_escape(how)}</text>')
        parts.append(f'<text x="560" y="{y}" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#8f3d32">{svg_escape(then)}</text>')
        parts.append(f'<text x="820" y="{y}" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="{now_color}">{svg_escape(now)}</text>')
    parts.append(
        f'<text x="24" y="{height - 14}" font-size="11" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">通用写作和推理不拿 jev-decision 去比 Laya：那一块本来就不是选择头的活。</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def numbers_chart() -> str:
    # 实测数字，分开两把尺子：错误率 vs 集合匹配
    w, h = 960, 340
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="#f7f6f2"/>',
        '<text x="24" y="30" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#1c211c">这几天测到的数</text>',
        '<text x="24" y="50" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="#5c6560">左边是误开/漏召；右边是集合匹配。绿条是 jev-decision。没有 Laya 柜门分。</text>',
        '<rect x="24" y="68" width="448" height="230" fill="#fff" stroke="#d5d1c7"/>',
        '<rect x="488" y="68" width="448" height="230" fill="#fff" stroke="#d5d1c7"/>',
        '<text x="44" y="96" font-size="14" font-weight="700" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">技能选错（越低越好）</text>',
        '<text x="508" y="96" font-size="14" font-weight="700" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">集合匹配（越高越好）</text>',
    ]
    # left: asking 8/10 = 80% then 0; login still miss = 100% miss then 100%
    left_rows = [
        ("提问误开（试用 10 句）", 80, 0, "8/10 → 挡住"),
        ("8 类旧事故漏掉", 100, 12.5, "8/8 → 1/8"),
        ("登录页换说法", 100, 100, "仍漏"),
    ]
    for i, (label, then, now, note) in enumerate(left_rows):
        y = 118 + i * 56
        parts.append(f'<text x="44" y="{y}" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">{svg_escape(label)}</text>')
        parts.append(f'<rect x="44" y="{y + 8}" width="280" height="10" fill="#eceae4"/>')
        parts.append(f'<rect x="44" y="{y + 8}" width="{2.8 * then:.1f}" height="10" fill="#1c211c"/>')
        parts.append(f'<rect x="44" y="{y + 22}" width="{max(4, 2.8 * now):.1f}" height="10" fill="#0c6b52"/>')
        parts.append(f'<text x="336" y="{y + 22}" font-size="11" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">{svg_escape(note)}</text>')
    right_rows = [
        ("回归 108 条", 100.0, "现行 108/108（含记忆）"),
        ("训差候选（未发布）", 91.7, "99/108，发布门拒绝"),
        ("盲测 37 条", 97.3, "36/37，漏登录页"),
    ]
    for i, (label, value, note) in enumerate(right_rows):
        y = 118 + i * 56
        parts.append(f'<text x="508" y="{y}" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">{svg_escape(label)}</text>')
        parts.append(f'<rect x="508" y="{y + 10}" width="280" height="12" fill="#eceae4"/>')
        parts.append(f'<rect x="508" y="{y + 10}" width="{2.8 * value:.1f}" height="12" fill="#0c6b52"/>')
        parts.append(f'<text x="800" y="{y + 20}" font-size="11" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">{value:.1f}%</text>')
        parts.append(f'<text x="508" y="{y + 40}" font-size="11" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">{svg_escape(note)}</text>')
    parts.append('<text x="44" y="310" font-size="11" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">黑条=当时，绿条=jev-decision。</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def scope_chart() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="960" height="280" viewBox="0 0 960 280">
<rect width="960" height="280" fill="#f7f6f2"/>
<text x="24" y="30" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="18" font-weight="700" fill="#1c211c">jev-decision 和 Laya：职责不同，不是同一张分数表</text>
<text x="24" y="50" font-family="Noto Sans SC, Segoe UI, sans-serif" font-size="12" fill="#5c6560">jev-decision 只训练「这句话要不要开哪几份技能/插件」。Laya 是通用智能体。仓库不发布 Laya 权重，选择路径也不再调用它。</text>
<rect x="24" y="68" width="448" height="180" fill="#e7f3ee" stroke="#d5d1c7"/>
<rect x="488" y="68" width="448" height="180" fill="#fff" stroke="#d5d1c7"/>
<text x="44" y="98" font-size="16" font-weight="700" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#0c6b52">jev-decision · 技能选择</text>
<text x="44" y="126" font-size="13" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">1.1 MB 线性头 · 39 门 · 229 条样本</text>
<text x="44" y="150" font-size="13" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">这几天修的就是上面那些选错</text>
<text x="44" y="174" font-size="13" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">回归 108/108，盲测 36/37</text>
<text x="44" y="210" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">开口前选定，模型不再挑技能</text>
<text x="508" y="98" font-size="16" font-weight="700" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">Laya · 通用能力</text>
<text x="508" y="126" font-size="13" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">写作、推理、规划、未点名的活</text>
<text x="508" y="150" font-size="13" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">不输出柜门 ID，未在本集打分</text>
<text x="508" y="174" font-size="13" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#1c211c">jev-decision 替代不了，也不该拿它去比通用</text>
<text x="508" y="210" font-size="12" font-family="Noto Sans SC, Segoe UI, sans-serif" fill="#5c6560">用通用模型猜柜门，才会出现左边那些坑</text>
</svg>
"""


def main() -> None:
    write("compare-laya-skill.svg", pits_chart())
    write("compare-failures.svg", table_chart())
    write("compare-set-match.svg", numbers_chart())
    write("compare-scope.svg", scope_chart())
    print("wrote 4 compare SVGs")


if __name__ == "__main__":
    main()
