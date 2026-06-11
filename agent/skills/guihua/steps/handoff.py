"""
handoff · 建模仿真第 5 步「移交设备安装」（确认型 HITL 门 gate=handoff · 模块边界）

对应交互：「超节点已创建并落位完毕，是否生成参数面设备…」是/否 → 是即移交「设备安装」模块。
这是建模仿真（规划设计前半段）的终点：本步只写移交标记 + 结题报告，不实现参数面设备生成
本身——那属于独立的「设备安装」模块（另一会话）。

确认（gate=handoff）后 run() 写：
  RunTime/handoff.json —— 移交载荷（combo / POD / 落位条数），供设备安装模块消费；
  Output/modeling_simulation_workbench_report.md —— 建模仿真结题报告。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult

CREATED_REL = "ProjectData/RunTime/combo_created.json"
PROGRESS_REL = "ProjectData/RunTime/move_progress.json"
HANDOFF_REL = "ProjectData/RunTime/handoff.json"
REPORT_REL = "ProjectData/Output/modeling_simulation_workbench_report.md"


class HandoffStep(BaseStep):
    key = "handoff"
    name = "移交设备安装"
    artifacts_pattern = [REPORT_REL, HANDOFF_REL]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        confs = (ctx.project or {}).get("confirmations") or {}
        if confs.get("handoff"):
            return {"ok": True, "missing": [], "found": ["confirmations.handoff"], "note": ""}
        return {
            "ok": False,
            "missing": [],
            "found": [],
            "note": "超节点已创建并落位完毕。是否生成参数面设备并移交「设备安装」模块继续？",
            "need_inputs": [{
                "id": "handoff",
                "label": "是否生成参数面设备，移交设备安装模块？",
                "options": [
                    {"label": "生成参数面，移交设备安装", "value": "confirm"},
                    {"label": "暂不移交", "value": "redo"},
                ],
            }],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        created = self._load(ctx.work_root / CREATED_REL)
        progress = self._load(ctx.work_root / PROGRESS_REL)
        combo = created.get("combo_base", "") or "待确认"
        pod_count = created.get("pod_count", 0)
        move_sent = progress.get("sent", 0)
        move_total = progress.get("total", 0)

        # 移交载荷：设备安装模块消费
        payload = {
            "from_module": "guihua/建模仿真",
            "to_module": "device-install/设备安装",
            "combo_base_model": combo,
            "pod_count": pod_count,
            "moved_cabinets": move_sent,
            "move_total": move_total,
            "generate_param_plane": True,
            "handed_off_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        handoff = ctx.work_root / HANDOFF_REL
        handoff.parent.mkdir(parents=True, exist_ok=True)
        handoff.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        report = ctx.work_root / REPORT_REL
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(self._markdown(combo, pod_count, created, progress), encoding="utf-8")

        emit(f"[{self.key}] 已生成移交载荷 + 结题报告，移交设备安装模块（combo={combo}，"
             f"落位 {move_sent}/{move_total}）")
        return {
            "metrics": {
                "handed_off": True,
                "report": str(report.relative_to(ctx.work_root)),
                "completed": True,
            },
        }

    @staticmethod
    def _load(path: Path) -> dict:
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    @staticmethod
    def _markdown(combo: str, pod_count: int, created: dict, progress: dict) -> str:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        live = "LIVE（真发仿真 API）" if created.get("live") else "dry-run（离线骨架 · 全量留痕）"
        return f"""# 规划设计 · 建模仿真（前半段）结题摘要

- 生成时间（UTC）：{ts}
- 仿真 API 模式：{live}
- 由 `agent/skills/guihua/steps/handoff.py` 在移交阶段写入。

## 阶段概览

1. **设备适配**：解析《建模仿真设备信息表》→ 调仿真 API（queryDeviceModel / querySlotMapping）
   匹配设备型号 + 板卡评分 → 生成《建模仿真设备适配信息表》。
2. **数据确认**：设备适配信息表经用户确认（HITL）。
3. **创建超节点**：超节点组合「{combo}」，{pod_count} 个 POD，
   batchCreateCombo {created.get('created_count', 0)} 组（create_ok={created.get('ok')}）。
4. **机柜落位**：刷新 nVisual 后逐机柜 batchMoveNodes，
   落位 {progress.get('sent', 0)}/{progress.get('total', 0)} 条（done={progress.get('done')}）。
5. **移交设备安装**：生成参数面设备 → 移交「设备安装」模块（见 RunTime/handoff.json）。

## 边界说明

> 建模仿真 = 规划设计**前半段**（设备适配 → 超节点创建 → 机柜落位）。
> 「生成参数面设备」及后续由独立的**设备安装**模块承接；后半段「系统设计」另行实现。
> 仿真 API 调用经统一出口 `services/sim_api.py`（默认 dry-run + 留痕，
> 置 `SIM_API_LIVE=1` 接内网真跑）。
"""
