"""
handoff · 建模仿真第 5 步「生成参数面设备 + 上架 + 拓扑」（确认型 HITL 门 gate=handoff + 真跑 csm-rack）

交互：「超节点已经创建并且落位完毕，是否生成参数面设备，并且完成设备上架和拓扑生成？」是/否。
是（gate=handoff）→ run() 子进程真跑 vendored csm-rack/scripts/run_device_install.py：
  reset 参数面 → 建 54 台 CE9866 Leaf → 跨视图上架 18 次 → batchCreateLink 双轨拓扑。
解析 output/execution-result.json 汇总（leaf / 上架 / 连线 状态码），写 metrics + 结题报告。

幂等：写 sentinel csm_done.json（含 run_id）；同 run full_restart 已成功则跳过。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..services import VENDOR_CSMRACK
from ..services.sentinel import is_same_run, read_json
from ..services.sim_api import is_live
from ..services.subproc import run_script

CREATED_REL = "ProjectData/RunTime/combo_created.json"
PROGRESS_REL = "ProjectData/RunTime/move_progress.json"
CSM_DONE_REL = "ProjectData/RunTime/csm_done.json"
REPORT_REL = "ProjectData/Output/modeling_simulation_workbench_report.md"


class HandoffStep(BaseStep):
    key = "handoff"
    name = "生成参数面设备"
    artifacts_pattern = [REPORT_REL, CSM_DONE_REL]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        confs = (ctx.project or {}).get("confirmations") or {}
        if confs.get("handoff"):
            return {"ok": True, "missing": [], "found": ["confirmations.handoff"], "note": ""}
        return {
            "ok": False,
            "missing": [],
            "found": [],
            "note": "超节点已经创建并且落位完毕。是否生成参数面设备，并完成设备上架和拓扑生成？",
            "need_inputs": [{
                "id": "handoff",
                "label": "超节点已经创建并且落位完毕，是否生成参数面设备，并且完成设备上架和拓扑生成？",
                "options": [
                    {"label": "是，生成参数面并上架连线", "value": "confirm"},
                    {"label": "否，暂不生成", "value": "redo"},
                ],
            }],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        sentinel = ctx.work_root / CSM_DONE_REL
        redo = bool((ctx.project or {}).get("_redo_handoff"))

        prev = read_json(sentinel)
        if is_same_run(prev, ctx.run_id) and prev.get("ok") and not redo:
            emit(f"[{self.key}] 本 run 参数面已生成并上架（leaf {prev.get('leaf_count', 0)} 台），跳过重复执行")
            return {"metrics": self._metrics(prev)}

        emit(f"[{self.key}] 仿真 API 模式：{'LIVE（真发仿真网关）' if is_live() else 'dry-run'}")
        emit(f"[{self.key}] 开始 csm-rack：reset 参数面 → 建 Leaf → 跨视图上架 → 拓扑连线")
        result = run_script(
            VENDOR_CSMRACK,
            ["scripts/run_device_install.py"],
            emit=emit,
            timeout=3600,
        )

        summary = self._read_execution_result(ctx)
        record = {
            "ok": result.get("ok", False) and not summary.get("has_error", False),
            "run_id": ctx.run_id,
            "exit_code": result.get("exit_code"),
            "live": is_live(),
            **summary,
        }
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        report = ctx.work_root / REPORT_REL
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(self._markdown(ctx, record), encoding="utf-8")

        if not record["ok"]:
            emit(f"[{self.key}] ⚠ csm-rack 存在失败（exit_code={record['exit_code']}），请查看 execution-result.json")
        else:
            emit(f"[{self.key}] 参数面设备生成 + 上架 + 拓扑完成："
                 f"leaf {record.get('leaf_count', 0)} / 上架 {record.get('rack_ok', 0)} / 连线 {record.get('topo_ok', 0)}")
        return {"metrics": self._metrics(record)}

    # ── helpers ──
    @staticmethod
    def _read_execution_result(ctx: SkillContext) -> dict:
        """从 vendored csm-rack/output/execution-result.json 抽汇总。"""
        out: dict = {"leaf_count": 0, "rack_ok": 0, "rack_total": 0,
                     "topo_ok": 0, "topo_total": 0, "has_error": False}
        f = Path(VENDOR_CSMRACK) / "output" / "execution-result.json"
        if not f.is_file():
            out["has_error"] = True
            return out
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            out["has_error"] = True
            return out
        out["leaf_count"] = data.get("leaf_count", 0)
        out["server_count"] = data.get("server_count", 0)
        for key, ok_k, tot_k in (("batch_rack", "rack_ok", "rack_total"),
                                 ("create_topo", "topo_ok", "topo_total")):
            s = (data.get(key) or {}).get("summary") or {}
            if s.get("skipped"):
                continue
            out[ok_k] = s.get("ok", 0)
            out[tot_k] = s.get("total", 0)
            if s.get("ok", 0) < s.get("total", 0):
                out["has_error"] = True
        dev = (data.get("create_device") or {}).get("summary") or {}
        if not dev.get("skipped") and dev.get("ok", 0) < dev.get("total", 0):
            out["has_error"] = True
        return out

    @staticmethod
    def _metrics(record: dict) -> dict:
        return {
            "csm_done": record.get("ok", False),
            "leaf_count": record.get("leaf_count", 0),
            "rack_ok": record.get("rack_ok", 0),
            "rack_total": record.get("rack_total", 0),
            "topo_ok": record.get("topo_ok", 0),
            "topo_total": record.get("topo_total", 0),
            "completed": record.get("ok", False),
            "report": REPORT_REL,
        }

    @staticmethod
    def _load(path: Path) -> dict:
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _markdown(self, ctx: SkillContext, record: dict) -> str:
        created = self._load(ctx.work_root / CREATED_REL)
        progress = self._load(ctx.work_root / PROGRESS_REL)
        combo = created.get("combo_base", "") or "待确认"
        pod_count = created.get("pod_count", 0)
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        live = "LIVE（真发仿真 API）" if record.get("live") else "dry-run"
        return f"""# 规划设计 · 建模仿真 结题摘要

- 生成时间（UTC）：{ts}
- 仿真 API 模式：{live}
- 由 `agent/skills/guihua/steps/handoff.py` 在 csm-rack 阶段写入。

## 阶段概览

1. **设备适配**：载入《建模仿真设备适配信息表》（jmfz/api_adapt 产物）。
2. **数据确认**：设备适配信息表经用户确认（HITL）。
3. **创建超节点**：超节点组合「{combo}」，{pod_count} 个 POD，batchCreateCombo
   {created.get('created_count', 0)} 组（create_ok={created.get('ok')}）。
4. **机柜落位**：逐机柜 batchMoveNodes，落位 {progress.get('sent', 0)}/{progress.get('total', 0)} 条
   （done={progress.get('done')}）。
5. **生成参数面设备（csm-rack）**：建 Leaf {record.get('leaf_count', 0)} 台，
   跨视图上架 {record.get('rack_ok', 0)}/{record.get('rack_total', 0)} 次，
   拓扑连线 {record.get('topo_ok', 0)}/{record.get('topo_total', 0)} 条。

## 边界说明

> 参数面设备生成 / 上架 / 拓扑由 vendored `csm-rack/scripts/run_device_install.py`
> 经 subprocess 真跑（本次明确豁免 AGENTS「禁 subprocess 调 py」红线，技术债：
> 后续可移植成 services 走 sim_api 统一出口）。详见 csm-rack/output/execution-result.json。
"""
