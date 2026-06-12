"""
task_dispatch · GKCLAW 任务下发（视频工勘 App 邮件链路）

意图: survey_work 专属（supplement 不开放，复勘轮 DAG 不回经本步 → 结构性不重发）

HITL ChoiceCard：confirm_table 之后询问「下发到现场 App / 跳过」。
  - dispatch → 现场勘测条目 → gkclaw.mail.v1 ZIP → mailer(mailgw) 发往 frontagent 邮箱
  - skip     → 本地人工勘测，wait_survey 走原有上传通道
重发语义：confirm_table redo 会清 dispatch_decision（skill.apply_resume_payload），
再次下发 = 新 task_id + 旧任务 superseded（契约无撤销包类型）。
人员来源：project["assignees"] 或 RunTime/gkclaw/assignees.json（缺失 → 字段型 HITL）。
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip

ASSIGNEES_FILE = "ProjectData/RunTime/gkclaw/assignees.json"

ASSIGNEES_HITL = {
    "id": "assignees",
    "type": "form",
    "label": "补充工勘人员信息",
    "payload_key": "assignees",
    "repeatable": True,
    "submit_label": "保存并下发",
    "help_text": "下发到现场 App 前需要至少 1 名工勘人员，按姓名 + 工号写入任务包。",
    "fields": [
        {
            "key": "surveyor_name",
            "label": "工勘人员姓名",
            "placeholder": "例如：张三",
            "required": True,
        },
        {
            "key": "surveyor_code",
            "label": "工号",
            "placeholder": "例如：S001",
            "required": True,
        },
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


def normalize_assignees(raw) -> list[dict]:
    """把 HITL 表单 / project / JSON 文件里的人员数据规范成 GKCLAW assignees。"""
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []

    assignees: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("surveyor_name") or item.get("name") or "").strip()
        code = str(item.get("surveyor_code") or item.get("code") or "").strip()
        if not name or not code:
            continue
        key = (name, code)
        if key in seen:
            continue
        seen.add(key)
        assignees.append({"surveyor_name": name, "surveyor_code": code})
    return assignees


def _load_assignees(ctx: SkillContext) -> list[dict]:
    """人员来源：project payload 优先，其次 RunTime/gkclaw/assignees.json。"""
    a = normalize_assignees(ctx.project.get("assignees") or [])
    if a:
        return a
    f = ctx.runtime_dir / "gkclaw" / "assignees.json"
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            return normalize_assignees(data)
        except Exception:
            pass
    return []


class TaskDispatchStep(BaseStep):
    key = "task_dispatch"
    name = "任务下发"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        decision = ctx.project.get("dispatch_decision", "")
        if decision == "skip":
            return {"ok": True, "missing": []}

        # 已下发过（resume 重放）→ 放行，run 内幂等处理
        if _read_project_info(ctx).get("gkclaw_task_id"):
            return {"ok": True, "missing": []}

        survey_table = _get_survey_table(ctx)
        if not survey_table:
            return {"ok": False, "missing": ["ProjectData/Output/*全量勘测结果表*.xlsx"]}

        if decision == "dispatch":
            if not _load_assignees(ctx):
                return {
                    "ok": False,
                    "missing": [],
                    "need_inputs": [ASSIGNEES_HITL],
                    "note": "下发需要任务分配人员（App/Web 按姓名+工号校验身份）。",
                }
            return {"ok": True, "missing": []}

        # 无决策 → ChoiceCard
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

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        if ctx.project.get("dispatch_decision", "") == "skip":
            emit("[task_dispatch] ⏭ 用户选择跳过下发（本地人工勘测）")
            return {"metrics": {"gkclaw_skipped": True}}

        from ..services.gkclaw.registry import TaskRegistry

        info = _read_project_info(ctx)
        existing = info.get("gkclaw_task_id", "")
        reg = TaskRegistry(ctx.runtime_dir)
        if existing:
            task = reg.get(existing)
            if task and task["state"] not in ("failed", "superseded"):
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

        emit("[task_dispatch] 打包 GKCLAW 任务（现场勘测条目 + 底表背景知识）…")
        result = dispatch_task(
            runtime_dir=ctx.runtime_dir,
            survey_table_path=survey_table,
            project=ctx.project,
            assignees=_load_assignees(ctx),
            generation_cooling=str(info.get("generation_cooling", "")
                                   or ctx.project.get("generation_cooling", "")),
            previous_task_id=existing,
            aida_run_id=ctx.run_id,
            aida_skill_id=ctx.skill_id,
            aida_resume_step="wait_survey",
        )
        _update_project_info(ctx, "gkclaw_task_id", result["task_id"])

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
            "gkclaw_message": str(result["send_result"].get("message", "")
                                  or result["send_result"].get("note", "")),
        }}
