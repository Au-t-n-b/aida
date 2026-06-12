# -*- coding: utf-8 -*-
"""
设备底表宽表导出（对齐 CPCIA ``DeviceInfoInterface.download_all_check_list_info``）。

长表：每个 (agent 三级任务 × 设备) 一行，由 ``dispatch_device_base`` 生成。
宽表：每个设备 IP 一行，列为场景相关的三级活动状态（与 Agent 下载的「全量设备完工清单列表」一致）。
"""

from __future__ import annotations

import json
import re
from ipaddress import ip_address
from pathlib import Path
from typing import Any

import pandas as pd

CHECKLIST_REPORT_NAME = "全量设备完工清单列表_{0}.xlsx"
CHECKLIST_LATEST_ALIAS = "全量设备完工清单列表_latest.xlsx"
CHECKLIST_SHEET_NAME = "设备完工情况"

# 与 CPCIA ``TaskStatus`` 展示值一致
TASK_STATUS_ZH: dict[str, str] = {
    "UN_INIT": "未初始化",
    "未初始化": "未初始化",
    "INIT_DONE": "完成初始化",
    "PENDING_DISPATCHED": "待派发",
    "待派发": "待派发",
    "DISPATCHED": "已派发",
    "EXECUTING": "执行中",
    "SUCCESS": "成功",
    "FAILED": "失败",
}


# --- 表头组成（摘自 CPCIA ``Headers`` / ``component_header``）---

_THIRD = {
    "OS_INSTALL": "OS安装",
    "ST_SOFTWARE_INSTALL": "昇腾软件安装",
    "SP_TEST": "计算硬件压测",
    "LINK_CHECK": "连线检查",
    "WEAK_LIGHT": "弱光检查",
    "SINGLE_COMPREHENSIVE_TEST": "单机综合检测",
    "HEALTH_CHECK": "执行健康检查",
    "AICORE_TEST": "AI核压测",
    "TRAFFIC_TEST": "灵衢总线打流测试",
    "LQ_CONFIG_CHECK": "灵衢配置检查",
    "LQ_LINK_CHECK": "灵衢连线检查",
    "HCCS_WEAK_LIGHT": "灵衢光链路检查",
    "LQ_HEALTH_CHECK": "灵衢健康检查",
    "PRBS_TEST": "灵衢PRBS压测",
    "SINGLE_TRAIN_TEST": "单机训练测试",
    "SINGLE_INFER": "单机推理测试",
    "HCCL_TEST": "集群通信配置测试",
    "CLUSTER_MODELS_TEST": "集群训练测试",
    "CLUSTER_INFER": "集群推理测试",
    "HCCL_TEST_SINGLE_POD": "集群通信配置测试-单Pod",
    "CLUSTER_MODELS_TEST_SINGLE_POD": "集群训练测试-单Pod",
    "CLUSTER_INFER_SINGLE_POD": "集群推理测试-单Pod",
}

_HEADER_BASIC = [
    _THIRD["OS_INSTALL"],
    _THIRD["ST_SOFTWARE_INSTALL"],
    _THIRD["SP_TEST"],
    _THIRD["LINK_CHECK"],
    _THIRD["WEAK_LIGHT"],
    _THIRD["SINGLE_COMPREHENSIVE_TEST"],
    _THIRD["HEALTH_CHECK"],
    _THIRD["AICORE_TEST"],
    _THIRD["TRAFFIC_TEST"],
]

_HEADER_LQ = [
    _THIRD["LQ_CONFIG_CHECK"],
    _THIRD["LQ_LINK_CHECK"],
    _THIRD["HCCS_WEAK_LIGHT"],
    _THIRD["LQ_HEALTH_CHECK"],
    _THIRD["PRBS_TEST"],
]

_BASE_HEADERS = {
    "infer": [_THIRD["SINGLE_INFER"], _THIRD["HCCL_TEST"], _THIRD["CLUSTER_INFER"]],
    "train": [_THIRD["SINGLE_TRAIN_TEST"], _THIRD["HCCL_TEST"], _THIRD["CLUSTER_MODELS_TEST"]],
    "train_infer": [
        _THIRD["SINGLE_TRAIN_TEST"],
        _THIRD["SINGLE_INFER"],
        _THIRD["HCCL_TEST"],
        _THIRD["CLUSTER_MODELS_TEST"],
        _THIRD["CLUSTER_INFER"],
    ],
}

_MULTI_POD_INSERTIONS = {
    "infer": {"items": [_THIRD["HCCL_TEST_SINGLE_POD"], _THIRD["CLUSTER_INFER_SINGLE_POD"]], "pos": 1},
    "train": {"items": [_THIRD["HCCL_TEST_SINGLE_POD"], _THIRD["CLUSTER_MODELS_TEST_SINGLE_POD"]], "pos": 1},
    "train_infer": {
        "items": [
            _THIRD["HCCL_TEST_SINGLE_POD"],
            _THIRD["CLUSTER_MODELS_TEST_SINGLE_POD"],
            _THIRD["CLUSTER_INFER_SINGLE_POD"],
        ],
        "pos": 2,
    },
}


