#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Milestone compression dry-run scheduling.

This module keeps each activity's existing duration/window intact and shifts
all parseable activity time points by the same delta between a baseline
milestone date and the requested compression anchor date.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from schedule_plan_activities import Activity, activity_display_name

DATE_FORMAT = "%Y-%m-%d"
STRATEGY_TOP3_SLACK = "TOP3_SLACK"
STRATEGY_PROPORTIONAL = "PROPORTIONAL"
STRATEGY_PROPORTIONAL_EXTENSION = "PROPORTIONAL_EXTENSION"


@dataclass(frozen=True)
class MilestoneCompressionResult:
    start: date | None
    finish: date | None
    shift_days: int


@dataclass(frozen=True)
class DurationCompressionResult:
    start: date | None
    finish: date | None
    original_duration_days: int
    compressed_duration_days: int
    compression_days: int
    slack_days: int
    is_critical_path: bool
    start_shift_days: int


@dataclass(frozen=True)
class DurationCompressionRun:
    results: dict[str, DurationCompressionResult]
    critical_path_keys: list[str]
    allocations: dict[str, int]
    requested_compression_days: int
    achieved_compression_days: int
    strategy: str
    critical_path_iterations: list[list[str]]
    stop_reason: str
    final_target_finish_date: date | None


@dataclass(frozen=True)
class DurationExtensionResult:
    start: date | None
    finish: date | None
    original_duration_days: int
    extended_duration_days: int
    extension_days: int
    is_critical_path: bool
    start_shift_days: int


@dataclass(frozen=True)
class DurationExtensionRun:
    results: dict[str, DurationExtensionResult]
    critical_path_keys: list[str]
    allocations: dict[str, int]
    requested_extension_days: int
    achieved_extension_days: int
    strategy: str


def parse_plan_date(raw_value: str) -> date | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    normalized = text.replace("/", "-")
    if len(normalized) >= 10:
        normalized = normalized[:10]
    try:
        return datetime.strptime(normalized, DATE_FORMAT).date()
    except ValueError:
        return None


def compute_milestone_compression_schedule(
    activities: dict[str, Activity],
    *,
    baseline_date: date,
    anchor_date: date,
    warnings: list[str],
) -> dict[str, MilestoneCompressionResult]:
    shift_days = (anchor_date - baseline_date).days
    shift = timedelta(days=shift_days)
    results: dict[str, MilestoneCompressionResult] = {}

    for activity_key, activity in activities.items():
        start = parse_plan_date(activity.planned_start)
        finish = parse_plan_date(activity.planned_end)
        if activity.planned_start and start is None:
            warnings.append(
                f"活动 `{activity_display_name(activity)}` 的开始日期 `{activity.planned_start}` 无法解析，已跳过该时间点。"
            )
        if activity.planned_end and finish is None:
            warnings.append(
                f"活动 `{activity_display_name(activity)}` 的结束日期 `{activity.planned_end}` 无法解析，已跳过该时间点。"
            )
        if start is None and finish is None:
            continue
        results[activity_key] = MilestoneCompressionResult(
            start=start + shift if start is not None else None,
            finish=finish + shift if finish is not None else None,
            shift_days=shift_days,
        )

    return results


def _inclusive_days(start: date, finish: date) -> int:
    return (finish - start).days + 1


def _activity_sort_key(activities: dict[str, Activity], key: str) -> tuple[int, str, str]:
    activity = activities[key]
    return (activity.row_order, activity.name, key)


def _topo_sort(activities: dict[str, Activity]) -> list[str]:
    indegree = {key: 0 for key in activities}
    outgoing: dict[str, list[str]] = {key: [] for key in activities}
    for key, activity in activities.items():
        for dependency_key in activity.dependency_keys:
            if dependency_key not in activities:
                continue
            indegree[key] += 1
            outgoing[dependency_key].append(key)

    queue = sorted(
        [key for key, value in indegree.items() if value == 0],
        key=lambda item: _activity_sort_key(activities, item),
    )
    ordered: list[str] = []
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        ordered.append(current)
        for successor_key in sorted(outgoing[current], key=lambda item: _activity_sort_key(activities, item)):
            indegree[successor_key] -= 1
            if indegree[successor_key] == 0:
                queue.append(successor_key)

    if len(ordered) < len(activities):
        remaining = [key for key in activities if key not in ordered]
        ordered.extend(sorted(remaining, key=lambda item: _activity_sort_key(activities, item)))
    return ordered


