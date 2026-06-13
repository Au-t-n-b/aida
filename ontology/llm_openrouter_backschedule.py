#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于交付计划做活动倒排，并输出参考 `zjyd倒排依赖图样例.md` 的 Mermaid Gantt Markdown 文件。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from schedule_plan_activities import (
    Activity,
    activity_display_name,
)
from schedule_ontology import LocalScheduleOntology

# 多目标在依赖图中共同经过的活动，用于 Gantt section 标题（非业务关键词分类）
DEFAULT_SHARED_SECTION_NAME = "共用依赖"

DATE_FORMAT = "%Y-%m-%d"


@dataclass
class BackScheduleResult:
    latest_finish: date
    latest_start: date


def parse_date(value: str) -> date:
    return datetime.strptime(value, DATE_FORMAT).date()


def format_date(value: date) -> str:
    return value.strftime(DATE_FORMAT)


def collect_closure(activities: dict[str, Activity], target_keys: list[str]) -> dict[str, set[str]]:
    memberships: dict[str, set[str]] = defaultdict(set)
    for target_key in target_keys:
        stack = [target_key]
        visited: set[str] = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            memberships[current].add(target_key)
            stack.extend(activities[current].dependency_keys)
    return memberships


def compute_back_schedule(
    activities: dict[str, Activity],
    target_keys: list[str],
    anchor_date: date,
    warnings: list[str],
) -> dict[str, BackScheduleResult]:
    constraints: dict[str, date] = {}
    queue: deque[tuple[str, date]] = deque((target_key, anchor_date) for target_key in target_keys)

    for target_key in target_keys:
        target = activities[target_key]
        if not target.dependency_names:
            warnings.append(
                f"目标活动 `{activity_display_name(target)}` 在原计划中未填写依赖活动，"
                f"倒排结果仅包含该活动自身。"
            )

    while queue:
        activity_key, finish_limit = queue.popleft()
        existing = constraints.get(activity_key)
        if existing is not None and existing <= finish_limit:
            continue
        constraints[activity_key] = finish_limit

        activity = activities[activity_key]
        if activity.duration_days > 0:
            latest_start = finish_limit - timedelta(days=activity.duration_days - 1)
        else:
            latest_start = finish_limit

        predecessor_finish = latest_start - timedelta(days=1)
        for dependency_key in activity.dependency_keys:
            queue.append((dependency_key, predecessor_finish))

    results: dict[str, BackScheduleResult] = {}
    for activity_key, latest_finish in constraints.items():
        activity = activities[activity_key]
        if activity.duration_days > 0:
            latest_start = latest_finish - timedelta(days=activity.duration_days - 1)
        else:
            latest_start = latest_finish
        results[activity_key] = BackScheduleResult(
            latest_finish=latest_finish,
            latest_start=latest_start,
        )
    return results


def topo_index_in_subset(
    activities: dict[str, Activity],
    keys: set[str],
) -> dict[str, int]:
    """在 keys 子图上做拓扑排序，得到依赖先后序号（同层按活动名稳定）。"""
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


def classify_section(
    activity: Activity,
    memberships: dict[str, set[str]],
    target_key: str | None,
    target_names: dict[str, str],
    shared_section_name: str,
) -> str:
    touched = memberships.get(activity.key, set())
    if len(touched) > 1:
        return shared_section_name
    if target_key is not None:
        return target_names[target_key]
    return "其他活动"


def order_keys(
    activity_keys: Iterable[str],
    activities: dict[str, Activity],
    results: dict[str, BackScheduleResult],
    topo_rank: dict[str, int] | None = None,
) -> list[str]:
    tr = topo_rank or {}
    return sorted(
        activity_keys,
        key=lambda key: (
            results[key].latest_start,
            results[key].latest_finish,
            activities[key].duration_days,
            tr.get(key, 0),
            activities[key].name,
            key,
        ),
    )


def collect_target_unique_keys(
    activities: dict[str, Activity],
    target_key: str,
    memberships: dict[str, set[str]],
) -> set[str]:
    stack = [target_key]
    unique: set[str] = set()
    visited: set[str] = set()
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        if memberships.get(current) == {target_key}:
            unique.add(current)
        stack.extend(activities[current].dependency_keys)
    return unique


