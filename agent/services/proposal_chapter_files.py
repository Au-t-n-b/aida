"""Chapter 5/7 proposal file inputs and Excel uploads."""
from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path
from typing import Any, Iterable

from shared.datacenter import DataCenterClient, SemanticFileRef

LOG = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DATA_ROOT = PROJECT_ROOT / "data" / "projects"
MOCK_PROJECT_ROOT = PROJECT_ROOT / "data" / "delivery" / "mock" / "mock_project"

PROPOSAL_PARSE = ("proposal", "解析结果")
PROPOSAL_OUTPUT = ("proposal", "输出结果")
DC_PROJECT_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return authorization.strip() or None


def normalize_dc_project_id(project_id: str | None) -> str | None:
    value = (project_id or "").strip()
    return value if DC_PROJECT_ID_RE.fullmatch(value) else None


def _ref(
    project_id: str,
    module_code: str,
    file_stage: str,
    folder_sub_path: str,
    file_name: str | None = None,
) -> SemanticFileRef:
    return SemanticFileRef(
        project_id=project_id,
        module_code=module_code,
        file_stage=file_stage,
        folder_sub_path=folder_sub_path,
        file_name=file_name,
    )


async def _read_source(
    token: str | None,
    ref: SemanticFileRef,
    local_path: Path,
    *,
    extra_local_paths: list[Path] | None = None,
) -> bytes:
    all_locals = [local_path, *(extra_local_paths or [])]
    for lp in all_locals:
        if lp.is_file():
            LOG.info("本地文件命中，跳过数据中心: %s", lp)
            return lp.read_bytes()
    if token and ref.project_id:
        import time

        t0 = time.perf_counter()
        try:
            client = DataCenterClient(token)
            resolved = ref
            if not ref.file_name:
                resolved, _ = await client.resolve_first_file(ref, extensions=(".json", ".xlsx"))
            content = await client.download_file(resolved)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            LOG.info(
                "数据中心源文件读取成功 ref=%s bytes=%s elapsed=%.1fms",
                resolved,
                len(content),
                elapsed_ms,
            )
            return content
        except Exception:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            LOG.warning(
                "数据中心源文件读取失败（耗时 %.1fms），无本地文件可回退: %s",
                elapsed_ms,
                local_path,
                exc_info=True,
            )
    raise FileNotFoundError(f"本地文件不存在且数据中心不可用: {[str(p) for p in all_locals]}")


def _cell_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_net_plane_xlsx(content: bytes) -> list[dict[str, Any]]:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
    finally:
        workbook.close()
    if not rows:
        return []
    headers = {_cell_text(value): index for index, value in enumerate(rows[0])}

    def get(row: tuple[Any, ...], name: str) -> Any:
        index = headers.get(name)
        return row[index] if index is not None and index < len(row) else None

    out: list[dict[str, Any]] = []
    for index, row in enumerate(rows[1:], start=1):
        model = _cell_text(get(row, "设备型号"))
        if not model:
            continue
        role = _cell_text(get(row, "设备角色"))
        if "交换机" not in role:
            continue
        out.append(
            {
                "row_id": f"device-{index}",
                "type": role or "网络设备",
                "vendor": "",
                "model": model,
                "ver": _cell_text(get(row, "版本")),
                "qty": int(get(row, "数量") or 0),
                "source": _cell_text(get(row, "来源")) or "自动解析",
                "proposal_version": _cell_text(get(row, "预案版本号")) or None,
                "note": None,
            }
        )
    return out


def parse_net_mgmt_json(content: bytes) -> list[dict[str, Any]]:
    payload = json.loads(content.decode("utf-8-sig"))
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for product in payload.get("products") or []:
        product_head = _cell_text(product.get("product_head"))
        product_id = _cell_text(product.get("product_id"))
        category_names = " ".join(
            _cell_text(category.get("name"))
            for category in product.get("categories") or []
            if isinstance(category, dict)
        )
        searchable = f"{product_head} {category_names}"
        for role in ("NCE", "CCAE", "DME"):
            if not re.search(rf"\b{role}\b", searchable, re.IGNORECASE):
                continue
            identity = (role, product_id or product_head)
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(
                {
                    "row_id": f"net-mgmt-{role.lower()}-{len(rows) + 1}",
                    "server_role": role,
                    "server_model": product_head,
                    "quantity": int(product.get("product_head_qty") or 1),
                    "data_source": "自动解析",
                    "proposal_version": None,
                }
            )
            break
    return rows


