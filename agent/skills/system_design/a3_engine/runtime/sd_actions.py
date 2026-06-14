"""Skill-First sd_* action mapping — preserves existing command/orchestrator logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# sd_* action -> L3/L1 command (existing orchestrator uses command_registry + executors)
SD_COMMAND: dict[str, str] = {
    "sd_start": "",
    "sd_after_input_upload": "",
    "sd_query_inputs": "检查输入件是否妥当",
    "sd_step2_mlag": "交换机MLAG规划",
    "sd_step2_dw_compute": "计算带外管理地址规划",
    "sd_step2_dw_net": "网络带外管理地址规划",
    "sd_step2_dw_storage": "存储带外管理地址规划",
    "sd_step2_dw_lq": "灵衢带外管理地址规划",
    "sd_step2_begin": "地址规划",
    "sd_step3_plane_compute_dw": "计算带外管理地址规划",
    "sd_step3_plane_compute_mgmt": "计算管理面地址规划",
    "sd_step3_plane_compute_gcm": "计算管存面地址规划",
    "sd_step3_plane_compute_ywm": "计算业务面地址规划",
    "sd_step3_plane_compute_ybm": "计算样本面地址规划",
    "sd_step3_plane_compute_csm": "计算参数面地址规划",
    "sd_step3_plane_compute_cpm": "计算超平面地址规划",
    "sd_step3_plane_storage_mgmt": "存储管理面地址规划",
    "sd_step3_plane_storage_ywm": "存储业务面地址规划",
    "sd_step3_plane_storage_ybm": "存储样本面地址规划",
    "sd_step4_interconnect": "互联规划",
    "sd_step4_asn": "网络设备ASN规划",
    "sd_step5_ccae": "CCAE规划",
    "sd_step5_nce": "NCE规划",
    "sd_step5_dme": "DME规划",
    "sd_step6_ztp_lld": "生成ZTP设计文件",
    "sd_step6_ztp_cfg": "生成ZTP配置文件",
    "sd_step6_lq_open": "生成灵衢开局文件",
    "sd_step6_skip_ztp": "",
    "sd_lld_generate": "生成完整LLD设计",
    "sd_lld_integrate": "融合完整LLD设计",
}

# Legacy action aliases (backward compatible)
LEGACY_TO_SD: dict[str, str] = {
    "start": "sd_start",
    "resume_after_upload_inputs": "sd_after_input_upload",
    "check_current_project": "sd_after_input_upload",
    "confirm_start_planning": "sd_step_confirm",
}

SD_TO_LEGACY_RESUME: dict[str, str] = {
    "sd_after_input_upload": "resume_after_upload_inputs",
    "sd_step_confirm": "confirm_start_planning",
    "sd_step2_begin_confirm": "confirm_start_planning",
    "sd_after_clarify_intent": "resume_after_clarify_intent",
}


@dataclass(frozen=True)
class NormalizedAction:
    action: str
    command: Optional[str] = None
    auto_execute: bool = False
    check_inputs_only: bool = False


def normalize_action(action: str) -> NormalizedAction:
    raw = (action or "sd_start").strip()
    if raw in LEGACY_TO_SD:
        raw = LEGACY_TO_SD[raw]

    if raw == "sd_start":
        return NormalizedAction(action="sd_start")
    if raw == "sd_after_input_upload":
        return NormalizedAction(action="sd_after_input_upload", check_inputs_only=True)
    if raw == "sd_query_inputs":
        return NormalizedAction(action="sd_query_inputs", command=SD_COMMAND["sd_query_inputs"], check_inputs_only=True)
    if raw == "sd_step_confirm":
        return NormalizedAction(action="sd_step_confirm", auto_execute=True)
    if raw == "sd_step6_skip_ztp":
        return NormalizedAction(action="sd_step6_skip_ztp")
    if raw in {"recognize_intent", "run_command", "sd_run_command"}:
        return NormalizedAction(action="run_command")
    if raw == "resume_after_clarify_intent" or raw == "sd_after_clarify_intent":
        return NormalizedAction(action="resume_after_clarify_intent")
    if raw == "fallback_cancel" or raw == "sd_cancel":
        return NormalizedAction(action="fallback_cancel")

    command = SD_COMMAND.get(raw)
    if command:
        return NormalizedAction(action=raw, command=command)

    return NormalizedAction(action=raw)


def sd_step3_plane_choices() -> list[dict[str, str]]:
    return [
        {"id": "sd_step3_plane_compute_dw", "label": "计算带外管理地址规划"},
        {"id": "sd_step3_plane_compute_mgmt", "label": "计算管理面地址规划"},
        {"id": "sd_step3_plane_compute_gcm", "label": "计算管存面地址规划"},
        {"id": "sd_step3_plane_compute_ywm", "label": "计算业务面地址规划"},
        {"id": "sd_step3_plane_compute_ybm", "label": "计算样本面地址规划"},
        {"id": "sd_step3_plane_compute_csm", "label": "计算参数面地址规划"},
        {"id": "sd_step3_plane_compute_cpm", "label": "计算超平面地址规划"},
        {"id": "sd_step3_plane_storage_mgmt", "label": "存储管理面地址规划"},
        {"id": "sd_step3_plane_storage_ywm", "label": "存储业务面地址规划"},
        {"id": "sd_step3_plane_storage_ybm", "label": "存储样本面地址规划"},
    ]
