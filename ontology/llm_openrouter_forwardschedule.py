#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于交付计划做活动正排，并输出参考 `zjyd倒排依赖图_2026-08-14.md` 的 Mermaid Gantt Markdown 文件。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from schedule_plan_activities import (
    Activity,
    activity_display_name,
    normalize_text,
    parse_activity_key_from_anchor_label,
)
from schedule_ontology import LocalScheduleOntology

# 正排 Gantt section：显式结构名，不按活动 ID/名称关键词做业务写死分类
DEFAULT_INPUT_ANCHOR_SECTION_NAME = "输入锚点"
DEFAULT_SHARED_SECTION_NAME = "共用依赖"
DEFAULT_REMAINING_SECTION_NAME = "其他活动"

DATE_FORMAT = "%Y-%m-%d"


@dataclass
class ForwardScheduleResult:
    start: date
    finish: date
    source: str
    explicit_anchor: bool = False


@dataclass
class AnchorWindow:
    start: date
    finish: date
    source: str
    explicit: bool = True


def parse_date(value: str) -> date:
    return datetime.strptime(value, DATE_FORMAT).date()


def format_date(value: date) -> str:
    return value.strftime(DATE_FORMAT)


def inclusive_days(start: date, finish: date) -> int:
    return (finish - start).days + 1


def build_successors(activities: dict[str, Activity]) -> dict[str, list[str]]:
    successors: defaultdict[str, list[str]] = defaultdict(list)
    for activity in activities.values():
        for dependency_key in activity.dependency_keys:
            successors[dependency_key].append(activity.key)
    return dict(successors)


def parse_anchor_spec(raw_value: str) -> tuple[str, date, date]:
    if "=" not in raw_value:
        raise ValueError(f"锚点格式错误：`{raw_value}`，应为 `活动=YYYY-MM-DD` 或 `活动=YYYY-MM-DD,YYYY-MM-DD`。")
    raw_name, raw_dates = raw_value.split("=", 1)
    activity_name = parse_activity_key_from_anchor_label(raw_name)
    parts = [normalize_text(item) for item in re.split(r"[,，]", raw_dates) if normalize_text(item)]
    if len(parts) == 1:
        finish = parse_date(parts[0])
        return activity_name, finish, finish
    if len(parts) == 2:
        start = parse_date(parts[0])
        finish = parse_date(parts[1])
        if finish < start:
            raise ValueError(f"锚点时间非法：`{raw_value}`，结束日期早于开始日期。")
        return activity_name, start, finish
    raise ValueError(f"锚点格式错误：`{raw_value}`，日期只支持 1 个或 2 个。")


def collect_explicit_anchors(args: argparse.Namespace) -> dict[str, AnchorWindow]:
    anchors: dict[str, AnchorWindow] = {}
    all_specs = []
    all_specs.extend(args.finish or [])
    all_specs.extend(args.anchor or [])
    for raw_value in all_specs:
        key, start, finish = parse_anchor_spec(raw_value)
        anchors[key] = AnchorWindow(start=start, finish=finish, source="explicit", explicit=True)
    return anchors


def resolve_explicit_anchor_keys(
    ontology: LocalScheduleOntology,
    anchors: dict[str, AnchorWindow],
) -> dict[str, AnchorWindow]:
    resolved: dict[str, AnchorWindow] = {}
    row_set = ontology.objects.DeliveryPlanRow
    for raw_key, anchor in anchors.items():
        resolved_key = row_set.resolve_key(raw_key)
        resolved[resolved_key] = anchor
    return resolved


def plan_root_anchor(activity: Activity) -> AnchorWindow | None:
    planned_start = activity.planned_start
    planned_end = activity.planned_end
    if planned_start and planned_end:
        start = parse_date(planned_start)
        finish = parse_date(planned_end)
        return AnchorWindow(start=start, finish=finish, source="plan-root", explicit=False)
    if planned_end:
        finish = parse_date(planned_end)
        if activity.duration_days > 0:
            start = finish - timedelta(days=activity.duration_days - 1)
        else:
            start = finish
        return AnchorWindow(start=start, finish=finish, source="plan-root", explicit=False)
    if planned_start:
        start = parse_date(planned_start)
        if activity.duration_days > 0:
            finish = start + timedelta(days=activity.duration_days - 1)
        else:
            finish = start
        return AnchorWindow(start=start, finish=finish, source="plan-root", explicit=False)
    return None


