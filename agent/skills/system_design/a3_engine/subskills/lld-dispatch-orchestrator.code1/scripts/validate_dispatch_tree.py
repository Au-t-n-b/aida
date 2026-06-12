#!/usr/bin/env python3
"""Validate dispatch_tree.yaml against intent-taxonomy.md L1/L2/children."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = SKILL_ROOT / "intent-taxonomy.md"
TREE_PATH = SKILL_ROOT / "dispatch_tree.yaml"


def _parse_taxonomy(text: str) -> dict[str, dict[str, list[str]]]:
    """Return {L1: {L2: [children]}} for offline-capable sections in tree file."""
    result: dict[str, dict[str, list[str]]] = {}
    in_l2_table = False
    in_l3_table = False
    l2_under_l1: dict[str, list[str]] = {}
    l3_under_l2: dict[str, list[str]] = {}

    for line in text.splitlines():
        if line.strip() == "## 二级分类":
            in_l2_table = True
            in_l3_table = False
            continue
        if line.strip() == "## 三级分类":
            in_l2_table = False
            in_l3_table = True
            continue
        if not line.strip().startswith("|"):
            continue
        if "---" in line or "一级" in line or "二级" in line and in_l2_table:
            continue
        if "二级" in line and in_l3_table:
            continue

        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if in_l2_table:
            l1, l2_csv = cells[0], cells[1]
            l2_under_l1[l1] = [x.strip() for x in l2_csv.split("、") if x.strip()]
        elif in_l3_table:
            l2, l3_csv = cells[0], cells[1]
            l3_under_l2[l2] = [x.strip() for x in l3_csv.split("、") if x.strip()]

    offline_l1 = {
        "地址规划",
        "互联规划",
        "接入规划",
        "网管规划",
        "路由规划",
        "LLD设计",
        "文件生成",
        "数据检查",
        "命名替换",
    }
    for l1 in offline_l1:
        result[l1] = {}
        for l2 in l2_under_l1.get(l1, []):
            result[l1][l2] = l3_under_l2.get(l2, [])
    return result


def _load_tree() -> dict[str, dict[str, list[str]]]:
    raw = yaml.safe_load(TREE_PATH.read_text(encoding="utf-8")) or {}
    tree = raw.get("tree") or {}
    out: dict[str, dict[str, list[str]]] = {}
    for l1, l2_map in tree.items():
        out[l1] = {}
        for l2, children in l2_map.items():
            out[l1][l2] = list(children or [])
    return out


def main() -> int:
    if not TAXONOMY.is_file():
        print(f"ERROR: taxonomy not found: {TAXONOMY}", file=sys.stderr)
        return 1
    expected = _parse_taxonomy(TAXONOMY.read_text(encoding="utf-8"))
    actual = _load_tree()
    errors: list[str] = []

    for l1, l2_map in expected.items():
        if l1 not in actual:
            errors.append(f"missing L1 in tree: {l1}")
            continue
        for l2, children in l2_map.items():
            if l2 not in actual[l1]:
                errors.append(f"missing L2 {l2} under {l1}")
                continue
            act_children = actual[l1][l2]
            if act_children != children:
                errors.append(
                    f"children mismatch for {l2}: tree={act_children} taxonomy={children}"
                )

    for l1 in actual:
        if l1 not in expected:
            errors.append(f"extra L1 in tree: {l1}")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    print("OK: dispatch_tree matches intent-taxonomy offline sections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
