"""Workspace writer protocol: standing rules plus a daily ledger.

A partition is a git working tree (or the given directory). The protocol file
stays local. Compact reads are meant for the model; the on-disk file can be long.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

DAY_MARK = "<!-- writer-day:"
HINT_MARK = "jev-writer:"
PROTOCOL_NAME = "WRITER-PROTOCOL.md"
LOG_DIR_NAME = "writer-log"
COMPACT_LIMIT = 3500
YESTERDAY_LINES = 8

_TEMPLATE = (Path(__file__).resolve().parent / "template.md").read_text(encoding="utf-8")


def today_stamp() -> str:
    return date.today().isoformat()


def find_workspace(start: str | Path | None = None) -> Path:
    cur = Path(start or Path.cwd()).resolve()
    for path in [cur, *cur.parents]:
        if (path / ".git").exists():
            return path
    return cur


def protocol_path(root: Path) -> Path:
    return root / PROTOCOL_NAME


def log_dir(root: Path) -> Path:
    return root / LOG_DIR_NAME


def day_on_disk(text: str) -> str:
    match = re.search(r"<!-- writer-day:\s*([0-9-]+)\s*-->", text)
    return match.group(1) if match else ""


def _ignore_line(root: Path) -> None:
    gitignore = root / ".gitignore"
    needed = [PROTOCOL_NAME, f"{LOG_DIR_NAME}/"]
    try:
        current = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    except OSError:
        return
    extra = [line for line in needed if line not in current.splitlines()]
    if not extra:
        return
    prefix = "" if not current or current.endswith("\n") else "\n"
    try:
        gitignore.write_text(current + prefix + "\n".join(extra) + "\n", encoding="utf-8")
    except OSError:
        return


def ensure(root: str | Path | None = None, writer: str = "") -> Path:
    """Create a protocol for this workspace if missing, then roll the day if needed."""
    workspace = find_workspace(root)
    path = protocol_path(workspace)
    if not path.is_file():
        text = _TEMPLATE.replace("DATE", today_stamp())
        path.write_text(text, encoding="utf-8")
        _ignore_line(workspace)
        if writer:
            append(workspace, writer, [PROTOCOL_NAME], "完成", "自动创建写者协议")
    roll_if_new_day(workspace)
    return path


def _ledger_rows(text: str) -> list[str]:
    rows = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| 时间") and "写者" in line:
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                in_table = False
                continue
            if re.match(r"^\|\s*-+", line):
                continue
            rows.append(line.strip())
    return rows


def summarize_day(text: str) -> str:
    rows = _ledger_rows(text)[:YESTERDAY_LINES]
    if not rows:
        return "昨日没有台账行。"
    bullets = []
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) < 3:
            continue
        bullets.append("- " + " · ".join(cells[:4]))
    return "昨日摘要：\n" + "\n".join(bullets[:YESTERDAY_LINES])


def _stamp_day(text: str, day: str) -> str:
    if re.search(r"<!-- writer-day:\s*[0-9-]*\s*-->", text):
        return re.sub(r"<!-- writer-day:\s*[0-9-]*\s*-->", f"{DAY_MARK} {day} -->", text, count=1)
    if "# 写者协议" in text:
        return text.replace("# 写者协议", f"# 写者协议\n\n{DAY_MARK} {day} -->", 1)
    return f"{DAY_MARK} {day} -->\n\n" + text


def roll_if_new_day(root: str | Path | None = None) -> bool:
    """Archive yesterday's ledger and open a blank table. Returns True when rolled."""
    workspace = find_workspace(root)
    path = protocol_path(workspace)
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    marked = day_on_disk(text)
    today = today_stamp()
    if marked == today:
        return False
    if not marked:
        path.write_text(_stamp_day(text, today), encoding="utf-8")
        return False
    archive = log_dir(workspace)
    archive.mkdir(parents=True, exist_ok=True)
    (archive / f"{marked}.md").write_text(text, encoding="utf-8")
    summary = summarize_day(text)
    heading_match = re.search(r"\n(## [^\n]*台账[^\n]*)", text)
    heading = heading_match.group(1) if heading_match else "## 今日台账"
    parts = re.split(r"\n## [^\n]*台账", text, maxsplit=1)
    if heading_match and parts:
        standing = _stamp_day(parts[0], today)
        body = (
            standing.rstrip()
            + f"\n\n{heading}\n\n| 时间 | 写者 | 范围 | 状态 | 提交 |\n|---|---|---|---|---|\n"
            + "| — | — | 新的一天 | — | — |\n\n## 昨日摘要\n\n"
            + summary
            + "\n"
        )
    else:
        body = _TEMPLATE.replace("DATE", today)
        body = re.sub(
            r"## 3\. 昨日摘要\n\n.*",
            f"## 3. 昨日摘要\n\n{summary}\n",
            body,
            count=1,
            flags=re.S,
        )
    path.write_text(body, encoding="utf-8")
    return True


def append(root: str | Path | None, writer: str, files: list[str], status: str, note: str = "", commit: str = "") -> dict:
    """Add one ledger row for today's protocol."""
    workspace = find_workspace(root)
    ensure(workspace)
    path = protocol_path(workspace)
    text = path.read_text(encoding="utf-8")
    when = datetime.now().strftime("%H:%M")
    scope = "、".join(files) if files else note or "（未列文件）"
    row = f"| {when} | {writer or 'unknown'} | {scope} | {status or '进行中'} | {commit or '未提交'} |"
    if note and note not in scope:
        row = f"| {when} | {writer or 'unknown'} | {scope}（{note}） | {status or '进行中'} | {commit or '未提交'} |"
    marker = "|---|---|---|---|---|"
    if marker in text:
        text = text.replace(marker, marker + "\n" + row, 1)
    else:
        text += "\n\n" + row + "\n"
    path.write_text(text, encoding="utf-8")
    return {"ok": True, "row": row, "path": str(path)}


def compact_read(root: str | Path | None = None) -> str:
    """Model-facing slice: hint, yesterday summary, today's ledger. Not the whole file."""
    workspace = find_workspace(root)
    ensure(workspace)
    text = protocol_path(workspace).read_text(encoding="utf-8")
    rows = _ledger_rows(text)
    yesterday = ""
    match = re.search(r"## [^\n]*昨日摘要\n+(.*?)(?:\n## |\Z)", text, re.S)
    if match:
        yesterday = match.group(1).strip()
    today_lines = rows[:12] or ["（今日还没有台账行。）"]
    standing = "文件级单写者；改完记台账；实现和测试同一次提交；协议文件不进 git。"
    parts = [
        HINT_MARK + " 工作区 " + str(workspace),
        standing,
        "今日台账：",
        *today_lines,
    ]
    if yesterday:
        parts.extend(["", yesterday[:800]])
    body = "\n".join(parts)
    if len(body) > COMPACT_LIMIT:
        body = body[: COMPACT_LIMIT - 1] + "…"
    return body


def session_hint(root: str | Path | None = None) -> str:
    """Short prefix for host plugins. Does not dump the constitution."""
    workspace = find_workspace(root)
    ensure(workspace)
    return (
        f"{HINT_MARK} 本工作区写者协议已就绪（{protocol_path(workspace).name}）。"
        "动手前看 compact 台账；每改一批文件就 append 一行。协议和 writer-log/ 不要提交。"
    )


def already_hinted(text: str) -> bool:
    return (text or "").lstrip().startswith(HINT_MARK)
