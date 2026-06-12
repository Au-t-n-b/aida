from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from deploy_chain import load_chain, merge_chain
from toolkit_executor import (
    emit_hitl_executor_configure,
    load_executor_config,
    parse_executor_from_hitl,
    save_executor_config,
)
from guidance_actions import sd_download_action, sd_runtime_action, sync_skill_dashboard
from paths import load_plan_runtime_step
from reset_workspace import reset_workspace
from resume_router import (
    build_connection_check_start_payload,
    build_entry_guidance_payload,
    build_reset_done_actions,
    build_toolkit_executor_done_payload,
    build_toolkit_import_done_payload,
    build_toolkit_import_start_payload,
    format_toolkit_import_detail,
    recommended_next_action,
)
from subskill_runner import run_subskill


def _now_ms() -> int:
    return int(time.time() * 1000)


def _emit(evt: dict[str, Any]) -> None:
    line = (json.dumps(evt, ensure_ascii=False) + "\n").encode("utf-8", errors="replace")
    sys.stdout.buffer.write(line)
    sys.stdout.buffer.flush()


_MODULE_CHAIN_FIELD = {
    "init_install": "step9_init_install_at",
    "subsystem_test": "step10_subsystem_test_at",
    "cluster_test": "step11_cluster_test_at",
}
_MODULE_STEP_NO = {"init_install": 9, "subsystem_test": 10, "cluster_test": 11}


def _run_commission_command(
    skill_root: Path,
    *,
    thread_id: str,
    skill_name: str,
    run_id: str,
    command: str,
    scope: str = "all",
    pod_ids: list[int] | None = None,
    devices: list[str] | None = None,
    task_no: str = "",
    only_installed: bool = True,
) -> int:
    """下发调测统一入口：任意命令 → task_runner 执行 → 写模块进度 → 回执卡片。"""
    from sd_script_import import import_sd_script  # noqa: WPS433
    from step_ui import step_done_banner  # noqa: WPS433

    runner = import_sd_script(skill_root, "9_commission/shared/task_runner", "task_runner")
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                "context": f"已开始执行 **{command}**：解析设备范围 → 下发任务 → 轮询 → 导出报告。\n\n（完成后会生成可下载的 report.zip，并写入结果区）",
                "cardId": "sd:commission_running",
                "actions": [],
            },
        }
    )
    res = runner.run_command(
        str(skill_root),
        command,
        scope=scope,
        pod_ids=pod_ids or [],
        devices=devices or [],
        task_no=task_no,
        only_installed=only_installed,
    )
    if not res.ok:
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": f"下发调测失败：{res.message}",
                    "cardId": "sd:commission_error",
                    "actions": [sd_runtime_action(label="查看工作台", action="sd_start")],
                },
            }
        )
        return 0

    module = str((res.detail or {}).get("module") or "init_install")
    field = _MODULE_CHAIN_FIELD.get(module)
    step_n = _MODULE_STEP_NO.get(module, 9)
    if field:
        merge_chain(skill_root, **{field: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    done_actions: list[dict[str, Any]] = []
    result_dir = Path(str((res.detail or {}).get("resultDir") or ""))
    report_zip = result_dir / "report.zip"
    if report_zip.is_file():
        rel_rpt = _ws_path(report_zip, skill_root)
        if rel_rpt:
            done_actions.append(
                sd_download_action(label="下载本次 report.zip", path=rel_rpt, filename="report.zip")
            )
    done_actions.append(sd_runtime_action(label="生成调测报告汇总", action="report_aggregate"))
    done_actions.append(sd_runtime_action(label="查看工作台", action="sd_start"))
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                "context": step_done_banner(step_n, detail=res.message),
                "cardId": "sd:commission_done",
                "actions": done_actions,
            },
        }
    )
    sync_skill_dashboard(
        skill_root=skill_root,
        thread_id=thread_id,
        skill_name=skill_name,
        run_id=run_id,
        timestamp_ms=_now_ms(),
    )
    return 0


def _ws_path(path: Path, skill_root: Path) -> str:
    """绝对路径 → `workspace/skills/...` 相对路径（供 /api/download）。"""
    ws_root = skill_root.resolve().parent.parent
    try:
        rel = path.resolve().relative_to(ws_root)
    except ValueError:
        return ""
    return f"workspace/{rel.as_posix()}"


