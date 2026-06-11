"""
智慧工勘 v4 — BOQ 解析

职责: 解析 BOQ.xlsx 提取代际和制冷方式
错误码前缀: SS-BP
"""
from __future__ import annotations

import os
import re
from typing import Optional

import openpyxl


# ──────────────────────────────────────────────
# 异常定义
# ──────────────────────────────────────────────

class BOQParseError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ──────────────────────────────────────────────
# 正则模式（来自旧 scene_filter.py，保留不修改）
# ──────────────────────────────────────────────

COOLING_PATTERNS: dict[str, list[str]] = {
    "液冷": [r"(?i)liquid", r"液冷", r"(?i)LC\d+"],
    "风冷": [r"(?i)air", r"风冷", r"(?i)AC\d+"],
}

GENERATION_PATTERNS: dict[str, list[str]] = {
    "A2": [r"A2", r"(?i)atlas\s*200"],
    "A3": [r"A3", r"(?i)atlas\s*300"],
    "A5": [r"A5", r"(?i)atlas\s*500"],
}


# ──────────────────────────────────────────────
# 公开接口
# ──────────────────────────────────────────────

def parse_boq(boq_path: str) -> str:
    """
    解析 BOQ 文件，返回代际-制冷组合字符串。

    返回值示例: "A3-液冷", "A3-风冷"

    异常:
        BOQParseError(SS-BP-E-001): 文件不存在
        BOQParseError(SS-BP-E-002): 未找到设备型号
        BOQParseError(SS-BP-E-003): 无法推断
    """
    if not os.path.exists(boq_path):
        raise BOQParseError("SS-BP-E-001", f"BOQ 文件不存在: {boq_path}")

    texts = _extract_all_text(boq_path)
    if not texts:
        raise BOQParseError("SS-BP-E-002", "BOQ 中未找到任何文本内容")

    full_text = " ".join(texts)

    generation = _match_first(full_text, GENERATION_PATTERNS)
    cooling = _match_first(full_text, COOLING_PATTERNS)

    if not generation and not cooling:
        raise BOQParseError("SS-BP-E-002", "BOQ 中未找到设备型号信息")

    if not generation or not cooling:
        missing = []
        if not generation:
            missing.append("代际")
        if not cooling:
            missing.append("制冷方式")
        raise BOQParseError(
            "SS-BP-E-003",
            f"无法从 BOQ 推断: {', '.join(missing)}。已识别: "
            f"代际={generation or '未知'}, 制冷={cooling or '未知'}",
        )

    return f"{generation}-{cooling}"


def parse_generation_cooling_from_text(
    text: str,
) -> tuple[Optional[str], Optional[str]]:
    """
    从任意文本中提取代际和制冷方式（用于解析用户对话）。

    返回:
        (generation, cooling) 元组，未匹配的为 None
    """
    if not text:
        return None, None

    generation = _match_first(text, GENERATION_PATTERNS)
    cooling = _match_first(text, COOLING_PATTERNS)

    return generation, cooling


# ──────────────────────────────────────────────
# 内部工具
# ──────────────────────────────────────────────

def _extract_all_text(xlsx_path: str) -> list[str]:
    """从 Excel 所有 Sheet 提取文本内容。"""
    texts = []
    try:
        wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        for ws in wb:
            for row in ws.iter_rows(values_only=True):
                for cell in row:
                    if cell is not None:
                        texts.append(str(cell))
        wb.close()
    except Exception:
        pass
    return texts


def _match_first(text: str, patterns: dict[str, list[str]]) -> Optional[str]:
    """在文本中匹配模式集合，返回第一个匹配的键。"""
    for key, regexes in patterns.items():
        for regex in regexes:
            if re.search(regex, text):
                return key
    return None