def topo_sort(activities: dict[str, Activity]) -> list[str]:
    indegree = {key: len(activity.dependency_keys) for key, activity in activities.items()}
    queue = deque(
        sorted(
            (key for key, value in indegree.items() if value == 0),
            key=lambda k: (activities[k].name, k),
        )
    )
    ordered: list[str] = []

    while queue:
        key = queue.popleft()
        ordered.append(key)
        for successor_key, successor in activities.items():
            if key in successor.dependency_keys:
                indegree[successor_key] -= 1
                if indegree[successor_key] == 0:
                    queue.append(successor_key)

    if len(ordered) != len(activities):
        raise RuntimeError("活动依赖中存在循环，无法完成正排。")
    return ordered


def derive_finish_from_duration(start: date, duration_days: int) -> date:
    if duration_days <= 0:
        return start
    return start + timedelta(days=duration_days - 1)


def derive_start_from_finish(finish: date, duration_days: int) -> date:
    if duration_days <= 0:
        return finish
    return finish - timedelta(days=duration_days - 1)


def compute_forward_schedule(
    activities: dict[str, Activity],
    explicit_anchors: dict[str, AnchorWindow],
    use_plan_roots: bool,
    warnings: list[str],
) -> tuple[dict[str, ForwardScheduleResult], set[str]]:
    results: dict[str, ForwardScheduleResult] = {}
    successors = build_successors(activities)
    ordered_keys = topo_sort(activities)
    root_fallback_keys: set[str] = set()

    for activity_key in ordered_keys:
        activity = activities[activity_key]
        anchor = explicit_anchors.get(activity_key)

        if anchor is not None:
            if anchor.start == anchor.finish and activity.duration_days > 0:
                start = derive_start_from_finish(anchor.finish, activity.duration_days)
                finish = anchor.finish
            else:
                start = anchor.start
                finish = anchor.finish
            results[activity_key] = ForwardScheduleResult(
                start=start,
                finish=finish,
                source=anchor.source,
                explicit_anchor=True,
            )
            continue

        if not activity.dependency_keys:
            if use_plan_roots:
                root_anchor = plan_root_anchor(activity)
                if root_anchor is not None:
                    results[activity_key] = ForwardScheduleResult(
                        start=root_anchor.start,
                        finish=root_anchor.finish,
                        source=root_anchor.source,
                        explicit_anchor=False,
                    )
                    root_fallback_keys.add(activity_key)
                else:
                    warnings.append(
                        f"根活动 `{activity_display_name(activity)}` 没有可用输入时间，也没有原计划时间，已跳过。"
                    )
            else:
                warnings.append(
                    f"根活动 `{activity_display_name(activity)}` 未提供输入时间，且未启用 `--use-plan-roots`，已跳过。"
                )
            continue

        missing_deps = [dep_key for dep_key in activity.dependency_keys if dep_key not in results]
        if missing_deps:
            warnings.append(
                f"活动 `{activity_display_name(activity)}` 有未排定前置："
                f"{'、'.join(activity_display_name(activities[key]) for key in missing_deps)}，已跳过。"
            )
            continue

        earliest_start = max(results[dep_key].finish for dep_key in activity.dependency_keys) + timedelta(days=1)
        earliest_finish = derive_finish_from_duration(earliest_start, activity.duration_days)
        results[activity_key] = ForwardScheduleResult(
            start=earliest_start,
            finish=earliest_finish,
            source="dependency",
            explicit_anchor=False,
        )

    for activity_key, result in results.items():
        activity = activities[activity_key]
        if not activity.dependency_keys or not result.explicit_anchor:
            continue
        if any(dep_key not in results for dep_key in activity.dependency_keys):
            continue
        required_start = max(results[dep_key].finish for dep_key in activity.dependency_keys) + timedelta(days=1)
        if result.start < required_start:
            warnings.append(
                f"显式输入的 `{activity_display_name(activity)}` 时间早于前置完成约束："
                f"输入开始 {format_date(result.start)}，最早应为 {format_date(required_start)}。"
            )

    filtered, isolated_root_keys = filter_output_activities(
        activities, successors, results, explicit_anchors
    )
    if root_fallback_keys:
        warnings.append(
            "未显式输入的根活动已默认沿用原计划时间参与正排。"
        )
    if isolated_root_keys:
        warnings.append(
            "以下活动在原表中未建立可串联依赖，当前仅按独立根任务存在，未纳入主图："
            + "、".join(
                activity_display_name(activities[key])
                for key in sorted(isolated_root_keys, key=lambda item: (activities[item].name, item))
            )
        )
    return filtered, root_fallback_keys