def build_sections(
    activities: dict[str, Activity],
    results: dict[str, BackScheduleResult],
    target_keys: list[str],
    memberships: dict[str, set[str]],
    shared_section_name: str = DEFAULT_SHARED_SECTION_NAME,
) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    target_names = {
        target_key: activity_display_name(activities[target_key])
        for target_key in target_keys
    }
    topo_rank = topo_index_in_subset(activities, set(results.keys()))

    shared_keys = [
        key
        for key in results
        if len(memberships.get(key, set())) > 1
    ]
    if shared_keys:
        sections.append(
            (
                shared_section_name,
                order_keys(shared_keys, activities, results, topo_rank),
            )
        )

    for target_key in target_keys:
        unique_keys = collect_target_unique_keys(activities, target_key, memberships)
        unique_keys = {key for key in unique_keys if key in results}
        if unique_keys:
            section_name = activity_display_name(activities[target_key])
            sections.append(
                (section_name, order_keys(unique_keys, activities, results, topo_rank))
            )

    assigned = {key for _, keys in sections for key in keys}
    remaining = [key for key in results if key not in assigned]
    if remaining:
        buckets: defaultdict[str, list[str]] = defaultdict(list)
        for key in remaining:
            target_key = next(iter(memberships.get(key, [])), None)
            section_name = classify_section(
                activities[key], memberships, target_key, target_names, shared_section_name
            )
            buckets[section_name].append(key)
        for section_name, keys in buckets.items():
            sections.append((section_name, order_keys(keys, activities, results, topo_rank)))
    return sections


def mermaid_line(activity: Activity, schedule: BackScheduleResult, is_target: bool) -> str:
    label = activity_display_name(activity)
    start_text = format_date(schedule.latest_start)
    finish_text = format_date(schedule.latest_finish)
    if activity.duration_days <= 0:
        return f"    {label} LF={finish_text} : milestone, {finish_text}, 0d"
    if is_target:
        return f"    {label} : crit, {start_text}, {activity.duration_days}d"
    return f"    {label} : {start_text}, {activity.duration_days}d"


def build_mermaid_gantt(
    source_path: Path,
    activities: dict[str, Activity],
    results: dict[str, BackScheduleResult],
    sections: list[tuple[str, list[str]]],
    target_keys: list[str],
    anchor_date: date,
) -> str:
    title = (
        f"project:{source_path.stem} - 上电倒排核对图（倒排至 {format_date(anchor_date)}）"
    )
    lines = [
        "```mermaid",
        "gantt",
        f'    title "{title}"',
        "    dateFormat YYYY-MM-DD",
        "    axisFormat %m/%d",
        "",
    ]

    target_key_set = set(target_keys)
    for section_name, activity_keys in sections:
        lines.append(f"    section {section_name}")
        for activity_key in activity_keys:
            lines.append(
                mermaid_line(
                    activities[activity_key],
                    results[activity_key],
                    activity_key in target_key_set,
                )
            )
        lines.append("")

    while lines and not lines[-1]:
        lines.pop()
    lines.append("```")
    return "\n".join(lines)