def _parse_activity_windows(
    activities: dict[str, Activity],
    warnings: list[str],
) -> tuple[dict[str, date], dict[str, date], dict[str, int]]:
    starts: dict[str, date] = {}
    finishes: dict[str, date] = {}
    durations: dict[str, int] = {}

    for activity_key, activity in activities.items():
        start = parse_plan_date(activity.planned_start)
        finish = parse_plan_date(activity.planned_end)
        if activity.planned_start and start is None:
            warnings.append(
                f"活动 `{activity_display_name(activity)}` 的开始日期 `{activity.planned_start}` 无法解析，已跳过该时间点。"
            )
        if activity.planned_end and finish is None:
            warnings.append(
                f"活动 `{activity_display_name(activity)}` 的结束日期 `{activity.planned_end}` 无法解析，已跳过该时间点。"
            )

        duration_days = activity.duration_days
        if duration_days <= 0 and start is not None and finish is not None:
            duration_days = _inclusive_days(start, finish)
        if start is None and finish is not None and duration_days > 0:
            start = finish - timedelta(days=duration_days - 1)
        if finish is None and start is not None and duration_days > 0:
            finish = start + timedelta(days=duration_days - 1)
        if start is None or finish is None:
            continue
        if finish < start:
            warnings.append(
                f"活动 `{activity_display_name(activity)}` 的结束日期早于开始日期，已跳过工期压缩计算。"
            )
            continue

        duration_days = max(0, duration_days)
        if duration_days == 0:
            duration_days = _inclusive_days(start, finish)
        starts[activity_key] = start
        finishes[activity_key] = finish
        durations[activity_key] = duration_days

    return starts, finishes, durations


def _parse_limit_duration_days(
    activity: Activity,
    raw_value: object,
    *,
    missing: bool,
    warnings: list[str],
) -> int | None:
    if missing or raw_value is None or str(raw_value).strip() == "":
        warnings.append(f"活动 `{activity_display_name(activity)}` 未提供极限工期，已按不可压缩处理。")
        return None
    if isinstance(raw_value, int):
        return raw_value if raw_value >= 0 else None

    text = str(raw_value).strip()
    match = re.fullmatch(r"(\d+)\s*(?:天|d|D)?", text)
    if match:
        return int(match.group(1))

    warnings.append(f"活动 `{activity_display_name(activity)}` 的极限工期 `{text}` 无法解析，已按不可压缩处理。")
    return None


def _critical_path_keys(
    activities: dict[str, Activity],
    target_keys: list[str],
    starts: dict[str, date],
    finishes: dict[str, date],
    warnings: list[str],
) -> list[str]:
    if not target_keys:
        raise ValueError("target_keys must contain at least one activity key.")

    valid_targets = [key for key in target_keys if key in activities and key in finishes]
    for key in target_keys:
        if key not in activities:
            warnings.append(f"关键路径目标 `{key}` 不存在，已忽略。")
        elif key not in finishes:
            warnings.append(f"关键路径目标 `{key}` 缺少可解析日期，已忽略。")
    if not valid_targets:
        raise ValueError("No target_keys with parseable activity dates.")

    current = max(
        valid_targets,
        key=lambda key: (
            finishes[key],
            starts[key],
            activities[key].row_order,
            activities[key].name,
            key,
        ),
    )
    reversed_path: list[str] = []
    visited: set[str] = set()
    while current not in visited:
        reversed_path.append(current)
        visited.add(current)
        dependencies = [
            key
            for key in activities[current].dependency_keys
            if key in activities and key in finishes
        ]
        if not dependencies:
            break
        current = max(
            dependencies,
            key=lambda key: (
                finishes[key],
                starts[key],
                activities[key].row_order,
                activities[key].name,
                key,
            ),
        )

    return list(reversed(reversed_path))


