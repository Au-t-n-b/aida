"""
gkclaw mapping · 全量勘测结果表 → task.json（契约 §10/§11/§12）

入选范围：勘测方法 == "现场勘测" 的行（数据类由 backagent 自行处理，不下发）。
背景知识来源：建表时被丢弃的底表列（视频勘测背景知识/语音助手背景知识/是否支持视频勘测），
下发时按自然键 (细分场景,勘测要素,项目,检查内容) 回连底表取回；join 失败→空+不阻断。

分簇 = 物理空间维度。v1 底表无该字段 → 单一兜底簇 cluster-all（契约 §12 规定动作）；
cluster_values 入参预留按「物理位置」列分簇的升级点（零代码切换，见设计决策）。
"""
from __future__ import annotations

from typing import Any

ON_SITE_METHOD = "现场勘测"


def _nat_key(d: dict[str, Any]) -> tuple[str, str, str, str]:
    return (str(d.get("细分场景", "")).strip(), str(d.get("勘测要素", "")).strip(),
            str(d.get("项目", "")).strip(), str(d.get("检查内容", "")).strip())


def join_base_enrichment(rows: list[dict], base_items: list[dict]) -> dict[int, dict]:
    """全量表行 → 底表行 的自然键 join。返回 {表序号: 底表行}；撞键以首条为准。"""
    index: dict[tuple, dict] = {}
    for b in base_items:
        index.setdefault(_nat_key(b), b)
    out: dict[int, dict] = {}
    for r in rows:
        hit = index.get(_nat_key(r))
        if hit is not None:
            out[int(r.get("序号", 0))] = hit
    return out


def derive_clusters(
    item_keys_in_order: list[str],
    *,
    room_name: str,
    cluster_values: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """物理空间分簇。cluster_values=None → 单兜底簇；否则按标签首现顺序分簇，空标签落「其他」。"""
    if not cluster_values:
        return [{
            "cluster_id": "cluster-all",
            "cluster_name": room_name.strip() or "全部条目",
            "item_keys": list(item_keys_in_order),
        }]
    ordered_labels: list[str] = []
    by_label: dict[str, list[str]] = {}
    leftovers: list[str] = []
    for k in item_keys_in_order:
        label = (cluster_values.get(k) or "").strip()
        if not label:
            leftovers.append(k)
            continue
        if label not in by_label:
            ordered_labels.append(label)
            by_label[label] = []
        by_label[label].append(k)
    clusters = [
        {"cluster_id": f"cluster-{i + 1:02d}", "cluster_name": label, "item_keys": by_label[label]}
        for i, label in enumerate(ordered_labels)
    ]
    if leftovers:
        clusters.append({"cluster_id": "cluster-other", "cluster_name": "其他",
                         "item_keys": leftovers})
    return clusters


def _to_front_note(row: dict, base: dict | None) -> str:
    prefix = f"【{str(row.get('勘测要素', '')).strip()}/{str(row.get('项目', '')).strip()}】"
    if not base:
        return prefix
    video = str(base.get("视频勘测背景知识", "")).strip()
    voice = str(base.get("语音助手背景知识", "")).strip()
    parts = [prefix + video if video else prefix]
    if voice and voice != video:
        parts.append(f"语音助手提示：{voice}")
    return "\n".join(parts)


def build_task_payload(
    *,
    task_id: str,
    rows: list[dict],
    base_items: list[dict],
    project: dict[str, Any],
    assignees: list[dict[str, str]],
    survey_round: int = 1,
    generation_cooling: str = "",
    cluster_values: dict[str, str] | None = None,
) -> dict[str, Any]:
    """组装契约 task.json（纯函数，不校验——校验交给 schema.validate_task）。"""
    enrich = join_base_enrichment(rows, base_items)
    items: list[dict[str, Any]] = []
    for r in rows:
        if str(r.get("勘测方法", "")).strip() != ON_SITE_METHOD:
            continue
        seq = int(r.get("序号", 0))
        base = enrich.get(seq)
        meta: dict[str, Any] = {
            "细分场景": str(r.get("细分场景", "")).strip(),
            "勘测要素": str(r.get("勘测要素", "")).strip(),
            "项目": str(r.get("项目", "")).strip(),
            "勘测方法": ON_SITE_METHOD,
        }
        if base is not None:
            meta["是否支持视频勘测"] = str(base.get("是否支持视频勘测", "")).strip()
            meta["底表序号"] = int(base.get("序号", 0))
        items.append({
            "问题序号": str(seq),
            "勘测项": str(r.get("检查内容", "")).strip(),
            "选项列表": [],
            "勘测结果": "",
            "to_front_备注": _to_front_note(r, base),
            "to_back_备注": "",
            "示例图": [],
            "metadata": meta,
        })

    room_name = str(project.get("room_name", "")).strip()
    project_name = str(project.get("project_name", "")).strip()
    round_suffix = f"（第{survey_round}轮）" if survey_round > 1 else ""
    return {
        "task_id": task_id,
        "task_name": f"{project_name}·{room_name} 现场勘测{round_suffix}".strip("·"),
        "project": {
            "project_id": str(project.get("activity_id", "")).strip()
                          or str(project.get("project_code", "")).strip(),
            "project_code": str(project.get("project_code", "")).strip(),
            "project_name": project_name,
        },
        "assignees": [
            {"surveyor_name": str(a.get("surveyor_name", "")).strip(),
             "surveyor_code": str(a.get("surveyor_code", "")).strip()}
            for a in assignees
        ],
        "items": items,
        "item_clusters": derive_clusters(
            [it["问题序号"] for it in items],
            room_name=room_name, cluster_values=cluster_values,
        ),
        "dependency_rules": [],
        "supplemental_context": None,
        "metadata": {
            "activity_id": str(project.get("activity_id", "")).strip(),
            "room_name": room_name,
            "generation_cooling": generation_cooling,
            "survey_round": survey_round,
            "location_label": room_name,
            "priority": "normal",
        },
    }
