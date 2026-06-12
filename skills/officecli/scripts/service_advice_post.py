#!/usr/bin/env python3
"""
技术建议书 / 服务建议书 → 验收策略表提取
遵循 officecli SKILL.md · 管线A（硬编码模板 + 关键词全文检索）
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

# 5 类验收条款硬编码模板（SKILL.md §管线A）
ACCEPTANCE_TEMPLATE: list[dict[str, str]] = [
    {
        "id": "1",
        "category": "硬件设备",
        "acceptance_scheme": "POD",
        "entry_criteria": "硬件到货",
        "contract_milestone": "硬件到货",
        "acceptance_documents": "硬件设备接收文档",
        "payment_terms": "100%",
        "payment_milestone": "到货",
    },
    {
        "id": "2",
        "category": "软件部分",
        "acceptance_scheme": "License激活完成软件验收",
        "entry_criteria": "License加载完成",
        "contract_milestone": "License加载",
        "acceptance_documents": "License加载证明",
        "payment_terms": "100%",
        "payment_milestone": "License加载",
    },
    {
        "id": "3",
        "category": "服务部分",
        "acceptance_scheme": "对应服务条目交付完成",
        "entry_criteria": "对应服务条目交付完成",
        "contract_milestone": "完工验/PAC",
        "acceptance_documents": "完工验/PAC报告",
        "payment_terms": "100%",
        "payment_milestone": "安装 PAC",
    },
    {
        "id": "4",
        "category": "培训服务",
        "acceptance_scheme": "培训课程完成即验收",
        "entry_criteria": "培训课程完成",
        "contract_milestone": "培训完成",
        "acceptance_documents": "签到表",
        "payment_terms": "100%",
        "payment_milestone": "培训完成",
    },
    {
        "id": "5",
        "category": "维保服务",
        "acceptance_scheme": "硬件到货和License激活后30天",
        "entry_criteria": "OM起算",
        "contract_milestone": "直线法",
        "acceptance_documents": "—",
        "payment_terms": "月度",
        "payment_milestone": "—",
    },
]

KEYWORD_RULES: dict[str, list[str]] = {
    "硬件设备": [
        "设备到货", "POD", "SuperPoD", "硬件验收", "设备验收", "到货验收",
        "设备签收", "开箱验收", "设备安装调试", "现场验收",
    ],
    "软件部分": [
        "License", "软件激活", "商用永久授权", "软件许可", "集群软件",
        "管理系统", "CANN", "MindSpore", "NPU驱动",
    ],
    "服务部分": [
        "完工验收", "PAC", "服务交付", "部署服务", "实施服务", "调测",
        "验收标准", "项目验收", "安装部署", "系统集成",
    ],
    "培训服务": [
        "培训", "培训课程", "技术培训", "培训计划", "赋能培训", "现场培训", "培训服务",
    ],
    "维保服务": [
        "维保", "售后服务", "质保期", "维护服务", "技术支持", "故障处理",
        "备件服务", "巡检", "运维",
    ],
}


def _parse_outline_chapters(outline_text: str) -> list[tuple[int, str]]:
    """解析 officecli outline 为 (paragraph_index, title) 列表。"""
    chapters: list[tuple[int, str]] = []
    for line in outline_text.splitlines():
        m = re.search(r"\[(\d+)\]\s+\"(.+?)\"", line)
        if m:
            chapters.append((int(m.group(1)), m.group(2)))
    return chapters


def _find_chapter_for_line(line_no: int, chapters: list[tuple[int, str]]) -> str:
    current = ""
    for idx, title in chapters:
        if idx <= line_no:
            current = title
        else:
            break
    return current


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    hits = []
    lower = text.lower()
    for kw in keywords:
        if kw.lower() in lower:
            hits.append(kw)
    return hits


def extract_from_text(full_text: str, outline_text: str = "") -> list[dict[str, Any]]:
    """从 officecli view text 输出提取验收表。"""
    chapters = _parse_outline_chapters(outline_text) if outline_text else []
    lines = full_text.splitlines()
    table: list[dict[str, Any]] = []

    for tpl in ACCEPTANCE_TEMPLATE:
        cat = tpl["category"]
        keywords = KEYWORD_RULES.get(cat, [])
        evidence: list[dict[str, Any]] = []
        seen: set[str] = set()

        for i, raw in enumerate(lines):
            content = re.sub(r"^\[/body/p\[@paraId=[^\]]+\]\]\s*", "", raw).strip()
            if not content:
                continue
            matched = _match_keywords(content, keywords)
            if not matched:
                continue
            chapter = _find_chapter_for_line(i, chapters) if chapters else ""
            key = f"{chapter}::{content[:80]}"
            if key in seen:
                continue
            seen.add(key)
            evidence.append({
                "chapter": chapter,
                "matched_keywords": matched,
                "content": content[:500],
            })

        table.append({
            **tpl,
            "total_keyword_matches": len(evidence),
            "evidence": evidence[:5],
        })

    # 仅保留有关键词命中的条目；若全部未命中则返回完整模板（供 UI 展示默认结构）
    matched_rows = [r for r in table if r["total_keyword_matches"] > 0]
    return matched_rows if matched_rows else table


def extract(docx_path: str | Path) -> list[dict[str, Any]]:
    """
    主入口：officecli 解析 docx → 验收策略行（前端 AcceptanceItem 可映射字段）。
    """
    path = Path(docx_path)
    import sys

    repo_root = Path(__file__).resolve().parents[3]  # aida/
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from agent.services.officecli_client import (
        view_text,
        run_officecli,
        list_docx_tables,
        get_json,
        extract_table_matrix,
    )

    full_text = view_text(path)
    outline_r = run_officecli("view", str(path), "outline")
    outline_text = outline_r.stdout if outline_r.returncode == 0 else ""

    rows = extract_from_text(full_text, outline_text)

    # 补充：尝试从 docx 表格直接提取含「验收」表头的结构化行
    table_rows = _extract_acceptance_tables(path, list_docx_tables, get_json, extract_table_matrix)
    if table_rows:
        rows = table_rows

    return rows


def _extract_acceptance_tables(
    path: Path,
    list_tables,
    get_json_fn,
    matrix_fn,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx in list_tables(path):
        try:
            tj = get_json_fn(path, f"/body/tbl[{idx}]", depth=3)
            matrix = matrix_fn(tj)
        except Exception:
            continue
        if not matrix:
            continue
        header = "".join(matrix[0])
        if not any(k in header for k in ("验收", "分类", "回款", "里程碑")):
            continue
        col_map: dict[str, int] = {}
        for i, h in enumerate(matrix[0]):
            h = str(h).strip()
            if "分类" in h:
                col_map["cat"] = i
            elif "验收方案" in h or h == "方案":
                col_map["scheme"] = i
            elif "验收标准" in h or h == "标准":
                col_map["standard"] = i
            elif "验收里程碑" in h or "里程碑" in h:
                col_map["milestone"] = i
            elif "验收文档" in h or "文档" in h:
                col_map["doc"] = i
            elif "回款条款" in h or "回款" in h:
                col_map["payment"] = i
            elif "回款里程碑" in h:
                col_map["paymentMilestone"] = i
        if not col_map:
            continue
        for row in matrix[1:]:
            if not any(str(c).strip() for c in row):
                continue
            get = lambda k, r=row: str(r[col_map[k]]).strip() if k in col_map and col_map[k] < len(r) else ""
            cat, scheme = get("cat"), get("scheme")
            if not cat and not scheme:
                continue
            items.append({
                "category": cat,
                "acceptance_scheme": scheme,
                "entry_criteria": get("standard"),
                "contract_milestone": get("milestone"),
                "acceptance_documents": get("doc"),
                "payment_terms": get("payment"),
                "payment_milestone": get("paymentMilestone"),
            })
    return items


def to_frontend_items(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """映射为前端 AcceptanceItem 字段。"""
    out: list[dict[str, str]] = []
    for r in rows:
        out.append({
            "cat": r.get("category", r.get("cat", "")),
            "scheme": r.get("acceptance_scheme", r.get("scheme", "")),
            "standard": r.get("entry_criteria", r.get("standard", "")),
            "milestone": r.get("contract_milestone", r.get("milestone", "")),
            "doc": r.get("acceptance_documents", r.get("doc", "")),
            "payment": r.get("payment_terms", r.get("payment", "")),
            "paymentMilestone": r.get("payment_milestone", r.get("paymentMilestone", "")),
        })
    return out