def extract_pod_names(file_names: Iterable[str]) -> list[str]:
    pods = {
        f"POD{int(match.group(1)):02d}"
        for name in file_names
        if not name.endswith(".consistency.json")
        for match in re.finditer(r"\bPOD[-_ ]?0*(\d+)\b", name, re.IGNORECASE)
    }
    return sorted(pods, key=lambda value: int(value[3:]))


# ── 输出结果 xlsx 解析 ──────────────────────────────────────────────────────

def _parse_output_xlsx(content: bytes) -> tuple[list[str], list[tuple[Any, ...]]]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()
    if not rows:
        return [], []
    headers = [_cell_text(v) for v in rows[0]]
    return headers, rows[1:]


def parse_net_plane_output_xlsx(content: bytes) -> list[dict[str, Any]]:
    """解析 网络平面配置信息表.xlsx（输出结果）→ NetPlaneRow 字典列表。"""
    headers, data_rows = _parse_output_xlsx(content)
    col = {h: i for i, h in enumerate(headers)}
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(data_rows, start=1):
        def get(name: str) -> str:
            i = col.get(name)
            return _cell_text(row[i]) if i is not None and i < len(row) else ""
        model = get("设备型号")
        if not model:
            continue
        out.append({
            "row_id": f"device-{idx}",
            "type": get("设备角色") or "网络设备",
            "vendor": get("设备厂家"),
            "model": model,
            "ver": get("设备版本"),
            "qty": int(get("数量") or 0),
            "source": get("来源") or "自动解析",
            "proposal_version": None,
            "note": get("备注") or None,
        })
    return out


def parse_net_mgmt_output_xlsx(content: bytes) -> list[dict[str, Any]]:
    """解析 网管服务器配置表.xlsx（输出结果）→ NetMgmtRow 字典列表。"""
    headers, data_rows = _parse_output_xlsx(content)
    col = {h: i for i, h in enumerate(headers)}
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(data_rows, start=1):
        def get(name: str) -> str:
            i = col.get(name)
            return _cell_text(row[i]) if i is not None and i < len(row) else ""
        role = get("服务器角色")
        if not role:
            continue
        out.append({
            "row_id": f"net-mgmt-{role.lower()}-{idx}",
            "server_role": role,
            "server_model": get("服务器型号") or "通算服务器",
            "quantity": int(get("数量") or 1),
            "data_source": "自动解析",
            "proposal_version": None,
        })
    return out


def parse_cluster_device_output_xlsx(content: bytes) -> list[dict[str, Any]]:
    """解析 集群设备清单表.xlsx（输出结果）→ ClusterDeviceRow 字典列表。"""
    headers, data_rows = _parse_output_xlsx(content)
    col = {h: i for i, h in enumerate(headers)}
    out: list[dict[str, Any]] = []
    field_map = [
        ("cluster_id", "集群ID"), ("cluster_type", "集群类型"),
        ("super_pod_id", "超节点ID"), ("storage_cluster_id", "存储集群ID"),
        ("zone_id", "ZONE ID"), ("ccae_cluster_id", "CCAE集群ID"),
        ("dme_cluster_id", "DME集群ID"), ("device_type", "设备类型"),
        ("vendor", "厂家"), ("device_model", "设备型号"),
        ("device_purpose", "设备用途"), ("start_device_name", "起始设备命名"),
        ("end_device_name", "截止设备命名"),
    ]
    for idx, row in enumerate(data_rows, start=1):
        def get(name: str) -> str:
            i = col.get(name)
            return _cell_text(row[i]) if i is not None and i < len(row) else ""
        str_fields = {"device_type", "vendor", "device_model"}
        entry: dict[str, Any] = {"row_id": f"cluster-{idx}", "data_source": "自动解析"}
        for field_key, header_name in field_map:
            val = get(header_name)
            entry[field_key] = (val or "") if field_key in str_fields else (val or None)
        entry["quantity"] = int(get("数量") or 0)
        entry["source_net_plane_id"] = None
        entry["max_quantity"] = entry["quantity"]
        entry["proposal_version"] = None
        out.append(entry)
    return out


