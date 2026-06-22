from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from openpyxl import Workbook

from agent.services.proposal_chapter_files import (
    extract_pod_names,
    load_net_plane_rows,
    normalize_dc_project_id,
    parse_net_mgmt_json,
    parse_net_plane_xlsx,
    upload_output,
)
from agent.services.proposal_dc_files import sync_proposal_slots

DC_PROJECT_ID = "70e5ca737ae5433e9f0f3134d216acf7"


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["设备型号", "数量", "版本", "来源", "预案版本号", "设备角色"])
    sheet.append(["CloudEngine 16800", 64, "V300R023", "自动解析", "V1.1", "交换机"])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_parse_net_plane_xlsx_uses_available_device_fields() -> None:
    rows = parse_net_plane_xlsx(_workbook_bytes())

    assert rows == [
        {
            "row_id": "device-1",
            "type": "交换机",
            "vendor": "",
            "model": "CloudEngine 16800",
            "ver": "V300R023",
            "qty": 64,
            "source": "自动解析",
            "proposal_version": "V1.1",
            "note": None,
        }
    ]


def test_parse_net_mgmt_counts_products_without_counting_categories_or_leaves() -> None:
    payload = {
        "products": [
            {
                "product_id": "ccae-01",
                "product_head": "iMaster CCAE V100R025(iMaster CCAE_01)",
                "product_head_qty": 1,
                "categories": [{"name": "CCAE"}],
                "leaves": [{"description": "CCAE license", "total_qty": 480}],
            },
            {
                "product_id": "ccae-01",
                "product_head": "iMaster CCAE V100R025(iMaster CCAE_01)",
                "product_head_qty": 1,
            },
            {
                "product_id": "nce-01",
                "product_head": "iMaster NCE",
                "product_head_qty": 2,
            },
        ]
    }

    rows = parse_net_mgmt_json(json.dumps(payload).encode())

    assert [(row["server_role"], row["server_model"], row["quantity"]) for row in rows] == [
        ("CCAE", "iMaster CCAE V100R025(iMaster CCAE_01)", 1),
        ("NCE", "iMaster NCE", 2),
    ]


def test_extract_pod_names_from_device_boq_filenames() -> None:
    names = [
        "项目-不含价格-POD01.normalized.json",
        "项目-不含价格-POD01.normalized.consistency.json",
        "项目-Pod9.normalized.json",
        "无POD文件.normalized.json",
    ]

    assert extract_pod_names(names) == ["POD01", "POD09"]


def test_upload_output_returns_error_when_remote_upload_fails() -> None:
    content = b"dc-only"
    client = AsyncMock()
    client.upload_file.side_effect = RuntimeError("data center unavailable")

    with patch("agent.services.proposal_chapter_files.DataCenterClient", return_value=client):
        result = asyncio.run(
            upload_output(
                "token",
                DC_PROJECT_ID,
                DC_PROJECT_ID,
                "测试目录",
                "test.xlsx",
                content,
                "早期介入/交付预案/输出结果/测试目录/test.xlsx",
            )
        )

    assert result["uploaded"] is False
    assert "远端上传失败" in result["warning"]


def test_upload_output_uploads_to_datacenter_only() -> None:
    client = AsyncMock()
    client.upload_file.return_value = {"logicalPath": "remote/test.xlsx"}

    with patch("agent.services.proposal_chapter_files.DataCenterClient", return_value=client):
        result = asyncio.run(
            upload_output(
                "token",
                DC_PROJECT_ID,
                DC_PROJECT_ID,
                "测试目录",
                "test.xlsx",
                b"dc-only",
                "早期介入/交付预案/输出结果/测试目录/test.xlsx",
            )
        )

    assert result["uploaded"] is True
    assert result["logical_path"] == "remote/test.xlsx"
    client.upload_file.assert_awaited_once()


def test_upload_output_requires_token() -> None:
    result = asyncio.run(
        upload_output(
            None,
            DC_PROJECT_ID,
            DC_PROJECT_ID,
            "测试目录",
            "test.xlsx",
            b"content",
            "早期介入/交付预案/输出结果/测试目录/test.xlsx",
        )
    )

    assert result["uploaded"] is False
    assert "token" in result["warning"]


def test_dc_project_id_requires_uuid32() -> None:
    assert normalize_dc_project_id(DC_PROJECT_ID) == DC_PROJECT_ID
    assert normalize_dc_project_id("56A0TXN") is None


def test_remote_read_uses_dc_uuid_not_local_project_code() -> None:
    client = AsyncMock()
    client.download_file.return_value = _workbook_bytes()

    artifact_path = MagicMock()
    artifact_path.is_file.return_value = False

    with (
        patch("agent.services.proposal_chapter_files.DataCenterClient", return_value=client),
        patch(
            "agent.services.proposal_chapter_files.chapter_artifact_path",
            return_value=artifact_path,
        ),
        patch(
            "agent.services.proposal_chapter_files.device_table_output_path",
            return_value=Path("/nonexistent/device.xlsx"),
        ),
    ):
        rows = asyncio.run(load_net_plane_rows("token", "56A0TXN", DC_PROJECT_ID))

    assert len(rows) == 1
    remote_ref = client.download_file.call_args.args[0]
    assert remote_ref.project_id == DC_PROJECT_ID


def test_sync_proposal_slots_isolates_slot_failure() -> None:
    with patch(
        "agent.services.proposal_dc_files._fetch_slot_bytes",
        new=AsyncMock(return_value=None),
    ):
        results, warnings = asyncio.run(
            sync_proposal_slots("token", DC_PROJECT_ID, "project", "56A0TXN", ["acceptance_out"])
        )

    assert results["acceptance_out"]["status"] == "optional_missing"
    assert warnings == []