def filter_output_activities(
    activities: dict[str, Activity],
    successors: dict[str, list[str]],
    results: dict[str, ForwardScheduleResult],
    explicit_anchors: dict[str, AnchorWindow],
) -> tuple[dict[str, ForwardScheduleResult], set[str]]:
    keep: set[str] = set()
    isolated_root_keys: set[str] = set()
    for key in results:
        if key in explicit_anchors:
            keep.add(key)
            continue
        if activities[key].dependency_keys:
            keep.add(key)
            continue
        if successors.get(key):
            keep.add(key)
            continue
        if results[key].source == "plan-root" and should_warn_isolated_root(activities[key]):
            isolated_root_keys.add(key)

    changed = True
    while changed:
        changed = False
        for key in list(keep):
            for dep_key in activities[key].dependency_keys:
                if dep_key in results and dep_key not in keep:
                    keep.add(dep_key)
                    changed = True

    return {key: results[key] for key in keep}, isolated_root_keys


def should_warn_isolated_root(activity: Activity) -> bool:
    activity_id = activity.activity_id
    if activity_id.endswith(".0"):
        return False
    return bool(activity.sla_raw or not activity_id)


def topo_index_in_subset(
    activities: dict[str, Activity],
    keys: set[str],
) -> dict[str, int]:
    """在 keys 子图上按依赖关系拓扑，用于同起止日时的条目标顺序。"""
    keys = {k for k in keys if k in activities}
    if not keys:
        return {}
    indegree: dict[str, int] = {}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for k in keys:
        preds = [d for d in activities[k].dependency_keys if d in keys]
        indegree[k] = len(preds)
        for p in preds:
            outgoing[p].append(k)
    queue = sorted(
        (k for k in keys if indegree[k] == 0),
        key=lambda x: (activities[x].name, x),
    )
    order: list[str] = []
    head = 0
    while head < len(queue):
        u = queue[head]
        head += 1
        order.append(u)
        for v in sorted(outgoing[u], key=lambda x: (activities[x].name, x)):
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    if len(order) < len(keys):
        rest = [k for k in keys if k not in order]
        rest.sort(key=lambda x: (activities[x].name, x))
        order.extend(rest)
    return {k: i for i, k in enumerate(order)}


def collect_forward_memberships(
    result_keys: set[str],
    anchor_keys: list[str],
    successors: dict[str, list[str]],
) -> dict[str, set[str]]:
    """从各显式锚点沿后继正向遍历，得到每个活动属于哪些「锚点下游」；用于分组合并。"""
    memberships: dict[str, set[str]] = defaultdict(set)
    for ak in anchor_keys:
        if ak not in result_keys:
            continue
        stack = [ak]
        seen: set[str] = set()
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            if u not in result_keys:
                continue
            memberships[u].add(ak)
            for v in successors.get(u, ()):
                if v in result_keys:
                    stack.append(v)
    return {k: v for k, v in memberships.items()}


def order_keys_forward(
    activity_keys: Iterable[str],
    activities: dict[str, Activity],
    results: dict[str, ForwardScheduleResult],
    topo_rank: dict[str, int] | None = None,
) -> list[str]:
    tr = topo_rank or {}
    return sorted(
        activity_keys,
        key=lambda key: (
            results[key].start,
            results[key].finish,
            activities[key].duration_days,
            tr.get(key, 0),
            activities[key].name,
            key,
        ),
    )