def parse_room_rack_output_xlsx(content: bytes) -> list[dict[str, Any]]:
    """解析 机房机柜信息表.xlsx（输出结果）→ RoomRackRow 字典列表。"""
    headers, data_rows = _parse_output_xlsx(content)
    col = {h: i for i, h in enumerate(headers)}
    out: list[dict[str, Any]] = []
    field_map = [
        ("pod_name", "PoD名称"), ("room_name", "机房名称"),
        ("compute", "计算柜"), ("bus", "总线柜"),
        ("param_leaf", "参数面Leaf柜"), ("biz_leaf", "业务面Leaf柜"),
        ("mgmt", "管理面柜"), ("sample_leaf", "样本面Leaf柜"),
    ]
    for idx, row in enumerate(data_rows, start=1):
        def get(name: str) -> str:
            i = col.get(name)
            return _cell_text(row[i]) if i is not None and i < len(row) else ""
        pod = get("PoD名称")
        if not pod:
            continue
        entry: dict[str, Any] = {
            "row_id": f"pod-{pod.lower()}",
            "data_source": "自动解析",
        }
        for field_key, header_name in field_map:
            entry[field_key] = get(header_name)
        out.append(entry)
    return out


# ── 本地输出文件路径 ────────────────────────────────────────────────────────

_NET_PLANE_OUTPUT = MOCK_PROJECT_ROOT / "早期介入" / "交付预案" / "输出结果" / "网络平面配置信息表" / "网络平面配置信息表.xlsx"
_NET_MGMT_OUTPUT = MOCK_PROJECT_ROOT / "早期介入" / "交付预案" / "输出结果" / "网管服务器配置表" / "网管服务器配置表.xlsx"
_CLUSTER_DEVICE_OUTPUT = MOCK_PROJECT_ROOT / "早期介入" / "交付预案" / "输出结果" / "集群设备清单表" / "集群设备清单表.xlsx"
_ROOM_RACK_OUTPUT = MOCK_PROJECT_ROOT / "孪生世界" / "算力底座孪生" / "输出结果" / "机房机柜信息表" / "机房机柜信息表.xlsx"


# ── 数据加载（本地输出优先 → 本地输入 → 数据中心） ───────────────────────────

async def load_net_plane_rows(
    token: str | None,
    project_id: str,
    dc_project_id: str | None = None,
) -> list[dict[str, Any]]:
    if _NET_PLANE_OUTPUT.is_file():
        LOG.info("5.1 从本地输出结果读取: %s", _NET_PLANE_OUTPUT)
        return parse_net_plane_output_xlsx(_NET_PLANE_OUTPUT.read_bytes())
    folder = "设备信息表"
    file_name = "设备信息表.xlsx"
    local = PROJECT_DATA_ROOT / project_id / "早期介入" / "交付预案" / "输出结果" / folder / file_name
    content = await _read_source(
        token,
        _ref(normalize_dc_project_id(dc_project_id), *PROPOSAL_OUTPUT, folder, file_name),
        local,
    )
    return parse_net_plane_xlsx(content)


async def load_net_mgmt_rows(
    token: str | None,
    project_id: str,
    dc_project_id: str | None = None,
) -> list[dict[str, Any]]:
    if _NET_MGMT_OUTPUT.is_file():
        LOG.info("5.2 从本地输出结果读取: %s", _NET_MGMT_OUTPUT)
        return parse_net_mgmt_output_xlsx(_NET_MGMT_OUTPUT.read_bytes())
    folder = "服务BOQ解析结果"
    file_name = "JXX-SBOQ.normalized.json"
    local = PROJECT_DATA_ROOT / project_id / "早期介入" / "交付预案" / "解析结果" / folder / file_name
    ref = _ref(normalize_dc_project_id(dc_project_id), *PROPOSAL_PARSE, folder, file_name)
    content = await _read_source(token, ref, local)
    rows = parse_net_mgmt_json(content)
    LOG.info(
        "5.2 网管服务器解析完成 project_id=%s source=%s bytes=%s rows=%s",
        project_id,
        ref,
        len(content),
        len(rows),
    )
    return rows