def _download_checklist(
    skill_root: Path, *, thread_id: str, skill_name: str, run_id: str
) -> int:
    """下载测试底表：返回回写后重导的宽表「全量设备完工清单列表_latest.xlsx」。"""
    xlsx = skill_root / "ProjectData" / "plan" / "Output" / "全量设备完工清单列表_latest.xlsx"
    if not xlsx.is_file():
        _emit({
            "event": "chat.guidance", "threadId": thread_id, "skillName": skill_name,
            "skillRunId": run_id, "timestamp": _now_ms(),
            "payload": {
                "context": "暂无测试底表：请先完成步骤 3（下发底表）。每次调测完成会自动回写并重导此表。",
                "cardId": "sd:checklist_missing",
            },
        })
        return 0
    rel = _ws_path(xlsx, skill_root)
    _emit({
        "event": "chat.guidance", "threadId": thread_id, "skillName": skill_name,
        "skillRunId": run_id, "timestamp": _now_ms(),
        "payload": {
            "context": (
                "📋 **测试底表**（含每台设备各三级活动的最新状态，调测后自动回写）\n\n"
                f"- 文件：`{xlsx.name}`\n- 下载：`/api/download?path={rel}`"
            ),
            "cardId": "sd:checklist_download",
            "actions": [sd_download_action(label="下载测试底表", path=rel, filename=xlsx.name)],
        },
    })
    return 0


def _report_aggregate(
    skill_root: Path, *, thread_id: str, skill_name: str, run_id: str
) -> int:
    """生成调测报告汇总 xlsx（全部命令，测过有内容、未测留空）。"""
    from sd_script_import import import_sd_script  # noqa: WPS433

    agg = import_sd_script(skill_root, "9_commission/shared", "report_aggregate")
    try:
        res = agg.build_aggregate(str(skill_root))
    except Exception as e:  # noqa: BLE001
        _emit({
            "event": "chat.guidance", "threadId": thread_id, "skillName": skill_name,
            "skillRunId": run_id, "timestamp": _now_ms(),
            "payload": {"context": f"生成报告汇总失败：{e}", "cardId": "sd:report_aggregate_error"},
        })
        return 0
    rel = _ws_path(Path(res["latestPath"]), skill_root)
    _emit({
        "event": "chat.guidance", "threadId": thread_id, "skillName": skill_name,
        "skillRunId": run_id, "timestamp": _now_ms(),
        "payload": {
            "context": (
                "📊 **调测报告汇总**已生成\n\n"
                f"- 命令总数：**{res['totalCommands']}** ｜ 已测：**{res['testedCommands']}** ｜ 未测：**{res['untestedCommands']}**\n"
                f"- 明细页：{res['detailSheets']} 个（每个已测命令一页，设备 × 结果）\n"
                f"- 文件：`{res['latestName']}`（含「调测总览」+ 各命令明细）\n"
                f"- 下载：`/api/download?path={rel}`\n\n"
                "_未测命令在总览中标「未测试」、内容留空。_"
            ),
            "cardId": "sd:report_aggregate_done",
            "actions": [sd_download_action(label="下载报告汇总", path=rel, filename=res["latestName"])],
        },
    })
    sync_skill_dashboard(
        skill_root=skill_root,
        thread_id=thread_id,
        skill_name=skill_name,
        run_id=run_id,
        timestamp_ms=_now_ms(),
    )
    return 0


def _parse_scope_params(req: dict[str, Any]) -> dict[str, Any]:
    pod_ids_raw = req.get("pod_ids") or req.get("podIds") or []
    try:
        pod_ids = [int(p) for p in pod_ids_raw if str(p).strip() != ""]
    except (TypeError, ValueError):
        pod_ids = []
    devices_raw = req.get("devices") or req.get("deviceList") or []
    devices = [str(d).strip() for d in devices_raw if str(d).strip()] if isinstance(devices_raw, list) else []
    only_installed = req.get("only_installed")
    only_installed = True if only_installed is None else bool(only_installed)
    return {
        "scope": str(req.get("scope") or "all"),
        "pod_ids": pod_ids,
        "devices": devices,
        "task_no": str(req.get("task_no") or req.get("taskNo") or ""),
        "only_installed": only_installed,
    }


