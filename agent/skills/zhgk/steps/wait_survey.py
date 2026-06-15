"""
wait_survey · 等待现场勘测结果上传

意图: survey_work 专属

HITL FilePicker：等待勘测工程师填写全量勘测结果表并上传。
  - check_inputs: 检查主表是否已有勘测结果，或 Input/ 是否有新上传的填写表
  - run: 读取上传的填写表 → write_survey_results(round=N) → 删除上传文件

多轮复勘支持：
  - 若 project["resurvey_decision"] == "resurvey"，跳过「已有结果」检测，
    按复勘方式等待 App 回传或本地上传（复勘第 N+1 轮）
  - 合并成功后清除复勘标记，确保下次进来走正常路径
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip

# 用户需要将填好的表格放到此路径
UPLOADED_FILENAME = "已填写_全量勘测结果表.xlsx"
RESULT_META_FILENAME = "gkclaw_result_meta.json"


def _now_local_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _build_survey_merge_metadata(
    result_meta: dict,
    round_num: int,
    *,
    fallback_time: str | None = None,
) -> dict[str, str]:
    source_type = "video" if result_meta.get("source") == "mailgw" else "manual"
    source_label = f"第{round_num}次视频工勘" if source_type == "video" else f"第{round_num}次手动上传"
    survey_time = (
        str(result_meta.get("completed_at") or result_meta.get("submitted_at")
            or result_meta.get("updated_at") or result_meta.get("created_at") or "").strip()
        or fallback_time
        or _now_local_text()
    )
    return {
        "survey_result_source": source_label,
        "survey_result_time": survey_time,
        "survey_result_source_type": source_type,
    }


def _build_app_wait_label(task_id: str) -> str:
    tid = str(task_id or "").strip() or "未获取"
    return (
        "等待现场APP勘测回传\n"
        f"task_id:{tid}\n"
        "回传后自动更新进度，也可手动检测刷新"
    )


def _build_app_wait_note(task_id: str, *parts: str) -> str:
    tid = str(task_id or "").strip() or "未获取"
    return _join_notes(
        f"等待现场 App 回传：暂未检测到回传结果（task_id:{tid}）",
        *parts,
    )


def _join_notes(*parts: str) -> str:
    return "\n".join(str(part).strip() for part in parts if str(part or "").strip())


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


def _find_uploaded_table(ctx: SkillContext) -> str | None:
    """在 Input/ 查找用户上传的已填写表"""
    if ctx.input_dir.exists():
        # 精确名匹配
        exact = ctx.input_dir / UPLOADED_FILENAME
        if exact.exists():
            return str(exact)
        # 模糊匹配（含"全量勘测结果表"且不是 BOQ）
        for p in sorted(ctx.input_dir.glob("*全量勘测结果表*.xlsx")):
            if "boq" not in p.name.lower():
                return str(p)
        # 用户不应被文件名约束：只要是 schema 正确的结果表即可
        for p in sorted(ctx.input_dir.glob("*.xlsx")):
            if "boq" in p.name.lower():
                continue
            if not _validate_uploaded(str(p)):
                return str(p)
    return None


def _read_project_info(ctx: SkillContext) -> dict:
    info_path = ctx.runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            return json.loads(info_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _write_project_info(ctx: SkillContext, info: dict) -> None:
    ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
    (ctx.runtime_dir / "project_info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _read_result_meta(ctx: SkillContext) -> dict:
    meta_path = ctx.input_dir / RESULT_META_FILENAME
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _current_gkclaw_task_id(ctx: SkillContext) -> str:
    return str(_read_project_info(ctx).get(_gkclaw_task_info_key(ctx), "")).strip()


def _is_current_app_result(ctx: SkillContext, uploaded: str | None) -> bool:
    if not uploaded:
        return False
    if Path(uploaded).name != UPLOADED_FILENAME:
        return False
    meta = _read_result_meta(ctx)
    return bool(meta.get("source") == "mailgw" and meta.get("task_id") == _current_gkclaw_task_id(ctx))


def _archive_stale_uploaded_table_for_app(ctx: SkillContext) -> str:
    """App 复勘只消费当前 task 的 mailgw 回传；旧本地表归档并给用户提示。"""
    uploaded = _find_uploaded_table(ctx)
    if not uploaded or _is_current_app_result(ctx, uploaded):
        return ""
    src = Path(uploaded)
    archive_dir = ctx.runtime_dir / "gkclaw" / "ignored_uploads"
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / f"{src.stem}-{time.strftime('%Y%m%d%H%M%S')}{src.suffix}"
    try:
        shutil.move(str(src), str(dest))
    except Exception:
        return f"检测到历史上传表 {src.name}，它不是当前 App 复勘任务的回传结果，已忽略。"
    meta_path = ctx.input_dir / RESULT_META_FILENAME
    if meta_path.exists():
        try:
            shutil.move(str(meta_path), str(dest.with_suffix(dest.suffix + ".meta.json")))
        except Exception:
            pass
    return f"检测到历史上传表 {src.name}，它不是当前 App 复勘任务的回传结果，已归档并忽略。"


def _uploaded_result_status(path: str) -> tuple[str, str, int, int]:
    """返回 (status, note, filled_count, row_count)。status=ready/empty/invalid。"""
    schema_err = _validate_uploaded(path)
    if schema_err:
        return "invalid", f"上传表格式不符：{schema_err}", 0, 0
    try:
        from ..services.survey_table_builder import read_survey_table
        rows = read_survey_table(path)
    except Exception as e:  # noqa: BLE001
        return "invalid", f"无法读取上传表：{e}", 0, 0
    filled = sum(1 for row in rows if str(row.get("最新检查结果", "")).strip())
    if filled <= 0:
        return (
            "empty",
            f"已读取到结果表 {Path(path).name}，但「最新检查结果」列为空，无法进入 AI 评估。"
            "请填写至少一条检查结果后重新上传。",
            0,
            len(rows),
        )
    return "ready", "", filled, len(rows)


def _validate_uploaded(path: str) -> str:
    """校验上传表 schema：必须含「序号」「最新检查结果」列头。
    返回空串=通过；否则返回中文错误原因（供清晰报错，防传错文件静默）。"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        headers = {str(ws.cell(1, c).value or "").strip()
                   for c in range(1, ws.max_column + 1)}
        wb.close()
    except Exception as e:
        return f"无法读取（{e}）——请确认是有效的 .xlsx"
    missing = [c for c in ("序号", "最新检查结果") if c not in headers]
    if missing:
        return f"缺少必需列：{'、'.join(missing)}——请下载 Output/ 的全量勘测结果表填写后再传，勿改表头"
    return ""


