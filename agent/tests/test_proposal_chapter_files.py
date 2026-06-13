from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from openpyxl import Workbook

from agent.services.proposal_chapter_files import (
    extract_pod_names,
    parse_net_mgmt_json,
    parse_net_plane_xlsx,
    upload_output,
)


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

    assert [(row["server_role"], row["quantity"]) for row in rows] == [
        ("NCE", 2),
        ("CCAE", 1),
    ]


def test_extract_pod_names_from_device_boq_filenames() -> None:
    names = [
        "项目-不含价格-POD01.normalized.json",
        "项目-不含价格-POD01.normalized.consistency.json",
        "项目-Pod9.normalized.json",
        "无POD文件.normalized.json",
    ]

    assert extract_pod_names(names) == ["POD01", "POD09"]


def test_upload_output_keeps_local_file_when_remote_upload_fails() -> None:
    content = b"local-first"
    client = AsyncMock()
    client.upload_file.side_effect = RuntimeError("data center unavailable")

    with (
        patch.object(Path, "mkdir") as mkdir,
        patch.object(Path, "write_bytes") as write_bytes,
        patch("agent.services.proposal_chapter_files.DataCenterClient", return_value=client),
    ):
        result = asyncio.run(
            upload_output(
                "token",
                "project-id",
                "测试目录",
                "test.xlsx",
                content,
                Path("早期介入/交付预案/输出结果/测试目录"),
            )
        )

    mkdir.assert_called_once_with(parents=True, exist_ok=True)
    write_bytes.assert_called_once_with(content)
    assert result["uploaded"] is False
    assert "远端上传失败" in result["warning"]
