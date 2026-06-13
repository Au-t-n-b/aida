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


def extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return authorization.strip() or None


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
) -> bytes:
    if token:
        try:
            client = DataCenterClient(token)
            resolved = ref
            if not ref.file_name:
                resolved, _ = await client.resolve_first_file(ref, extensions=(".json", ".xlsx"))
            return await client.download_file(resolved)
        except Exception:
            LOG.warning("数据中心源文件读取失败，回退本地文件: %s", local_path, exc_info=True)
    return local_path.read_bytes()


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
    counts = {role: 0 for role in ("NCE", "CCAE", "DME")}
    seen: set[tuple[str, str]] = set()
    for product in payload.get("products") or []:
        product_head = _cell_text(product.get("product_head"))
        product_id = _cell_text(product.get("product_id"))
        for role in counts:
            if not re.search(rf"\b{role}\b", product_head, re.IGNORECASE):
                continue
            identity = (role, product_id or product_head)
            if identity in seen:
                continue
            seen.add(identity)
            counts[role] += int(product.get("product_head_qty") or 1)
            break
    return [
        {
            "row_id": f"net-mgmt-{role.lower()}",
            "server_role": role,
            "server_model": "",
            "quantity": quantity,
            "data_source": "自动解析",
            "proposal_version": None,
        }
        for role, quantity in counts.items()
        if quantity > 0
    ]


def extract_pod_names(file_names: Iterable[str]) -> list[str]:
    pods = {
        f"POD{int(match.group(1)):02d}"
        for name in file_names
        if not name.endswith(".consistency.json")
        for match in re.finditer(r"\bPOD[-_ ]?0*(\d+)\b", name, re.IGNORECASE)
    }
    return sorted(pods, key=lambda value: int(value[3:]))


async def load_net_plane_rows(token: str | None, project_id: str) -> list[dict[str, Any]]:
    folder = "设备信息表"
    file_name = "设备信息表.xlsx"
    local = PROJECT_DATA_ROOT / project_id / "早期介入" / "交付预案" / "输出结果" / folder / file_name
    content = await _read_source(
        token,
        _ref(project_id, *PROPOSAL_OUTPUT, folder, file_name),
        local,
    )
    return parse_net_plane_xlsx(content)


async def load_net_mgmt_rows(token: str | None, project_id: str) -> list[dict[str, Any]]:
    folder = "服务BOQ解析结果"
    file_name = "JXX-SBOQ.normalized.json"
    local = PROJECT_DATA_ROOT / project_id / "早期介入" / "交付预案" / "解析结果" / folder / file_name
    content = await _read_source(
        token,
        _ref(project_id, *PROPOSAL_PARSE, folder, file_name),
        local,
    )
    return parse_net_mgmt_json(content)


async def load_pod_names(token: str | None, project_id: str) -> list[str]:
    folder = "设备BOQ解析结果"
    local = PROJECT_DATA_ROOT / project_id / "早期介入" / "交付预案" / "解析结果" / folder
    if token:
        try:
            data = await DataCenterClient(token).list_files(_ref(project_id, *PROPOSAL_PARSE, folder))
            return extract_pod_names(str(item.get("fileName") or "") for item in data.get("list") or [])
        except Exception:
            LOG.warning("数据中心设备 BOQ 目录读取失败，回退本地目录: %s", local, exc_info=True)
    return extract_pod_names(path.name for path in local.glob("*.json"))


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
    project_id: str,
    folder: str,
    file_name: str,
    content: bytes,
    local_relative: Path,
    module_code: str = "proposal",
    file_stage: str = "输出结果",
) -> dict[str, Any]:
    local_path = MOCK_PROJECT_ROOT / local_relative / file_name
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(content)
    result: dict[str, Any] = {
        "saved_path": str(local_path.relative_to(PROJECT_ROOT)),
        "uploaded": False,
    }
    if not token:
        result["warning"] = "未携带数据中心 token，仅写入本地镜像"
        return result
    try:
        uploaded = await DataCenterClient(token).upload_file(
            _ref(project_id, module_code, file_stage, folder, file_name),
            content,
            file_name,
        )
        result.update({"uploaded": True, "logical_path": uploaded.get("logicalPath") or ""})
    except Exception as exc:
        LOG.warning("数据中心上传失败，已保留本地文件: %s", local_path, exc_info=True)
        result["warning"] = f"远端上传失败，已保存本地：{exc}"
    return result