def _has_survey_results(survey_table_path: str) -> bool:
    """检查主表中是否已有非空的「最新检查结果」（即已合并过某轮结果）"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(survey_table_path, read_only=True, data_only=True)
        ws = wb.active
        headers = [str(ws.cell(1, c).value or "").strip() for c in range(1, ws.max_column + 1)]
        try:
            res_col = headers.index("最新检查结果") + 1
        except ValueError:
            wb.close()
            return False
        for row in ws.iter_rows(min_row=2, max_col=res_col, values_only=True):
            if row[-1] is not None and str(row[-1]).strip():
                wb.close()
                return True
        wb.close()
    except Exception:
        pass
    return False


def _is_resurvey_app_mode(ctx: SkillContext) -> bool:
    return (
        ctx.project.get("resurvey_decision") == "resurvey"
        and ctx.project.get("resurvey_dispatch_decision") == "dispatch"
    )


def _is_initial_app_mode(ctx: SkillContext) -> bool:
    if ctx.project.get("resurvey_decision") == "resurvey":
        return False
    info = _read_project_info(ctx)
    task_id = str(info.get("gkclaw_task_id", "")).strip()
    if not task_id:
        return False
    try:
        from ..services.gkclaw.registry import TaskRegistry
        task = TaskRegistry(ctx.runtime_dir).get(task_id)
    except Exception:
        task = None
    if not task:
        return ctx.project.get("dispatch_decision") == "dispatch"
    if str(task.get("state", "")) == "completed":
        uploaded = _find_uploaded_table(ctx)
        if _is_current_app_result(ctx, uploaded):
            return True
        survey_table = _get_survey_table(ctx)
        if survey_table and _has_survey_results(survey_table):
            return False
    if ctx.project.get("dispatch_decision") == "dispatch":
        return True
    return str(task.get("state", "")) in {"dispatched", "accepted", "staged_returned"}


def _is_any_app_mode(ctx: SkillContext) -> bool:
    return _is_resurvey_app_mode(ctx) or _is_initial_app_mode(ctx)


def _gkclaw_task_info_key(ctx: SkillContext) -> str:
    return "resurvey_gkclaw_task_id" if _is_resurvey_app_mode(ctx) else "gkclaw_task_id"


class WaitSurveyStep(BaseStep):
    key = "wait_survey"
    name = "等待现场上传"
    artifacts_pattern = []

    def _gkclaw_status_note(self, ctx: SkillContext) -> str:
        """GKCLAW 链路钩子：有已下发任务时拉取邮件回传并返回状态行（异常不阻断流程）。

        dry-run 任务或 mailgw 未配置时只展示状态不拉取。拉取可由等待页手动刷新触发；
        若 mailgw 开启 pop3.poll_interval + agent_notify，收到回传邮件后也会通知本接口检查。
        """
        try:
            info_path = ctx.runtime_dir / "project_info.json"
            if not info_path.exists():
                return ""
            info = json.loads(info_path.read_text(encoding="utf-8"))
            tid = info.get(_gkclaw_task_info_key(ctx), "")
            if not tid:
                return ""
            from ..services.gkclaw.registry import TaskRegistry
            reg = TaskRegistry(ctx.runtime_dir)
            task = reg.get(tid)
            if task is None:
                return ""
            alerts: list[str] = []
            if not task.get("dry_run"):
                import agent.mailbox as mailbox
                if mailbox.is_configured() and task["state"] in (
                        "dispatched", "accepted", "staged_returned"):
                    from ..services.gkclaw.ingest import poll_and_ingest
                    summary = poll_and_ingest(
                        runtime_dir=ctx.runtime_dir, input_dir=ctx.input_dir,
                        survey_table_path=_get_survey_table(ctx))
                    alerts = list(summary.get("alerts", []))
                    task = reg.get(tid) or task
            bits = [f"GKCLAW 任务 {tid} · 状态 {task['state']}"]
            if task.get("dry_run"):
                bits.append("dry-run 未真发")
            if task.get("web_access_url"):
                bits.append(f"现场 Web 入口 {task['web_access_url']}")
            if task.get("merge_blocked"):
                bits.append(f"⚠ 合并阻塞：{task.get('merge_blocked_reason', '')}")
            return "；".join(bits) + ("；" + "；".join(alerts[-3:]) if alerts else "")
        except Exception as e:  # noqa: BLE001 — 邮件链路异常绝不阻断人工上传通道
            return f"[gkclaw] 拉取回传失败：{e}"

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        resurvey_pending = ctx.project.get("resurvey_decision") == "resurvey"
        app_stale_note = ""
        if _is_any_app_mode(ctx):
            app_stale_note = _archive_stale_uploaded_table_for_app(ctx)

        gk_note = self._gkclaw_status_note(ctx)
        survey_table = _get_survey_table(ctx)

        if resurvey_pending:
            # 复勘模式：忽略「已有结果」检测，必须有本轮回传/上传文件
            if _is_resurvey_app_mode(ctx):
                uploaded = _find_uploaded_table(ctx)
                if uploaded and _is_current_app_result(ctx, uploaded):
                    status, note, _filled, _rows = _uploaded_result_status(uploaded)
                    if status == "ready":
                        return {"ok": True, "missing": []}
                    return {
                        "ok": False,
                        "missing": [],
                        "need_inputs": [],
                        "note": note + (f"\n{gk_note}" if gk_note else ""),
                    }
                current_tid = _current_gkclaw_task_id(ctx)
                return {
                    "ok": False,
                    "missing": [],
                    "need_inputs": [{
                        "id": "resurvey_wait_result",
                        "label": _build_app_wait_label(current_tid),
                        "repeatable": True,
                        "options": [
                            {
                                "label": "刷新检查回传",
                                "value": "refresh",
                                "description": "重新拉取 mailgw/GKCLAW 回传，若已到达将自动合并",
                            },
                        ],
                    }],
                    "note": _build_app_wait_note(current_tid, app_stale_note, gk_note),
                    "hide_reason": True,
                }
            uploaded = _find_uploaded_table(ctx)
            if uploaded is not None:
                status, note, _filled, _rows = _uploaded_result_status(uploaded)
                if status == "ready":
                    return {"ok": True, "missing": []}
                return {
                    "ok": False,
                    "missing": ["ProjectData/Input/复勘结果表（需填写「最新检查结果」）"],
                    "note": note + (f"\n{gk_note}" if gk_note else ""),
                }
            base_note = (
                "请上传本轮复勘后的全量勘测结果表，并填写「最新检查结果」列。"
            )
            return {
                "ok": False,
                "missing": ["ProjectData/Input/复勘结果表（需填写「最新检查结果」）"],
                "note": base_note + (f"\n{gk_note}" if gk_note else ""),
            }

        # 首轮 App 下发：必须等待当前 task_id 的 mailgw 回传，不能复用主表历史结果。
        if _is_initial_app_mode(ctx):
            uploaded = _find_uploaded_table(ctx)
            if uploaded and _is_current_app_result(ctx, uploaded):
                status, note, _filled, _rows = _uploaded_result_status(uploaded)
                if status == "ready":
                    return {"ok": True, "missing": []}
                return {
                    "ok": False,
                    "missing": [],
                    "need_inputs": [],
                    "note": note + (f"\n{gk_note}" if gk_note else ""),
                }
            current_tid = _current_gkclaw_task_id(ctx)
            return {
                "ok": False,
                "missing": [],
                "need_inputs": [{
                    "id": "survey_wait_result",
                    "label": _build_app_wait_label(current_tid),
                    "repeatable": True,
                    "options": [
                        {
                            "label": "刷新检查回传",
                            "value": "refresh",
                            "description": "重新拉取 mailgw/GKCLAW 回传，若已到达将自动合并",
                        },
                    ],
                }],
                "note": _build_app_wait_note(current_tid, app_stale_note, gk_note),
                "hide_reason": True,
            }

        # 正常流程（本地人工上传 / 历史续跑）
        if survey_table and _has_survey_results(survey_table):
            return {"ok": True, "missing": []}

        uploaded = _find_uploaded_table(ctx)
        if uploaded is not None:
            status, note, _filled, _rows = _uploaded_result_status(uploaded)
            if status == "ready":
                return {"ok": True, "missing": []}
            return {
                "ok": False,
                "missing": ["ProjectData/Input/勘测结果表（需填写「最新检查结果」）"],
                "note": note + (f"\n{gk_note}" if gk_note else ""),
            }

        base_note = (
            "请从 Output/ 下载全量勘测结果表，完成现场勘测后填写「最新检查结果」列，"
            "再上传到 ProjectData/Input/"
        )
        return {
            "ok": False,
            "missing": ["ProjectData/Input/勘测结果表（需填写「最新检查结果」）"],
            "note": base_note + (f"\n{gk_note}" if gk_note else ""),
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        from ..services.survey_table_builder import read_survey_table
        from ..services.resurvey_manager import get_current_round, write_survey_results

        survey_table = _get_survey_table(ctx)
        if not survey_table:
            raise RuntimeError("wait_survey: 全量勘测结果表不存在")

        resurvey_pending = ctx.project.get("resurvey_decision") == "resurvey"
        initial_app_pending = _is_initial_app_mode(ctx)

        # 非 App 链路且主表已有结果 → 无需重合并；App 链路必须等当前 task 回传。
        if not resurvey_pending and not initial_app_pending and _has_survey_results(survey_table):
            emit("[wait_survey] ✓ 勘测结果已就绪（跳过合并）")
            return {"metrics": {"survey_already_filled": True}}

        uploaded = _find_uploaded_table(ctx)
        if not uploaded:
            raise RuntimeError(
                f"wait_survey: 未找到上传的勘测结果表（期望: Input/{UPLOADED_FILENAME}）"
            )

        if _is_any_app_mode(ctx) and not _is_current_app_result(ctx, uploaded):
            current_tid = _current_gkclaw_task_id(ctx)
            reason = (
                f"检测到历史上传表 {os.path.basename(uploaded)}，它不是当前 App 任务"
                f"（{current_tid}）的回传结果，已忽略。请等待现场 App 回传当前任务。"
            )
            emit(f"[wait_survey] ⚠ {reason}")
            return {
                "hitl": {
                    "step": self.key,
                    "reason": reason,
                    "need_files": [],
                    "need_inputs": [],
                },
                "metrics": {"stale_uploaded_table_ignored": True},
            }

        emit(f"[wait_survey] 读取已填写表: {os.path.basename(uploaded)}")

        # #6 schema 校验：传错文件当场清晰报错，不静默
        schema_err = _validate_uploaded(uploaded)
        if schema_err:
            raise RuntimeError(f"上传表格式不符：{schema_err}")

        filled_rows = read_survey_table(uploaded)
        results: dict[int, str] = {
            row["序号"]: row["最新检查结果"]
            for row in filled_rows
            if row.get("最新检查结果", "").strip()
        }

        if not results:
            reason = (
                f"已读取到结果表 {os.path.basename(uploaded)}，共 {len(filled_rows)} 行，"
                "但「最新检查结果」列为空，无法进入 AI 评估。请填写至少一条检查结果后重新上传。"
            )
            emit(f"[wait_survey] ⚠ {reason}")
            return {
                "hitl": {
                    "step": self.key,
                    "reason": reason,
                    "need_files": ["ProjectData/Input/勘测结果表（需填写「最新检查结果」）"],
                    "need_inputs": [],
                },
                "metrics": {"filled_count": 0, "uploaded_rows": len(filled_rows)},
            }

        round_num = get_current_round(survey_table)
        merge_meta = _build_survey_merge_metadata(
            _read_result_meta(ctx),
            round_num,
            fallback_time=_now_local_text(),
        )
        emit(f"[wait_survey] 合并第 {round_num} 轮勘测结果：{len(results)} 条")
        stat = write_survey_results(
            survey_table,
            results,
            round_num,
            source_label=merge_meta["survey_result_source"],
            survey_time=merge_meta["survey_result_time"],
        )
        merged = stat.get("matched", len(results))
        skipped = stat.get("skipped", 0)
        emit(f"[wait_survey] ✓ 结果已合并（第{round_num}轮，匹配 {merged}/{len(filled_rows)} 行）"
             + (f"；⚠ {skipped} 行序号未对上、已跳过" if skipped else ""))

        # 删除上传的临时文件，为下一轮复勘准备
        try:
            os.remove(uploaded)
            emit(f"[wait_survey] 已清理上传临时文件: {os.path.basename(uploaded)}")
        except Exception:
            pass
        meta_path = ctx.input_dir / RESULT_META_FILENAME
        if meta_path.exists():
            try:
                os.remove(meta_path)
            except Exception:
                pass

        # 多轮复勘历史：累积每轮汇总（SDUI 轮次对比 Table）。
        # metrics 扁平 merge 是 last-write-wins，故读旧历史→去重当前轮→追加→整列回写。
        history = list((state.get("metrics") or {}).get("survey_round_history") or [])
        history = [h for h in history if h.get("round") != round_num]
        history.append({
            "round": round_num,
            "filled": merged,
            "total": len(filled_rows),
            "source": merge_meta["survey_result_source"],
            "source_type": merge_meta["survey_result_source_type"],
            "time": merge_meta["survey_result_time"],
        })
        history.sort(key=lambda h: h.get("round", 0))

        project_diff = {
            **ctx.project,
            "resurvey_decision": "",
            "resurvey_dispatch_decision": "",
        } if resurvey_pending else ctx.project
        if initial_app_pending and not resurvey_pending:
            project_diff = {
                **ctx.project,
                "dispatch_decision": "",
                "gkclaw_initial_merged_task_id": _current_gkclaw_task_id(ctx),
                "gkclaw_initial_merged_at": merge_meta["survey_result_time"],
            }

        if resurvey_pending:
            info = _read_project_info(ctx)
            tid = str(info.get(_gkclaw_task_info_key(ctx), "")).strip()
            if tid:
                gk_history = list(info.get("resurvey_gkclaw_task_history") or [])
                seen = False
                for item in gk_history:
                    if item.get("task_id") == tid:
                        item["state"] = "merged"
                        item["merged_round"] = round_num
                        item["merged_at"] = merge_meta["survey_result_time"]
                        item["source"] = merge_meta["survey_result_source"]
                        seen = True
                        break
                if not seen:
                    gk_history.append({
                        "round": round_num,
                        "task_id": tid,
                        "state": "merged",
                        "merged_at": merge_meta["survey_result_time"],
                        "source": merge_meta["survey_result_source"],
                    })
                info["resurvey_gkclaw_task_history"] = gk_history
            info.pop("resurvey_gkclaw_task_id", None)
            info.pop("resurvey_mode", None)
            info.pop("resurvey_round", None)
            _write_project_info(ctx, info)

        return {
            "metrics": {
                "survey_round": round_num,
                "filled_count": merged,
                "uploaded_rows": len(filled_rows),
                "survey_matched": merged,
                "survey_skipped": skipped,
                "survey_skipped_seqs": stat.get("skipped_seqs", []),
                "survey_round_history": history,
                **merge_meta,
            },
            "project": project_diff,
        }