def _scene_field(scene: dict[str, Any], *keys: str, default: str = "") -> str:
    for k in keys:
        v = scene.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


def component_header(scene: dict[str, Any]) -> list[str]:
    """对齐 CPCIA ``db_service.component_header``。"""
    pod_info = _scene_field(scene, "pod_info", "podInfo", default="single_pod")
    train_infer = _scene_field(scene, "train_infer_scene", default="infer")
    product_spec = _scene_field(scene, "productSpecification", "product_spec", default="").upper()

    components: list[list[str]] = [["设备IP", "设备名称"]]
    if pod_info == "multi_pods":
        components.append(["POD_ID"])
    if product_spec == "A3":
        components.append(_HEADER_LQ.copy())
    components.append(_HEADER_BASIC.copy())

    header_append = list(_BASE_HEADERS.get(train_infer, _BASE_HEADERS["infer"]))
    if pod_info == "multi_pods":
        insertion = _MULTI_POD_INSERTIONS.get(train_infer)
        if insertion:
            pos = insertion["pos"]
            items = insertion["items"]
            header_append = header_append[:pos] + items + header_append[pos:]
    components.append(header_append)

    return [item for sub in components for item in sub]


def resolve_project_display_name(
    *,
    scene: dict[str, Any] | None = None,
    project_id: str | None = None,
    project_name: str | None = None,
    skill_root: Path | None = None,
) -> str:
    if project_name and str(project_name).strip():
        return str(project_name).strip()
    sc = scene or {}
    for key in ("projectDisplayName", "projectName", "projectCode"):
        v = sc.get(key)
        if v and str(v).strip():
            return str(v).strip()
    if project_id and str(project_id).strip():
        return str(project_id).strip()
    if skill_root:
        try:
            from projects_registry import load_projects_doc, pick_project

            doc = load_projects_doc()
            proj = pick_project(doc, project_id)
            if proj:
                for key in ("projectName", "name", "projectCode", "projectId"):
                    v = proj.get(key)
                    if v and str(v).strip():
                        return str(v).strip()
        except Exception:
            pass
    return "nanobot-local"


def _status_zh(raw: Any) -> str:
    s = str(raw or "").strip()
    return TASK_STATUS_ZH.get(s, s or "未初始化")


def _ip_sort_key(ip: str) -> tuple:
    try:
        return (0, ip_address(ip))
    except ValueError:
        return (1, ip)


def pivot_device_tasks_to_checklist(
    device_tasks: list[dict[str, Any]],
    header: list[str],
) -> list[dict[str, Any]]:
    """长表 → 宽表（每设备一行，仅填充 header 中的三级活动列）。"""
    header_set = set(header)
    by_ip: dict[str, dict[str, Any]] = {}

    for row in device_tasks:
        ip = str(row.get("deviceIp") or "").strip()
        if not ip:
            continue
        third = str(row.get("thirdTaskName") or "").strip()
        if third not in header_set:
            continue
        if ip not in by_ip:
            by_ip[ip] = {col: "" for col in header}
            by_ip[ip]["设备IP"] = ip
            by_ip[ip]["设备名称"] = str(row.get("deviceName") or "")
            if "POD_ID" in header_set:
                by_ip[ip]["POD_ID"] = row.get("superpodId") if row.get("superpodId") is not None else 0
        by_ip[ip][third] = _status_zh(row.get("taskStatus"))
        if not by_ip[ip].get("设备名称"):
            by_ip[ip]["设备名称"] = str(row.get("deviceName") or "")

    return [by_ip[k] for k in sorted(by_ip.keys(), key=lambda x: _ip_sort_key(x))]


def export_device_checklist_xlsx(
    *,
    device_tasks: list[dict[str, Any]],
    scene: dict[str, Any],
    output_dir: Path,
    project_display_name: str,
) -> dict[str, Any]:
    """
    写出 ``全量设备完工清单列表_{项目名}.xlsx``，返回路径与统计。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    header = component_header(scene)
    rows = pivot_device_tasks_to_checklist(device_tasks, header)
    file_name = CHECKLIST_REPORT_NAME.format(project_display_name)
    # 文件名安全化
    safe = re.sub(r'[<>:"/\\|?*]', "_", file_name)
    out_path = output_dir / safe

    df = pd.DataFrame(rows, columns=header) if rows else pd.DataFrame(columns=header)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=CHECKLIST_SHEET_NAME, index=False)

    alias_path = output_dir / CHECKLIST_LATEST_ALIAS
    if alias_path.resolve() != out_path.resolve():
        import shutil

        shutil.copy2(out_path, alias_path)

    long_rows = len(device_tasks)
    return {
        "path": str(out_path.resolve()),
        "latestAliasPath": str(alias_path.resolve()),
        "fileName": safe,
        "latestAliasName": CHECKLIST_LATEST_ALIAS,
        "sheetName": CHECKLIST_SHEET_NAME,
        "headerColumns": len(header),
        "deviceRows": len(rows),
        "longTableRows": long_rows,
    }


def load_scene(skill_root: Path) -> dict[str, Any]:
    p = skill_root / "ProjectData" / "plan" / "RunTime" / "scene.json"
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}
