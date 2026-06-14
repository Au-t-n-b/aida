"""
activity_catalog · 设备安装「活动 ID → 活动名称」固定映射（三级任务可追溯的唯一真相）。

设备安装的三级任务由「二级活动（7.1–7.24）× 管理单元（机房 / POD）」组合生成。
二级活动类型及其规范名称是固定的（与上游 CPCIA 安装模块 InstallationActivityId /
ACTIVITY_ID_NAME_MAPPING 对齐），因此三级任务名称「有迹可循」：
    三级任务 = {管理单元} {活动名称}（活动名称取本表，按 activity_id 规范化）。

《交付计划表》里的 ACTIVITY_NAME 可能因来源不同而措辞各异；解析时一律按 activity_id
回查本表得到规范名称，回查不到才回退原表名，保证命名一致、可追溯。
"""
from __future__ import annotations

from ._common import as_str

# 设备安装二级活动 ID → 规范活动名称（7.0 一级「工程安装」，7.1–7.24 二级活动）。
ACTIVITY_ID_NAME_MAPPING: dict[str, str] = {
    "7.0":  "工程安装",
    "7.1":  "机房洁净度测试",
    "7.2":  "综合布线与成端-通用线缆",
    "7.3":  "综合布线与成端-灵衢线缆",
    "7.4":  "智算服务器安装",
    "7.5":  "智算设备上电",
    "7.6":  "智算服务器硬件验收",
    "7.7":  "通算服务器安装",
    "7.8":  "通算设备上电",
    "7.9":  "通算服务器硬件验收",
    "7.10": "存储设备安装",
    "7.11": "存储设备上电",
    "7.12": "存储设备硬件验收",
    "7.13": "网络设备安装",
    "7.14": "网络设备上电",
    "7.15": "网络设备硬件验收",
    "7.16": "灵衢交换机安装",
    "7.17": "灵衢设备上电",
    "7.18": "灵衢设备硬件验收",
    "7.19": "液冷计算柜安装",
    "7.20": "液冷计算柜设备上电",
    "7.21": "液冷计算柜验收",
    "7.22": "总线设备柜安装",
    "7.23": "总线设备柜设备上电",
    "7.24": "总线设备柜验收",
}


def _normalize_aid(activity_id: str) -> str:
    """活动 ID 归一：去空格；7.10 vs 7.1 保持原样（不裁尾零，二者是不同活动）。"""
    return as_str(activity_id).replace(" ", "")


def canonical_activity_name(activity_id: str, fallback: str = "") -> str:
    """按活动 ID 回查规范活动名称；查不到回退 fallback（原表活动名），再退活动 ID。"""
    aid = _normalize_aid(activity_id)
    name = ACTIVITY_ID_NAME_MAPPING.get(aid)
    if name:
        return name
    return as_str(fallback) or aid


def third_task_name(unit: str, activity_id: str, activity_name: str = "") -> str:
    """三级任务名称 = {管理单元} {规范活动名称}。"""
    name = canonical_activity_name(activity_id, activity_name)
    u = as_str(unit)
    return f"{u} {name}".strip() if u else name
