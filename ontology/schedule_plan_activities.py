#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交付计划活动表解析：多 PoD（管理单元 + 重复活动名）与单表通用逻辑。
与 llm_openrouter_forwardschedule / llm_openrouter_backschedule 共用。
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

FIELD_ACTIVITY_ID = "活动ID"
FIELD_UNIT = "管理单元"
FIELD_NAME = "活动名称"
FIELD_START = "开始日期"
FIELD_END = "结束日期"
FIELD_SLA = "SLA"
FIELD_DEPENDENCY = "依赖活动"
FIELD_BATCH = "批次"
FIELD_ROW_ID = "序列号"

# 多 PoD 时非空管理单元行：内部主键 = normalize(f"{unit}::{name}")，同单元同名多行时追加 f"::{id8}"
MULTI_POD_KEY_SEP = "::"
ROW_ID_KEY_LEN = 8


@dataclass
class Activity:
    name: str
    key: str
    activity_id: str
    unit: str
    planned_start: str
    planned_end: str
    sla_raw: str
    duration_days: int
    batch: str
    dependency_names: list[str]
    dependency_keys: list[str] = field(default_factory=list)
    unresolved_dependencies: list[str] = field(default_factory=list)
    """整张表因重复活动名而启用了多 PoD 主键时置 True，用于 Gantt/输出展示名。"""
    multi_pod_table: bool = False
    """表中的行序（0..n-1），用于同名单元多行时依赖消歧。"""
    row_order: int = 0
    """同管理单元+活动名多行时主键中追加的 序列号 片段，空表示无需区分。"""
    key_disambig: str = ""

    @property
    def row_key(self) -> str:
        """Ontology/OSDK 稳定对象主键；保持与内部依赖图 key 完全一致。"""
        return self.key


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.replace("\u3000", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_activity_key(value: str) -> str:
    return normalize_text(value).strip(",")


def normalize_plan_date(value: str) -> str:
    text = normalize_text(value)
    match = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:\s+.*)?", text)
    if not match:
        return text
    return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def parse_dependencies(raw_value: str) -> list[str]:
    normalized = normalize_text(raw_value).replace("，", ",")
    parts = [normalize_activity_key(item) for item in normalized.split(",")]
    return [item for item in parts if item]


def parse_duration_days(sla_raw: str, warnings: list[str], activity_name: str) -> int:
    text = normalize_text(sla_raw)
    if not text:
        return 0
    match = re.fullmatch(r"(\d+)\s*天", text)
    if match:
        return int(match.group(1))
    warnings.append(
        f"活动 `{activity_name}` 的 SLA `{text}` 无法解析，已按 0 天里程碑处理。"
    )
    return 0


def _table_has_duplicate_activity_names(rows: list[dict[str, str]]) -> bool:
    name_counts: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        name = normalize_text(row.get(FIELD_NAME, ""))
        if name:
            name_counts[normalize_activity_key(name)] += 1
    return any(c > 1 for c in name_counts.values())


def _row_id_suffix(row: dict[str, str]) -> str:
    raw = normalize_text(row.get(FIELD_ROW_ID, ""))
    if not raw:
        return "norowid"
    return re.sub(r"[^0-9a-fA-F]", "", raw)[:ROW_ID_KEY_LEN] or "norowid"


def _row_base_key(name: str, unit: str, multi_pod: bool) -> str:
    nk = normalize_activity_key(name)
    if not multi_pod:
        return nk
    if not unit:
        return nk
    return normalize_activity_key(f"{unit}{MULTI_POD_KEY_SEP}{name}")


def split_management_units(unit: str) -> list[str]:
    """
    将「管理单元」拆成子单元列表。支持同一格内用英文/中文逗号填写多个 PoD
    （如 B2DH401-POD01,B2DH401-POD02），用于依赖与逐 PoD 先行活动对齐。
    空则返回 []；无分隔符则返回单元素（与整串 trim 后一致）。
    """
    t = normalize_text(unit)
    if not t:
        return []
    parts = re.split(r"[,，]+", t)
    return [p for p in (normalize_text(x) for x in parts) if p]