def build_sections(
    activities: dict[str, Activity],
    results: dict[str, ForwardScheduleResult],
    explicit_anchors: dict[str, AnchorWindow],
    successors: dict[str, list[str]],
    input_anchor_section_name: str = DEFAULT_INPUT_ANCHOR_SECTION_NAME,
    shared_section_name: str = DEFAULT_SHARED_SECTION_NAME,
    remaining_section_name: str = DEFAULT_REMAINING_SECTION_NAME,
) -> list[tuple[str, list[str]]]:
    result_keys = set(results.keys())
    anchor_keys = [k for k in explicit_anchors if k in result_keys]
    topo_rank = topo_index_in_subset(activities, result_keys)
    memberships = collect_forward_memberships(result_keys, anchor_keys, successors)
    exp_set = set(anchor_keys)

    sections: list[tuple[str, list[str]]] = []

    input_keys = [k for k in explicit_anchors if k in result_keys]
    if input_keys:
        sections.append(
            (input_anchor_section_name, order_keys_forward(input_keys, activities, results, topo_rank))
        )

    shared_keys = [
        k
        for k in result_keys
        if k not in exp_set and len(memberships.get(k, set())) > 1
    ]
    if shared_keys:
        sections.append(
            (shared_section_name, order_keys_forward(shared_keys, activities, results, topo_rank))
        )

    for ak in anchor_keys:
        unique_keys = [
            k
            for k in result_keys
            if k not in exp_set and memberships.get(k) == {ak}
        ]
        if unique_keys:
            sections.append(
                (
                    activity_display_name(activities[ak]),
                    order_keys_forward(unique_keys, activities, results, topo_rank),
                )
            )

    assigned = {key for _, key_list in sections for key in key_list}
    remaining = [k for k in result_keys if k not in assigned]
    if remaining:
        sections.append(
            (remaining_section_name, order_keys_forward(remaining, activities, results, topo_rank))
        )
    return sections


def mermaid_line(activity: Activity, result: ForwardScheduleResult) -> str:
    label = activity_display_name(activity)
    start_text = format_date(result.start)
    finish_text = format_date(result.finish)
    if result.explicit_anchor:
        if result.start == result.finish:
            return f"    {label} 输入={finish_text} : milestone, {finish_text}, 0d"
        return f"    {label} 输入窗口 : active, {start_text}, {inclusive_days(result.start, result.finish)}d"
    if activity.duration_days <= 0:
        return f"    {label} EF={finish_text} : milestone, {finish_text}, 0d"
    return f"    {label} : {start_text}, {activity.duration_days}d"


def build_mermaid_gantt(
    source_path: Path,
    activities: dict[str, Activity],
    results: dict[str, ForwardScheduleResult],
    explicit_anchors: dict[str, AnchorWindow],
    input_anchor_section_name: str = DEFAULT_INPUT_ANCHOR_SECTION_NAME,
    shared_section_name: str = DEFAULT_SHARED_SECTION_NAME,
    remaining_section_name: str = DEFAULT_REMAINING_SECTION_NAME,
) -> str:
    successors = build_successors(activities)
    sections = build_sections(
        activities,
        results,
        explicit_anchors,
        successors,
        input_anchor_section_name=input_anchor_section_name,
        shared_section_name=shared_section_name,
        remaining_section_name=remaining_section_name,
    )
    lines = [
        "```mermaid",
        "gantt",
        f'    title "project:{source_path.stem} - 正排核对图"',
        "    dateFormat YYYY-MM-DD",
        "    axisFormat %m/%d",
        "",
    ]
    for section_name, keys in sections:
        lines.append(f"    section {section_name}")
        for key in keys:
            lines.append(mermaid_line(activities[key], results[key]))
        lines.append("")
    while lines and not lines[-1]:
        lines.pop()
    lines.append("```")
    return "\n".join(lines)


