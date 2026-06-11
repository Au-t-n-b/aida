"""
cabinet_move · 建模仿真第 4 步「机柜落位」（确认型 HITL 门 gate=move + auto_dragd 落位阶段）

对应交互：「超节点已创建完毕，是否开始机柜落位」——其中夹一次手动刷新 nVisual（原 CLI 的
input() 暂停），AIDA 里收敛成本步的 HITL 确认门：用户刷新 nVisual 后点「已刷新，开始落位」。

确认（gate=move）后 run() 执行 run_place_api.py run --only-move：逐机柜 batchMoveNodes ×162
（前一条成功才发下一条，统一走 SimApiClient）。on_each 进度回流 SSE；写 move_progress.json
支持断点续跑（失败后重跑从断点继续，对齐原脚本 --start-move）。
"""
from __future__ import annotations

import json
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ..services import FIXTURE_REQUESTS
from ..services.place_api import load_or_build_requests, send_move
from ..services.sim_api import SimApiClient, is_live

REQUESTS_REL = "ProjectData/RunTime/requests.json"
COMPAT_TABLE_REL = "ProjectData/RunTime/compat_table.md"
PROGRESS_REL = "ProjectData/RunTime/move_progress.json"


class CabinetMoveStep(BaseStep):
    key = "cabinet_move"
    name = "机柜落位"
    artifacts_pattern = [PROGRESS_REL]

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        confs = (ctx.project or {}).get("confirmations") or {}
        if confs.get("move"):
            return {"ok": True, "missing": [], "found": ["confirmations.move"], "note": ""}
        return {
            "ok": False,
            "missing": [],
            "found": [],
            "note": "超节点已创建完毕。请在 nVisual 仿真软件中手动刷新一次，确认超节点已显示后开始机柜落位。",
            "need_inputs": [{
                "id": "move",
                "label": "已刷新 nVisual，是否开始机柜落位？",
                "options": [
                    {"label": "已刷新，开始落位", "value": "confirm"},
                    {"label": "暂不落位", "value": "redo"},
                ],
            }],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        progress = ctx.work_root / PROGRESS_REL
        redo = bool((ctx.project or {}).get("_redo_move"))

        doc = self._load_requests(ctx, emit)
        total = len(doc.get("move", []))

        # 断点 / 幂等：已全部落位且非重做 → 跳过，回放 metrics
        prev = self._load_progress(progress)
        if prev.get("done") and not redo:
            emit(f"[{self.key}] 机柜落位已完成（{prev.get('sent', total)}/{total}），跳过")
            return {"metrics": self._metrics(prev, total)}

        start = 1 if redo else max(1, int(prev.get("sent", 0)) + 1)
        if start > 1:
            emit(f"[{self.key}] 断点续跑：从第 {start}/{total} 条机柜继续")

        emit(f"[{self.key}] 仿真 API 模式：{'LIVE' if is_live() else 'dry-run（不发真请求，全量留痕）'}")
        emit(f"[{self.key}] 开始逐机柜落位，共 {total} 条")
        client = SimApiClient(work_root=ctx.work_root, emit=emit)

        def on_each(i: int, tot: int) -> None:
            # 进度回流（emit 内部已推 SSE）+ 落盘断点
            self._write_progress(progress, sent=i, total=tot, done=(i >= tot))
            if i % 18 == 0 or i == tot:   # 每个 POD（18 柜）汇报一次
                emit(f"[{self.key}] 落位进度 {i}/{tot}（{round(100 * i / max(tot, 1))}%）")

        result = send_move(client, doc, start=start, emit=emit, on_each=on_each)
        done = result.get("ok", False)
        self._write_progress(progress, sent=result.get("sent", 0), total=total, done=done,
                             ok=done, error=result.get("error", ""))

        if not done:
            emit(f"[{self.key}] ⚠ 落位中断于第 {result.get('failed_at')} 条：{result.get('error')}")
        else:
            emit(f"[{self.key}] 机柜落位完成：{result.get('sent')}/{total} 条")
        return {"metrics": self._metrics(self._load_progress(progress), total)}

    # ── helpers ──
    def _load_requests(self, ctx: SkillContext, emit: Emit) -> dict:
        req_path = ctx.work_root / REQUESTS_REL
        if req_path.is_file():
            return json.loads(req_path.read_text(encoding="utf-8"))
        # combo_create 未留 requests.json（异常路径）→ 回落 fixture
        emit(f"[{self.key}] 未找到 combo_create 的 requests.json，回落预建 fixture")
        return load_or_build_requests(
            adapt_md=ctx.work_root / COMPAT_TABLE_REL, xlsx_path=None, grid_path=None,
            fixture_path=FIXTURE_REQUESTS, emit=emit,
        )

    @staticmethod
    def _load_progress(path: Path) -> dict:
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    @staticmethod
    def _write_progress(path: Path, *, sent: int, total: int, done: bool,
                        ok: bool | None = None, error: str = "") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"sent": sent, "total": total, "done": done}
        if ok is not None:
            rec["ok"] = ok
        if error:
            rec["error"] = error
        path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _metrics(prog: dict, total: int) -> dict:
        return {
            "move_total": prog.get("total", total),
            "move_sent": prog.get("sent", 0),
            "move_done": bool(prog.get("done")),
        }
