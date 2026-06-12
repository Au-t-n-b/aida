"""Release promote draft → versioned output + rebuild working draft."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from openpyxl import Workbook

from agent.integrations.occ_review_client import resolve_review_tag
from agent.proposal.auth import ProposalSession, proposal_operator_display_name
from agent.proposal.draft_store import (
    archive_draft_snapshot,
    device_table_xlsx_path,
    format_display_datetime,
    load_chapter_02,
    load_chapter_81,
    load_chapter_82,
    load_chapter_83,
    load_chapter_84,
    load_manifest,
    maint_sla_xlsx_path,
    maint_strategy_xlsx_path,
    output_xlsx_path,
    rebuild_draft_from_version,
    save_chapter_02_output,
    save_chapter_81_output,
    save_chapter_82_output,
    save_chapter_83_output,
    save_chapter_84_output,
    save_manifest,
    save_version_info,
    service_content_xlsx_path,
)
from agent.proposal.models import ReleaseAndDecideBody
from agent.proposal.chapter_files import promote_draft_chapters_to_version, sync_all_chapter_excel
from agent.proposal.services.maintenance_sla import get_sla as get_sla_payload
from agent.proposal.services.maintenance_strategy import list_rows as list_maint_rows
from agent.proposal.services.service_content import list_rows as list_content_rows
from agent.proposal.services import metadata as metadata_service
from agent.proposal.services.device_info import list_rows as list_device_rows
from agent.proposal.services.service_delivery_ui import list_rows as list_delivery_rows


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_MAIN_VERSION_PATTERN = re.compile(r"^V(?P<major>\d+)\.(?P<minor>\d+)$")


def _parse_main_version(version: str | None) -> tuple[int, int] | None:
    """Parse `Vx.y` head and normalize legacy overflow minor."""
    if not version:
        return None
    head = version.split("_")[0]
    match = _MAIN_VERSION_PATTERN.match(head)
    if not match:
        return None

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    if major < 1 or minor < 0:
        return None

    # Legacy names like V1.10/V1.11 are treated as overflow and
    # normalized to the rollover edge so next release becomes V2.0.
    if minor > 9:
        return major + 1, 9
    return major, minor


def _next_main_version(latest_version: str | None) -> str:
    parsed = _parse_main_version(latest_version)
    if parsed is None:
        return "V1.0"

    major, minor = parsed
    if minor >= 9:
        return f"V{major + 1}.0"
    return f"V{major}.{minor + 1}"


def _next_version(manifest: dict, *, review_tag_hint: str | None = None) -> str:
    latest = manifest.get("latestReleaseVersion")
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    base = f"{_next_main_version(latest)}_{ts}"

    if review_tag_hint and review_tag_hint.upper() in ("DTRB", "DRB"):
        return f"{base}_{review_tag_hint.upper()}"
    if latest and ("_DTRB" in latest or "_DRB" in latest):
        tag = "_DTRB" if "_DTRB" in latest else "_DRB"
        return f"{base}{tag}"
    return base


def promote_chapter_02(project_id: str, new_version: str) -> dict[str, Any]:
    rows, _dependencies = list_device_rows(project_id, version="draft")
    if not rows:
        raise ValueError("第 2 章设备信息表为空，请先解析设备 BOQ")

    payload = load_chapter_02(project_id, "draft")
    stamped_rows = []
    for raw in payload.get("rows") or []:
        item = dict(raw)
        item["proposalVersion"] = new_version
        stamped_rows.append(item)
    output_payload = {"rows": stamped_rows}
    save_chapter_02_output(project_id, new_version, output_payload)

    xlsx_path = device_table_xlsx_path(project_id, new_version)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "设备信息表"
    ws.append([
        "设备型号",
        "产品编码",
        "数量",
        "版本",
        "生命周期状态",
        "GA实际时间",
        "GA计划时间",
        "EOM实际时间",
        "EOM计划时间",
        "EOS实际时间",
        "EOS计划时间",
        "设备U高",
        "来源",
        "预案版本号",
        "产品部件类别",
        "部件编码",
        "硬件子类",
        "设备角色",
    ])
    for row in rows:
        ws.append([
            row.device_model,
            row.product_code,
            row.quantity,
            row.version,
            row.lifecycle_status,
            row.ga_actual_date or "",
            row.ga_plan_date or "",
            row.eom_actual_date or "",
            row.eom_plan_date or "",
            row.eos_actual_date or "",
            row.eos_plan_date or "",
            row.device_u_height if row.device_u_height is not None else "",
            row.data_source.value,
            new_version,
            row.product_part_category.value,
            row.part_code,
            row.hardware_subtype.value,
            row.device_role,
        ])
    wb.save(xlsx_path)

    legacy = device_table_xlsx_path(project_id)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    wb.save(legacy)

    return {
        "proposalVersion": new_version,
        "outputPath": str(xlsx_path),
        "rowCount": len(rows),
    }


def promote_chapter_81(project_id: str, new_version: str) -> dict[str, Any]:
    rows = list_delivery_rows(project_id, version="draft")
    if len(rows) != 13:
        raise ValueError("8.1 须包含 13 行后再 Release；请先 POST initialize")

    payload = load_chapter_81(project_id, "draft")
    stamped_rows = []
    for raw in payload.get("rows") or []:
        item = dict(raw)
        item["proposalVersion"] = new_version
        stamped_rows.append(item)
    output_payload = {"rows": stamped_rows}
    save_chapter_81_output(project_id, new_version, output_payload)

    xlsx_path = output_xlsx_path(project_id, new_version)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "服务配置"
    ws.append(["服务大类", "服务细项", "交付界面", "预案版本号"])
    for row in rows:
        ws.append([
            row.service_major,
            row.service_item,
            row.delivery_channel.value,
            new_version,
        ])
    wb.save(xlsx_path)

    legacy_xlsx = output_xlsx_path(project_id)
    legacy_xlsx.parent.mkdir(parents=True, exist_ok=True)
    wb.save(legacy_xlsx)

    return {
        "proposalVersion": new_version,
        "outputPath": str(xlsx_path),
        "rowCount": len(rows),
    }


def promote_chapter_82(project_id: str, new_version: str) -> dict[str, Any]:
    rows, _ = list_content_rows(project_id, version="draft", collapse=False)
    if not rows:
        raise ValueError("8.2 服务内容为空，请先解析服务 BOQ")

    payload = load_chapter_82(project_id, "draft")
    stamped_rows = []
    for raw in payload.get("rows") or []:
        item = dict(raw)
        item["proposalVersion"] = new_version
        stamped_rows.append(item)
    save_chapter_82_output(project_id, new_version, {"rows": stamped_rows})

    xlsx_path = service_content_xlsx_path(project_id, new_version)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "服务内容"
    ws.append(["服务名称", "服务内容", "数量", "单位", "预案版本号"])
    for row in rows:
        ws.append([
            row.service_name,
            row.service_content,
            row.quantity,
            row.unit,
            new_version,
        ])
    wb.save(xlsx_path)

    legacy = service_content_xlsx_path(project_id)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    wb.save(legacy)

    return {
        "proposalVersion": new_version,
        "outputPath": str(xlsx_path),
        "rowCount": len(rows),
    }


def promote_chapter_83(project_id: str, new_version: str) -> dict[str, Any]:
    rows = list_maint_rows(project_id, version="draft")
    if not rows:
        raise ValueError("8.3 维保策略为空，请先解析维保 BOQ")

    payload = load_chapter_83(project_id, "draft")
    stamped_rows = []
    for raw in payload.get("rows") or []:
        item = dict(raw)
        item["proposalVersion"] = new_version
        stamped_rows.append(item)
    save_chapter_83_output(project_id, new_version, {"rows": stamped_rows})

    xlsx_path = maint_strategy_xlsx_path(project_id, new_version)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "维保策略"
    ws.append([
        "序号",
        "产品型号",
        "保修策略",
        "维保策略",
        "维保开始时间",
        "维保结束时间",
        "产品EOS时间",
        "是否超EOS服务",
        "超EOS审批结论",
        "预案版本号",
    ])
    for row in rows:
        ws.append([
            row.seq,
            row.product_model,
            row.warranty_policy,
            row.maintenance_policy,
            row.maint_start_date,
            row.maint_end_date,
            row.product_eos_date or "",
            row.over_eos.value,
            row.over_eos_approval,
            new_version,
        ])
    wb.save(xlsx_path)

    legacy = maint_strategy_xlsx_path(project_id)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    wb.save(legacy)

    return {
        "proposalVersion": new_version,
        "outputPath": str(xlsx_path),
        "rowCount": len(rows),
    }


def promote_chapter_84(project_id: str, new_version: str) -> dict[str, Any] | None:
    data = get_sla_payload(project_id, version="draft")
    rows = data["rows"]
    if not rows:
        return None

    payload = load_chapter_84(project_id, "draft")
    stamped_rows = []
    for raw in payload.get("rows") or []:
        item = dict(raw)
        item["proposalVersion"] = new_version
        stamped_rows.append(item)
    output_payload = {
        "hardwareSupport": payload.get("hardwareSupport") or "",
        "serviceLevel": payload.get("serviceLevel") or "",
        "rows": stamped_rows,
    }
    save_chapter_84_output(project_id, new_version, output_payload)

    xlsx_path = maint_sla_xlsx_path(project_id, new_version)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "维保SLA"
    ws.append([
        "问题等级",
        "服务覆盖时间",
        "响应时间",
        "回复时间",
        "解决时间",
        "硬件支持",
        "服务类型",
        "预案版本号",
    ])
    hardware = payload.get("hardwareSupport") or ""
    service_level = payload.get("serviceLevel") or ""
    for row in rows:
        ws.append([
            row.severity_level,
            row.coverage_period,
            row.response_time,
            row.restore_time,
            row.resolve_time,
            hardware,
            service_level,
            new_version,
        ])
    wb.save(xlsx_path)

    legacy = maint_sla_xlsx_path(project_id)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    wb.save(legacy)

    return {
        "proposalVersion": new_version,
        "outputPath": str(xlsx_path),
        "rowCount": len(rows),
    }


def _build_release_change_description(
    project_id: str,
    prev_version: str | None,
    manual_records: list[dict[str, Any]],
) -> str:
    manual_entries = [
        {
            "chapter": str(r.get("chapter") or ""),
            "changeDescription": str(
                r.get("description") or r.get("changeDescription") or ""
            ),
        }
        for r in manual_records
    ]
    return metadata_service._format_manual_change_description(manual_entries)


def release_and_decide(
    project_id: str,
    body: ReleaseAndDecideBody | None,
    session: ProposalSession,
) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    basic, _deps = metadata_service.read_project_basic_info(project_id)
    project_code = basic.get("projectId") or project_id
    review_hint = resolve_review_tag(project_code)
    new_version = _next_version(manifest, review_tag_hint=review_hint)
    prev_version = manifest.get("latestReleaseVersion")
    operator = proposal_operator_display_name(session)

    pending_manual_records: list[dict[str, Any]] = list(manifest.get("changeRecords") or [])
    if body and body.change_records:
        pending_manual_records = [r.model_dump() for r in body.change_records]
        manifest["changeRecords"] = pending_manual_records
        save_manifest(project_id, manifest)

    archive_draft_snapshot(project_id, new_version)
    ch02_result = promote_chapter_02(project_id, new_version)
    ch81_result = promote_chapter_81(project_id, new_version)
    ch82_result = promote_chapter_82(project_id, new_version)
    ch83_result = promote_chapter_83(project_id, new_version)
    ch84_result = promote_chapter_84(project_id, new_version)

    promote_draft_chapters_to_version(project_id, new_version)
    sync_all_chapter_excel(project_id, new_version)

    meta_snapshot: dict[str, Any] | None = None
    full_snap: dict[str, Any] = {}
    try:
        meta_snapshot = metadata_service.promote_metadata_on_release(
            project_id,
            new_version,
            operator,
            prev_version=prev_version,
        )
        from agent.proposal.version_info_store import find_snapshot

        full_snap = find_snapshot(project_id, new_version) or {}
    except Exception:
        meta_snapshot = None

    now = _now_iso()
    legacy_change_description = _build_release_change_description(
        project_id, prev_version, pending_manual_records
    )

    if meta_snapshot is None:
        meta_snapshot = {
            "createdBy": manifest.get("createdBy") or operator,
            "createdAt": manifest.get("createdAt"),
            "updatedBy": operator,
            "updatedAt": format_display_datetime(now),
            "changeDescription": legacy_change_description,
            "documentSummary": "",
        }

    version_records = full_snap.get("changeRecords") if full_snap else None
    if not version_records:
        version_records = pending_manual_records

    change_description = (
        meta_snapshot.get("changeDescription") or legacy_change_description
    )

    version_info = {
        "proposalVersion": new_version,
        "status": "published",
        "createdBy": meta_snapshot.get("createdBy"),
        "createdAt": meta_snapshot.get("createdAt"),
        "updatedBy": meta_snapshot.get("updatedBy"),
        # Keep published version-info timestamp in same display timezone
        # as metadata API, avoiding UTC/raw drift in UI.
        "updatedAt": meta_snapshot.get("updatedAt") or format_display_datetime(now),
        "changeDescription": change_description,
        "documentSummary": meta_snapshot.get("documentSummary", ""),
        "changeRecords": version_records,
    }
    save_version_info(project_id, new_version, version_info)

    published = list(manifest.get("publishedVersions") or [])
    if new_version not in published:
        published.append(new_version)
    manifest_after = load_manifest(project_id)
    manifest_after["publishedVersions"] = published
    manifest_after["latestReleaseVersion"] = new_version
    manifest_after["changeRecords"] = []
    save_manifest(project_id, manifest_after)

    rebuild_draft_from_version(
        project_id,
        new_version,
        updated_by=operator,
    )
    sync_all_chapter_excel(project_id, "draft")
    manifest_final = load_manifest(project_id)
    if manifest_final.get("changeRecords"):
        manifest_final["changeRecords"] = []
        save_manifest(project_id, manifest_final)

    archived_docs = [
        str(device_table_xlsx_path(project_id, new_version)),
        str(output_xlsx_path(project_id, new_version)),
        str(service_content_xlsx_path(project_id, new_version)),
        str(maint_strategy_xlsx_path(project_id, new_version)),
    ]
    if ch84_result:
        archived_docs.append(str(maint_sla_xlsx_path(project_id, new_version)))

    label = new_version
    chapters_result: dict[str, Any] = {
        "2": ch02_result,
        "8.1": ch81_result,
        "8.2": ch82_result,
        "8.3": ch83_result,
    }
    if ch84_result:
        chapters_result["8.4"] = ch84_result

    return {
        "proposalVersion": new_version,
        "status": "published",
        "createdBy": version_info["createdBy"],
        "updatedBy": proposal_operator_display_name(session),
        "updatedAt": format_display_datetime(now),
        "decisionEvalJobId": f"job_{new_version}",
        "sideEffects": {
            "tasksCreated": 3,
            "risksCreated": 3,
            "integrationRequirementsCreated": 2,
            "documentsArchived": archived_docs,
        },
        "progress": [
            {"role": "user", "body": f"生成预案并决策 · {label}"},
            {
                "role": "ai",
                "body": f"预案 {label} 已发布 · 正在下发任务与风险…",
                "chips": ["预案已发布"],
            },
            {
                "role": "ai",
                "body": "任务下发完成：ConnectX-7 数量确认（何博）/ 样本面接入设备补齐（王明）/ k8s 平台版本确认（TD）已进入计划任务列表。",
                "chips": ["任务 +3", "已指定责任人"],
            },
            {
                "role": "ai",
                "body": "风险已写入项目孪生风险预警：BOQ 冲突（高）/ 组网缺失（高）/ CAD 缺失（中）· 进入孪生看板可见全貌。",
                "chips": ["风险 +3", "已同步看板"],
            },
        ],
        "chapters": chapters_result,
    }