def _parse_action(raw: str) -> tuple[str | None, str]:
    action = str(raw or "").strip()
    if action in {"sd_reset", "reset", "reset_demo", "clear_progress"}:
        return "reset", "run"
    if action in {"sd_continue", "continue_next"}:
        return "continue", "run"
    if action in {"sd_start", "sd_resume", "start", "cold_start", "resume"}:
        return "entry", "start"
    if action in {"upstream_check", "check_upstream"}:
        return "upstream", "check"
    if action.startswith("cloudops_"):
        return "cloudops", action[9:]
    # 兼容旧入口：ZTP/参数材料现在归入步骤 6 的导入前材料检查。
    if action.startswith("ztp_") or action.startswith("params_"):
        return "cloudops", action
    if action in ("commission_run", "commission_invoke"):
        return "toolkit", "commission_run"
    if action in ("download_checklist", "checklist_download", "download_base_table"):
        return "toolkit", "download_checklist"
    if action in ("report_aggregate", "aggregate_report", "export_report_summary"):
        return "toolkit", "report_aggregate"
    if action in ("connection_check_start", "connection_check_invoke"):
        return "toolkit", action
    if action in ("lq_connection_check", "lq_connection_check_invoke"):
        return "toolkit", "lq_connection_check"
    if action in ("toolkit_import_start", "toolkit_import_invoke"):
        return "toolkit", action[len("toolkit_") :]
    if action.startswith("toolkit_executor_"):
        return "toolkit", action[len("toolkit_executor_") :]
    if action.startswith("plan_"):
        return "plan", action[5:]
    if action in {"receive", "split", "dispatch", "regenerate"}:
        return "plan", action
    return None, action


