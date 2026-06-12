#!/usr/bin/env python3
"""删除 nanobot 自带 skills，仅保留 README。"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "nanobot-main" / "nanobot" / "skills"

KEEP = {"README.md"}


def main() -> int:
    if not SKILLS_DIR.is_dir():
        print(f"[skip] {SKILLS_DIR} not found")
        return 0
    removed = []
    for item in SKILLS_DIR.iterdir():
        if item.name in KEEP:
            continue
        if item.is_dir():
            shutil.rmtree(item)
            removed.append(item.name)
        elif item.is_file():
            item.unlink()
            removed.append(item.name)
    print(f"[ok] removed {len(removed)} items: {', '.join(removed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
