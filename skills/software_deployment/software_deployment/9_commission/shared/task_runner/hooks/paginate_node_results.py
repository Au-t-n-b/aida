# -*- coding: utf-8 -*-
"""分页拉取任务节点结果，供 result.json 记录设备级 Pass/Fail。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeResultsArtifact:
    devices: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


def _list_data(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    raw = data.get("listData") or data.get("list") or []
    return [x for x in raw if isinstance(x, dict)]


def _device_result(check_result: str) -> str:
    return "Fail" if check_result == "检查失败" else "Pass"


def paginate_node_results(
    *,
    client,
    work_stage: str,
    task_id: str,
    query_template: dict[str, Any],
    device_count: int,
) -> NodeResultsArtifact:
    page_size = int(query_template.get("pageSize") or 1000)
    page_size = max(1, page_size)
    page_count = max(1, device_count // page_size + 1)

    devices: list[dict[str, Any]] = []
    for page in range(1, page_count + 1):
        body = dict(query_template)
        body["taskId"] = task_id
        body["currentPage"] = page
        body["pageSize"] = page_size
        payload = client.query_task(work_stage=work_stage, body=body)
        items = _list_data(payload)
        if not items and page > 1:
            break
        for item in items:
            ip = str(
                item.get("nodeIp")
                or item.get("nodeIP")
                or item.get("deviceIp")
                or item.get("ip")
                or ""
            ).strip()
            check_result = str(item.get("checkResult") or item.get("result") or "").strip()
            if not ip:
                continue
            devices.append(
                {
                    "ip": ip,
                    "checkResult": check_result,
                    "result": _device_result(check_result),
                }
            )
        if len(items) < page_size:
            break

    passed = sum(1 for d in devices if d.get("result") == "Pass")
    failed = sum(1 for d in devices if d.get("result") == "Fail")
    return NodeResultsArtifact(
        devices=devices,
        summary={"total": len(devices), "passed": passed, "failed": failed},
    )
