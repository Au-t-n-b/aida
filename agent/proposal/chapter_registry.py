"""Leaf chapter registry — JSON / XLSX basename SSOT."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterSpec:
    key: str
    json_file: str
    label: str
    legacy_json: str | None = None


# 父章节不落盘；仅叶子章节（与 0610 页面大纲一致）
LEAF_CHAPTERS: tuple[ChapterSpec, ...] = (
    ChapterSpec("meta", "元数据信息.json", "元数据信息"),
    ChapterSpec("1", "1.项目背景.json", "1. 项目背景"),
    ChapterSpec("2", "2.设备配置信息.json", "2. 设备配置信息"),
    ChapterSpec("3", "3.部件配置信息.json", "3. 部件配置信息"),
    ChapterSpec("4", "4.软件配置信息.json", "4. 软件配置信息"),
    ChapterSpec("5.1", "5.1网络平面配置.json", "5.1 网络平面配置"),
    ChapterSpec("5.2", "5.2服务器配置.json", "5.2 服务器配置"),
    ChapterSpec("5.3", "5.3集群设备配置.json", "5.3 集群设备配置"),
    ChapterSpec("6", "6.集成验证需求.json", "6. 集成验证需求"),
    ChapterSpec("7", "7.机房信息.json", "7. 机房信息"),
    ChapterSpec("8.1", "8.1服务交付界面.json", "8.1 服务交付界面"),
    ChapterSpec("8.2", "8.2服务配置.json", "8.2 服务配置"),
    ChapterSpec("8.3", "8.3维保策略.json", "8.3 维保策略"),
    ChapterSpec("8.4", "8.4维保SLA.json", "8.4 维保SLA"),
    ChapterSpec("9", "9.责任矩阵信息.json", "9. 责任矩阵信息"),
    ChapterSpec("10", "10.计划.json", "10. 计划"),
    ChapterSpec("11", "11.验收策略.json", "11. 验收策略"),
    ChapterSpec("12", "12.测试用例.json", "12. 测试用例"),
)

CHAPTER_BY_KEY = {spec.key: spec for spec in LEAF_CHAPTERS}
CHAPTER_BY_JSON = {spec.json_file: spec for spec in LEAF_CHAPTERS}
for _spec in LEAF_CHAPTERS:
    if _spec.legacy_json:
        CHAPTER_BY_JSON[_spec.legacy_json] = _spec

SKIP_JSON_NAMES = frozenset({"manifest.json", "version-info.json"})
