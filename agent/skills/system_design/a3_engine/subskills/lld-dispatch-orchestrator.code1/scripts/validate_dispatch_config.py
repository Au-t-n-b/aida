#!/usr/bin/env python3
"""Validate l3_skill_index coverage, entrypoints, and L2 policies."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from dispatch_cli_builder import entrypoint_path
from dispatch_config_loader import (
    load_dispatch_tree,
    load_l2_policies,
    load_l2_without_offline,
    load_l3_index,
)


def main() -> int:
    tree = load_dispatch_tree()
    policies = load_l2_policies()
    without = load_l2_without_offline()
    l3 = load_l3_index()
    errors: list[str] = []

    all_l3: set[str] = set()
    all_l2: set[str] = set()
    for _l1, l2_list in tree.l1_to_l2.items():
        for l2 in l2_list:
            all_l2.add(l2)
            for child in tree.l2_children.get(l2, []):
                all_l3.add(child)

    for pol in policies.values():
        if pol.strategy == "direct" and pol.third_intent:
            all_l3.add(pol.third_intent)

    for intent in sorted(all_l3):
        skill = l3.get(intent)
        if not skill:
            errors.append(f"missing l3_skill_index: {intent}")
            continue
        if skill.unsupported or skill.pending:
            continue
        if not skill.package or not skill.entrypoint:
            errors.append(f"incomplete l3_skill_index: {intent}")
            continue
        ep = entrypoint_path(skill)
        if not ep.is_file():
            errors.append(f"missing entrypoint for {intent}: {ep}")

    for l2 in sorted(all_l2):
        if l2 in without:
            continue
        if l2 not in policies:
            errors.append(f"missing l2 policy: {l2}")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1

    print(
        f"OK: config valid ({len(all_l2)} L2, {len(all_l3)} L3, {len(l3)} index entries)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
