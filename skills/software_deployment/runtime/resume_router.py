# -*- coding: utf-8 -*-
"""中途进入 /「继续」：与 deploy_chain 对齐的下一步推荐（driver 与 dashboard 共用）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deploy_chain import load_chain, sync_step3_from_state
from guidance_actions import sd_done_payload, sd_runtime_action
from paths import load_plan_runtime_step
from plan_chain import is_step3_done, migrate_chain_from_state
from step_ui import STEP_TITLES, TOTAL_STEPS, step_done_banner

_STEP_RUNTIME_ACTION: dict[int, str] = {
    1: "plan_receive",
    2: "plan_split",
    3: "plan_dispatch",
    4: "cloudops_init_start",
    5: "cloudops_supplement_start",
    6: "cloudops_full_start",
    7: "toolkit_executor_configure",
    8: "toolkit_import_start",
    9: "connection_check_start",
}

_ACTION_LABELS: dict[str, str] = {
    "plan_receive": "接收二级任务",
    "plan_receive_invoke": "确认接收二级任务",
    "plan_split": "拆分调测计划",
    "plan_split_invoke": "确认拆分调测计划",
    "plan_dispatch": "下发设备底表",
    "plan_dispatch_invoke": "确认下发设备底表",
    "plan_regenerate": "一键重算",
    "cloudops_init_start": "步骤 4：CloudOps 初配",
    "cloudops_init_invoke": "确认 CloudOps 初配",
    "cloudops_supplement_start": "步骤 5：补充配置",
    "cloudops_full_start": "步骤 6：完整配置",
    "cloudops_material_check": "步骤 6：检查 ZTP / 测试参数",
    "cloudops_ztp_upload_done": "上传 / 刷新 ZTP",
    "cloudops_params_upload_done": "上传 / 刷新测试参数",
    "toolkit_executor_configure": "步骤 7：设置调测设备",
    "toolkit_import_start": "步骤 8：导入 Toolkit",
    "toolkit_import_invoke": "确认执行步骤 8",
    "connection_check_start": "步骤 9：连线检查",
    "connection_check_invoke": "确认执行连线检查",
    "upstream_check": "检查材料",
    "sd_continue": "继续（执行推荐步骤）",
    "sd_start": "查看进度说明",
    "sd_resume": "查看进度说明",
}


def action_label(action: str) -> str:
    return _ACTION_LABELS.get(action, action)


def continue_button_label(action: str) -> str:
    """大盘 / 重置卡 / 引导卡共用的主按钮文案。"""
    if action in {"sd_start", "sd_resume", "sd_continue"}:
        return "继续"
    label = action_label(action)
    if action.endswith("_invoke"):
        return f"继续 · {label}"
    if label.startswith("步骤"):
        return f"继续 · {label}"
    return f"继续 · {label}"


def _has_deploy_progress(chain: dict[str, Any], plan_step: str) -> bool:
    if _chain_progress_started(chain):
        return True
    if any(
        str(chain.get(k) or "").strip()
        for k in (
            "step1_plan_receive_at",
            "step2_plan_split_at",
            "step3_plan_dispatch_at",
        )
    ):
        return True
    return str(plan_step or "").strip().lower() not in {"", "idle"}


def _materials_ready_for_step(skill_root: Path, step_index: int) -> bool:
    """当前步 input 是否已齐备（可进闸门卡，不要求 chain 已有进度）。"""
    checks: dict[int, Any] = {
        1: _can_invoke_plan_receive,
        2: _can_invoke_plan_split,
        3: _can_invoke_plan_dispatch,
        4: _can_invoke_cloudops_init,
    }
    fn = checks.get(step_index)
    return bool(fn(skill_root)) if fn else False


def _should_show_continue_entry(
    chain: dict[str, Any],
    plan_step: str,
    next_action: str,
    *,
    skill_root: Path | None = None,
) -> bool:
    """是否展示「可继续执行」入口（含重置后材料齐备、中途续做）。"""
    if _has_deploy_progress(chain, plan_step):
        return True
    if skill_root is not None:
        cur = _running_step_index(chain, plan_step)
        if _materials_ready_for_step(skill_root, cur):
            return True
    return bool(next_action.endswith("_invoke"))


def _chain_progress_started(chain: dict[str, Any]) -> bool:
    keys = (
        "step4_cloudops_init_at",
        "step5_cloudops_supplement_at",
        "step6_cloudops_full_at",
        "step7_executor_config_at",
        "step8_toolkit_import_at",
        "step9_init_install_at",
    )
    return any(str(chain.get(k) or "").strip() for k in keys)


def step_done_flags(chain: dict[str, Any], plan_step: str) -> list[bool]:
    """与 dashboard Stepper 共用：推断各步是否已完成（含 chain 缺字段时的回填推断）。"""
    step = str(plan_step or "idle").strip().lower()
    done = [False] * TOTAL_STEPS
    if chain.get("step1_plan_receive_at"):
        done[0] = True
    elif step not in {"", "idle"}:
        done[0] = True
    elif chain.get("step2_plan_split_at") or chain.get("step3_plan_dispatch_at"):
        done[0] = True
    if chain.get("step2_plan_split_at"):
        done[1] = True
    elif step in {"split", "dispatched", "dispatch"}:
        done[1] = True
    elif chain.get("step3_plan_dispatch_at"):
        done[1] = True
    if chain.get("step3_plan_dispatch_at"):
        done[2] = True
    elif step in {"dispatched", "dispatch"}:
        done[2] = True
    if chain.get("step4_cloudops_init_at"):
        done[3] = True
    if chain.get("step5_cloudops_supplement_at"):
        done[4] = True
    if chain.get("step6_cloudops_full_at"):
        done[5] = True
    if chain.get("step7_executor_config_at"):
        done[6] = True
    if chain.get("step8_toolkit_import_at"):
        done[7] = True
    if chain.get("step9_init_install_at"):
        done[8] = True
    if chain.get("step10_subsystem_test_at"):
        done[9] = True
    if chain.get("step11_cluster_test_at"):
        done[10] = True
    return done


def _running_step_index(chain: dict[str, Any], plan_step: str) -> int:
    """1-based 当前应聚焦的步骤号（与 dashboard stepper 一致）。"""
    for i, d in enumerate(step_done_flags(chain, plan_step)):
        if not d:
            return i + 1
    return TOTAL_STEPS


def _scene_pod_info(skill_root: Path) -> str:
    p = skill_root / "ProjectData/plan/RunTime/scene.json"
    if not p.is_file():
        return "single_pod"
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return str(raw.get("pod_info") or raw.get("podInfo") or "single_pod")
    except Exception:
        pass
    return "single_pod"


def _can_invoke_plan_receive(skill_root: Path) -> bool:
    from paths import resolve_slot

    slot = resolve_slot("second_level_tasks", skill_root=skill_root)
    return not bool(slot.get("missing"))


def _can_invoke_plan_split(skill_root: Path) -> bool:
    from paths import check_prerequisites, resolve_slot

    if not _can_invoke_plan_receive(skill_root):
        return False
    gate = check_prerequisites(for_actions=["plan_split"], skill_root=skill_root)
    if not gate.get("ok"):
        return False
    if resolve_slot("testcase", skill_root=skill_root).get("missing"):
        return False
    if _scene_pod_info(skill_root) == "multi_pods" and resolve_slot("pod_map", skill_root=skill_root).get("missing"):
        return False
    second_path = skill_root / "ProjectData/plan/Input/second_level_tasks.json"
    if second_path.is_file():
        try:
            raw = json.loads(second_path.read_text(encoding="utf-8"))
            tasks = raw.get("tasks") if isinstance(raw, dict) else []
            return bool(tasks)
        except Exception:
            return False
    return True


def _can_invoke_plan_dispatch(skill_root: Path) -> bool:
    from paths import resolve_slot

    third = skill_root / "ProjectData/plan/Output/third_level_tasks.json"
    if not third.is_file():
        return False
    try:
        raw = json.loads(third.read_text(encoding="utf-8"))
        tasks = raw.get("tasks") if isinstance(raw, dict) else []
        if not tasks:
            return False
    except Exception:
        return False
    return not resolve_slot("lld_design", skill_root=skill_root).get("missing")


def _can_invoke_cloudops_init(skill_root: Path) -> bool:
    return is_step3_done(load_chain(skill_root))


def recommended_next_action(skill_root: Path) -> str:
    """dashboard「继续」与 entry 推荐按钮共用；与 Stepper 当前步对齐。

    始终返回 ``*_start`` 闸门动作（如 ``plan_receive``），由左侧对话出材料引导卡；
    用户点闸门内「确认」后再走 ``*_invoke``。避免 ``sd_continue`` 静默直跑导致「大盘动、对话无反馈」。
    """
    chain = migrate_chain_from_state(skill_root)
    plan_step = load_plan_runtime_step(skill_root)
    if not is_step3_done(chain):
        sync_step3_from_state(skill_root)
        chain = load_chain(skill_root)
    cur = _running_step_index(chain, plan_step)
    if cur >= 10:
        return "sd_resume"
    return _STEP_RUNTIME_ACTION.get(cur, "sd_resume")


def _load_toolkit_import_receipt(skill_root: Path) -> dict[str, Any]:
    p = skill_root / "ProjectData" / "plan" / "RunTime" / "toolkit_import.json"
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _progress_summary(skill_root: Path) -> str:
    chain = load_chain(skill_root)
    plan_step = load_plan_runtime_step(skill_root)
    cur = _running_step_index(chain, plan_step)
    title = STEP_TITLES.get(cur, f"步骤 {cur}")
    lines = [
        f"**当前进度：步骤 {cur}/{TOTAL_STEPS} · {title}**",
        f"- plan 状态：`{plan_step or 'idle'}`（deploy_chain ①～③ 为真值）",
    ]
    if chain.get("step2_testcase_path"):
        lines.append(f"- 验收用例 Word：`{chain['step2_testcase_path']}`")
    if chain.get("step8_toolkit_import_at"):
        lines.append(f"- 步骤 8 导入时间：`{chain['step8_toolkit_import_at']}`")
        receipt = _load_toolkit_import_receipt(skill_root)
        imp = receipt.get("importResponse") if isinstance(receipt.get("importResponse"), dict) else {}
        if str(imp.get("code") or "") == "200":
            lines.append("- Toolkit 上传回执：`200` 成功")
    if chain.get("step9_init_install_at"):
        lines.append(f"- 步骤 9 初始化与软件安装：`{chain['step9_init_install_at']}`")
    elif cur >= 9:
        lines.append("- 步骤 9 推荐先做 **连线检查**；其余命令（子系统/集群测试）待接入。")
    return "\n".join(lines)


def _build_continue_action_list(
    *,
    next_action: str,
    chain: dict[str, Any],
) -> list[dict[str, Any]]:
    """主按钮统一走 ``sd_continue``（与右侧大盘橙色「继续」一致）。"""
    actions: list[dict[str, Any]] = []
    if next_action not in {"sd_start", "sd_resume"}:
        actions.append(
            sd_runtime_action(label=continue_button_label(next_action), action="sd_continue"),
        )
    elif not chain.get("step8_toolkit_import_at"):
        actions.append(sd_runtime_action(label="继续 · 导入 Toolkit", action="sd_continue"))
    else:
        actions.append(sd_runtime_action(label="继续 · 重新导入 Toolkit", action="sd_continue"))
        actions.append(sd_runtime_action(label="检查材料", action="upstream_check"))
    actions.append(sd_runtime_action(label="流程说明", action="sd_start"))
    return actions


def build_entry_guidance_payload(skill_root: Path) -> dict[str, Any]:
    """``sd_start`` / ``sd_resume``：展示进度说明；执行步骤请用 ``sd_continue`` 或大盘「继续」。"""
    chain = load_chain(skill_root)
    plan_step = load_plan_runtime_step(skill_root)
    next_action = recommended_next_action(skill_root)
    summary = _progress_summary(skill_root)

    if _should_show_continue_entry(chain, plan_step, next_action, skill_root=skill_root):
        has_progress = _has_deploy_progress(chain, plan_step)
        actions = _build_continue_action_list(next_action=next_action, chain=chain)
        step_hint = action_label(next_action)
        if has_progress:
            body = (
                f"**中途续做** · 已从 deploy_chain 恢复进度。\n\n{summary}\n\n"
                f"请点击 **继续** 进入当前步骤 **{step_hint}** 的材料闸门（左侧对话会出现引导卡）；"
                "确认材料后再执行本步。与右侧大盘橙色「继续」相同。"
            )
            card_id = "sd:entry_resume"
        else:
            body = (
                f"**可继续执行推荐步骤**（input 材料已就绪，进度链已清空）。\n\n{summary}\n\n"
                f"请点击 **继续** 进入 **{step_hint}** 材料闸门；左侧对话会出引导卡，"
                "确认后再执行本步（不会静默直跑）。"
            )
            card_id = "sd:entry_continue"
        if next_action in {"sd_start", "sd_resume"}:
            cur = _running_step_index(chain, plan_step)
            body += (
                f"\n\n▶️ 推荐关注右侧 Tab **{cur}**；"
                "步骤 10～11 及其它 Toolkit 子命令接入后可在此一键继续。"
            )
        return {
            "context": body,
            "cardId": card_id,
            "variant": "rows",
            "actions": actions,
        }

    return {
        "context": (
            "冷启动 · 十一步主线：\n"
            "1～3 计划 → 4～6 CloudOps（含 ZTP/测试参数提醒）→ 7 调测设备 → 8～11 Toolkit\n\n"
            "各步 input 目录**已有材料**时会提示「已检测到」，可选**沿用目录文件**或**重新上传**。"
        ),
        "cardId": "sd:entry_cold_start",
        "actions": [
            sd_runtime_action(label="开始：接收任务", action="plan_receive"),
            sd_runtime_action(label="检查材料", action="upstream_check"),
            sd_runtime_action(label="下载测试底表", action="download_checklist"),
            sd_runtime_action(label="生成调测报告汇总", action="report_aggregate"),
        ],
    }


def build_reset_done_actions(skill_root: Path) -> list[dict[str, Any]]:
    """演示重置完成卡：主按钮与大盘「继续」一致。"""
    next_action = recommended_next_action(skill_root)
    return [
        sd_runtime_action(label=continue_button_label(next_action), action="sd_continue"),
        sd_runtime_action(label="流程说明", action="sd_start"),
    ]


def format_toolkit_import_detail(
    skill_root: Path,
    *,
    message: str = "",
    receipt: dict[str, Any] | None = None,
) -> str:
    """步骤 8 完成卡：导入回执 + 底表刷新汇总。"""
    rec = receipt if isinstance(receipt, dict) else _load_toolkit_import_receipt(skill_root)
    chain = load_chain(skill_root)
    lines: list[str] = []
    if message.strip():
        lines.append(message.strip())
    at = str(chain.get("step8_toolkit_import_at") or "").strip()
    if at:
        lines.append(f"- 完成时间：`{at}`")
    cfg = str(rec.get("configFile") or "").strip()
    if cfg:
        lines.append(f"- 导入文件：`{cfg}`")
    imp = rec.get("importResponse") if isinstance(rec.get("importResponse"), dict) else {}
    if imp:
        code = str(imp.get("code") or "").strip()
        msg = str(imp.get("msg") or "").strip()
        if code or msg:
            lines.append(f"- 网关回执：`{code or '?'}` {msg}".strip())
    ref = rec.get("refresh") if isinstance(rec.get("refresh"), dict) else {}
    if ref.get("skipped"):
        lines.append(f"- 9c 底表刷新：已跳过（{ref.get('reason') or '缺少完工清单'}）")
    elif ref.get("ok"):
        lines.append(
            f"- 9c 底表刷新：{ref.get('devicesRefreshed', 0)} 台设备、"
            f"{ref.get('rowsRefreshed', 0)} 行任务"
        )
        checklist = str(ref.get("checklist") or "").strip()
        if checklist:
            lines.append(f"- 完工清单：`{checklist}`")
    summary = ref.get("baseTableSummary") if isinstance(ref.get("baseTableSummary"), dict) else {}
    by_dev = summary.get("byDeviceInit") if isinstance(summary.get("byDeviceInit"), dict) else {}
    by_task = summary.get("byTaskStatus") if isinstance(summary.get("byTaskStatus"), dict) else {}
    if by_dev:
        lines.append(
            f"- 底表（设备）：未初始化 {by_dev.get('UN_INIT', 0)}，"
            f"完成初始化 {by_dev.get('INIT_DONE', 0)}"
        )
    if by_task:
        task_bits = "，".join(
            f"{k}:{v}" for k, v in sorted(by_task.items(), key=lambda x: (-int(x[1]), x[0]))[:6]
        )
        if task_bits:
            lines.append(f"- 底表（任务行）：{task_bits}")
    return "\n".join(lines)


def build_toolkit_executor_done_payload(*, detail: str, skill_root: Path | None = None) -> dict[str, Any]:
    """步骤 7 完成卡：主按钮进步骤 8，保留修改执行机入口。"""
    next_step, next_action, next_label = 8, "toolkit_import_start", "继续步骤 8：导入 Toolkit"
    if skill_root is not None:
        chain = load_chain(skill_root)
        if chain.get("step8_toolkit_import_at"):
            next_step, next_action, next_label = (
                9,
                "connection_check_start",
                "继续步骤 9：服务器连线检查",
            )
    payload = sd_done_payload(
        card_id="sd:toolkit_executor_done",
        step=7,
        detail=detail,
        next_step=next_step,
        next_action=next_action,
        next_label=next_label,
    )
    payload["actions"].append(
        sd_runtime_action(label="修改调测设备", action="toolkit_executor_configure"),
    )
    return payload


def build_toolkit_import_done_payload(skill_root: Path, *, detail: str = "") -> dict[str, Any]:
    payload = sd_done_payload(
        card_id="sd:toolkit_import_done",
        step=8,
        detail=detail or format_toolkit_import_detail(skill_root),
        next_step=9,
        next_action="connection_check_start",
        next_label="继续步骤 9：服务器连线检查",
    )
    payload["actions"].append(
        sd_runtime_action(label="重新导入 Toolkit", action="toolkit_import_invoke"),
    )
    return payload


def build_toolkit_import_start_payload(skill_root: Path, *, already_done: bool) -> dict[str, Any]:
    from step_ui import step_gate_banner

    if already_done:
        detail = format_toolkit_import_detail(skill_root)
        detail += "\n\n如需再次上传完整配置，可点 **重新导入**（会覆盖 Toolkit 侧配置）。"
        return build_toolkit_import_done_payload(skill_root, detail=detail)

    return {
        "context": step_gate_banner(
            8,
            body=(
                "将执行：\n"
                "1) 导入 `plan/Output/CloudOps完整配置文件.xlsx` 到执行机 Toolkit（APIGW UploadFile/lldImport）\n"
                "2) 9c 底表刷新：用「设备安装完工清单」对齐底表，把默认“未初始化”更新为“完成初始化”，并重新导出宽表\n"
            ),
        ),
        "cardId": "sd:toolkit_import_intro",
        "actions": [sd_runtime_action(label="确认执行步骤 8", action="toolkit_import_invoke")],
    }


def build_connection_check_start_payload(skill_root: Path, *, already_done: bool) -> dict[str, Any]:
    from step_ui import step_done_banner, step_gate_banner

    if already_done:
        chain = load_chain(skill_root)
        at = str(chain.get("step9_init_install_at") or "").strip()
        from task_results import latest_run

        run = latest_run(skill_root, task_type="connection")
        detail = f"已于 `{at}` 完成服务器连线检查。" if at else "步骤 9 连线检查已标记完成。"
        tid = str(run.get("taskId") or "").strip()
        rdir = str(run.get("dir") or "").strip()
        if tid:
            detail += f"\ntaskId：`{tid}`"
        if rdir:
            detail += f"\n结果目录：`{Path(rdir).name}/`（report.zip + receipt.json）"
        return {
            "context": step_done_banner(9, detail=detail)
            + "\n\n可 **重新执行**（会再次 CreateTask 并覆盖同名校验由 Toolkit 侧处理）。",
            "cardId": "sd:connection_check_done",
            "actions": [
                sd_runtime_action(label="重新执行连线检查", action="connection_check_invoke"),
                sd_runtime_action(label="续做指引", action="sd_resume"),
            ],
        }

    return {
        "context": step_gate_banner(
            9,
            body=(
                "将执行 **服务器连线检查**（Toolkit `CreateTask` / `connectionCheck`，与 CPCIA `LinkCheckHandler` 一致）：\n"
                "1) 下发任务（默认 `collectAllServer=true`）\n"
                "2) 轮询任务状态直至 `reportEnd` 且处理中设备数为 0\n"
                "3) 等待约 60s 后导出报告至 `ProjectData/results/connection/<taskName>/`\n\n"
                "_注意：这不是 AscendCheck 连通性检查。_"
            ),
            prev_done_step=8,
        ),
        "cardId": "sd:connection_check_intro",
        "actions": [sd_runtime_action(label="确认执行连线检查", action="connection_check_invoke")],
    }