def _resolve_dep_among_candidates(
    activity: Activity,
    dependency_name: str,
    candidates: list[str],
    activities: dict[str, Activity],
    warnings: list[str],
) -> None:
    """
    在 len(candidates)>1 时，用当前行管理单元与候选的 unit 消歧，结果写入
    activity.dependency_keys 或 unresolved_dependencies。
    若管理单元为「多 PoD 合并」字符串，则按子单元分别匹配并各连一条边（全成功才落边）。
    """
    u = activity.unit
    sub_units = split_management_units(u)

    if len(sub_units) > 1:
        resolved_keys: list[str] = []
        any_sub_failed = False
        for sub_u in sub_units:
            sub_matched = [k for k in candidates if activities[k].unit == sub_u]
            if len(sub_matched) == 0:
                # 被依赖活动可能仅为「多 PoD 合并」行（无单 PoD 行），则按子单元是否出现在该行的管理单元中匹配
                sub_matched = [
                    k
                    for k in candidates
                    if sub_u in split_management_units(activities[k].unit)
                ]
            if len(sub_matched) == 1:
                resolved_keys.append(sub_matched[0])
            elif len(sub_matched) == 0:
                any_sub_failed = True
                warnings.append(
                    f"活动 `{activity_display_name(activity)}` 的依赖 `{dependency_name}` 在表内存在多行，"
                    f"子管理单元 `{sub_u}` 无匹配，已忽略。"
                )
            else:
                chosen = min(sub_matched, key=lambda k: activities[k].row_order)
                resolved_keys.append(chosen)
                warnings.append(
                    f"活动 `{activity_display_name(activity)}` 的依赖 `{dependency_name}` 在子管理单元 `{sub_u}` 下"
                    f"有 {len(sub_matched)} 行，已取文件中最早一行作为前置（主键 {activities[chosen].key}）。"
                )
        if any_sub_failed:
            activity.unresolved_dependencies.append(dependency_name)
        else:
            seen: set[str] = set()
            for k in resolved_keys:
                if k not in seen:
                    activity.dependency_keys.append(k)
                    seen.add(k)
        return

    matched = [k for k in candidates if activities[k].unit == u]
    if len(matched) == 1:
        activity.dependency_keys.append(matched[0])
    elif len(matched) == 0:
        activity.unresolved_dependencies.append(dependency_name)
        if not u:
            warnings.append(
                f"活动 `{activity_display_name(activity)}` 的依赖 `{dependency_name}` 在表内存在多行，"
                f"当前行无管理单元，无法消歧，已忽略。"
            )
        else:
            warnings.append(
                f"活动 `{activity_display_name(activity)}` 的依赖 `{dependency_name}` 在表内存在多行，"
                f"与当前管理单元 `{u}` 无匹配，已忽略。"
            )
    else:
        chosen = min(matched, key=lambda k: activities[k].row_order)
        activity.dependency_keys.append(chosen)
        warnings.append(
            f"活动 `{activity_display_name(activity)}` 的依赖 `{dependency_name}` 在管理单元 `{u}` 下"
            f"有 {len(matched)} 行，已取文件中最早一行作为前置（主键 {activities[chosen].key}）。"
        )


def build_activities(
    rows: Iterable[dict[str, str]],
) -> tuple[dict[str, Activity], list[str]]:
    """构建活动图。存在重复活动名时启用多 PoD 主键与按管理单元解析依赖。"""
    warnings: list[str] = []
    prepared_rows = list(rows)
    multi_pod = _table_has_duplicate_activity_names(prepared_rows)
    # (unit, name) -> 行数，仅 multi_pod 且非空 unit 时用于同名单元多行拆 key
    pair_counts: defaultdict[tuple[str, str], int] = defaultdict(int)
    if multi_pod:
        for row in prepared_rows:
            name = normalize_text(row.get(FIELD_NAME, ""))
            if not name:
                continue
            unit = normalize_text(row.get(FIELD_UNIT, ""))
            if not unit:
                continue
            pair_counts[(unit, name)] += 1

    activities: dict[str, Activity] = {}
    for line_index, row in enumerate(prepared_rows):
        name = normalize_text(row.get(FIELD_NAME, ""))
        if not name:
            continue
        unit = normalize_text(row.get(FIELD_UNIT, ""))
        base = _row_base_key(name, unit, multi_pod)
        id8 = _row_id_suffix(row)
        disambig = ""
        if multi_pod and unit and pair_counts.get((unit, name), 0) > 1:
            key = normalize_activity_key(f"{base}{MULTI_POD_KEY_SEP}{id8}")
            disambig = id8
        else:
            key = base
        if key in activities:
            raise RuntimeError(
                f"活动主键冲突，无法建图：{key}。请检查「管理单元、活动名称、序列号」是否唯一。"
            )
        activities[key] = Activity(
            name=name,
            key=key,
            activity_id=normalize_text(row.get(FIELD_ACTIVITY_ID, "")),
            unit=unit,
            planned_start=normalize_plan_date(row.get(FIELD_START, "")),
            planned_end=normalize_plan_date(row.get(FIELD_END, "")),
            sla_raw=normalize_text(row.get(FIELD_SLA, "")),
            duration_days=parse_duration_days(
                row.get(FIELD_SLA, ""), warnings, name
            ),
            batch=normalize_text(row.get(FIELD_BATCH, "")),
            dependency_names=parse_dependencies(row.get(FIELD_DEPENDENCY, "")),
            multi_pod_table=multi_pod,
            row_order=line_index,
            key_disambig=disambig,
        )

    if multi_pod:
        seen_empty: set[str] = set()
        for row in prepared_rows:
            name = normalize_text(row.get(FIELD_NAME, ""))
            if not name:
                continue
            u = normalize_text(row.get(FIELD_UNIT, ""))
            if u:
                continue
            nk = normalize_activity_key(name)
            if nk in seen_empty:
                raise RuntimeError(
                    f"多 PoD 模式下「管理单元」为空的行出现重复活动名称，无法建图：{name}"
                )
            seen_empty.add(nk)

    for activity in activities.values():
        for dependency_name in activity.dependency_names:
            dep_nk = normalize_activity_key(dependency_name)
            candidates = [
                k
                for k, a in activities.items()
                if normalize_activity_key(a.name) == dep_nk
            ]
            if len(candidates) == 0:
                activity.unresolved_dependencies.append(dependency_name)
                warnings.append(
                    f"活动 `{activity_display_name(activity)}` 的依赖 `{dependency_name}` 未在计划中找到，已忽略。"
                )
            elif len(candidates) == 1:
                activity.dependency_keys.append(candidates[0])
            else:
                _resolve_dep_among_candidates(
                    activity, dependency_name, candidates, activities, warnings
                )

    return activities, warnings