def main() -> int:
    try:
        req = json.loads(sys.stdin.read() or "{}")
    except Exception:
        req = {}

    skill_root = Path.cwd().resolve()
    thread_id = str(req.get("thread_id") or "thread-unknown")
    skill_name = str(req.get("skill_name") or skill_root.name)
    request_id = str(req.get("request_id") or "req-sd")
    raw_action = str(req.get("action") or "sd_start")
    subskill, sub_action = _parse_action(raw_action)

    if not subskill:
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": f"{request_id}:{_now_ms()}",
                "timestamp": _now_ms(),
                "payload": {
                    "context": (
                        f"未识别 action={raw_action}。可用：sd_start、upstream_check、"
                        "plan_receive、plan_split、plan_dispatch、"
                        "cloudops_init_start、cloudops_supplement_start、cloudops_full_start、"
                        "cloudops_material_check、cloudops_ztp_upload_done、cloudops_params_upload_done、"
                        "toolkit_executor_configure、"
                        "toolkit_import_start、connection_check_start"
                    ),
                    "cardId": "sd:unknown",
                },
            }
        )
        return 0

    if subskill == "reset":
        scope = str(req.get("reset_scope") or req.get("scope") or "all").strip()
        from_step = req.get("from_step") or req.get("fromStep")
        try:
            fs = int(from_step) if from_step is not None else None
        except (TypeError, ValueError):
            fs = None
        result = reset_workspace(skill_root, scope=scope, from_step=fs)
        removed = result.get("removed") or []
        notes = result.get("notes") or []
        lines = [notes[0] if notes else "清理完成。"]
        if removed:
            lines.append("")
            lines.append("已删除产物：")
            for r in removed[:20]:
                lines.append(f"- {r}")
            if len(removed) > 20:
                lines.append(f"- …共 {len(removed)} 项")
        lines.append("")
        lines.append(
            "演示重置（仅 Skill 内联调）：`reset_scope` 或 `from_step` **1～6** 均可；"
            "默认保留 `ProjectData/input/*`，只清 state/chain/Output。"
        )
        lines.append("")
        lines.append(
            "点击下方 **继续** 将执行推荐步骤（与右侧大盘橙色「继续」相同）；"
            "「流程说明」仅查看十一步主线与当前进度，不会自动执行。"
        )
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": f"{request_id}:{_now_ms()}",
                "timestamp": _now_ms(),
                "payload": {
                    "context": "\n".join(lines),
                    "cardId": "sd:reset_done",
                    "actions": build_reset_done_actions(skill_root),
                },
            }
        )
        sync_skill_dashboard(
            skill_root=skill_root,
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=f"{request_id}:{_now_ms()}",
            timestamp_ms=_now_ms(),
        )
        return 0

    if subskill == "entry":
        run_id = f"{request_id}:{_now_ms()}"
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": build_entry_guidance_payload(skill_root),
            }
        )
        sync_skill_dashboard(
            skill_root=skill_root,
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            timestamp_ms=_now_ms(),
        )
        return 0

    if subskill == "continue":
        next_action = recommended_next_action(skill_root)
        if next_action in {"sd_start", "sd_resume"}:
            run_id = f"{request_id}:{_now_ms()}"
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": build_entry_guidance_payload(skill_root),
                }
            )
            sync_skill_dashboard(
                skill_root=skill_root,
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                timestamp_ms=_now_ms(),
            )
            return 0
        subskill, sub_action = _parse_action(next_action)
        if subskill in {None, "entry", "continue", "reset"}:
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": f"{request_id}:{_now_ms()}",
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": f"无法继续：未识别推荐动作 `{next_action}`。",
                        "cardId": "sd:continue_error",
                        "actions": [
                            sd_runtime_action(label="查看进度说明", action="sd_start"),
                        ],
                    },
                }
            )
            return 0

    if subskill == "toolkit":
        run_id = f"{request_id}:{_now_ms()}"
        result = req.get("result") if isinstance(req.get("result"), dict) else {}
        if sub_action in {"configure", "toolkit_executor_configure"}:
            emit_hitl_executor_configure(
                _emit,
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                request_id=request_id,
                existing=load_executor_config(skill_root),
            )
            return 0
        if sub_action in {"configured", "toolkit_executor_configured"}:
            if str(req.get("status") or "").strip().lower() == "cancel" or result.get("cancelled"):
                _emit(
                    {
                        "event": "chat.guidance",
                        "threadId": thread_id,
                        "skillName": skill_name,
                        "skillRunId": run_id,
                        "timestamp": _now_ms(),
                        "payload": {
                            "context": "已取消设置调测设备。需要时可再次打开表单填写调测 IP 与 SK。",
                            "cardId": "sd:toolkit_executor_cancelled",
                            "actions": [
                                sd_runtime_action(
                                    label="设置调测设备",
                                    action="toolkit_executor_configure",
                                ),
                            ],
                        },
                    }
                )
                return 0
            parsed = parse_executor_from_hitl(result)
            if not parsed.get("base_url_ip") or not parsed.get("secret_key"):
                _emit(
                    {
                        "event": "chat.guidance",
                        "threadId": thread_id,
                        "skillName": skill_name,
                        "skillRunId": run_id,
                        "timestamp": _now_ms(),
                        "payload": {
                            "context": "执行机配置无效：请填写 **调测IP** 与 **SK**（端口默认 28880）。",
                            "cardId": "sd:toolkit_executor_error",
                            "actions": [
                                sd_runtime_action(label="重新设置调测设备", action="toolkit_executor_configure"),
                            ],
                        },
                    }
                )
                return 0
            save_executor_config(
                skill_root,
                {
                    **parsed,
                    "gateway_service_ack": True,
                    "configured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
            merge_chain(skill_root, step7_executor_config_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            detail = (
                f"执行机 `{parsed['base_url_ip']}:{parsed['base_url_port']}` 已写入 toolkit_executor.json。"
            )
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": build_toolkit_executor_done_payload(
                        detail=detail,
                        skill_root=skill_root,
                    ),
                }
            )
            sync_skill_dashboard(
                skill_root=skill_root,
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                timestamp_ms=_now_ms(),
            )
            return 0

        if sub_action in {"import_start", "toolkit_import_start"}:
            from sd_script_import import import_sd_script  # noqa: WPS433
            from step_ui import step_gate_banner  # noqa: WPS433

            mod = import_sd_script(skill_root, "8_toolkit_import", "toolkit_import")
            chain = load_chain(skill_root)
            if str(chain.get("step8_toolkit_import_at") or "").strip():
                _emit(
                    {
                        "event": "chat.guidance",
                        "threadId": thread_id,
                        "skillName": skill_name,
                        "skillRunId": run_id,
                        "timestamp": _now_ms(),
                        "payload": build_toolkit_import_start_payload(
                            skill_root, already_done=True
                        ),
                    }
                )
                sync_skill_dashboard(
                    skill_root=skill_root,
                    thread_id=thread_id,
                    skill_name=skill_name,
                    run_id=run_id,
                    timestamp_ms=_now_ms(),
                )
                return 0

            ok, missing = mod.preflight_step8(str(skill_root))
            if not ok:
                body = "\n".join([f"- {m}" for m in missing]).strip()
                _emit(
                    {
                        "event": "chat.guidance",
                        "threadId": thread_id,
                        "skillName": skill_name,
                        "skillRunId": run_id,
                        "timestamp": _now_ms(),
                        "payload": {
                            "context": step_gate_banner(8, body=body),
                            "cardId": "sd:toolkit_import_preflight",
                            "actions": [
                                sd_runtime_action(label="回到步骤 6", action="cloudops_full_start"),
                                sd_runtime_action(label="回到步骤 7", action="toolkit_executor_configure"),
                            ],
                        },
                    }
                )
                return 0

            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": build_toolkit_import_start_payload(skill_root, already_done=False),
                }
            )
            sync_skill_dashboard(
                skill_root=skill_root,
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                timestamp_ms=_now_ms(),
            )
            return 0

        if sub_action in {"import_invoke", "toolkit_import_invoke"}:
            from sd_script_import import import_sd_script  # noqa: WPS433

            mod = import_sd_script(skill_root, "8_toolkit_import", "toolkit_import")
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": (
                            "⏳ **步骤 8 执行中 · 导入 CloudOps 到 Toolkit**\n\n"
                            "正在上传完整配置文件并刷新底表，大文件可能需要 1～3 分钟，请稍候…"
                        ),
                        "cardId": "sd:toolkit_import_running",
                        "actions": [],
                    },
                }
            )
            res = mod.run_step8_import_and_refresh(skill_dir=str(skill_root))
            if not res.ok:
                _emit(
                    {
                        "event": "chat.guidance",
                        "threadId": thread_id,
                        "skillName": skill_name,
                        "skillRunId": run_id,
                        "timestamp": _now_ms(),
                        "payload": {
                            "context": f"步骤 8 失败：{res.message}",
                            "cardId": "sd:toolkit_import_error",
                            "actions": [
                                sd_runtime_action(label="重新检查", action="toolkit_import_start"),
                            ],
                        },
                    }
                )
                return 0

            merge_chain(skill_root, step8_toolkit_import_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            detail = format_toolkit_import_detail(skill_root, message=res.message)
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": build_toolkit_import_done_payload(skill_root, detail=detail),
                }
            )
            sync_skill_dashboard(
                skill_root=skill_root,
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                timestamp_ms=_now_ms(),
            )
            return 0

        if sub_action == "connection_check_start":
            from sd_script_import import import_sd_script  # noqa: WPS433

            runner = import_sd_script(skill_root, "9_commission/shared/task_runner", "task_runner")
            chain = load_chain(skill_root)
            already = bool(str(chain.get("step9_init_install_at") or "").strip())
            if not already:
                ok, missing = runner.preflight_toolkit(str(skill_root))
                if not ok:
                    from step_ui import step_gate_banner  # noqa: WPS433

                    body = "\n".join([f"- {m}" for m in missing]).strip()
                    _emit(
                        {
                            "event": "chat.guidance",
                            "threadId": thread_id,
                            "skillName": skill_name,
                            "skillRunId": run_id,
                            "timestamp": _now_ms(),
                            "payload": {
                                "context": step_gate_banner(9, body=body, prev_done_step=8),
                                "cardId": "sd:connection_check_preflight",
                                "actions": [
                                    sd_runtime_action(label="回到步骤 8", action="toolkit_import_start"),
                                ],
                            },
                        }
                    )
                    return 0
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": build_connection_check_start_payload(skill_root, already_done=already),
                }
            )
            sync_skill_dashboard(
                skill_root=skill_root,
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                timestamp_ms=_now_ms(),
            )
            return 0

        if sub_action == "connection_check_invoke":
            return _run_commission_command(
                skill_root,
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                command="connection",
                scope="all",
            )

        if sub_action == "lq_connection_check":
            params = _parse_scope_params(req)
            return _run_commission_command(
                skill_root,
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                command="lq_connection",
                **params,
            )

        if sub_action == "commission_run":
            command = str(req.get("command") or req.get("task") or "").strip()
            if not command:
                _emit(
                    {
                        "event": "chat.guidance",
                        "threadId": thread_id,
                        "skillName": skill_name,
                        "skillRunId": run_id,
                        "timestamp": _now_ms(),
                        "payload": {
                            "context": "commission_run 缺少 `command`（命令名/别名，见 9_commission/shared/task_catalog）。",
                            "cardId": "sd:commission_no_command",
                        },
                    }
                )
                return 0
            params = _parse_scope_params(req)
            return _run_commission_command(
                skill_root,
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                command=command,
                **params,
            )

        if sub_action == "download_checklist":
            return _download_checklist(
                skill_root, thread_id=thread_id, skill_name=skill_name, run_id=run_id
            )

        if sub_action == "report_aggregate":
            return _report_aggregate(
                skill_root, thread_id=thread_id, skill_name=skill_name, run_id=run_id
            )

        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": f"未识别 toolkit action: {sub_action}",
                    "cardId": "sd:toolkit_unknown",
                    "actions": [
                        sd_runtime_action(label="设置调测设备", action="toolkit_executor_configure"),
                        sd_runtime_action(label="步骤 8：导入 Toolkit 配置", action="toolkit_import_start"),
                    ],
                },
            }
        )
        return 0

    try:
        events = run_subskill(subskill, sub_action, req, skill_root=skill_root)
    except Exception as e:
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": f"{request_id}:{_now_ms()}",
                "timestamp": _now_ms(),
                "payload": {"context": f"子流程 {subskill}/{sub_action} 失败：{e}", "cardId": "sd:error"},
            }
        )
        return 1

    for env in events:
        if isinstance(env, dict):
            env.setdefault("skillName", skill_name)
            _emit(env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
