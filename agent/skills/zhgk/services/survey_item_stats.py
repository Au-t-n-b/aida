"""底表条目统计 · SDUI 黄金指标与 determine_gen 预览共用。"""
from __future__ import annotations

import os
from typing import Any


def compute_survey_item_stats(gen_cooling: str | None = None) -> dict[str, Any]:
    """统计底表条目数；若给定代际制冷则返回过滤预览（与 filter_build 同规则）。"""
    from ..path_config import get_base_table_path
    from .table_filter import (
        TableFilterError,
        filter_items,
        get_sub_scenes_for_cooling,
        load_base_table,
    )

    path = get_base_table_path()
    if not os.path.isfile(path):
        return {}

    items = load_base_table(path)
    out: dict[str, Any] = {"base_table_count": len(items)}

    gc = (gen_cooling or "").strip()
    if not gc:
        return out

    sub_scenes = get_sub_scenes_for_cooling(gc)
    try:
        filtered = filter_items(
            items,
            generation_cooling=gc,
            category="标准",
            sub_scenes=sub_scenes,
        )
        filtered_count = len(filtered)
        preview_rows = [
            {
                "细分场景": str(it.get("细分场景", "") or ""),
                "勘测要素": str(it.get("勘测要素", "") or ""),
                "项目": str(it.get("项目", "") or ""),
                "勘测方法": str(it.get("勘测方法", "") or ""),
            }
            for it in filtered[:10]
        ]
    except TableFilterError:
        filtered_count = 0
        preview_rows = []

    out.update({
        "generation_cooling": gc,
        "filtered_count": filtered_count,
        "sub_scenes": sub_scenes,
        "preview_rows": preview_rows,
    })
    return out