def build_md_content(
    source_path: Path,
    activities: dict[str, Activity],
    results: dict[str, ForwardScheduleResult],
    explicit_anchors: dict[str, AnchorWindow],
    warnings: list[str],
    input_anchor_section_name: str = DEFAULT_INPUT_ANCHOR_SECTION_NAME,
    shared_section_name: str = DEFAULT_SHARED_SECTION_NAME,
    remaining_section_name: str = DEFAULT_REMAINING_SECTION_NAME,
) -> str:
    anchor_summaries = []
    for key, anchor in sorted(explicit_anchors.items(), key=lambda item: (item[1].start, item[0])):
        disp = activity_display_name(activities[key])
        if anchor.start == anchor.finish:
            anchor_summaries.append(f"`{disp}={format_date(anchor.finish)}`")
        else:
            anchor_summaries.append(
                f"`{disp}={format_date(anchor.start)}~{format_date(anchor.finish)}`"
            )

    lines = [
        f"# {source_path.stem} 正排依赖图",
        "",
        f"- 来源文件：`{source_path.name}`",
        f"- 输入锚点：{'、'.join(anchor_summaries)}",
        f"- 说明：未显式输入的根活动默认沿用原计划时间参与正排",
        "",
        build_mermaid_gantt(
            source_path=source_path,
            activities=activities,
            results=results,
            explicit_anchors=explicit_anchors,
            input_anchor_section_name=input_anchor_section_name,
            shared_section_name=shared_section_name,
            remaining_section_name=remaining_section_name,
        ),
    ]

    if warnings:
        lines.extend(["", "## 告警", ""])
        for warning in sorted(dict.fromkeys(warnings)):
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def get_openrouter_config(args: argparse.Namespace) -> tuple[str, str, str]:
    api_key = args.openrouter_api_key or os.getenv("OPENROUTER_API_KEY", "")
    base_url = args.openrouter_base_url or os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    model = args.openrouter_model or os.getenv("OPENROUTER_MODEL", "")
    return api_key, base_url.rstrip("/"), model


