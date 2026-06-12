"""
gkclaw dispatch · 任务下发服务（建包 → 经 mailer 发送 → 状态登记）

发送唯一出口 = agent.mailer.send_mail（lint_no_naked_send 铁律）；send_fn 仅供测试注入。
dry-run（AIDA_SEND_EMAIL≠1 或显式 dry_run=True）：照常建包+登记，标 dry_run，不发邮件。
重发语义（契约无撤销包类型）：内容变更重发 = 新 task_id；previous_task_id 标 superseded。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from . import ids, mapping, package, schema
from .registry import TaskRegistry


def dispatch_task(
    *,
    runtime_dir: Path | str,
    survey_table_path: str,
    project: dict[str, Any],
    assignees: list[dict[str, str]],
    dry_run: bool | None = None,
    send_fn: Callable[..., dict] | None = None,
    frontagent_mailbox: str | None = None,
    generation_cooling: str = "",
    survey_round: int = 1,
    previous_task_id: str = "",
    aida_run_id: str = "",
    aida_skill_id: str = "zhgk",
    aida_resume_step: str = "wait_survey",
) -> dict[str, Any]:
    """下发一个 GKCLAW 任务。返回 {task_id, state, dry_run, zip_path, items_count, send_result}。

    校验失败抛 ValueError；发送失败任务标 failed 并抛 RuntimeError（step 层据此呈现/重试）。
    """
    from ..survey_table_builder import read_survey_table

    rows = read_survey_table(survey_table_path)

    # 底表回连（背景知识 enrich）：失败不阻断，join 不到=空备注
    base_items: list[dict] = []
    try:
        from ..table_filter import load_base_table
        from ...path_config import get_base_table_path
        base_items = load_base_table(get_base_table_path())
    except Exception:  # noqa: BLE001
        base_items = []

    reg = TaskRegistry(runtime_dir)
    task_id = ids.new_task_id(str(project.get("project_code", "")), reg.root)
    payload = mapping.build_task_payload(
        task_id=task_id, rows=rows, base_items=base_items,
        project=project, assignees=assignees,
        survey_round=survey_round, generation_cooling=generation_cooling,
    )
    errors = schema.validate_task(payload)
    if errors:
        raise ValueError("task.json 契约校验失败: " + "；".join(errors))

    if dry_run is None:
        dry_run = os.environ.get("AIDA_SEND_EMAIL", "0").strip() != "1"

    package_id = ids.new_package_id()
    out_dir = reg.root / task_id / "outbox"
    zip_path = package.build_package(
        package_type="task.dispatch", task_id=task_id,
        project=payload["project"], payload=payload,
        out_dir=out_dir, package_id=package_id,
    )
    fingerprint = package.sha256_file(survey_table_path)
    reg.create_task(
        task_id=task_id, task_payload=payload,
        zip_path=f"outbox/{zip_path.name}",
        table_fingerprint=fingerprint, project=payload["project"], dry_run=dry_run,
        aida_run_id=str(aida_run_id or ""),
        aida_skill_id=str(aida_skill_id or "zhgk"),
        aida_resume_step=str(aida_resume_step or "wait_survey"),
    )
    reg.record_package(task_id, {
        "package_id": package_id, "checksum": package.sha256_file(zip_path),
        "package_type": "task.dispatch", "direction": "out", "disposition": "processed",
    })
    if previous_task_id and previous_task_id != task_id:
        reg.mark_superseded(previous_task_id)

    project_code = payload["project"]["project_code"]
    send_result: dict[str, Any] = {}
    if dry_run:
        reg.set_state(task_id, "dispatched", mailgw_status="dry_run")
        send_result = {"ok": True, "dry_run": True,
                       "note": "dry-run：任务包已生成未发送（设 AIDA_SEND_EMAIL=1 才发）"}
    else:
        to = (frontagent_mailbox or os.environ.get("GKCLAW_FRONTAGENT_MAILBOX", "")).strip()
        if not to:
            reg.set_state(task_id, "failed", last_error="GKCLAW_FRONTAGENT_MAILBOX 未配置")
            raise RuntimeError("GKCLAW_FRONTAGENT_MAILBOX 未配置（frontagent 收件邮箱）")
        if send_fn is None:
            from agent.mailer import send_mail as send_fn  # type: ignore[no-redef]
        subject = f"[GKCLAW][TASK_DISPATCH] {project_code}/{task_id}"
        body = (f"GKCLAW 任务下发：{payload['task_name']}\n"
                f"task_id: {task_id}\n项目: {project_code}\n"
                f"权威数据见附件 ZIP（manifest.json / task.json）。")
        send_result = send_fn([to], subject, body, attachments=[str(zip_path)], dry_run=False)
        if not send_result.get("ok"):
            err = str(send_result.get("error", send_result))
            reg.set_state(task_id, "failed", last_error=err)
            raise RuntimeError(f"任务包发送失败: {err}")
        reg.set_state(
            task_id, "dispatched",
            mailgw_task_id=str(send_result.get("mailgw_task_id", "")),
            mailgw_status=str(send_result.get("mailgw_status", "")),
        )

    return {"task_id": task_id, "state": "dispatched", "dry_run": bool(dry_run),
            "zip_path": str(zip_path), "items_count": len(payload["items"]),
            "send_result": send_result}