def _target_finish_date(
    activities: dict[str, Activity],
    target_keys: list[str],
    starts: dict[str, date],
    finishes: dict[str, date],
) -> date | None:
    valid_targets = [key for key in target_keys if key in activities and key in starts and key in finishes]
    if not valid_targets:
        return None
    target_key = max(
        valid_targets,
        key=lambda key: (
            finishes[key],
            starts[key],
            activities[key].row_order,
            activities[key].name,
            key,
        ),
    )
    return finishes[target_key]


def _critical_path_limit_duration_days(
    activities: dict[str, Activity],
    critical_path_keys: list[str],
    limit_duration_by_key: dict[str, object],
    warnings: list[str],
) -> dict[str, int]:
    limit_days_by_key: dict[str, int] = {}
    for key in critical_path_keys:
        limit_days = _parse_limit_duration_days(
            activities[key],
            limit_duration_by_key.get(key),
            missing=key not in limit_duration_by_key,
            warnings=warnings,
        )
        if limit_days is not None:
            limit_days_by_key[key] = limit_days
    return limit_days_by_key


def _critical_path_slack_days(
    critical_path_keys: list[str],
    durations: dict[str, int],
    limit_days_by_key: dict[str, int],
) -> dict[str, int]:
    slack_by_key: dict[str, int] = {}
    for key in critical_path_keys:
        duration_days = durations.get(key, 0)
        limit_days = limit_days_by_key.get(key)
        if duration_days <= 0 or limit_days is None:
            slack_by_key[key] = 0
            continue
        slack_by_key[key] = max(0, duration_days - limit_days)
    return slack_by_key


def _allocate_top_slack(
    critical_path_keys: list[str],
    slack_by_key: dict[str, int],
    requested_days: int,
    top_n: int,
) -> dict[str, int]:
    path_index = {key: index for index, key in enumerate(critical_path_keys)}
    candidates = [
        (key, slack)
        for key, slack in slack_by_key.items()
        if slack > 0
    ]
    candidates.sort(key=lambda item: (-item[1], path_index[item[0]], item[0]))
    remaining = requested_days
    allocations: dict[str, int] = {}
    for key, slack in candidates[: max(0, top_n)]:
        if remaining <= 0:
            break
        compression_days = min(slack, remaining)
        if compression_days > 0:
            allocations[key] = compression_days
            remaining -= compression_days
    return {
        key: allocations[key]
        for key in critical_path_keys
        if allocations.get(key, 0) > 0
    }


def _allocate_proportionally(
    critical_path_keys: list[str],
    slack_by_key: dict[str, int],
    durations: dict[str, int],
    requested_days: int,
) -> dict[str, int]:
    candidates = [
        (key, slack_by_key[key], durations.get(key, 0))
        for key in critical_path_keys
        if slack_by_key.get(key, 0) > 0 and durations.get(key, 0) > 0
    ]
    total_slack = sum(slack for _, slack, _duration in candidates)
    if total_slack <= 0 or requested_days <= 0:
        return {}
    if requested_days >= total_slack:
        return {key: slack for key, slack, _duration in candidates if slack > 0}

    allocations: dict[str, int] = {}
    remaining_days = requested_days
    remaining_candidates = list(candidates)
    while remaining_candidates:
        total_weight = sum(duration for _key, _slack, duration in remaining_candidates)
        if total_weight <= 0:
            break
        capped_keys = [
            key
            for key, slack, duration in remaining_candidates
            if remaining_days * duration / total_weight >= slack
        ]
        if not capped_keys:
            break
        capped_set = set(capped_keys)
        for key, slack, duration in remaining_candidates:
            if key in capped_set:
                allocations[key] = slack
                remaining_days -= slack
        remaining_candidates = [
            item
            for item in remaining_candidates
            if item[0] not in capped_set
        ]
    if remaining_days <= 0 or not remaining_candidates:
        return {
            key: allocations[key]
            for key in critical_path_keys
            if allocations.get(key, 0) > 0
        }

    remainders: list[tuple[float, int, int, str]] = []
    path_index = {key: index for index, key in enumerate(critical_path_keys)}
    allocated = 0
    total_weight = sum(duration for _key, _slack, duration in remaining_candidates)
    for key, slack, duration in remaining_candidates:
        raw_share = remaining_days * duration / total_weight
        base = min(slack, int(raw_share))
        allocations[key] = allocations.get(key, 0) + base
        allocated += base
        remainders.append((raw_share - base, slack, path_index[key], key))

    remaining = remaining_days - allocated
    remainders.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
    while remaining > 0:
        progressed = False
        for _fraction, _slack, _index, key in remainders:
            if remaining <= 0:
                break
            if allocations[key] >= slack_by_key[key]:
                continue
            allocations[key] += 1
            remaining -= 1
            progressed = True
        if not progressed:
            break

    return {
        key: allocations[key]
        for key in critical_path_keys
        if allocations.get(key, 0) > 0
    }


