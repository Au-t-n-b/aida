"""
智慧工勘 v4 — 项目元数据读取

职责: 从 projects.json 读取项目元数据
错误码前缀: SS-PM
"""
from __future__ import annotations

import json
import os
from typing import Optional

from .types import ProjectMeta


# ──────────────────────────────────────────────
# 异常定义
# ──────────────────────────────────────────────

class ProjectMetaError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ──────────────────────────────────────────────
# 公开接口
# ──────────────────────────────────────────────

def load_project_meta(projects_json_path: str) -> ProjectMeta:
    """
    从 projects.json 读取当前项目元数据。

    异常:
        ProjectMetaError(SS-PM-E-001): 文件不存在
        ProjectMetaError(SS-PM-E-002): 格式错误
    """
    if not os.path.exists(projects_json_path):
        raise ProjectMetaError(
            "SS-PM-E-001", f"projects.json 不存在: {projects_json_path}"
        )

    try:
        with open(projects_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ProjectMetaError("SS-PM-E-002", f"projects.json 格式错误: {e}")

    # projects.json 可能是 dict 或 list，适配两种结构
    if isinstance(data, list):
        project = data[0] if data else {}
    elif isinstance(data, dict):
        project = data
    else:
        project = {}

    name = project.get("name", "")
    delivery_tags = project.get("deliveryTags", [])
    if not isinstance(delivery_tags, list):
        delivery_tags = []

    generation_cooling = infer_generation_cooling_from_tags(delivery_tags)

    return ProjectMeta(
        project_name=name,
        delivery_tags=delivery_tags,
        generation_cooling=generation_cooling or "",
    )


def infer_generation_cooling_from_tags(delivery_tags: list[str]) -> Optional[str]:
    """
    从 deliveryTags 推断代际-制冷。

    规则:
        - 寻找代际标签: "A2", "A3", "A5"
        - 寻找制冷标签: "液冷", "风冷"
        - 两者都找到 → 返回 "{代际}-{制冷}"
        - 否则返回 None
    """
    generation = None
    cooling = None

    generation_keywords = {"A2", "A3", "A5"}
    cooling_keywords = {"液冷", "风冷"}

    for tag in delivery_tags:
        tag_upper = tag.strip().upper()
        for gk in generation_keywords:
            if gk in tag_upper:
                generation = gk
                break
        for ck in cooling_keywords:
            if ck in tag:
                cooling = ck
                break

    if generation and cooling:
        return f"{generation}-{cooling}"
    return None
