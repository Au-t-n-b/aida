"""项目创建/编辑后同步「项目交付场景信息表.xlsx」到业务数据目录。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from manager.config import business_root

LOG = logging.getLogger("aida.manager.project_delivery_scene")

DELIVERY_SCENE_HEADERS: tuple[str, ...] = (
    "产品代际",
    "制冷方式",
    "集群形态",
    "PoD形态",
    "部署阶段",
    "算力规模",
    "产品规模",
    "卡数",
    "算力集群交付模式",
    "大EP类型",
)

# 每次同步时由项目表单覆盖的列
_ALWAYS_OVERWRITE = frozenset({
    "集群形态",
    "部署阶段",
    "算力集群交付模式",
    "大EP类型",
})

_DELIVERY_MODE_FIXED = "集群集成"

_DEPLOY_PHASE = frozenset({"新建", "节点扩容"})
_CLUSTER_FORM = frozenset({"训练", "推理", "训推一体"})

_REL_XLSX = Path("早期介入") / "合同" / "解析结果" / "项目交付场景信息表.xlsx"


def project_delivery_scene_xlsx_path(project_id: str) -> Path:
    pid = (project_id or "").strip()
    if not pid:
        raise ValueError("缺少项目 ID")
    return business_root() / "projects" / pid / _REL_XLSX


def _trait_strings(traits: list[Any] | None) -> list[str]:
    if not traits:
        return []
    out: list[str] = []
    for item in traits:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
            continue
        if isinstance(item, dict):
            for key in ("label", "name", "value", "trait"):
                raw = item.get(key)
                if raw is not None:
                    s = str(raw).strip()
                    if s:
                        out.append(s)
                    break
    return out


def delivery_traits_to_scene_row(traits: list[Any] | None) -> dict[str, str]:
    """从 deliveryTraits / 场景 chip 解析需写入 xlsx 的四列。"""
    selected = _trait_strings(traits)
    deploy_phase = next((s for s in selected if s in _DEPLOY_PHASE), "")
    cluster_form = next((s for s in selected if s in _CLUSTER_FORM), "")
    large_ep_type = ""
    if selected:
        large_ep_type = "大EP" if "大EP" in selected else "非大EP"
    return {
        "集群形态": cluster_form,
        "部署阶段": deploy_phase,
        "算力集群交付模式": _DELIVERY_MODE_FIXED if selected else "",
        "大EP类型": large_ep_type,
    }


def project_to_delivery_scene_row(project: dict[str, Any]) -> dict[str, str]:
    traits = project.get("deliveryTraits")
    if traits is not None and not isinstance(traits, list):
        traits = None
    scene = delivery_traits_to_scene_row(traits)
    row = {h: "" for h in DELIVERY_SCENE_HEADERS}
    row.update(scene)
    if scene.get("算力集群交付模式"):
        row["算力集群交付模式"] = _DELIVERY_MODE_FIXED
    return row


def _read_existing_row(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        from openpyxl import load_workbook
    except ImportError:
        LOG.warning("openpyxl 未安装，无法读取已有项目交付场景信息表")
        return {}
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=1, max_row=2, values_only=True))
        wb.close()
    except (OSError, ValueError) as exc:
        LOG.warning("读取项目交付场景信息表失败 path=%s err=%s", path, exc)
        return {}
    if len(rows) < 2:
        return {}
    headers = [str(h or "").replace("\ufeff", "").strip() for h in rows[0]]
    values = rows[1]
    mapping = {
        h: ("" if v is None else str(v).strip())
        for h, v in zip(headers, values)
        if h
    }
    return {h: mapping.get(h, "") for h in DELIVERY_SCENE_HEADERS}


def _merge_rows(existing: dict[str, str], fresh: dict[str, str]) -> dict[str, str]:
    merged = dict(existing)
    for header in DELIVERY_SCENE_HEADERS:
        value = fresh.get(header, "")
        if header in _ALWAYS_OVERWRITE:
            if value:
                merged[header] = value
            elif header not in merged:
                merged[header] = ""
        elif value:
            merged[header] = value
        elif header not in merged:
            merged[header] = ""
    return {h: merged.get(h, "") for h in DELIVERY_SCENE_HEADERS}


def _write_row(path: Path, row: dict[str, str]) -> None:
    from openpyxl import Workbook

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "项目交付场景信息"
    ws.append(list(DELIVERY_SCENE_HEADERS))
    ws.append([row.get(h, "") for h in DELIVERY_SCENE_HEADERS])
    wb.save(path)


def sync_project_delivery_scene_xlsx(
    project: dict[str, Any],
    *,
    delivery_traits_hint: list[Any] | None = None,
) -> Path:
    """将场景字段写入/更新到 早期介入/合同/解析结果/项目交付场景信息表.xlsx。"""
    project_id = str(project.get("projectId") or "").strip()
    if not project_id:
        raise ValueError("项目数据缺少 projectId")

    merged_project = dict(project)
    traits = merged_project.get("deliveryTraits")
    if (not traits or not isinstance(traits, list)) and delivery_traits_hint:
        merged_project["deliveryTraits"] = delivery_traits_hint

    path = project_delivery_scene_xlsx_path(project_id)
    existing = _read_existing_row(path)
    fresh = project_to_delivery_scene_row(merged_project)
    if not any(fresh.get(h) for h in _ALWAYS_OVERWRITE):
        LOG.info(
            "跳过项目交付场景信息表同步（无场景字段） path=%s projectId=%s",
            path,
            project_id,
        )
        return path

    merged = _merge_rows(existing, fresh)
    _write_row(path, merged)
    LOG.info("项目交付场景信息表已同步 path=%s projectId=%s", path, project_id)
    return path