def _allocate_extension_proportionally(
    critical_path_keys: list[str],
    durations: dict[str, int],
    requested_days: int,
) -> dict[str, int]:
    candidates = [(key, durations[key]) for key in critical_path_keys if durations.get(key, 0) > 0]
    total_duration = sum(duration for _, duration in candidates)
    if total_duration <= 0 or requested_days <= 0:
        return {}

    allocations: dict[str, int] = {}
    remainders: list[tuple[float, int, int, str]] = []
    path_index = {key: index for index, key in enumerate(critical_path_keys)}
    allocated = 0
    for key, duration in candidates:
        raw_share = requested_days * duration / total_duration
        base = int(raw_share)
        allocations[key] = base
        allocated += base
        remainders.append((raw_share - base, duration, path_index[key], key))

    remaining = requested_days - allocated
    remainders.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
    while remaining > 0:
        progressed = False
        for _fraction, _duration, _index, key in remainders:
            if remaining <= 0:
                break
            allocations[key] += 1
            remaining -= 1
            progressed = True
        if not progressed:
            break

    return {
        key: allocations[key]
        for key in critical_path_keys
        if allocations.get(key, 0) > 0
    }


def _allocate_duration_compression(
    *,
    strategy: str,
    critical_path_keys: list[str],
    slack_by_key: dict[str, int],
    durations: dict[str, int],
    requested_days: int,
    top_n: int,
) -> dict[str, int]:
    normalized_strategy = strategy.strip().upper()
    if normalized_strategy == STRATEGY_TOP3_SLACK:
        return _allocate_top_slack(critical_path_keys, slack_by_key, requested_days, top_n)
    if normalized_strategy == STRATEGY_PROPORTIONAL:
        return _allocate_proportionally(critical_path_keys, slack_by_key, durations, requested_days)
    raise ValueError(f"Unsupported duration compression strategy: {strategy}")


def _ensure_limit_duration_days(
    activities: dict[str, Activity],
    critical_path_keys: list[str],
    limit_duration_by_key: dict[str, object],
    warnings: list[str],
    parsed_limit_keys: set[str],
    limit_days_by_key: dict[str, int],
) -> None:
    for key in critical_path_keys:
        if key in parsed_limit_keys:
            continue
        limit_days = _parse_limit_duration_days(
            activities[key],
            limit_duration_by_key.get(key),
            missing=key not in limit_duration_by_key,
            warnings=warnings,
        )
        if limit_days is not None:
            limit_days_by_key[key] = limit_days
        parsed_limit_keys.add(key)


def _duration_windows_from_allocations(
    activities: dict[str, Activity],
    starts: dict[str, date],
    finishes: dict[str, date],
    durations: dict[str, int],
    allocations: dict[str, int],
    limit_days_by_key: dict[str, int],
) -> dict[str, tuple[date, date]]:
    windows: dict[str, tuple[date, date]] = {}
    for key in _topo_sort(activities):
        if key not in starts or key not in finishes:
            continue
        activity = activities[key]
        original_start = starts[key]
        original_duration = durations[key]
        compression_days = allocations.get(key, 0)
        if original_duration <= 0:
            compressed_duration = 0
        else:
            compressed_duration = max(1, original_duration - compression_days)
            if key in limit_days_by_key:
                compressed_duration = max(compressed_duration, min(original_duration, limit_days_by_key[key]))

        dependency_keys = [
            dependency_key
            for dependency_key in activity.dependency_keys
            if dependency_key in windows and dependency_key in finishes
        ]
        if dependency_keys:
            original_ready = max(finishes[dependency_key] + timedelta(days=1) for dependency_key in dependency_keys)
            refreshed_ready = max(windows[dependency_key][1] + timedelta(days=1) for dependency_key in dependency_keys)
            proposed_start = original_start + timedelta(days=(refreshed_ready - original_ready).days)
            if proposed_start < refreshed_ready:
                proposed_start = refreshed_ready
        else:
            proposed_start = original_start

        if compressed_duration <= 0:
            proposed_finish = proposed_start
        else:
            proposed_finish = proposed_start + timedelta(days=compressed_duration - 1)
        windows[key] = (proposed_start, proposed_finish)
    return windows


