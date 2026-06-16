"""
task_dispatch · GKCLAW 任务下发（视频工勘 App 邮件链路）

意图: survey_work 专属（supplement 不开放；复勘选择 App 方式时会重新回到本步下发）

HITL ChoiceCard：confirm_table 之后询问「下发到现场 App / 跳过」。
  - dispatch → 现场勘测条目 → gkclaw.mail.v1 ZIP → mailer(mailgw) 发往 frontagent 邮箱
  - skip     → 本地人工勘测，wait_survey 走原有上传通道
复勘语义：resurvey_gate 选择 App 下发后，本步只打包需复勘条目，写入
resurvey_gkclaw_task_id；不复用也不覆盖首轮 gkclaw_task_id。
重发语义：confirm_table redo 会清 dispatch_decision（skill.apply_resume_payload），
再次下发 = 新 task_id + 旧任务 superseded（契约无撤销包类型）。
人员来源：project["assignees"] 或 RunTime/gkclaw/assignees.json（缺失 → 表单型 HITL）。
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip

ASSIGNEES_FILE = "ProjectData/RunTime/gkclaw/assignees.json"
ASSIGNEES_FORM_INPUT = {
    "id": "gkclaw_assignees",
    "type": "form",
    "label": "填写现场勘测人员",
    "payloadKey": "assignees",
    "repeatable": True,
    "submitLabel": "确认人员并下发",
    "helpText": "用于现场 App 按姓名和工号校验任务可见性。可添加多名人员。",
    "fields": [
        {"key": "surveyor_name", "label": "姓名", "placeholder": "张三", "required": True},
        {"key": "surveyor_code", "label": "工号", "placeholder": "S001", "required": True},
    ],
}


def _get_survey_table(ctx: SkillContext) -> str | None:
    info_path = ctx.runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            path = json.loads(info_path.read_text(encoding="utf-8")).get("survey_table_path", "")
            if path and os.path.exists(path):
                return path
        except Exception:
            pass
    tables = sorted(ctx.output_dir.glob("*全量勘测结果表*.xlsx")) if ctx.output_dir.exists() else []
    return str(tables[0]) if tables else None


def _read_project_info(ctx: SkillContext) -> dict:
    info_path = ctx.runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            return json.loads(info_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _update_project_info(ctx: SkillContext, key: str, value) -> None:
    info = _read_project_info(ctx)
    info[key] = value
    ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
    (ctx.runtime_dir / "project_info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_project_info(ctx: SkillContext, info: dict) -> None:
    ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
    (ctx.runtime_dir / "project_info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_assignees(ctx: SkillContext) -> list[dict]:
    """人员来源：project payload 优先，其次 RunTime/gkclaw/assignees.json。"""
    a = ctx.project.get("assignees") or []
    if a:
        return list(a)
    f = ctx.runtime_dir / "gkclaw" / "assignees.json"
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _persist_assignees(ctx: SkillContext, assignees: list[dict]) -> None:
    if not assignees:
        return
    d = ctx.runtime_dir / "gkclaw"
    d.mkdir(parents=True, exist_ok=True)
    (d / "assignees.json").write_text(
        json.dumps(assignees, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _is_resurvey_dispatch(ctx: SkillContext) -> bool:
    return (
        ctx.project.get("resurvey_decision") == "resurvey"
        and ctx.project.get("resurvey_dispatch_decision") == "dispatch"
    )


def _task_info_key(ctx: SkillContext) -> str:
    return "resurvey_gkclaw_task_id" if _is_resurvey_dispatch(ctx) else "gkclaw_task_id"


def _resurvey_item_seqs(survey_table: str) -> list[int]:
    from ..services.resurvey_manager import get_items_needing_resurvey
    return [int(item.get("序号", 0)) for item in get_items_needing_resurvey(survey_table)]


class TaskDispatchStep(BaseStep):
    key = "task_dispatch"
    name = "任务下发"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        resurvey_mode = _is_resurvey_dispatch(ctx)
        decision = ctx.project.get("dispatch_decision", "")
        if not resurvey_mode and decision == "skip":
            return {"ok": True, "missing": []}
        if ctx.project.get("resurvey_decision") == "resurvey" and not resurvey_mode:
            return {"ok": True, "missing": []}

        survey_table = _get_survey_table(ctx)
        if not survey_table:
            return {"ok": False, "missing": ["ProjectData/Output/*全量勘测结果表*.xlsx"]}

        if not resurvey_mode and decision not in {"dispatch", "skip"}:
            return {
                "ok": False,
                "missing": [],
                "need_inputs": [{
                    "id": "dispatch_decision",
                    "label": "是否下发视频工勘任务到现场 App",
                    "options": [
                        {"label": "📤 下发到现场 App（邮件链路）", "value": "dispatch",
                         "description": "现场勘测条目打包为 GKCLAW 任务，经邮件网关发往 frontagent，"
                                        "回传结果自动合并"},
                        {"label": "⏭ 跳过下发（本地人工勘测）", "value": "skip",
                         "description": "沿用原有流程：下载勘测表，现场填写后人工上传"},
                    ],
                }],
                "note": "勘测表已确认，可选择经 GKCLAW 邮件链路下发到现场 App",
            }

        # 已下发过（resume 重放）→ 放行，run 内幂等处理。
        # 仅在用户已经明确选择下发/复勘下发后生效，避免历史 task_id 吞掉首次下发方式选择。
        if _read_project_info(ctx).get(_task_info_key(ctx)):
            return {"ok": True, "missing": []}

        if resurvey_mode or decision == "dispatch":
            if not _load_assignees(ctx):
                return {
                    "ok": False,
                    "missing": [],
                    "need_inputs": [ASSIGNEES_FORM_INPUT],
                    "note": (
                        "下发需要任务分配人员（App/Web 按姓名+工号校验身份）。"
                        "请填写现场勘测人员姓名和工号后继续下发。"
                    ),
                }
            return {"ok": True, "missing": []}

        return {"ok": True, "missing": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        resurvey_mode = _is_resurvey_dispatch(ctx)
        if ctx.project.get("resurvey_decision") == "resurvey" and not resurvey_mode:
            emit("[task_dispatch] ⏭ 用户选择本地人工复勘（不下发 App 任务）")
            return {"metrics": {"gkclaw_skipped": True, "resurvey_dispatch_skipped": True}}

        if not resurvey_mode and ctx.project.get("dispatch_decision", "") == "skip":
            emit("[task_dispatch] ⏭ 用户选择跳过下发（本地人工勘测）")
            return {"metrics": {"gkclaw_skipped": True}}

        from ..services.gkclaw.registry import TaskRegistry

        info = _read_project_info(ctx)
        info_key = _task_info_key(ctx)
        existing = info.get(info_key, "")
        reg = TaskRegistry(ctx.runtime_dir)
        if existing:
            task = reg.get(existing)
            if task and task.get("state") == "completed":
                existing = ""
            elif task and task["state"] not in ("failed", "superseded"):
                emit(f"[task_dispatch] ✓ 任务已下发过：{existing}（状态 {task['state']}），不重复下发")
                return {"metrics": {
                    "gkclaw_task_id": existing,
                    "gkclaw_state": task["state"],
                    "gkclaw_dry_run": bool(task.get("dry_run")),
                    "gkclaw_items": len((reg.task_payload(existing) or {}).get("items", [])),
                    "gkclaw_web_url": task.get("web_access_url", ""),
                }}

        survey_table = _get_survey_table(ctx)
        if not survey_table:
            raise RuntimeError("task_dispatch: 全量勘测结果表不存在")

        from ..services.gkclaw.dispatch import dispatch_task
        from ..services.resurvey_manager import get_current_round

        item_filter = None
        survey_round = 1
        if resurvey_mode:
            item_filter = _resurvey_item_seqs(survey_table)
            survey_round = max(2, get_current_round(survey_table))
            emit(f"[task_dispatch] 打包 GKCLAW 复勘任务（{len(item_filter)} 条待复勘项）…")
        else:
            emit("[task_dispatch] 打包 GKCLAW 任务（现场勘测条目 + 底表背景知识）…")
        assignees = _load_assignees(ctx)
        _persist_assignees(ctx, assignees)
        result = dispatch_task(
            runtime_dir=ctx.runtime_dir,
            survey_table_path=survey_table,
            project=ctx.project,
            assignees=assignees,
            generation_cooling=str(info.get("generation_cooling", "")
                                   or ctx.project.get("generation_cooling", "")),
            survey_round=survey_round,
            previous_task_id=existing,
            item_seq_filter=item_filter,
        )
        info[info_key] = result["task_id"]
        if resurvey_mode:
            history = list(info.get("resurvey_gkclaw_task_history") or [])
            entry = {
                "round": survey_round,
                "task_id": result["task_id"],
                "state": result["state"],
                "items_count": result["items_count"],
            }
            history = [h for h in history if h.get("task_id") != result["task_id"]]
            history.append(entry)
            info["resurvey_gkclaw_task_history"] = history
            info["resurvey_round"] = survey_round
            info["resurvey_mode"] = "app"
        _write_project_info(ctx, info)

        if result["dry_run"]:
            emit(f"[task_dispatch] ✓ dry-run：任务包已生成未发送（{result['task_id']}，"
                 f"{result['items_count']} 条现场条目）")
        else:
            emit(f"[task_dispatch] ✓ 任务包已发出：{result['task_id']}"
                 f"（{result['items_count']} 条，mailgw: "
                 f"{result['send_result'].get('mailgw_status', '')}）")

        return {"metrics": {
            "gkclaw_task_id": result["task_id"],
            "gkclaw_state": result["state"],
            "gkclaw_dry_run": result["dry_run"],
            "gkclaw_items": result["items_count"],
            "gkclaw_resurvey": resurvey_mode,
            "gkclaw_message": str(result["send_result"].get("message", "")
                                  or result["send_result"].get("note", "")),
        }}
