"""
combo_create · 建模仿真第 3 步「创建超节点」（auto_dragd 创建阶段移植）

对应 run_place_api.py run --only-create：9 个 POD 平铺创建超节点，按 roomName×model 分 5 次
batchCreateCombo（统一走 SimApiClient）。请求由 place_api 现建（适配表 + 机房机柜表.xlsx +
cabinets.json），缺输入时回落 fixtures/requests_fixture.json（已固化 5 创建 + 162 移动）。

幂等：写 sentinel combo_created.json；full_restart 重跑时若已创建则跳过（避免 live 重复创建），
跳过时仍回放 metrics 保持 KPI 稳定。下游 cabinet_move 复用本步写出的 requests.json。
"""
from __future__ import annotations

import json
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit
from ..services import FIXTURE_CABINETS, FIXTURE_REQUESTS
from ..services.place_api import load_or_build_requests, send_create
from ..services.sim_api import SimApiClient, is_live

COMPAT_TABLE_REL = "ProjectData/RunTime/compat_table.md"
REQUESTS_REL = "ProjectData/RunTime/requests.json"
CREATED_REL = "ProjectData/RunTime/combo_created.json"
_XLSX_HINTS = ("机房机柜", "cabinet", "机柜信息")
_CABINETS_HINTS = ("cabinet",)


class ComboCreateStep(BaseStep):
    key = "combo_create"
    name = "创建超节点"
    artifacts_pattern = [REQUESTS_REL, CREATED_REL]

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        sentinel = ctx.work_root / CREATED_REL
        redo = bool((ctx.project or {}).get("_redo_create"))

        # 幂等：已创建且非重做 → 跳过，回放 metrics
        if sentinel.is_file() and not redo:
            try:
                prev = json.loads(sentinel.read_text(encoding="utf-8"))
                emit(f"[{self.key}] 超节点已创建（{prev.get('created_count', 0)} 组），跳过重复创建")
                return {"metrics": self._metrics(prev)}
            except Exception:
                pass

        # 现建 / 回落请求
        adapt_md = ctx.work_root / COMPAT_TABLE_REL
        xlsx = self._find_input(ctx, _XLSX_HINTS, (".xlsx", ".xls"))
        grid = self._find_input(ctx, _CABINETS_HINTS, (".json",)) or FIXTURE_CABINETS
        doc = load_or_build_requests(
            adapt_md=adapt_md, xlsx_path=xlsx, grid_path=grid,
            fixture_path=FIXTURE_REQUESTS, emit=emit,
        )
        meta = doc.get("meta", {})
        combo_base = meta.get("combo_base_model", "")
        pod_count = meta.get("pod_count", 0)

        # 落 requests.json 供下游 cabinet_move 复用
        req_path = ctx.work_root / REQUESTS_REL
        req_path.parent.mkdir(parents=True, exist_ok=True)
        req_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

        emit(f"[{self.key}] 仿真 API 模式：{'LIVE' if is_live() else 'dry-run（不发真请求，全量留痕）'}")
        client = SimApiClient(work_root=ctx.work_root, emit=emit)
        result = send_create(client, doc, emit=emit)

        record = {
            "ok": result.get("ok", False),
            "created_count": result.get("total", len(doc.get("create", []))),
            "move_total": len(doc.get("move", [])),
            "pod_count": pod_count,
            "combo_base": combo_base,
            "live": is_live(),
            "error": result.get("error", ""),
        }
        sentinel.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        if not result.get("ok"):
            emit(f"[{self.key}] ⚠ 创建失败于第 {result.get('failed_at')} 组：{result.get('error')}")
        else:
            emit(f"[{self.key}] 超节点创建完成：{record['created_count']} 组 / {pod_count} 个 POD")
        return {"metrics": self._metrics(record)}

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

    @staticmethod
    def _find_input(ctx: SkillContext, hints: tuple[str, ...], exts: tuple[str, ...]) -> Path | None:
        cands = [p for p in sorted(ctx.input_dir.glob("*"))
                 if p.is_file() and p.suffix.lower() in exts]
        if not cands:
            return None
        for p in cands:
            if any(h in p.name.lower() for h in hints):
                return p
        return cands[0]