def _window_maps(
    windows: dict[str, tuple[date, date]],
) -> tuple[dict[str, date], dict[str, date], dict[str, int]]:
    starts = {key: value[0] for key, value in windows.items()}
    finishes = {key: value[1] for key, value in windows.items()}
    durations = {key: _inclusive_days(value[0], value[1]) for key, value in windows.items()}
    return starts, finishes, durations


def _duration_results_from_windows(
    activities: dict[str, Activity],
    starts: dict[str, date],
    durations: dict[str, int],
    windows: dict[str, tuple[date, date]],
    allocations: dict[str, int],
    slack_by_key: dict[str, int],
    critical_path_keys: list[str],
) -> dict[str, DurationCompressionResult]:
    critical_set = set(critical_path_keys)
    results: dict[str, DurationCompressionResult] = {}
    for key in _topo_sort(activities):
        if key not in starts or key not in windows:
            continue
        proposed_start, proposed_finish = windows[key]
        original_start = starts[key]
        original_duration = durations[key]
        compressed_duration = _inclusive_days(proposed_start, proposed_finish) if original_duration > 0 else 0
        results[key] = DurationCompressionResult(
            start=proposed_start,
            finish=proposed_finish,
            original_duration_days=original_duration,
            compressed_duration_days=compressed_duration,
            compression_days=allocations.get(key, 0),
            slack_days=slack_by_key.get(key, 0),
            is_critical_path=key in critical_set,
            start_shift_days=(proposed_start - original_start).days,
        )
    return results


def _compute_dynamic_proportional_duration_compression(
    activities: dict[str, Activity],
    *,
    target_keys: list[str],
    baseline_date: date,
    anchor_date: date,
    limit_duration_by_key: dict[str, object],
    warnings: list[str],
) -> DurationCompressionRun:
    requested_days = max(0, (baseline_date - anchor_date).days)
    starts, finishes, durations = _parse_activity_windows(activities, warnings)
    allocations: dict[str, int] = {}
    limit_days_by_key: dict[str, int] = {}
    parsed_limit_keys: set[str] = set()
    windows = _duration_windows_from_allocations(activities, starts, finishes, durations, allocations, limit_days_by_key)
    current_starts, current_finishes, current_durations = _window_maps(windows)
    initial_critical_keys: list[str] = []
    iteration_paths: list[list[str]] = []
    previous_critical_keys: list[str] | None = None
    stop_reason = "TARGET_REACHED"
    max_iterations = max(1, sum(max(0, value) for value in durations.values()) + 1)

    for _iteration in range(max_iterations):
        current_target_finish = _target_finish_date(activities, target_keys, current_starts, current_finishes)
        if current_target_finish is not None and current_target_finish <= anchor_date:
            stop_reason = "TARGET_REACHED"
            break

        critical_keys = _critical_path_keys(activities, target_keys, current_starts, current_finishes, warnings)
        if not initial_critical_keys:
            initial_critical_keys = list(critical_keys)
        iteration_paths.append(list(critical_keys))
        if previous_critical_keys is not None and critical_keys == previous_critical_keys:
            stop_reason = "CRITICAL_PATH_UNCHANGED"
            warnings.append(
                f"全局等比压缩后目标仍未达到 {anchor_date.isoformat()}，"
                "但关键路径未发生变化，已停止继续压缩，无法完全压缩。"
            )
            break

        _ensure_limit_duration_days(
            activities,
            critical_keys,
            limit_duration_by_key,
            warnings,
            parsed_limit_keys,
            limit_days_by_key,
        )
        slack_by_key = _critical_path_slack_days(critical_keys, current_durations, limit_days_by_key)
        remaining_days = (
            max(0, (current_target_finish - anchor_date).days)
            if current_target_finish is not None
            else requested_days
        )
        next_allocations = _allocate_proportionally(critical_keys, slack_by_key, current_durations, remaining_days)
        if not next_allocations:
            stop_reason = "NO_COMPRESSIBLE_SLACK"
            warnings.append(
                f"全局等比压缩后目标仍未达到 {anchor_date.isoformat()}，"
                "当前关键路径无可继续压缩空闲，无法完全压缩。"
            )
            break

        for key, days in next_allocations.items():
            allocations[key] = allocations.get(key, 0) + days
        windows = _duration_windows_from_allocations(activities, starts, finishes, durations, allocations, limit_days_by_key)
        current_starts, current_finishes, current_durations = _window_maps(windows)
        previous_critical_keys = list(critical_keys)
    else:
        stop_reason = "ITERATION_LIMIT"
        warnings.append("全局等比压缩达到迭代上限，已停止继续压缩。")

    final_target_finish = _target_finish_date(activities, target_keys, current_starts, current_finishes)
    achieved_days = (
        min(requested_days, max(0, (baseline_date - final_target_finish).days))
        if final_target_finish is not None
        else sum(allocations.values())
    )
    if requested_days > achieved_days and stop_reason not in {"CRITICAL_PATH_UNCHANGED", "NO_COMPRESSIBLE_SLACK"}:
        warnings.append(
            f"全局等比压缩预计实现 {achieved_days} 天，少于目标 {requested_days} 天。"
        )

    result_slack_by_key: dict[str, int] = {}
    for key, limit_days in limit_days_by_key.items():
        result_slack_by_key[key] = max(0, durations.get(key, 0) - limit_days)
    critical_path_keys = initial_critical_keys or _critical_path_keys(activities, target_keys, starts, finishes, warnings)
    critical_union = [key for path in iteration_paths for key in path]
    results = _duration_results_from_windows(
        activities,
        starts,
        durations,
        windows,
        allocations,
        result_slack_by_key,
        critical_union or critical_path_keys,
    )
    return DurationCompressionRun(
        results=results,
        critical_path_keys=critical_path_keys,
        allocations=allocations,
        requested_compression_days=requested_days,
        achieved_compression_days=achieved_days,
        strategy=STRATEGY_PROPORTIONAL,
        critical_path_iterations=iteration_paths or [critical_path_keys],
        stop_reason=stop_reason,
        final_target_finish_date=final_target_finish,
    )