def fetch_llm_summary(
    activities: dict[str, Activity],
    results: dict[str, ForwardScheduleResult],
    warnings: list[str],
    args: argparse.Namespace,
) -> tuple[str | None, list[str]]:
    api_key, base_url, model = get_openrouter_config(args)
    if not api_key or not model:
        warnings.append("已启用 `--llm-summary`，但未完整提供 OpenRouter 配置，已跳过模型总结。")
        return None, warnings

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是交付计划分析助手。请基于已计算好的正排结果，"
                    "输出 3-5 句简短中文总结，不要重新计算日期，不要输出 Markdown 表格。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "results": {
                            str(key): {
                                "name": activity_display_name(activities[key]),
                                "start": format_date(result.start),
                                "finish": format_date(result.finish),
                                "source": result.source,
                            }
                            for key, result in results.items()
                        },
                        "warnings": warnings,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.2,
    }

    request = urllib.request.Request(
        url=f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        warnings.append(
            f"OpenRouter 调用失败（HTTP {exc.code}），已跳过模型总结。响应片段：{error_body[:240]}"
        )
        return None, warnings
    except Exception as exc:  # pragma: no cover
        warnings.append(f"OpenRouter 调用失败，已跳过模型总结：{exc}")
        return None, warnings

    choices = body.get("choices") or []
    if not choices:
        warnings.append("OpenRouter 未返回可用内容，已跳过模型总结。")
        return None, warnings

    content = ((choices[0].get("message") or {}).get("content") or "").strip()
    if not content:
        warnings.append("OpenRouter 返回内容为空，已跳过模型总结。")
        return None, warnings

    return content, warnings


def default_output_path(source_path: Path, explicit_anchors: dict[str, AnchorWindow]) -> Path:
    key_parts = []
    for key, anchor in sorted(explicit_anchors.items(), key=lambda item: (item[1].start, item[0])):
        activity_name = re.sub(r"[\\/:*?\"<>|@]+", "_", key)
        key_parts.append(f"{activity_name}_{format_date(anchor.finish)}")
    suffix = "__".join(key_parts[:2]) if key_parts else "forward"
    return source_path.with_name(f"{source_path.stem}_正排依赖图_{suffix}.md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="交付计划正排并输出 Mermaid Gantt Markdown。")
    parser.add_argument("--file", required=True, help="计划文件路径，支持 .csv / .xlsx")
    parser.add_argument(
        "--finish",
        action="append",
        help="显式输入完成时间，格式 `活动=YYYY-MM-DD`；多 PoD 时活动可用 `活动名@管理单元` 或 `管理单元::活动名[::行号片段]`，可重复传入",
    )
    parser.add_argument(
        "--anchor",
        action="append",
        help="显式时间窗口，格式 `活动=YYYY-MM-DD,YYYY-MM-DD` 或 `活动=YYYY-MM-DD`；活动名规则同 --finish",
    )
    parser.add_argument(
        "--no-use-plan-roots",
        action="store_true",
        help="不使用原计划中的根活动时间作为默认锚点",
    )
    parser.add_argument(
        "--input-anchor-section-name",
        default=DEFAULT_INPUT_ANCHOR_SECTION_NAME,
        help="显式锚点活动在 Gantt 中的 section 名称，默认「输入锚点」",
    )
    parser.add_argument(
        "--shared-section-name",
        default=DEFAULT_SHARED_SECTION_NAME,
        help="多锚点共用下游在 Gantt 中的 section 名称，默认「共用依赖」",
    )
    parser.add_argument(
        "--remaining-section-name",
        default=DEFAULT_REMAINING_SECTION_NAME,
        help="无法归入任一锚点下游时的 section 名称，默认「其他活动」",
    )
    parser.add_argument("--output", help="输出 Markdown 文件路径；未传时自动生成新 .md 文件")
    parser.add_argument("--llm-summary", action="store_true", help="调用 OpenRouter 追加简短总结")
    parser.add_argument("--openrouter-api-key", help="OpenRouter API Key")
    parser.add_argument(
        "--openrouter-base-url",
        help="OpenRouter Base URL，默认读取环境变量或 https://openrouter.ai/api/v1",
    )
    parser.add_argument("--openrouter-model", help="OpenRouter 模型名")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    source_path = Path(args.file).expanduser().resolve()
    if not source_path.exists():
        print(f"文件不存在：{source_path}", file=sys.stderr)
        return 1

    try:
        explicit_anchors = collect_explicit_anchors(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not explicit_anchors:
        print("请至少通过 `--finish` 或 `--anchor` 提供一个输入锚点。", file=sys.stderr)
        return 1

    try:
        ontology = LocalScheduleOntology.from_file(source_path)
        activities = ontology.activities
        explicit_anchors = resolve_explicit_anchor_keys(ontology, explicit_anchors)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    schedule_run = ontology.functions.forward_schedule(
        explicit_anchors=explicit_anchors,
        use_plan_roots=not args.no_use_plan_roots,
        compute=compute_forward_schedule,
    )
    results = schedule_run.results
    warnings = schedule_run.warnings

    markdown = build_md_content(
        source_path=source_path,
        activities=activities,
        results=results,
        explicit_anchors=explicit_anchors,
        warnings=warnings,
        input_anchor_section_name=args.input_anchor_section_name,
        shared_section_name=args.shared_section_name,
        remaining_section_name=args.remaining_section_name,
    )

    if args.llm_summary:
        llm_summary, warnings = fetch_llm_summary(
            activities=activities,
            results=results,
            warnings=warnings,
            args=args,
        )
        markdown = build_md_content(
            source_path=source_path,
            activities=activities,
            results=results,
            explicit_anchors=explicit_anchors,
            warnings=warnings,
            input_anchor_section_name=args.input_anchor_section_name,
            shared_section_name=args.shared_section_name,
            remaining_section_name=args.remaining_section_name,
        )
        if llm_summary:
            markdown = markdown.rstrip() + "\n\n## OpenRouter 总结\n\n" + llm_summary + "\n"

    output_path = Path(args.output).expanduser().resolve() if args.output else default_output_path(
        source_path, explicit_anchors
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"已生成正排 Markdown：{output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
