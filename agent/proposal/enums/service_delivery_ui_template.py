"""8.1 写死枚举 — 13 行，与开发文档 §3.1 对齐。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceDeliveryUiTemplateRow:
    service_major: str
    service_item: str


SERVICE_DELIVERY_UI_TEMPLATE: tuple[ServiceDeliveryUiTemplateRow, ...] = (
    ServiceDeliveryUiTemplateRow("硬件安装", "数通设备安装"),
    ServiceDeliveryUiTemplateRow("硬件安装", "存储设备安装"),
    ServiceDeliveryUiTemplateRow("硬件安装", "昇腾服务器安装"),
    ServiceDeliveryUiTemplateRow("规划设计与实施", "数通设备规划设计与实施"),
    ServiceDeliveryUiTemplateRow("规划设计与实施", "存储设备规划设计与实施"),
    ServiceDeliveryUiTemplateRow("规划设计与实施", "昇腾设备规划设计与实施"),
    ServiceDeliveryUiTemplateRow("技术集成服务", "数通设备技术集成服务"),
    ServiceDeliveryUiTemplateRow("技术集成服务", "存储设备技术集成服务"),
    ServiceDeliveryUiTemplateRow("技术集成服务", "昇腾设备技术集成服务"),
    ServiceDeliveryUiTemplateRow("使能服务", "AI 计算使能服务"),
    ServiceDeliveryUiTemplateRow("运维服务", "数通设备运维服务"),
    ServiceDeliveryUiTemplateRow("运维服务", "存储设备运维服务"),
    ServiceDeliveryUiTemplateRow("运维服务", "昇腾设备运维服务"),
)


def row_key(service_major: str, service_item: str) -> str:
    return f"{service_major}\0{service_item}"
