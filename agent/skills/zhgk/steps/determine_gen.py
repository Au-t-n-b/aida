"""
determine_gen · 代际-制冷识别 v4

意图: survey_work / supplement / report_gen

流程：
  1. 若 project["generation_cooling"] 已有值（HITL 选择路径）→ 直接用
  2. 若 RunTime/project_info.json 里已缓存 → 直接用
  3. 否则尝试解析 Input/BOQ.xlsx → 写 project_info.json → 返回 metrics
  4. 若 BOQ 解析失败(E-003) → HITL ChoiceCard 让用户手动指定
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip

GEN_COOLING_OPTIONS = [
    {"label": "A3-液冷", "value": "A3-液冷", "description": "Atlas 300 + 液冷系统"},
    {"label": "A3-风冷", "value": "A3-风冷", "description": "Atlas 300 + 风冷系统"},
    {"label": "A2-风冷", "value": "A2-风冷", "description": "Atlas 200 + 风冷系统"},
    {"label": "A5-液冷", "value": "A5-液冷", "description": "Atlas 500 + 液冷系统"},
]

_HITL_INPUT = {
    "id": "gen_cooling_choice",
    "label": "请手动指定代际-制冷",
    "options": GEN_COOLING_OPTIONS,
}


def _read_cached_gc(runtime_dir) -> str:
    """从 RunTime/project_info.json 读取已缓存的代际制冷，不存在返回空字符串。"""
    info_path = runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            return json.loads(info_path.read_text(encoding="utf-8")).get(
                "generation_cooling", ""
            )
        except Exception:
            pass
    return ""


def _write_project_info(runtime_dir, project: dict, generation_cooling: str) -> None:
    """写（或更新）RunTime/project_info.json。"""
    info_path = runtime_dir / "project_info.json"
    try:
        existing = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    except Exception:
        existing = {}
    existing.update({
        "project_name":       project.get("project_name", ""),
        "activity_id":        project.get("activity_id", ""),
        "room_name":          project.get("room_name", ""),
        "survey_date":        project.get("survey_date", ""),
        "surveyor":           project.get("surveyor", ""),
        "generation_cooling": generation_cooling,
    })
    runtime_dir.mkdir(parents=True, exist_ok=True)
    info_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


class DetermineGenStep(BaseStep):
    key = "determine_gen"
    name = "代际制冷识别"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        # 1. 已有 generation_cooling（HITL 选择 or 外部传入）
        if ctx.project.get("generation_cooling"):
            return {"ok": True, "missing": []}

        # 2. 已缓存在 project_info.json
        if _read_cached_gc(ctx.runtime_dir):
            return {"ok": True, "missing": []}

        # 3. BOQ 文件存在 → run() 会自动解析
        boq_files = list(ctx.input_dir.glob("*BOQ*.xlsx")) if ctx.input_dir.exists() else []
        if boq_files:
            return {"ok": True, "missing": []}

        # 4. 无 BOQ 也无缓存 → HITL：用户手动指定
        return {
            "ok": False,
            "missing": [],
            "need_inputs": [_HITL_INPUT],
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        # ── 1. 已有 generation_cooling（HITL 选择路径）──────────────────────
        gen_cooling = ctx.project.get("generation_cooling", "")
        source = "project（HITL 选择）"

        # ── 2. 已缓存在 project_info.json ─────────────────────────────────
        if not gen_cooling:
            gen_cooling = _read_cached_gc(ctx.runtime_dir)
            if gen_cooling:
                source = "缓存（project_info.json）"

        # ── 3. 自动解析 BOQ ────────────────────────────────────────────────
        if not gen_cooling:
            from ..services.boq_parser import parse_boq, BOQParseError
            boq_files = sorted(ctx.input_dir.glob("*BOQ*.xlsx")) if ctx.input_dir.exists() else []
            if boq_files:
                boq_path = str(boq_files[0])
                emit(f"[determine_gen] 解析 BOQ: {boq_files[0].name}")
                try:
                    gen_cooling = parse_boq(boq_path)
                    source = f"BOQ 自动解析（{boq_files[0].name}）"
                    emit(f"[determine_gen] 识别结果: {gen_cooling}")
                except BOQParseError as e:
                    if e.code == "SS-BP-E-003":
                        # 无法推断 → HITL
                        emit(f"[determine_gen] BOQ 无法推断代际制冷: {e.message}")
                        emit("[determine_gen] 需要用户手动指定")
                        return {
                            "hitl": {
                                "step": self.key,
                                "reason": f"BOQ 解析失败（{e.message}），请手动指定代际-制冷",
                                "need_files": [],
                                "need_inputs": [_HITL_INPUT],
                            }
                        }
                    elif e.code == "SS-BP-E-002":
                        emit(f"[determine_gen] BOQ 未找到设备型号: {e.message}")
                        return {
                            "hitl": {
                                "step": self.key,
                                "reason": "BOQ 文件中未找到可识别的设备型号，请手动指定代际-制冷",
                                "need_files": [],
                                "need_inputs": [_HITL_INPUT],
                            }
                        }
                    else:
                        raise

        # ── 4. 还是没有 → HITL ────────────────────────────────────────────
        if not gen_cooling:
            emit("[determine_gen] 无 BOQ 且无缓存，等待用户指定…")
            return {
                "hitl": {
                    "step": self.key,
                    "reason": "未上传 BOQ 文件，请手动指定代际-制冷",
                    "need_files": [],
                    "need_inputs": [_HITL_INPUT],
                }
            }

        # ── 5. 写 project_info.json ────────────────────────────────────────
        _write_project_info(ctx.runtime_dir, ctx.project, gen_cooling)
        emit(f"[determine_gen] ✓ 代际制冷: {gen_cooling}（来源: {source}）")
        emit(f"[determine_gen] project_info.json 已写入 RunTime/")

        return {
            "metrics": {
                "generation_cooling": gen_cooling,
                "gen_cooling_source": source,
            }
        }
