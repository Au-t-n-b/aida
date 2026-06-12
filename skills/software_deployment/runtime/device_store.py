# -*- coding: utf-8 -*-
"""设备底表状态回写（对标 CPCIA Agent ``device_info_db_service.update_device_status``）。

调测命令在执行机跑完后，把每台设备的通过/失败结果回写到 ``device_base_table.json``
对应行的 ``taskStatus``，并重新导出宽表「全量设备完工清单列表」。

与 Agent 的对应关系：

    Agent                                   本模块
    -----                                   ------
    status_manager.construct_test_result    build_device_results（命令→设备级结果）
    device_info_db_service.update_device_status   writeback_task_result（按行 UPSERT 状态）
    TaskStatus（中文枚举）                    TASK_STATUS_*（同字符串）

匹配键：``thirdTaskName + deviceIp``（MVP；Agent 用 second+third+ip 三键）。
底表当前已含服务器（智算）与灵衢交换机行，故 server / switch 类命令均可回写；
匹配不上的设备 IP 通过 ``devicesUnmatched`` 如实返回，不静默吞掉。

MVP 操作本地 JSON；上库时本模块即 DATA_STORE.md 的 ``DeviceStore`` 入口，
调用方（task_runner）不变。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 与 Agent constant/tasks.py TaskStatus 的中文值保持一致
TASK_STATUS_PROCESSING = "执行中"
TASK_STATUS_FINISHED = "已完成"
TASK_STATUS_FAIL = "未通过"
TASK_STATUS_EXECUTE_FAIL = "执行失败"

# task_type → 底表 thirdTaskName（中文活动名，取自 checklist_export._THIRD）。
# 仅登记会写底表的命令；留位命令（implemented=False）不在此。
TASK_TYPE_TO_THIRD: dict[str, str] = {
    # init_install（步骤 9）
    "connection": "连线检查",
    "lq_connection": "灵衢连线检查",
    "lq_config_check": "灵衢配置检查",
    "lq_health_check": "灵衢健康检查",
    "hccs_weak_light": "灵衢光链路检查",
    "weak_light": "弱光检查",
    "cluster_health_check": "执行健康检查",
    "os_install": "OS安装",
    "ascend_install": "昇腾软件安装",
    # subsystem_test（步骤 10）
    "lq_prbs_test": "灵衢PRBS压测",
    "burn_test": "计算硬件压测",
    "single_comprehensive": "单机综合检测",
    "single_model_test": "单机训练测试",
    "traffic_test": "灵衢总线打流测试",
    "hccl_test_single_pod": "集群通信配置测试-单Pod",
    "cluster_train_single_pod": "集群训练测试-单Pod",
    "cluster_infer_single_pod": "集群推理测试-单Pod",
    # cluster_test（步骤 11）
    "hccl_test": "集群通信配置测试",
    "cluster_model_test": "集群训练测试",
}


def third_task_name_for(task_type: str) -> str:
    """task_type → 底表中文三级活动名；未登记返回空串（回写将跳过）。"""
    return TASK_TYPE_TO_THIRD.get(str(task_type or "").strip(), "")


def _skill_root(skill_dir: str | Path) -> Path:
    return Path(skill_dir).resolve()


def _base_table_path(skill_dir: str | Path) -> Path:
    return _skill_root(skill_dir) / "ProjectData" / "plan" / "Output" / "device_base_table.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 结果构造：命令 → [{deviceIp, taskStatus}] ──────────────────────────────
#
# 对标 Agent status_manager.construct_test_result：能从返回/报告拿到设备级
# pass/fail 的命令走细分，拿不到的命令 fallback 整批（按 successNum/failNum）。


def _results_from_list_data(list_data: list[dict[str, Any]]) -> list[dict[str, str]] | None:
    """从 query 返回的 listData[] 解析设备级结果。

    兼容常见字段：设备 IP 取 deviceId/deviceIp/nodeIp；结果取 optResult（"1" 成功）
    或 checkResult（"检查失败" 视为失败）/ taskStatus。无法判定的行跳过。
    返回 None 表示该结构不含可用的设备级明细。
    """
    if not isinstance(list_data, list) or not list_data:
        return None
    out: list[dict[str, str]] = []
    for node in list_data:
        if not isinstance(node, dict):
            continue
        ip = str(
            node.get("deviceId")
            or node.get("deviceIp")
            or node.get("nodeIp")
            or node.get("ip")
            or ""
        ).strip()
        if not ip:
            continue
        opt = node.get("optResult")
        check = node.get("checkResult")
        if opt is not None:
            status = TASK_STATUS_FINISHED if str(opt) == "1" else TASK_STATUS_FAIL
        elif check is not None:
            status = TASK_STATUS_FAIL if str(check).strip() == "检查失败" else TASK_STATUS_FINISHED
        else:
            raw = str(node.get("taskStatus") or node.get("status") or "").strip()
            if raw in {TASK_STATUS_FINISHED, "success", "SUCCESS", "成功"}:
                status = TASK_STATUS_FINISHED
            elif raw in {TASK_STATUS_FAIL, TASK_STATUS_EXECUTE_FAIL, "fail", "FAIL", "失败"}:
                status = TASK_STATUS_FAIL
            else:
                continue
        out.append({"deviceIp": ip, "taskStatus": status})
    return out or None


def build_device_results(
    *,
    task_type: str,
    ips: list[str],
    last_query: dict[str, Any] | None,
    parsed: Any = None,
    ok: bool = True,
) -> tuple[list[dict[str, str]], str]:
    """构造 [{deviceIp, taskStatus}] 列表，及一行判定说明。

    优先级：
      1) parsed（report_parser 已给出设备级 deviceResults/checkResults）
      2) last_query.data.listData 设备级明细
      3) fallback：按 last_query.data 的 successNum/failNum 整批；
         无汇总时按 ok 整批。
    """
    # 1) 报告解析器已产出设备级结果
    if isinstance(parsed, dict):
        for key in ("deviceResults", "checkResults", "testResult"):
            cand = parsed.get(key)
            norm = _results_from_list_data(cand) if isinstance(cand, list) else None
            if norm:
                return norm, f"设备级（来自报告解析 {key}）"

    data = (last_query or {}).get("data")
    data = data if isinstance(data, dict) else {}

    # 2) query 返回含设备级 listData
    norm = _results_from_list_data(data.get("listData"))
    if norm:
        return norm, "设备级（来自 query listData）"

    # 3) fallback 整批
    succ = data.get("successNum")
    fail = data.get("failNum")
    if succ is not None or fail is not None:
        try:
            fail_n = int(fail or 0)
        except (TypeError, ValueError):
            fail_n = 0
        status = TASK_STATUS_FINISHED if fail_n == 0 else TASK_STATUS_FAIL
        note = f"整批（汇总 通过{succ}/失败{fail} → {status}；无设备级明细）"
    else:
        status = TASK_STATUS_FINISHED if ok else TASK_STATUS_EXECUTE_FAIL
        note = f"整批（无汇总，按任务{'成功' if ok else '失败'} → {status}）"
    return [{"deviceIp": str(ip).strip(), "taskStatus": status} for ip in ips if str(ip).strip()], note


# ── 回写：把设备级结果写进底表对应行 ───────────────────────────────────────


def writeback_task_result(
    *,
    skill_dir: str | Path,
    task_type: str,
    device_results: list[dict[str, str]],
    re_export_checklist: bool = True,
) -> dict[str, Any]:
    """按 (thirdTaskName, deviceIp) 匹配底表行，更新 taskStatus，重导宽表。

    对标 Agent device_info_db_service.update_device_status，但仅做 UPDATE
    （MVP 不向底表插入新设备行——底表由步骤 3 dispatch 全量生成）。

    返回摘要：thirdTaskName / rowsUpdated / devicesMatched / devicesUnmatched /
    unmatchedIps / byStatus / checklistReexported。
    """
    third = third_task_name_for(task_type)
    summary: dict[str, Any] = {
        "thirdTaskName": third,
        "rowsUpdated": 0,
        "devicesMatched": 0,
        "devicesUnmatched": 0,
        "unmatchedIps": [],
        "byStatus": {},
        "checklistReexported": False,
    }
    if not third:
        summary["skipped"] = f"task_type「{task_type}」未登记底表活动名，跳过回写"
        return summary
    if not device_results:
        summary["skipped"] = "无设备结果，跳过回写"
        return summary

    base_path = _base_table_path(skill_dir)
    base = _load_json(base_path)
    tasks = base.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        summary["skipped"] = "底表为空或缺失，跳过回写"
        return summary

    status_by_ip: dict[str, str] = {}
    for item in device_results:
        ip = str(item.get("deviceIp") or "").strip()
        st = str(item.get("taskStatus") or "").strip()
        if ip and st:
            status_by_ip[ip] = st

    matched_ips: set[str] = set()
    rows_updated = 0
    by_status: dict[str, int] = {}
    for row in tasks:
        if not isinstance(row, dict):
            continue
        if str(row.get("thirdTaskName") or "").strip() != third:
            continue
        ip = str(row.get("deviceIp") or "").strip()
        new_status = status_by_ip.get(ip)
        if not new_status:
            continue
        matched_ips.add(ip)
        if str(row.get("taskStatus") or "").strip() != new_status:
            row["taskStatus"] = new_status
            rows_updated += 1
        by_status[new_status] = by_status.get(new_status, 0) + 1

    unmatched = [ip for ip in status_by_ip if ip not in matched_ips]
    summary.update(
        {
            "rowsUpdated": rows_updated,
            "devicesMatched": len(matched_ips),
            "devicesUnmatched": len(unmatched),
            "unmatchedIps": unmatched[:50],
            "byStatus": by_status,
        }
    )

    if rows_updated:
        base["schemaVersion"] = int(base.get("schemaVersion") or 1)
        base["tasks"] = tasks
        _save_json(base_path, base)
        if re_export_checklist:
            summary["checklistReexported"] = _reexport_checklist(skill_dir, tasks)

    return summary


def _reexport_checklist(skill_dir: str | Path, tasks: list[dict[str, Any]]) -> bool:
    """重新导出宽表「全量设备完工清单列表」。复用 checklist_export，best-effort。"""
    try:
        import sys

        runtime_dir = _skill_root(skill_dir) / "runtime"
        if str(runtime_dir) not in sys.path:
            sys.path.insert(0, str(runtime_dir))
        from checklist_export import (  # noqa: WPS433
            export_device_checklist_xlsx,
            load_scene,
            resolve_project_display_name,
        )

        root = _skill_root(skill_dir)
        scene = load_scene(root)
        display = resolve_project_display_name(scene=scene, skill_root=root)
        export_device_checklist_xlsx(
            device_tasks=[t for t in tasks if isinstance(t, dict)],
            scene=scene,
            output_dir=root / "ProjectData" / "plan" / "Output",
            project_display_name=display,
        )
        return True
    except Exception:
        return False