def _strategy_compression_capacity(
    *,
    strategy: str,
    critical_path_keys: list[str],
    slack_by_key: dict[str, int],
    top_n: int,
) -> int:
    normalized_strategy = strategy.strip().upper()
    if normalized_strategy == STRATEGY_TOP3_SLACK:
        path_index = {key: index for index, key in enumerate(critical_path_keys)}
        candidates = [(key, slack) for key, slack in slack_by_key.items() if slack > 0]
        candidates.sort(key=lambda item: (-item[1], path_index[item[0]], item[0]))
        return sum(slack for _key, slack in candidates[: max(0, top_n)])
    if normalized_strategy == STRATEGY_PROPORTIONAL:
        return sum(slack_by_key.values())
    raise ValueError(f"Unsupported duration compression strategy: {strategy}")


def compute_duration_compression_schedule(
    activities: dict[str, Activity],
    *,
    target_keys: list[str],
    baseline_date: date,
    anchor_date: date,
    limit_duration_by_key: dict[str, object],
    strategy: str = STRATEGY_TOP3_SLACK,
    top_n: int = 3,
    warnings: list[str],
) -> DurationCompressionRun:
    requested_days = max(0, (baseline_date - anchor_date).days)
    normalized_strategy = strategy.strip().upper()
    if normalized_strategy == STRATEGY_PROPORTIONAL:
        return _compute_dynamic_proportional_duration_compression(
            activities,
            target_keys=target_keys,
            baseline_date=baseline_date,
            anchor_date=anchor_date,
            limit_duration_by_key=limit_duration_by_key,
            warnings=warnings,
        )

    starts, finishes, durations = _parse_activity_windows(activities, warnings)
    critical_keys = _critical_path_keys(activities, target_keys, starts, finishes, warnings)
    limit_days_by_key = _critical_path_limit_duration_days(
        activities,
        critical_keys,
        limit_duration_by_key,
        warnings,
    )
    slack_by_key = _critical_path_slack_days(critical_keys, durations, limit_days_by_key)
    total_slack = sum(slack_by_key.values())
    strategy_capacity = _strategy_compression_capacity(
        strategy=normalized_strategy,
        critical_path_keys=critical_keys,
        slack_by_key=slack_by_key,
        top_n=top_n,
    )
    if requested_days > strategy_capacity:
        warnings.append(
            f"初始关键路径按 {normalized_strategy} 可压缩空闲合计 {strategy_capacity} 天，"
            f"少于目标 {requested_days} 天；活动达到极限工期后固定，其余活动继续压缩，无法完全压缩。"
        )

    allocations = _allocate_duration_compression(
        strategy=normalized_strategy,
        critical_path_keys=critical_keys,
        slack_by_key=slack_by_key,
        durations=durations,
        requested_days=requested_days,
        top_n=top_n,
    )
    achieved_days = sum(allocations.values())
    windows = _duration_windows_from_allocations(activities, starts, finishes, durations, allocations, limit_days_by_key)
    window_starts, window_finishes, _window_durations = _window_maps(windows)
    final_target_finish = _target_finish_date(activities, target_keys, window_starts, window_finishes)
    results = _duration_results_from_windows(
        activities,
        starts,
        durations,
        windows,
        allocations,
        slack_by_key,
        critical_keys,
    )

    return DurationCompressionRun(
        results=results,
        critical_path_keys=critical_keys,
        allocations=allocations,
        requested_compression_days=requested_days,
        achieved_compression_days=achieved_days,
        strategy=normalized_strategy,
        critical_path_iterations=[critical_keys],
        stop_reason=(
            "TARGET_REACHED"
            if final_target_finish is not None and final_target_finish <= anchor_date
            else "PARTIAL_CAPACITY"
        ),
        final_target_finish_date=final_target_finish,
    )


