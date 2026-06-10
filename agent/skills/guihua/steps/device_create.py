"""
device_create · 第 3 步「创建设备」

移植自 jmfz device_create：把确认后的设备清单"落库为设备节点+属性"。
线下版为状态机占位（真实环境此处对接内网 Nvisual 建设备 API）；
写 RunTime/devices_created.json 留痕，metrics 出创建数。
"""
from __future__ import annotations

import json
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit

DEVICE_LIST_REL = "ProjectData/RunTime/device_list.json"
CREATED_REL = "ProjectData/RunTime/devices_created.json"


class DeviceCreateStep(BaseStep):
    key = "device_create"
    name = "创建设备"
    artifacts_pattern = [CREATED_REL]

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        devices = []
        src = ctx.work_root / DEVICE_LIST_REL
        if src.is_file():
            try:
                devices = json.loads(src.read_text(encoding="utf-8"))
            except Exception:
                devices = []

        created = [
            {**d, "node_id": f"dev-{i+1:03d}", "status": "created"}
            for i, d in enumerate(devices)
        ]
        out = ctx.work_root / CREATED_REL
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(created, ensure_ascii=False, indent=2), encoding="utf-8")

        emit(f"[{self.key}] 已创建 {len(created)} 个设备节点（线下占位；真实环境对接 Nvisual 建设备 API）")
        return {"metrics": {"created_count": len(created)}}