async def load_pod_names(
    token: str | None,
    project_id: str,
    dc_project_id: str | None = None,
) -> list[str]:
    if _ROOM_RACK_OUTPUT.is_file():
        LOG.info("7.1 从本地输出结果提取 POD 名称: %s", _ROOM_RACK_OUTPUT)
        rows = parse_room_rack_output_xlsx(_ROOM_RACK_OUTPUT.read_bytes())
        return [r["pod_name"] for r in rows if r.get("pod_name")]
    folder = "设备BOQ解析结果"
    local = PROJECT_DATA_ROOT / project_id / "早期介入" / "交付预案" / "解析结果" / folder
    if local.is_dir():
        names = extract_pod_names(p.name for p in local.glob("*.json"))
        if names:
            LOG.info("POD 名称从本地目录加载: %s (%d pods)", local, len(names))
            return names
    remote_project_id = normalize_dc_project_id(dc_project_id)
    if token and remote_project_id:
        import time

        t0 = time.perf_counter()
        try:
            data = await DataCenterClient(token).list_files(_ref(remote_project_id, *PROPOSAL_PARSE, folder))
            elapsed_ms = (time.perf_counter() - t0) * 1000
            names = extract_pod_names(str(item.get("fileName") or "") for item in data.get("list") or [])
            LOG.info("数据中心 BOQ 目录读取成功 pods=%d elapsed=%.1fms", len(names), elapsed_ms)
            return names
        except Exception:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            LOG.warning(
                "数据中心设备 BOQ 目录读取失败（耗时 %.1fms）: %s",
                elapsed_ms,
                local,
                exc_info=True,
            )
    return []


async def load_room_rack_rows(
    token: str | None,
    project_id: str,
    dc_project_id: str | None = None,
) -> list[dict[str, Any]]:
    """加载机房机柜完整行数据（本地输出优先）。"""
    if _ROOM_RACK_OUTPUT.is_file():
        LOG.info("7.1 从本地输出结果读取: %s", _ROOM_RACK_OUTPUT)
        return parse_room_rack_output_xlsx(_ROOM_RACK_OUTPUT.read_bytes())
    pods = await load_pod_names(token, project_id, dc_project_id)
    return [
        {"row_id": f"pod-{pod.lower()}", "pod_name": pod, "data_source": "自动解析"}
        for pod in pods
    ]


async def load_cluster_device_rows(
    token: str | None,
    project_id: str,
    dc_project_id: str | None = None,
) -> list[dict[str, Any]]:
    """加载集群设备清单数据（本地输出优先，否则由 5.1 继承）。"""
    if _CLUSTER_DEVICE_OUTPUT.is_file():
        LOG.info("5.3 从本地输出结果读取: %s", _CLUSTER_DEVICE_OUTPUT)
        return parse_cluster_device_output_xlsx(_CLUSTER_DEVICE_OUTPUT.read_bytes())
    return []


def build_xlsx(sheet_title: str, headers: list[str], rows: Iterable[Iterable[Any]]) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_title
    sheet.append(headers)
    for row in rows:
        sheet.append(list(row))
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


async def upload_output(
    token: str | None,
    dc_project_id: str | None,
    folder: str,
    file_name: str,
    content: bytes,
    local_relative: Path,
    module_code: str = "proposal",
    file_stage: str = "输出结果",
) -> dict[str, Any]:
    import time

    local_path = MOCK_PROJECT_ROOT / local_relative / file_name
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(content)
    result: dict[str, Any] = {
        "saved_path": str(local_path.relative_to(PROJECT_ROOT)),
        "uploaded": False,
    }
    remote_project_id = normalize_dc_project_id(dc_project_id)
    if not token or not remote_project_id:
        result["warning"] = "未携带数据中心 token 或项目 UUID，仅写入本地镜像"
        return result
    t0 = time.perf_counter()
    try:
        uploaded = await DataCenterClient(token).upload_file(
            _ref(remote_project_id, module_code, file_stage, folder, file_name),
            content,
            file_name,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        result.update({"uploaded": True, "logical_path": uploaded.get("logicalPath") or ""})
        LOG.info(
            "数据中心上传成功 folder=%s file=%s bytes=%s elapsed=%.1fms",
            folder,
            file_name,
            len(content),
            elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        LOG.warning(
            "数据中心上传失败（耗时 %.1fms），已保留本地文件: %s — %s",
            elapsed_ms,
            local_path,
            exc,
        )
        result["warning"] = f"远端上传失败，已保存本地：{exc}"
    return result