def build_md_content(
    source_path: Path,
    activities: dict[str, Activity],
    results: dict[str, BackScheduleResult],
    target_keys: list[str],
    anchor_date: date,
    warnings: list[str],
    shared_section_name: str = DEFAULT_SHARED_SECTION_NAME,
) -> str:
    memberships = collect_closure(activities, target_keys)
    sections = build_sections(
        activities,
        results,
        target_keys,
        memberships,
        shared_section_name=shared_section_name,
    )
    mermaid = build_mermaid_gantt(
        source_path=source_path,
        activities=activities,
        results=results,
        sections=sections,
        target_keys=target_keys,
        anchor_date=anchor_date,
    )

    lines = [
        f"# {source_path.stem} 倒排依赖图",
        "",
        f"- 来源文件：`{source_path.name}`",
        f"- 目标日期：`{format_date(anchor_date)}`",
        f"- 目标活动：`{'`、`'.join(activity_display_name(activities[key]) for key in target_keys)}`",
        "",
        mermaid,
    ]

    if warnings:
        lines.extend(["", "## 告警", ""])
        for item in sorted(dict.fromkeys(warnings)):
            lines.append(f"- {item}")
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
    results: dict[str, BackScheduleResult],
    target_keys: list[str],
    warnings: list[str],
    args: argparse.Namespace,
) -> tuple[str | None, list[str]]:
    api_key, base_url, model = get_openrouter_config(args)
    if not api_key or not model:
        warnings.append(
            "已启用 `--llm-summary`，但未完整提供 OpenRouter 配置，已跳过模型总结。"
        )
        return None, warnings

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是交付计划分析助手。请基于已计算好的倒排结果，"
                    "输出 3-5 句简短中文总结，不要重新计算日期，不要输出 Markdown 表格。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "targets": [activity_display_name(activities[k]) for k in target_keys],
                        "target_keys": [str(k) for k in target_keys],
                        "results": {
                            str(key): {
                                "name": activity_display_name(activities[key]),
                                "latest_start": format_date(schedule.latest_start),
                                "latest_finish": format_date(schedule.latest_finish),
                                "duration_days": activities[key].duration_days,
                                "dependencies": [
                                    activity_display_name(activities[dep_key])
                                    for dep_key in activities[key].dependency_keys
                                ],
                            }
                            for key, schedule in results.items()
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
    except Exception as exc:  # pragma: no cover - 网络异常路径
        warnings.append(f"OpenRouter 调用失败，已跳过模型总结：{exc}")
        return None, warnings

    choices = body.get("choices") or []
    if not choices:
        warnings.append("OpenRouter 未返回可用内容，已跳过模型总结。")
        return None, warnings

    message = choices[0].get("message") or {}
    content = (message.get("content") or "").strip()
    if not content:
        warnings.append("OpenRouter 返回内容为空，已跳过模型总结。")
        return None, warnings

    return content, warnings


def default_output_path(source_path: Path, anchor_date: date) -> Path:
    return source_path.with_name(f"{source_path.stem}_倒排依赖图_{format_date(anchor_date)}.md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="交付计划倒排并输出 Mermaid Gantt Markdown。")
    parser.add_argument("--file", required=True, help="计划文件路径，支持 .csv / .xlsx")
    parser.add_argument(
        "--targets",
        required=True,
        help="目标活动列表，逗号分隔；多 PoD 时可用「活动@管理单元」或「管理单元::活动名」",
    )
    parser.add_argument(
        "--target-date",
        required=True,
        help="目标活动最晚完成日期，格式 YYYY-MM-DD",
    )
    parser.add_argument(
        "--output",
        help="输出 Markdown 文件路径；未传时自动生成新 .md 文件",
    )
    parser.add_argument(
        "--shared-section-name",
        default=DEFAULT_SHARED_SECTION_NAME,
        help="多目标共用依赖在 Gantt 中的 section 名称，默认「共用依赖」",
    )
    parser.add_argument(
        "--llm-summary",
        action="store_true",
        help="调用 OpenRouter 为结果追加简短总结",
    )
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
        anchor_date = parse_date(args.target_date)
    except ValueError:
        print(f"`--target-date` 格式错误：{args.target_date}，应为 YYYY-MM-DD", file=sys.stderr)
        return 1

    try:
        ontology = LocalScheduleOntology.from_file(source_path)
        activities = ontology.activities
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        target_rows = ontology.objects.DeliveryPlanRow.resolve_many(args.targets)
        target_keys = [row.local_row_key for row in target_rows]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not target_keys:
        print("`--targets` 未能解析出任何活动。", file=sys.stderr)
        return 1

    schedule_run = ontology.functions.back_schedule(
        targets=target_keys,
        anchor_date=anchor_date,
        compute=compute_back_schedule,
    )
    results = schedule_run.results
    warnings = schedule_run.warnings
    llm_summary: str | None = None
    if args.llm_summary:
        llm_summary, warnings = fetch_llm_summary(
            activities=activities,
            results=results,
            target_keys=target_keys,
            warnings=warnings,
            args=args,
        )
    markdown = build_md_content(
        source_path=source_path,
        activities=activities,
        results=results,
        target_keys=target_keys,
        anchor_date=anchor_date,
        warnings=warnings,
        shared_section_name=args.shared_section_name,
    )
    if llm_summary:
        markdown = markdown.rstrip() + "\n\n## OpenRouter 总结\n\n" + llm_summary + "\n"

    output_path = Path(args.output).expanduser().resolve() if args.output else default_output_path(
        source_path, anchor_date
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"已生成倒排 Markdown：{output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
