"""CloudOps 第 4～6 步（LLD 初配 / 手工补充 / 完整配置）。"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path.cwd().resolve()
_RT = _ROOT / "runtime"
if str(_RT) not in sys.path:
    sys.path.insert(0, str(_RT))

os.environ.setdefault("SD_SKILL_ROOT", str(_ROOT))

from sd_script_import import import_sd_script  # noqa: E402

_co_full = import_sd_script(_ROOT, "6_cloudops_full", "checklist_to_full")
_co_init = import_sd_script(_ROOT, "4_cloudops_init", "cloudops_runner")
_co_mat = import_sd_script(_ROOT, "6_cloudops_full", "material_check")
_co_pre = import_sd_script(_ROOT, "6_cloudops_full", "prerequisites")
_co_sup = import_sd_script(_ROOT, "5_cloudops_supplement", "supplement")
run_full_config_for_project = _co_full.run_full_config_for_project
plan_output_dir = _co_init.plan_output_dir
default_template_path = _co_init.default_template_path
run_cloudops_init_for_project = _co_init.run_cloudops_init_for_project
format_missing_materials_context = _co_pre.format_missing_materials_context
preflight_step6 = _co_pre.preflight_step6
build_step6_material_markdown = _co_mat.build_step6_material_markdown
process_params_upload = _co_mat.process_params_upload
probe_params = _co_mat.probe_params
process_ztp_upload = _co_mat.process_ztp_upload
probe_ztp = _co_mat.probe_ztp
scene_requires_ztp = _co_mat.scene_requires_ztp
build_step5_guidance_markdown = _co_sup.build_step5_guidance_markdown
process_manual_supplement_upload = _co_sup.process_manual_supplement_upload
probe_checklist = _co_sup.probe_checklist
from deploy_chain import clear_from_step, load_chain, merge_chain, sync_step3_from_state  # noqa: E402
from guidance_actions import (  # noqa: E402
    sd_done_payload,
    sd_guidance_payload,
    sd_runtime_action,
    sync_skill_dashboard,
)
from projects_registry import sync_scene_from_projects  # noqa: E402
from material_gate import append_reupload_action, file_line, material_footer  # noqa: E402
from paths import resolve_slot  # noqa: E402


def _now_ms() -> int:
    return int(time.time() * 1000)


def _emit(evt: dict[str, Any]) -> None:
    line = (json.dumps(evt, ensure_ascii=False) + "\n").encode("utf-8", errors="replace")
    sys.stdout.buffer.write(line)
    sys.stdout.buffer.flush()


def _hitl_confirm(
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
    card_id: str,
    title: str,
    description: str,
    resume_action: str,
    step_id: str,
) -> None:
    _emit(
        {
            "event": "hitl.confirm_request",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                "requestId": f"{request_id}:{card_id}:{_now_ms()}",
                "cardId": card_id,
                "title": title,
                "description": description,
                "confirmLabel": "确认执行",
                "cancelLabel": "取消",
                "resumeAction": resume_action,
                "onCancelAction": resume_action.replace("_invoke_done", "_start").replace("_upload_done", "_start"),
                "skillName": skill_name,
                "stateNamespace": skill_name,
                "stepId": step_id,
                "expiresAt": _now_ms() + 3600_000,
            },
        }
    )


def _emit_materials_gap(
    *,
    thread_id: str,
    skill_name: str,
    run_id: str,
    card_id: str,
    context: str,
    retry_action: str,
    retry_label: str,
    request_id: str,
    hitl_checklist: bool = False,
) -> None:
    """缺材料：说明原因 + 重试按钮；缺完工清单时弹出上传卡。"""
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                "context": context,
                "cardId": card_id,
                "variant": "rows",
                "actions": [
                    sd_runtime_action(label=retry_label, action=retry_action, skill_name=skill_name),
                    sd_runtime_action(label="回到步骤 5", action="cloudops_supplement_start", skill_name=skill_name),
                ],
            },
        }
    )
    if hitl_checklist:
        _hitl_upload(
            thread_id=thread_id,
            skill_name=skill_name,
            request_id=request_id,
            run_id=run_id,
            purpose="sd-cloudops-checklist",
            title="上传设备安装完工清单",
            description=(
                "步骤 6 需要完工清单 xlsx（文件名含「完工清单」）。"
                "上传后点「完成上传并继续」将重新检查材料。"
            ),
            resume_action=retry_action,
            step_id="sd.cloudops.checklist",
        )


def _hitl_upload(
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
    purpose: str,
    title: str,
    description: str,
    resume_action: str,
    step_id: str,
    accept: str = ".xlsx",
    on_cancel_action: str | None = None,
) -> None:
    _emit(
        {
            "event": "hitl.file_request",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                "requestId": f"{request_id}:{purpose}:{_now_ms()}",
                "cardId": f"sd:hitl:{purpose}",
                "purpose": purpose,
                "title": title,
                "description": description,
                "accept": accept,
                "multiple": False,
                "saveRelativeDir": f"skills/{_ROOT.name}/ProjectData/input/cloudops",
                "resumeAction": resume_action,
                "onCancelAction": on_cancel_action or "cloudops_supplement_start",
                "skillName": skill_name,
                "stateNamespace": skill_name,
                "stepId": step_id,
                "expiresAt": _now_ms() + 3600_000,
            },
        }
    )


def _emit_step6_material_panel(
    *,
    thread_id: str,
    skill_name: str,
    run_id: str,
    request_id: str,
    scene: dict[str, Any],
    full_detail: str = "",
    card_id: str = "sd:cloudops_full_materials",
    emit_upload_cards: bool = False,
) -> None:
    """步骤 6b：ZTP / 测试参数只提醒和登记，不阻塞步骤 7/8。"""
    chain = load_chain(_ROOT)
    requires_ztp = scene_requires_ztp(scene)
    ztp_probe = probe_ztp(skill_dir=str(_ROOT), chain=chain)
    params_probe = probe_params(skill_dir=str(_ROOT), chain=chain)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ready = (not requires_ztp or ztp_probe.present) and params_probe.present
    merge_payload: dict[str, Any] = {"step6_materials_checked_at": now}
    if ztp_probe.present:
        merge_payload["step6_ztp_at"] = str(chain.get("step6_ztp_at") or now)
        if ztp_probe.local_path:
            merge_payload["step6_ztp_path"] = f"skills/{_ROOT.name}/ProjectData/input/cloudops/{os.path.basename(ztp_probe.local_path)}"
            merge_payload["step6_ztp_source"] = ztp_probe.source or "deployment_local"
    if params_probe.present:
        merge_payload["step6_params_at"] = str(chain.get("step6_params_at") or now)
        if params_probe.local_path:
            merge_payload["step6_params_path"] = f"skills/{_ROOT.name}/ProjectData/input/cloudops/{os.path.basename(params_probe.local_path)}"
    merge_payload["step6_materials_ready_at"] = now if ready else ""
    merge_chain(_ROOT, **merge_payload)

    if not full_detail.strip():
        full_path = str(chain.get("step6_cloudops_full_path") or "CloudOps完整配置文件.xlsx")
        full_detail = f"已生成 `{full_path}`。" if chain.get("step6_cloudops_full_at") else "尚未生成 CloudOps 完整配置。"

    body = build_step6_material_markdown(
        full_detail=full_detail,
        requires_ztp=requires_ztp,
        ztp_present=ztp_probe.present,
        ztp_message=ztp_probe.message,
        params_present=params_probe.present,
        params_message=params_probe.message,
    )
    actions = [
        sd_runtime_action(label="上传 / 刷新 ZTP", action="cloudops_ztp_upload_done", skill_name=skill_name),
        sd_runtime_action(label="上传 / 刷新测试参数", action="cloudops_params_upload_done", skill_name=skill_name),
        sd_runtime_action(label="继续步骤 7：配置调测设备", action="toolkit_executor_configure", skill_name=skill_name),
        sd_runtime_action(label="导入 CloudOps 配置文件", action="toolkit_import_start", skill_name=skill_name),
    ]
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                "context": body,
                "cardId": card_id,
                "variant": "rows",
                "actions": actions,
            },
        }
    )
    if emit_upload_cards and not ztp_probe.present:
        _hitl_upload(
            thread_id=thread_id,
            skill_name=skill_name,
            request_id=request_id,
            run_id=run_id,
            purpose="sd-cloudops-ztp",
            title="上传 ZTP 文件（灵衢配置检查，可后补）",
            description="请上传灵衢 ZTP 开局 zip（文件名须带 ZTP），保存到 input/cloudops。该材料不阻塞导入 CloudOps 配置。",
            resume_action="cloudops_ztp_upload_done",
            step_id="sd.cloudops.materials.ztp",
            accept=".zip",
            on_cancel_action="cloudops_material_check",
        )
    if emit_upload_cards and not params_probe.present:
        _hitl_upload(
            thread_id=thread_id,
            skill_name=skill_name,
            request_id=request_id,
            run_id=run_id,
            purpose="sd-cloudops-params",
            title="上传 CloudOps 测试参数文件（可后补）",
            description="请上传 CloudOps_task_params_template 填写后的 xlsx，保存到 input/cloudops。后续具体 Toolkit API 任务会按需解析。",
            resume_action="cloudops_params_upload_done",
            step_id="sd.cloudops.materials.params",
            accept=".xlsx",
            on_cancel_action="cloudops_material_check",
        )


def _load_scene(req: dict[str, Any]) -> dict[str, Any]:
    scene_path = _ROOT / "ProjectData" / "plan" / "RunTime" / "scene.json"
    if scene_path.is_file():
        try:
            raw = json.loads(scene_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except Exception:
            pass
    proj_id = str(req.get("project_id") or req.get("projectId") or "").strip() or None
    scene, _ = sync_scene_from_projects(_ROOT, project_id=proj_id)
    return scene or {}


def _scene_ps_cooling(scene: dict[str, Any]) -> tuple[str, str]:
    ps = str(scene.get("productSpecification") or scene.get("product_spec") or "A3").strip().upper()
    cool = str(scene.get("cooling") or "air_cooling").strip()
    return ps, cool


def _require_step3(
    *,
    thread_id: str,
    skill_name: str,
    run_id: str,
) -> bool:
    if sync_step3_from_state(_ROOT):
        return True
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                "context": "请先完成 **第 3 步：下发计划**（deploy_chain.step3_plan_dispatch_at 未设置）。",
                "cardId": "sd:cloudops_need_dispatch",
                "actions": [sd_runtime_action(label="下发计划", action="plan_dispatch", skill_name=skill_name)],
            },
        }
    )
    return False


def _run_init(action: str, req: dict[str, Any], *, thread_id: str, skill_name: str, request_id: str, run_id: str) -> int:
    if not _require_step3(thread_id=thread_id, skill_name=skill_name, run_id=run_id):
        return 0
    scene = _load_scene(req)
    ps, cool = _scene_ps_cooling(scene)
    proj_id = str(req.get("project_id") or req.get("projectId") or scene.get("projectId") or "nanobot-local")

    if action in ("start", "cloudops_init_start", "init_start"):
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": sd_guidance_payload(
                    card_id="sd:cloudops_init_intro",
                    step=4,
                    body=(
                        f"将读取 `input/plan_dispatch` 的 LLD，结合模板生成 "
                        f"`plan/Output/CloudOps初始配置.xlsx`。\n"
                        f"场景：产品 **{ps}**，冷却 **{cool}**。"
                    ),
                    action="cloudops_init_invoke",
                    action_label="确认执行步骤 4：生成 CloudOps 初配",
                    skill_name=skill_name,
                ),
            }
        )
        return 0

    if action in ("invoke", "invoke_done", "cloudops_init_invoke", "init_invoke"):
        clear_from_step(_ROOT, 4)
        out_path = os.path.join(plan_output_dir(str(_ROOT)), "CloudOps初始配置.xlsx")
        result = run_cloudops_init_for_project(
            skill_dir=str(_ROOT),
            product_specification=ps,
            cooling=cool,
            template_path=default_template_path(str(_ROOT)),
            output_path=out_path,
        )
        if not result.ok:
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": (
                            f"步骤 4 生成失败：{result.message}\n\n"
                            "请确认 `input/plan_dispatch` 中 LLD 可读，或补齐后点「重试步骤 4」。"
                        ),
                        "cardId": "sd:cloudops_init_error",
                        "actions": [
                            sd_runtime_action(
                                label="重试步骤 4",
                                action="cloudops_init_start",
                                skill_name=skill_name,
                            ),
                        ],
                    },
                }
            )
            return 0
        rel = f"skills/{_ROOT.name}/ProjectData/plan/Output/CloudOps初始配置.xlsx"
        merge_chain(
            _ROOT,
            project_id=proj_id,
            step4_cloudops_init_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            step4_cloudops_output_path=rel,
            step4_cloudops_lld_source=result.lld_source,
        )
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": sd_done_payload(
                    card_id="sd:cloudops_init_done",
                    step=4,
                    detail=(
                        f"已生成 CloudOps初始配置.xlsx（{result.output_bytes_len} 字节）。\n"
                        f"LLD 来源：{result.lld_source}"
                    ),
                    next_step=5,
                    next_action="cloudops_supplement_start",
                    next_label="继续步骤 5：补充 CloudOps 配置",
                    skill_name=skill_name,
                ),
            }
        )
        sync_skill_dashboard(
            skill_root=_ROOT,
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            timestamp_ms=_now_ms(),
        )
        return 0
    return 0


def _emit_step5_supplement_complete(
    *,
    thread_id: str,
    skill_name: str,
    run_id: str,
    request_id: str,
    detail: str,
    checklist_present: bool,
    can_proceed_full_config: bool,
) -> None:
    """步骤 5 完成卡 + 步骤 6 入口（可重复 emit，用于 duplicate 续跑刷新 UI）。"""
    if can_proceed_full_config:
        payload = sd_done_payload(
            card_id="sd:cloudops_supplement_done",
            step=5,
            detail=detail,
            next_step=6,
            next_action="cloudops_full_start",
            next_label="继续步骤 6：生成完整配置",
            skill_name=skill_name,
        )
    else:
        payload = sd_done_payload(
            card_id="sd:cloudops_supplement_done",
            step=5,
            detail=(
                detail
                + "\n\n⚠️ **步骤 6 尚不可执行**：未检测到设备安装完工清单。"
                "请用下方上传卡补充，或放入 `ProjectData/input/cloudops/` 后点「检查材料并进入步骤 6」。"
            ),
            skill_name=skill_name,
        )
        payload["actions"] = [
            sd_runtime_action(label="检查材料并进入步骤 6", action="cloudops_full_start", skill_name=skill_name),
        ]
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": payload,
        }
    )
    if not checklist_present:
        _hitl_upload(
            thread_id=thread_id,
            skill_name=skill_name,
            request_id=request_id,
            run_id=run_id,
            purpose="sd-cloudops-checklist",
            title="上传设备安装完工清单（步骤 6 必需）",
            description="文件名建议含「设备安装完工清单」或「完工清单」，保存到 input/cloudops。",
            resume_action="cloudops_full_start",
            step_id="sd.cloudops.checklist",
        )


def _run_supplement(action: str, req: dict[str, Any], *, thread_id: str, skill_name: str, request_id: str, run_id: str) -> int:
    chain = load_chain(_ROOT)
    if not chain.get("step4_cloudops_init_at"):
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "timestamp": _now_ms(),
                "skillRunId": run_id,
                "payload": {
                    "context": "请先完成步骤 4（CloudOps 初始配置）。",
                    "cardId": "sd:cloudops_need_init",
                    "actions": [sd_runtime_action(label="步骤 4", action="cloudops_init_start", skill_name=skill_name)],
                },
            }
        )
        return 0

    if action in ("start", "cloudops_supplement_start", "supplement_start"):
        scene = _load_scene(req)
        proj_id = str(
            req.get("project_id")
            or req.get("projectId")
            or chain.get("project_id")
            or scene.get("projectId")
            or "nanobot-local"
        )
        checklist_ok, checklist_src = probe_checklist(skill_dir=str(_ROOT))
        manual_slot = resolve_slot("cloudops_manual", skill_root=_ROOT)
        has_manual = not manual_slot.get("missing")
        md = build_step5_guidance_markdown(
            skill_dir=str(_ROOT),
            chain=chain,
            checklist_ok=checklist_ok,
            checklist_src=checklist_src,
        )
        if has_manual:
            primary = str(manual_slot.get("primary") or "")
            md += f"\n\n**已检测到手工补充表**：{file_line(primary)}\n\n{material_footer(has_required=True)}"
        else:
            md += f"\n\n{material_footer(has_required=False)}"
        payload = sd_guidance_payload(
            card_id="sd:cloudops_supplement_intro",
            step=5,
            body=md,
            action="cloudops_supplement_upload_done",
            action_label="使用现有CloudOps手工补充表" if has_manual else "上传手工补充表并登记步骤 5",
            skill_name=skill_name,
        )
        if has_manual:
            payload = append_reupload_action(
                payload,
                reupload_action="cloudops_supplement_reupload",
                reupload_label="重新上传手工补充表",
                skill_name=skill_name,
            )
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": payload,
            }
        )
        if not has_manual:
            _hitl_upload(
                thread_id=thread_id,
                skill_name=skill_name,
                request_id=request_id,
                run_id=run_id,
                purpose="sd-cloudops-manual",
                title="上传 CloudOps 手工补充表",
                description="将编辑后的 xlsx 保存为 CloudOps配置_手工补充 类文件名，上传到 input/cloudops。",
                resume_action="cloudops_supplement_upload_done",
                step_id="sd.cloudops.supplement",
            )
        sync_skill_dashboard(
            skill_root=_ROOT,
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            timestamp_ms=_now_ms(),
        )
        return 0

    if action in ("reupload", "supplement_reupload", "cloudops_supplement_reupload"):
        _hitl_upload(
            thread_id=thread_id,
            skill_name=skill_name,
            request_id=request_id,
            run_id=run_id,
            purpose="sd-cloudops-manual",
            title="重新上传 CloudOps 手工补充表",
            description="将编辑后的 xlsx 上传到 input/cloudops，上传完成后点「完成上传并继续」登记步骤 5。",
            resume_action="cloudops_supplement_upload_done",
            step_id="sd.cloudops.supplement.reupload",
        )
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": "已弹出上传卡片；上传完成后将自动登记步骤 5。",
                    "cardId": "sd:cloudops_supplement_reupload",
                },
            }
        )
        return 0

    # NOTE: root driver strips the `cloudops_` prefix before invoking this subskill,
    # so `cloudops_supplement_upload_done` becomes `supplement_upload_done`.
    if action in ("upload_done", "cloudops_supplement_upload_done", "supplement_upload_done"):
        scene = _load_scene(req)
        proj_id = str(
            req.get("project_id")
            or req.get("projectId")
            or chain.get("project_id")
            or scene.get("projectId")
            or "nanobot-local"
        )
        result_obj = req.get("result")
        if not isinstance(result_obj, dict):
            result_obj = req
        up = process_manual_supplement_upload(
            skill_dir=str(_ROOT),
            result_obj=result_obj,
        )
        if not up.ok:
            if chain.get("step5_cloudops_supplement_at"):
                checklist_ok, checklist_src = probe_checklist(skill_dir=str(_ROOT))
                done_at = str(chain.get("step5_cloudops_supplement_at") or "").strip()
                manual = str(chain.get("step5_cloudops_manual_path") or "").strip()
                refresh_detail = (
                    f"步骤 5 已于 **{done_at}** 登记完成（本次上传未重新解析文件，仅刷新引导）。\n"
                    f"- 手工表：`{manual or 'CloudOps配置_手工补充.xlsx'}`\n"
                    f"- 完工清单：{'已检测到（' + checklist_src + '）' if checklist_ok else '未检测到'}"
                )
                _emit_step5_supplement_complete(
                    thread_id=thread_id,
                    skill_name=skill_name,
                    run_id=run_id,
                    request_id=request_id,
                    detail=refresh_detail,
                    checklist_present=checklist_ok,
                    can_proceed_full_config=checklist_ok,
                )
                sync_skill_dashboard(
                    skill_root=_ROOT,
                    thread_id=thread_id,
                    skill_name=skill_name,
                    run_id=run_id,
                    timestamp_ms=_now_ms(),
                )
                return 0
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": up.message,
                        "cardId": "sd:cloudops_supplement_error",
                        "actions": [
                            sd_runtime_action(
                                label="重新打开步骤 5",
                                action="cloudops_supplement_start",
                                skill_name=skill_name,
                            ),
                        ],
                    },
                }
            )
            return 0
        rel = f"skills/{_ROOT.name}/ProjectData/plan/Output/CloudOps配置_手工补充.xlsx"
        merge_chain(
            _ROOT,
            step5_cloudops_supplement_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            step5_cloudops_manual_path=rel,
            step5_checklist_detected=up.checklist_present,
        )
        _emit_step5_supplement_complete(
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            request_id=request_id,
            detail=up.message,
            checklist_present=up.checklist_present,
            can_proceed_full_config=up.can_proceed_full_config,
        )
        sync_skill_dashboard(
            skill_root=_ROOT,
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            timestamp_ms=_now_ms(),
        )
        return 0
    return 0


def _run_full(action: str, req: dict[str, Any], *, thread_id: str, skill_name: str, request_id: str, run_id: str) -> int:
    chain = load_chain(_ROOT)
    scene = _load_scene(req)
    if action in ("material_check", "materials_check", "material_refresh", "cloudops_material_check"):
        _emit_step6_material_panel(
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            request_id=request_id,
            scene=scene,
            card_id="sd:cloudops_material_check",
            emit_upload_cards=True,
        )
        sync_skill_dashboard(
            skill_root=_ROOT,
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            timestamp_ms=_now_ms(),
        )
        return 0

    if action in ("cloudops_ztp_upload_done",):
        result_obj = req.get("result")
        if not isinstance(result_obj, dict):
            result_obj = req
        up = process_ztp_upload(skill_dir=str(_ROOT), result_obj=result_obj)
        if not up.ok:
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": up.message,
                        "cardId": "sd:cloudops_ztp_error",
                        "actions": [
                            sd_runtime_action(label="重新上传 / 检查 ZTP", action="cloudops_material_check", skill_name=skill_name),
                        ],
                    },
                }
            )
            return 0
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        merge_chain(
            _ROOT,
            step6_ztp_at=now,
            step6_ztp_path=up.workspace_rel,
            step6_ztp_source=up.source,
        )
        _emit_step6_material_panel(
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            request_id=request_id,
            scene=scene,
            full_detail=up.message,
            card_id="sd:cloudops_ztp_done",
            emit_upload_cards=False,
        )
        sync_skill_dashboard(
            skill_root=_ROOT,
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            timestamp_ms=_now_ms(),
        )
        return 0

    if action in ("params_upload_done", "cloudops_params_upload_done"):
        result_obj = req.get("result")
        if not isinstance(result_obj, dict):
            result_obj = req
        up = process_params_upload(skill_dir=str(_ROOT), result_obj=result_obj)
        if not up.ok:
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": up.message,
                        "cardId": "sd:cloudops_params_error",
                        "actions": [
                            sd_runtime_action(label="重新上传 / 检查测试参数", action="cloudops_material_check", skill_name=skill_name),
                        ],
                    },
                }
            )
            return 0
        merge_chain(
            _ROOT,
            step6_params_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            step6_params_path=up.workspace_rel,
        )
        _emit_step6_material_panel(
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            request_id=request_id,
            scene=scene,
            full_detail=up.message,
            card_id="sd:cloudops_params_done",
            emit_upload_cards=False,
        )
        sync_skill_dashboard(
            skill_root=_ROOT,
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            timestamp_ms=_now_ms(),
        )
        return 0

    if action in ("checklist_reupload", "cloudops_checklist_reupload"):
        _hitl_upload(
            thread_id=thread_id,
            skill_name=skill_name,
            request_id=request_id,
            run_id=run_id,
            purpose="sd-cloudops-checklist",
            title="重新上传设备安装完工清单",
            description=(
                "步骤 6 合并需要设备安装完工清单 xlsx（文件名建议含「完工清单」）。"
                "将保存到 input/cloudops；上传完成后将重新进入步骤 6 材料检查。"
                "（手工补充表已在步骤 5 登记，此处无需重传。）"
            ),
            resume_action="cloudops_full_start",
            step_id="sd.cloudops.checklist.reupload",
            on_cancel_action="cloudops_full_start",
        )
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": (
                        "已弹出完工清单上传卡片。上传完成后将重新检查材料并回到步骤 6 闸门。"
                        "若需更换手工补充表，请回到 **步骤 5**。"
                    ),
                    "cardId": "sd:cloudops_checklist_reupload",
                },
            }
        )
        return 0

    if not chain.get("step5_cloudops_supplement_at"):
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": "请先完成步骤 5（上传手工补充表）。",
                    "cardId": "sd:cloudops_need_supplement",
                    "actions": [sd_runtime_action(label="步骤 5", action="cloudops_supplement_start", skill_name=skill_name)],
                },
            }
        )
        return 0

    if action in ("start", "cloudops_full_start", "full_start"):
        proj_id = str(
            req.get("project_id")
            or req.get("projectId")
            or chain.get("project_id")
            or scene.get("projectId")
            or "nanobot-local"
        )
        pf = preflight_step6(str(_ROOT), chain)
        if not pf.ok:
            _emit_materials_gap(
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                card_id="sd:cloudops_full_preflight",
                context=format_missing_materials_context(pf),
                retry_action="cloudops_full_start",
                retry_label="重新检查并进入步骤 6",
                request_id=request_id,
                hitl_checklist=not pf.checklist_ok,
            )
            sync_skill_dashboard(
                skill_root=_ROOT,
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                timestamp_ms=_now_ms(),
            )
            return 0
        manual_name = os.path.basename(pf.manual_path) if pf.manual_path else "（步骤 5 已登记）"
        body = (
            "材料检查已通过。本步将**合并**步骤 5 已登记的手工补充表与设备安装完工清单，"
            "生成完整配置（**无需重新上传手工表**）。\n\n"
            f"- 手工补充（步骤 5）：`{manual_name}`\n"
            f"- 设备安装完工清单：{pf.checklist_source or '已检测'}\n"
            "→ 输出 `plan/Output/CloudOps完整配置文件.xlsx`\n\n"
            "请点下方按钮执行合并；若清单有误，请 **重新上传完工清单**。"
            "需改手工表请回到 **步骤 5**。"
        )
        payload = sd_guidance_payload(
            card_id="sd:cloudops_full_intro",
            step=6,
            body=body,
            action="cloudops_full_invoke",
            action_label="使用已登记材料，生成完整配置",
            skill_name=skill_name,
        )
        payload = append_reupload_action(
            payload,
            reupload_action="cloudops_checklist_reupload",
            reupload_label="重新上传设备安装完工清单",
            skill_name=skill_name,
        )
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": payload,
            }
        )
        return 0

    if action in ("invoke", "invoke_done", "cloudops_full_invoke", "full_invoke"):
        proj_id = str(
            req.get("project_id")
            or req.get("projectId")
            or chain.get("project_id")
            or scene.get("projectId")
            or "nanobot-local"
        )
        pf = preflight_step6(str(_ROOT), chain)
        if not pf.ok:
            _emit_materials_gap(
                thread_id=thread_id,
                skill_name=skill_name,
                run_id=run_id,
                card_id="sd:cloudops_full_preflight_invoke",
                context=format_missing_materials_context(pf, step_label="步骤 6 执行"),
                retry_action="cloudops_full_start",
                retry_label="重新检查材料",
                request_id=request_id,
                hitl_checklist=not pf.checklist_ok,
            )
            return 0
        result = run_full_config_for_project(
            skill_dir=str(_ROOT),
            chain=chain,
        )
        if not result.ok:
            hint = (
                f"生成失败：{result.message}\n\n"
                "常见原因：完工清单表头缺「设备名称/ESN」、手工表被 Excel 占用、"
                "或清单与手工表设备名不一致导致无 SN 行。"
            )
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": hint,
                        "cardId": "sd:cloudops_full_error",
                        "variant": "rows",
                        "actions": [
                            sd_runtime_action(
                                label="重新检查并执行步骤 6",
                                action="cloudops_full_start",
                                skill_name=skill_name,
                            ),
                            sd_runtime_action(
                                label="回到步骤 5",
                                action="cloudops_supplement_start",
                                skill_name=skill_name,
                            ),
                        ],
                    },
                }
            )
            return 0
        rel = f"skills/{_ROOT.name}/ProjectData/plan/Output/CloudOps完整配置文件.xlsx"
        merge_chain(_ROOT, step6_cloudops_full_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), step6_cloudops_full_path=rel)
        full_detail = (
            f"CloudOps完整配置文件.xlsx（{result.output_bytes_len} 字节）；"
            f"服务器 {result.server_rows} 行，交换机 {result.switch_rows} 行。"
        )
        _emit_step6_material_panel(
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            request_id=request_id,
            scene=scene,
            full_detail=full_detail,
            card_id="sd:cloudops_full_done",
            emit_upload_cards=True,
        )
        sync_skill_dashboard(
            skill_root=_ROOT,
            thread_id=thread_id,
            skill_name=skill_name,
            run_id=run_id,
            timestamp_ms=_now_ms(),
        )
        return 0
    return 0


def _run_ztp(action: str, req: dict[str, Any], *, thread_id: str, skill_name: str, request_id: str, run_id: str) -> int:
    """兼容旧 action；ZTP 现在归属步骤 6 的材料检查。"""
    return _run_full(action, req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id)


def main() -> int:
    try:
        req = json.loads(sys.stdin.read() or "{}")
    except Exception:
        req = {}
    thread_id = str(req.get("thread_id") or "thread-unknown")
    skill_name = str(req.get("skill_name") or "software_deployment")
    request_id = str(req.get("request_id") or "req-cloudops")
    raw = str(req.get("action") or "").strip()
    if raw.startswith("cloudops_"):
        action = raw[9:]
    elif raw in ("init", "supplement", "full"):
        action = raw
    else:
        action = raw
    run_id = f"{request_id}:{_now_ms()}"

    if action.startswith("init") or action in ("cloudops_init", "s04"):
        return _run_init(action, req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id)
    if action.startswith("supplement") or action in ("cloudops_supplement", "s05"):
        return _run_supplement(action, req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id)
    if (
        action.startswith("full")
        or action in ("cloudops_full", "s06", "material_check", "materials_check", "material_refresh")
        or action.startswith("ztp")
        or action.startswith("params")
    ):
        return _run_full(action, req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id)

    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                "context": f"未知 CloudOps action={raw}",
                "cardId": "sd:cloudops_unknown",
            },
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
