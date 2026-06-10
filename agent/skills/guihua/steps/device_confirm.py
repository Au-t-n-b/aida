"""
device_confirm · 第 2 步「设备确认」（确认型 HITL 门）

移植自 jmfz 的 device_confirm：用户复核 BOQ 抽出的设备清单后才放行。
机制：check_inputs 检查 project.confirmations.device；未确认 → 返回 need_inputs
（ChoiceCard），execute_step 据此软中断。用户在 resume 选「确认」→ apply_resume_payload
把 confirmations.device 写进 project（full_restart 重跑保留），本步 check_inputs 放行。
"""
from __future__ import annotations

import json
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult

CACHE_REL = "ProjectData/RunTime/device_list.json"


class DeviceConfirmStep(BaseStep):
    key = "device_confirm"
    name = "设备确认"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        confs = (ctx.project or {}).get("confirmations") or {}
        if confs.get("device"):
            return {"ok": True, "missing": [], "found": ["confirmations.device"], "note": ""}

        # 读设备数量用于提示
        n = 0
        cache = ctx.work_root / CACHE_REL
        if cache.is_file():
            try:
                n = len(json.loads(cache.read_text(encoding="utf-8")))
            except Exception:
                n = 0
        return {
            "ok": False,
            "missing": [],
            "found": [],
            "note": f"请核对 BOQ 抽出的设备清单（共 {n} 项），确认接口/型号/数量后继续创建设备。",
            "need_inputs": [{
                "id": "device",
                "label": f"确认设备清单（{n} 项）",
                "options": [
                    {"label": "确认无误，创建设备", "value": "confirm"},
                    {"label": "重新提取 BOQ", "value": "redo"},
                ],
            }],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        emit(f"[{self.key}] 设备清单已确认，进入创建设备")
        return {"metrics": {"device_confirmed": True}}