def compute_duration_extension_schedule(
    activities: dict[str, Activity],
    *,
    target_keys: list[str],
    baseline_date: date,
    anchor_date: date,
    warnings: list[str],
) -> DurationExtensionRun:
    requested_days = max(0, (anchor_date - baseline_date).days)
    starts, finishes, durations = _parse_activity_windows(activities, warnings)
    critical_keys = _critical_path_keys(activities, target_keys, starts, finishes, warnings)
    critical_set = set(critical_keys)
    allocations = _allocate_extension_proportionally(critical_keys, durations, requested_days)
    achieved_days = sum(allocations.values())

    windows: dict[str, tuple[date, date]] = {}
    results: dict[str, DurationExtensionResult] = {}
    for key in _topo_sort(activities):
        if key not in starts or key not in finishes:
            continue
        activity = activities[key]
        original_start = starts[key]
        original_finish = finishes[key]
        original_duration = durations[key]
        extension_days = allocations.get(key, 0)
        extended_duration = max(1, original_duration + extension_days) if original_duration > 0 else 0

        dependency_keys = [
            dependency_key
            for dependency_key in activity.dependency_keys
            if dependency_key in windows and dependency_key in finishes
        ]
        if dependency_keys:
            original_ready = max(finishes[dependency_key] + timedelta(days=1) for dependency_key in dependency_keys)
            refreshed_ready = max(windows[dependency_key][1] + timedelta(days=1) for dependency_key in dependency_keys)
            proposed_start = original_start + timedelta(days=(refreshed_ready - original_ready).days)
            if proposed_start < refreshed_ready:
                proposed_start = refreshed_ready
        else:
            proposed_start = original_start

        proposed_finish = proposed_start + timedelta(days=max(0, extended_duration - 1))
        windows[key] = (proposed_start, proposed_finish)
        results[key] = DurationExtensionResult(
            start=proposed_start,
            finish=proposed_finish,
            original_duration_days=original_duration,
            extended_duration_days=extended_duration,
            extension_days=extension_days,
            is_critical_path=key in critical_set,
            start_shift_days=(proposed_start - original_start).days,
        )

    return DurationExtensionRun(
        results=results,
        critical_path_keys=critical_keys,
        allocations=allocations,
        requested_extension_days=requested_days,
        achieved_extension_days=achieved_days,
        strategy=STRATEGY_PROPORTIONAL_EXTENSION,
    )