def activity_display_name(activity: Activity) -> str:
    base: str
    if activity.multi_pod_table and activity.unit:
        base = f"{activity.name} [{activity.unit}]"
    else:
        base = activity.name
    if activity.key_disambig:
        return f"{base} ·{activity.key_disambig}"
    return base


def parse_activity_key_from_anchor_label(raw_name: str) -> str:
    """
    与 build_activities 的 key 规则一致，用于 --finish / --anchor 左端、倒排 --targets 等。

    支持：「活动名@管理单元」或「管理单元::活动名」、含行区分段的完整主键
   「单元::活动名::id8」；否则为全局规范化后的单名主键。
    """
    s = raw_name.strip()
    if "@" in s:
        name_part, unit_part = s.rsplit("@", 1)
        return normalize_activity_key(
            f"{unit_part.strip()}{MULTI_POD_KEY_SEP}{name_part.strip()}"
        )
    sep = MULTI_POD_KEY_SEP
    if s.count(sep) >= 2:
        return normalize_activity_key(s)
    if sep in s:
        unit_part, name_part = s.split(sep, 1)
        return normalize_activity_key(
            f"{unit_part.strip()}{sep}{name_part.strip()}"
        )
    return normalize_activity_key(s)


def resolve_user_activity_key(user_input: str, activities: dict[str, Activity]) -> str:
    """
    将用户输入解析为活动主键。优先完整 key；其次 @/:: 形式；同名单元多行时可用主键前缀匹配到最早一行。
    无法唯一确定时抛 ValueError。
    """
    u = user_input.strip()
    if not u:
        raise ValueError("活动标识不能为空。")
    k = normalize_activity_key(u)
    if k in activities:
        return k
    k2 = parse_activity_key_from_anchor_label(u)
    if k2 in activities:
        return k2
    by_prefix = [
        x
        for x in activities
        if x == k2 or x.startswith(f"{k2}{MULTI_POD_KEY_SEP}")
    ]
    if len(by_prefix) == 1:
        return by_prefix[0]
    if len(by_prefix) > 1:
        return min(by_prefix, key=lambda x: activities[x].row_order)
    cands = [
        a.key
        for a in activities.values()
        if normalize_activity_key(a.name) == k
    ]
    if len(cands) == 1:
        return cands[0]
    if len(cands) > 1:
        raise ValueError(
            f"活动名 `{u}` 在表内有多行，请使用 `活动名@管理单元` 或带行区分的完整主键（如 `管理单元::活动名` "
            f"或 `管理单元::活动名::{ROW_ID_KEY_LEN}位序列号片段`）指定其中一行。"
        )
    raise ValueError(f"未在计划中找到活动：`{u}`。")


def resolve_target_key_list(
    raw_targets: str, activities: dict[str, Activity]
) -> list[str]:
    """逗号分隔的多个目标，每项经 resolve_user_activity_key。"""
    parts = re.split(r"[,，]+", raw_targets)
    keys: list[str] = []
    seen: set[str] = set()
    for part in parts:
        part = part.strip()
        if not part:
            continue
        key = resolve_user_activity_key(part, activities)
        if key not in seen:
            keys.append(key)
            seen.add(key)
    return keys
