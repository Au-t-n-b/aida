"""
method_split · 勘测方法分流

意图: survey_work 专属

将全量勘测结果表按「勘测方法」列分组，统计各方法条目数，
结果写入 RunTime/project_info.json["method_groups"]。

v4 业务逻辑：分流后把「客户反馈」类条目自动发邮件给项目组
（设计文档 意图B Step 4）。走 agent/mailer.py 统一出口，默认 dry-run，
AIDA_SEND_EMAIL=1 才真发。无 HITL。
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip


def _resolve_project_recipients(ctx: SkillContext, emit: Emit) -> list[dict]:
    """解析项目组收件人（复用工作区 path_config）。不可用时优雅降级为 []。"""
    from ..bridge import get_zhgk_root
    try:
        root = str(Path(get_zhgk_root()))
        if root not in sys.path:
            sys.path.insert(0, root)
        from path_config import get_recipients  # type: ignore
        # 客户反馈走全体干系人/项目组；不同部署角色常量名可能不同，逐个兜底
        for role_name in ("ROLE_ALL_STAKEHOLDERS", "ROLE_PROJECT_TEAM", "ROLE_PD_TD_EXPERT"):
            try:
                import path_config as _pc  # type: ignore
                role = getattr(_pc, role_name, None)
                if role is not None:
                    rcs = get_recipients(role) or []
                    if rcs:
                        return rcs
            except Exception:
                continue
        return []
    except Exception as e:  # noqa: BLE001
        emit(f"  [提示] 读取项目组收件人失败：{e}")
        return []


def _send_customer_feedback_email(
    ctx: SkillContext,
    feedback_rows: list[dict],
    emit: Emit,
) -> dict:
    """组「客户反馈待确认」邮件并发送（默认 dry-run）。返回发送结果摘要。"""
    from agent.mailer import send_mail

    # 项目信息（从 project_info.json 取，缺则用占位）
    info: dict = {}
    info_path = ctx.runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except Exception:
            info = {}
    project_name = info.get("项目名称", "") or "未知项目"
    room_name = info.get("机房名称", "") or ""
    survey_date = info.get("勘察日期", "") or info.get("勘测日期", "")

    recipients = _resolve_project_recipients(ctx, emit)
    to = [r.get("email", "") for r in recipients if r.get("email")]

    subject = f"[工勘-客户反馈] {project_name} {room_name} - 待确认勘测项".strip()
    lines = [
        f"项目: {project_name}",
        f"机房: {room_name}",
        f"日期: {survey_date}",
        "",
        f"以下 {len(feedback_rows)} 项需要项目组确认反馈：",
        "",
    ]
    for i, row in enumerate(feedback_rows, 1):
        lines.append(
            f"{i}. [{row.get('勘测要素', '')}] "
            f"{row.get('项目', '')} - {row.get('检查内容', '')}"
        )
    lines += ["", "请在全量勘测结果表中填写检查结果后回传。"]
    body = "\n".join(lines)

    if not to:
        emit("  [跳过] 未解析到项目组收件人，客户反馈邮件未发送（审批包/条目仍就绪）")
        return {"emailed": False, "recipients": 0, "reason": "no_recipients"}

    res = send_mail(to, subject, body)  # dry_run 默认由 AIDA_SEND_EMAIL 控制
    if res.get("dry_run"):
        emit(f"  [dry-run] 客户反馈邮件未真发（设 AIDA_SEND_EMAIL=1 启用）→ {len(to)} 收件人")
    elif res.get("ok"):
        emit(f"  ✓ 客户反馈邮件已发送 → {len(to)} 收件人（via {res.get('via')}）")
    else:
        emit(f"  [警告] 客户反馈邮件发送失败：{res.get('error')}")
    return {"emailed": bool(res.get("ok") and not res.get("dry_run")), "recipients": len(to), "dry_run": bool(res.get("dry_run"))}


def _get_survey_table(ctx: SkillContext) -> str | None:
    """找到全量勘测结果表：优先 project_info.json，退而 glob"""
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


class MethodSplitStep(BaseStep):
    key = "method_split"
    name = "勘测方法分流"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}
        if _get_survey_table(ctx) is None:
            return {"ok": False, "missing": ["ProjectData/Output/*全量勘测结果表*.xlsx"]}
        return {"ok": True, "missing": []}

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        from ..services.survey_table_builder import read_survey_table

        survey_table_path = _get_survey_table(ctx)
        if not survey_table_path:
            raise RuntimeError("method_split: 全量勘测结果表不存在")

        emit(f"[method_split] 读取: {os.path.basename(survey_table_path)}")
        rows = read_survey_table(survey_table_path)

        groups: dict[str, int] = defaultdict(int)
        feedback_rows: list[dict] = []
        for row in rows:
            method = row.get("勘测方法") or "未知"
            groups[method] += 1
            if method == "客户反馈":
                feedback_rows.append(row)

        total = len(rows)
        emit(f"[method_split] 总条目: {total}")
        for method, count in sorted(groups.items()):
            emit(f"[method_split]   {method}: {count} 条")

        # v4：客户反馈条目自动发邮件给项目组（默认 dry-run）
        fb_result: dict = {"emailed": False, "recipients": 0}
        if feedback_rows:
            emit(f"[method_split] 客户反馈条目 {len(feedback_rows)} 条 → 通知项目组")
            fb_result = _send_customer_feedback_email(ctx, feedback_rows, emit)

        # 写统计到 project_info.json
        info_path = ctx.runtime_dir / "project_info.json"
        try:
            existing = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
        except Exception:
            existing = {}
        existing["method_groups"] = dict(groups)
        existing["total_items"] = total
        ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
        info_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

        emit(f"[method_split] ✓ 分流完成，{len(groups)} 种勘测方法")

        return {
            "metrics": {
                "total_items": total,
                "method_groups": dict(groups),
                "customer_feedback_count": len(feedback_rows),
                "customer_feedback_emailed": fb_result.get("emailed", False),
                "customer_feedback_recipients": fb_result.get("recipients", 0),
            }
        }
