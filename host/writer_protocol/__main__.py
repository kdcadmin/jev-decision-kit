"""CLI: python -m host.writer_protocol ensure|read|append|mcp"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from host.writer_protocol import append, compact_read, ensure, session_hint


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m host.writer_protocol")
    parser.add_argument("command", choices=("ensure", "read", "hint", "append", "mcp"))
    parser.add_argument("--root", default="")
    parser.add_argument("--writer", default="")
    parser.add_argument("--files", default="")
    parser.add_argument("--status", default="进行中")
    parser.add_argument("--note", default="")
    parser.add_argument("--commit", default="")
    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else None
    if args.command == "mcp":
        from host.writer_protocol.mcp import run

        run()
        return 0
    if args.command == "ensure":
        path = ensure(root, args.writer)
        print(path)
        return 0
    if args.command == "read":
        print(compact_read(root))
        return 0
    if args.command == "hint":
        print(session_hint(root))
        return 0
    files = [part.strip() for part in args.files.split(",") if part.strip()]
    print(json.dumps(append(root, args.writer, files, args.status, args.note, args.commit), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
