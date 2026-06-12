"""
下发计划 / 设备底表（摘自 CPCIA ``dispatch_task.py``，随 skill 内置，无外部仓库依赖）。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_LOG = logging.getLogger("software_deployment.plan_dispatch")


def _skill_root() -> Path:
    return Path(os.environ.get("SD_SKILL_ROOT", Path.cwd())).resolve()


def _split_constants():
    rt = _skill_root() / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    from sd_script_import import import_sd_script  # noqa: WPS433

    return import_sd_script(_skill_root(), "2_plan_split", "constants")


def _split_plan_mod():
    rt = _skill_root() / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    from sd_script_import import import_sd_script  # noqa: WPS433

    return import_sd_script(_skill_root(), "2_plan_split", "plan_split")


C = _split_constants()


def get_device_list_by_type(third_task: dict[str, Any], fullstack_device_info: dict[str, list]) -> tuple[list, str]:
    device_list = third_task.get("device_list")
    device_type = _get_device_type_from_model(device_list)
    return fullstack_device_info.get(device_type, []).copy(), device_type


def _get_device_type_from_model(model: str) -> str:
    return _split_plan_mod().get_device_type_from_model(model)


class DispatchRunner:
    def __init__(
        self,
        *,
        lld_path: str,
        scene: dict[str, Any],
        project_id: str,
        second_tasks: list[dict[str, Any]],
        third_tasks: list[dict[str, Any]],
    ) -> None:
        self.lld_file_path = lld_path
        self.project_id = project_id
        self.second_tasks = second_tasks
        self.third_tasks = third_tasks
        self.product_specification = str(scene.get("productSpecification") or scene.get("product_spec") or "")
        self.pod_info = str(scene.get("pod_info") or scene.get("podInfo") or "single_pod")
        self.fullstack_device_info = {d_type: [] for d_type in C.DEVICE_ALL}

    def load_lld_data(self):
        all_sheets = set(pd.ExcelFile(self.lld_file_path).sheet_names)
        candidate = [
            C.SHEET_SERVER_OOB,
            C.SHEET_LQ_OOB,
            C.SHEET_STORAGE_OOB,
            C.SHEET_HYPERPLANE,
            C.SHEET_DEVICE_LOCATION,
        ]
        available = [s for s in candidate if s in all_sheets]
        if C.SHEET_SERVER_OOB not in available:
            raise ValueError(f"LLD设计文件中缺少【{C.SHEET_SERVER_OOB}】页签，请检查。")
        device_data = pd.read_excel(self.lld_file_path, sheet_name=available)
        if self.product_specification == "A3":
            try:
                hyperplane_df = pd.read_excel(self.lld_file_path, sheet_name=C.SHEET_HYPERPLANE)
                switch_df = device_data.get(C.SHEET_LQ_OOB)
                if switch_df is not None:
                    merged = pd.merge(switch_df, hyperplane_df, on=C.COL_DEVICE_NAME, how="left")
                    device_data[C.SHEET_LQ_OOB] = merged
            except ValueError:
                _LOG.warning("A3 场景缺少超平面网络规划页签，跳过 Pod 合并")
        return device_data

    def fill_servers_info(self, device_data) -> None:
        server_data = device_data.get(C.SHEET_SERVER_OOB).to_dict(orient="records")
        for server in server_data:
            self.fullstack_device_info[C.DEVICE_SERVER].append(
                {
                    "设备名称": server.get(C.CC_DEVICE_NAME),
                    "设备SN": server.get(C.CC_SERIAL_NUMBER, ""),
                    "超节点ID": server.get(C.COL_SUPER_NODE, ""),
                    "设备IP": server.get(C.COL_MGMT_IP),
                }
            )

    def fill_switches_info(self, device_data) -> None:
        switch_data = device_data.get(C.SHEET_LQ_OOB)
        if switch_data is None:
            return
        for switch in switch_data.to_dict(orient="records"):
            switch_name = switch.get(C.COL_DEVICE_NAME)
            if not switch_name or pd.isna(switch_name):
                continue
            self.fullstack_device_info[C.DEVICE_LQ_SWITCH].append(
                {
                    "设备名称": switch_name,
                    "设备IP": switch.get(C.COL_DEVICE_ID) or switch.get(C.COL_MGMT_IP),
                    "设备SN": switch.get(C.CC_SERIAL_NUMBER, ""),
                    "超节点ID": switch.get(C.COL_SUPER_NODE, ""),
                }
            )

    def _third_under_second(self, second_task_sn: str) -> list[dict[str, Any]]:
        out = []
        for t in self.third_tasks:
            if str(t.get("second_task_sn") or "") != str(second_task_sn):
                continue
            if t.get("third_task_status") != C.TASK_STATUS_PENDING_DISPATCHED:
                continue
            if t.get("task_type") != "agent":
                continue
            out.append(t)
        return out

    def dispatch_device_task_by_type(self, second_task: dict[str, Any]) -> list[dict[str, Any]]:
        db_params: list[dict[str, Any]] = []
        second_task_sn = second_task.get("serial_number")
        for third_task in self._third_under_second(second_task_sn):
            device_list, device_type = get_device_list_by_type(third_task, self.fullstack_device_info)
            pod_ids = json.loads(third_task.get("pod_ids") or "[0]")
            if self.pod_info == C.SINGLE_POD:
                pod_ids = [0]
            for device in device_list:
                params = {
                    "project_id": self.project_id,
                    "device_ip": device.get("设备IP", ""),
                    "device_name": device.get("设备名称"),
                    "device_type": device_type,
                    "start_date": third_task.get("start_date"),
                    "end_date": third_task.get("end_date"),
                    "second_task_sn": second_task_sn,
                    "second_task_name": second_task.get("activity_name", ""),
                    "third_task_sn": third_task.get("serial_number"),
                    "third_task_name": third_task.get("third_instruction"),
                    "task_status": C.TASK_STATUS_UN_INIT,
                    "update_time": third_task.get("update_time"),
                    "principal": third_task.get("principal"),
                    "superpod_id": 0,
                }
                if pod_ids == [0]:
                    db_params.append(params)
                    continue
                for pod_id in pod_ids:
                    try:
                        if int(pod_id) == int(device.get("超节点ID") or 0):
                            params["superpod_id"] = pod_id
                            db_params.append(params)
                    except ValueError:
                        pass
        return db_params

    def run(self) -> tuple[list[dict[str, Any]], dict[str, int]]:
        device_data = self.load_lld_data()
        self.fill_servers_info(device_data)
        self.fill_switches_info(device_data)
        all_params: list[dict[str, Any]] = []
        for second_task in self.second_tasks:
            all_params.extend(self.dispatch_device_task_by_type(second_task))
        return all_params, {k: len(v) for k, v in self.fullstack_device_info.items()}


def _device_rows_to_nanobot(db_params: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "projectId": p.get("project_id"),
            "deviceIp": p.get("device_ip"),
            "deviceName": p.get("device_name"),
            "deviceType": p.get("device_type"),
            "superpodId": p.get("superpod_id") or 0,
            "secondTaskId": p.get("second_task_sn"),
            "secondTaskName": p.get("second_task_name"),
            "thirdTaskId": p.get("third_task_sn"),
            "thirdTaskName": p.get("third_task_name"),
            "taskStatus": p.get("task_status"),
            "principal": p.get("principal"),
            "startDate": p.get("start_date"),
            "endDate": p.get("end_date"),
        }
        for p in db_params
    ]


def third_row_to_internal(third: dict[str, Any], *, project_id: str) -> dict[str, Any]:
    _device_list_stub = _split_plan_mod()._device_list_stub

    dt = str(third.get("deviceType") or "SERVER")
    return {
        "project_id": project_id,
        "serial_number": str(third.get("id") or ""),
        "start_date": third.get("startDate") or "",
        "end_date": third.get("endDate") or "",
        "device_list": _device_list_stub(dt),
        "second_task_sn": third.get("secondId") or "",
        "second_instruction": third.get("secondActivityName") or "",
        "third_instruction": third.get("thirdActivityName") or "",
        "third_task_status": C.TASK_STATUS_PENDING_DISPATCHED,
        "task_type": third.get("taskType") or "agent",
        "pod_ids": json.dumps(third.get("podIds") or [0]),
        "principal": third.get("principal") or "",
        "update_time": "",
    }


def dispatch_device_base(
    *,
    lld_path: str,
    third_tasks: list[dict[str, Any]],
    second_tasks: list[dict[str, Any]],
    scene: dict[str, Any],
    project_id: str = "nanobot-local",
) -> dict[str, Any]:
    from pathlib import Path

    second_row_to_internal = _split_plan_mod().second_row_to_internal

    internals = [second_row_to_internal(s, project_id=project_id) for s in second_tasks]
    third_internal = [third_row_to_internal(t, project_id=project_id) for t in third_tasks]
    db_params, pool_summary = DispatchRunner(
        lld_path=str(lld_path),
        scene=scene,
        project_id=project_id,
        second_tasks=internals,
        third_tasks=third_internal,
    ).run()
    device_rows = _device_rows_to_nanobot(db_params)
    return {
        "deviceTasks": device_rows,
        "devicePoolSummary": pool_summary,
        "lldPath": str(Path(lld_path).resolve()),
        "stats": {
            "rows": len(device_rows),
            "thirdIn": len(third_tasks),
            "thirdAgent": sum(1 for t in third_tasks if str(t.get("taskType") or "agent") == "agent"),
        },
    }
