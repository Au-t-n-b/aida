"""网络平面规格 · 系统设计规划覆盖矩阵（对齐 a3 dashboard plane-matrix / dispatch_tree）。

每个平面 = 一次确定性地址/互联/接入规划的产出单元。本模块只给**规格与分组**，
供 plane_planning step 遍历、并投影成 SDUI PlaneMatrix。真实执行走 a3_bridge.run_command /
run_dispatch（vendored a3_engine 子 skill）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlaneSpec:
    key: str           # 唯一 key（PlaneMatrix cell）
    label: str         # 显示名
    group: str         # 分组（计算面/网络面/存储面/管理衍生件）
    plane_name: str    # 资源表「网络平面」列匹配值
    connect_hint: str  # 007 端口连线表里对应 sheet/列关键词


# 对齐 a3 data/dashboard.json plane-matrix 的四组平面
PLANE_SPECS: list[PlaneSpec] = [
    # 计算面
    PlaneSpec("compute_dw", "计算带外管理面", "计算面", "计算带外管理面", "计算带外管理"),
    PlaneSpec("compute_mgmt", "计算管理面", "计算面", "计算管理面", "计算管理面"),
    PlaneSpec("compute_biz", "计算业务面", "计算面", "计算业务面", "计算业务面"),
    PlaneSpec("compute_sample", "计算样本面", "计算面", "计算样本面", "计算样本面"),
    PlaneSpec("compute_param", "计算参数面", "计算面", "计算参数面", "参数面"),
    # 网络面
    PlaneSpec("net_dw", "网络带外管理面", "网络面", "网络带外管理面", "网络带外管理"),
    PlaneSpec("net_interconnect", "网络互联", "网络面", "网络互联规划", "互联"),
    PlaneSpec("net_access", "网络接入", "网络面", "网络接入规划", "接入"),
    # 存储面
    PlaneSpec("storage_dw", "存储带外管理面", "存储面", "存储带外管理面", "存储带外管理"),
    PlaneSpec("storage_mgmt", "存储管理面", "存储面", "存储管理面", "存储管理面"),
    PlaneSpec("storage_biz", "存储业务面", "存储面", "存储业务面", "存储业务面"),
    # 管理 / 衍生件
    PlaneSpec("lq_dw", "灵衢带外管理面", "管理/衍生件", "灵衢带外管理面", "灵衢带外管理"),
]
