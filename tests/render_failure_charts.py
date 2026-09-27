"""Charts in docs/compare-*.svg are hand-authored Laya vs JEV.

Do not regenerate the old 规则 / JEV / 记忆 bake-off. Running this module
is a no-op so CI or habit does not overwrite the README figures.
"""

from __future__ import annotations


def main() -> None:
    print("skip: compare SVGs are Laya vs JEV, not rules vs JEV vs memory")


if __name__ == "__main__":
    main()
