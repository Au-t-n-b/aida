# -*- coding: utf-8 -*-
"""灵衢光链路检查 · 轮询后采集 listData → Markdown + 采集 xlsx；导出后合并进 report.zip。"""
from __future__ import annotations

import io
import time
import zipfile
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CollectArtifact:
    markdown: str = ""
    xlsx_bytes: bytes = b""
    xlsx_name: str = ""
    collect_summary: dict[str, int] = field(default_factory=dict)
    devices: list[dict[str, Any]] = field(default_factory=list)


def _list_data(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    raw = data.get("listData") or data.get("list") or []
    return [x for x in raw if isinstance(x, dict)]


def _is_collect_ok(opt_result: Any) -> bool:
    return str(opt_result or "").strip() == "1"


def _build_xlsx(rows: list[tuple[str, str, str]]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "采集信息"
    ws.append(["设备IP", "采集结果", "optResult"])
    for ip, label, opt in rows:
        ws.append([ip, label, opt])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def collect_switch_info(last_payload: dict[str, Any]) -> CollectArtifact:
    """读轮询末次 payload 的 listData，生成采集 Markdown 与 xlsx。"""
    items = _list_data(last_payload)
    ts = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
    xlsx_name = f"灵衢设备采集信息_{ts}.xlsx"

    devices: list[dict[str, Any]] = []
    xlsx_rows: list[tuple[str, str, str]] = []
    success = 0
    failed = 0

    for item in items:
        ip = str(item.get("deviceIp") or item.get("deviceIP") or item.get("ip") or "").strip()
        if not ip:
            continue
        opt = str(item.get("optResult") or item.get("result") or "").strip()
        ok = _is_collect_ok(opt)
        if ok:
            success += 1
            label = "成功"
            result = "Pass"
        else:
            failed += 1
            label = "失败"
            result = "Fail"
        devices.append({"ip": ip, "collectOk": ok, "result": result})
        xlsx_rows.append((ip, label, opt))

    total = len(devices)
    summary = {"total": total, "success": success, "failed": failed}

    md_lines = [
        "### 设备采集统计",
        f"- 总计：**{total}** 台 · 成功 **{success}** · 失败 **{failed}**",
    ]
    if devices:
        md_lines.append("")
        md_lines.append("| 设备IP | 采集 |")
        md_lines.append("| --- | --- |")
        for d in devices[:50]:
            tag = "✅" if d["collectOk"] else "❌"
            md_lines.append(f"| {d['ip']} | {tag} {d['result']} |")
        if len(devices) > 50:
            md_lines.append(f"| … | 共 {len(devices)} 台 |")

    xlsx_bytes = _build_xlsx(xlsx_rows) if xlsx_rows else _build_xlsx([])

    return CollectArtifact(
        markdown="\n".join(md_lines),
        xlsx_bytes=xlsx_bytes,
        xlsx_name=xlsx_name,
        collect_summary=summary,
        devices=devices,
    )


def merge_collect_xlsx(report_bytes: bytes, artifact: CollectArtifact) -> bytes:
    """将采集 xlsx 追加写入 report.zip（对齐 Agent extend_export_response）。"""
    if not report_bytes or not artifact.xlsx_bytes or not artifact.xlsx_name:
        return report_bytes
    buf = io.BytesIO(report_bytes)
    with zipfile.ZipFile(buf, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        if artifact.xlsx_name not in zf.namelist():
            zf.writestr(artifact.xlsx_name, artifact.xlsx_bytes)
    return buf.getvalue()
