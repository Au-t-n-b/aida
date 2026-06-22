"""
combo_create · 建模仿真第 3 步「创建超节点」（确认型 HITL 门 gate=combo + 真跑 --only-create）

交互：data_confirm「数据准确？」是 之后，左对话框「数据已确认，是否开始创建超节点？」是/否。
是（gate=combo）→ run() 子进程真跑 vendored run_place_api.py run --only-create
（9 个 POD 平铺创建，按 roomName×model 分 5 次 batchCreateCombo，真发仿真网关）。

每次进入 run() 均真调脚本，除非本 run 已成功写入 sentinel（run_id 一致）。
"""
from __future__ import annotations

import json
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..path_config import get_parse_dir
from ..services import VENDOR_AUTODRAGD
from ..services.sentinel import is_same_run, read_json
from ..services.sim_api import is_live
from ..services.subproc import run_script, _subproc_failure_hint


class ComboCreateStep(BaseStep):
    key = "combo_create"
    name = "创建超节点"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        confs = (ctx.project or {}).get("confirmations") or {}
        if confs.get("combo"):
            return {"ok": True, "missing": [], "found": ["confirmations.combo"], "note": ""}
        meta = self._requests_meta()
        combo = meta.get("combo_base_model", "")
        combo_txt = f"（超节点组合：{combo}）" if combo else ""
        return {
            "ok": False,
            "missing": [],
            "found": [],
            "note": f"数据已确认{combo_txt}。是否开始创建超节点（batchCreateCombo ×{meta.get('create_count', 5)}，真发仿真网关）？",
            "need_inputs": [{
                "id": "combo",
                "label": "数据已确认，是否开始创建超节点？",
                "options": [
                    {"label": "是，开始创建超节点", "value": "confirm"},
                    {"label": "否，暂不创建", "value": "redo"},
                ],
            }],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        sentinel = get_parse_dir() / "combo_created.json"
        redo = bool((ctx.project or {}).get("_redo_create"))
        meta = self._requests_meta()

        prev = read_json(sentinel)
        if is_same_run(prev, ctx.run_id) and prev.get("ok") and not redo:
            emit(f"[{self.key}] 本 run 超节点已创建（{prev.get('created_count', 0)} 组），跳过重复创建")
            return {"metrics": self._metrics(prev)}

        emit(f"[{self.key}] 仿真 API 模式：{'LIVE（真发仿真网关）' if is_live() else 'dry-run'}")
        result = run_script(
            VENDOR_AUTODRAGD,
            ["scripts/run_place_api.py", "run", "--only-create"],
            emit=emit,
        )

        record = {
            "ok": result.get("ok", False),
            "run_id": ctx.run_id,
            "created_count": meta.get("create_count", 0),
            "move_total": meta.get("move_count", 0),
            "pod_count": meta.get("pod_count", 0),
            "combo_base": meta.get("combo_base_model", ""),
            "live": is_live(),
            "exit_code": result.get("exit_code"),
        }
        if not record["ok"]:
            hint = _subproc_failure_hint(result)
            emit(f"[{self.key}] ⚠ 创建失败：{hint}")
            record["error"] = hint
        sentinel.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        if not record["ok"]:
            return {"metrics": self._metrics(record), "error": hint}
        emit(f"[{self.key}] 超节点创建完成：{record['created_count']} 组 / {record['pod_count']} 个 POD")
        return {"metrics": self._metrics(record)}

    # ── helpers ──
    @staticmethod
    def _requests_meta() -> dict:
        req = Path(VENDOR_AUTODRAGD) / "requests.json"
        if req.is_file():
            try:
                return json.loads(req.read_text(encoding="utf-8")).get("meta", {})
            except Exception:
                return {}
        return {}

    @staticmethod
    def _metrics(record: dict) -> dict:
        return {
            "created_count": record.get("created_count", 0),
            "move_total": record.get("move_total", 0),
            "pod_count": record.get("pod_count", 0),
            "combo_base": record.get("combo_base", ""),
            "sim_live": record.get("live", False),
            "create_ok": record.get("ok", False),
        }
