from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path.cwd().resolve()
if str(_ROOT / "runtime") not in sys.path:
    sys.path.insert(0, str(_ROOT / "runtime"))

os.environ.setdefault("SD_SKILL_ROOT", str(_ROOT))

from sd_script_import import import_sd_script  # noqa: E402

_receive_tasks = import_sd_script(_ROOT, "1_plan_receive", "receive_tasks")
_split_plan = import_sd_script(_ROOT, "2_plan_split", "plan_split")
_dispatch_plan = import_sd_script(_ROOT, "3_plan_dispatch", "dispatch_plan")
_lld_resolve = import_sd_script(_ROOT, "3_plan_dispatch", "lld_resolve")
split_plan = _split_plan.split_plan
split_plan_report = _split_plan.split_plan_report
dispatch_device_base = _dispatch_plan.dispatch_device_base
resolve_lld_path = _lld_resolve.resolve_lld_path
load_second_tasks = _receive_tasks.load_second_tasks
persist_received_tasks = _receive_tasks.persist_received_tasks

from guidance_actions import (  # noqa: E402
    sd_done_payload,
    sd_guidance_payload,
    sd_runtime_action,
    sync_skill_dashboard,
)
from paths import (  # noqa: E402
    check_prerequisites,
    load_plan_runtime_step,
    load_second_to_third,
    plan_dispatch_input_dir,
    plan_receive_dir,
    plan_split_input_dir,
    resolve_slot,
)
from checklist_export import (  # noqa: E402
    export_device_checklist_xlsx,
    resolve_project_display_name,
)
from projects_registry import sync_scene_from_projects  # noqa: E402
from plan_chain import mark_step1_complete, mark_step2_complete, mark_step3_complete  # noqa: E402
from deploy_chain import load_chain, merge_chain  # noqa: E402
from material_gate import append_reupload_action, material_footer, slot_bullet  # noqa: E402


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
    cancel_action: str,
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
                "onCancelAction": cancel_action,
                "skillName": skill_name,
                "stateNamespace": skill_name,
                "stepId": step_id,
                "expiresAt": _now_ms() + 3600_000,
            },
        }
    )


def _hitl_resume_result(req: dict[str, Any]) -> bool:
    """HITL 上传续跑会在 result 里带上文件信息；skill_runtime_start 的 result 通常为空。"""
    result = req.get("result")
    if not isinstance(result, dict) or not result:
        return False
    if result.get("upload") or result.get("uploads"):
        return True
    files = result.get("files") or result.get("uploadedFiles") or result.get("uploaded_files")
    return bool(files)


def _is_step_confirmed(req: dict[str, Any], invoke_action: str) -> bool:
    """上传完成 resume、或显式 invoke / confirm 后才真正执行本步。"""
    invoke = str(invoke_action or "").strip().lower()
    req_action = str(req.get("action") or "").strip().lower()
    if req_action.startswith("plan_"):
        req_action = req_action[5:]

    if req_action == invoke or req_action.endswith("_invoke"):
        return True
    if req.get("confirm") in (True, 1, "1", "true", "yes"):
        return True

    st = str(req.get("status") or "").strip().lower()
    if st in {"done", "completed", "success", "ok"}:
        # 平台 skill_runtime_start 也会带 status=ok，不能据此跳过 intro 闸门。
        return _hitl_resume_result(req)
    return False


def _effective_plan_next(completed_step: int) -> tuple[int, str, str]:
    """按 deploy_chain 跳过已完成步骤，避免完成卡指错下一步。"""
    chain = load_chain(_ROOT)
    plan_done: dict[int, str] = {
        1: "step1_plan_receive_at",
        2: "step2_plan_split_at",
        3: "step3_plan_dispatch_at",
    }
    labels: dict[int, str] = {
        2: "继续步骤 2：拆分计划",
        3: "继续步骤 3：下发计划",
        4: "继续步骤 4：CloudOps 初配",
    }
    actions: dict[int, str] = {
        2: "plan_split",
        3: "plan_dispatch",
        4: "cloudops_init_start",
    }
    step = completed_step + 1
    while step <= 3 and chain.get(plan_done.get(step, "")):
        step += 1
    return step, actions.get(step, "sd_continue"), labels.get(step, f"继续步骤 {step}")


def _file_line(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        return ""
    try:
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))
    except OSError:
        mtime = "?"
    return f"`{p.name}`（{mtime}）"


def _hitl_file_request(
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
    purpose: str,
    card_id: str,
    title: str,
    description: str,
    accept: str,
    save_relative_dir: str,
    resume_action: str,
    on_cancel: str = "upstream_check",
    step_id: str,
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
                "cardId": card_id,
                "purpose": purpose,
                "title": title,
                "description": description,
                "accept": accept,
                "multiple": False,
                "saveRelativeDir": save_relative_dir,
                "resumeAction": resume_action,
                "onCancelAction": on_cancel,
                "skillName": skill_name,
                "stateNamespace": skill_name,
                "stepId": step_id,
                "expiresAt": _now_ms() + 60 * 60 * 1000,
            },
        }
    )


def _skill_upload_prefix() -> str:
    return f"skills/{_ROOT.name}"


def _plan_dir() -> Path:
    return _ROOT / "ProjectData" / "plan"


def _save_json(path: Path, data: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_long_device_table() -> bool:
    """默认不写 52 万行长表 JSON；调试时设 SD_SAVE_DEVICE_LONG_TABLE=1。"""
    return str(os.environ.get("SD_SAVE_DEVICE_LONG_TABLE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _write_dispatch_outputs(
    *,
    result: dict[str, Any],
    scene_dict: dict[str, Any],
    req: dict[str, Any],
    proj_id: str,
) -> dict[str, Any]:
    """默认仅宽表 xlsx；长表 JSON 由你后续改逻辑后再按需开启。"""
    out_dir = _plan_dir() / "Output"
    device_tasks = result["deviceTasks"]
    long_saved = False
    if _save_long_device_table():
        _save_json(
            out_dir / "device_base_table.json",
            {"schemaVersion": 1, "tasks": device_tasks},
            compact=True,
        )
        long_saved = True
    display_name = resolve_project_display_name(
        scene=scene_dict,
        project_id=proj_id,
        project_name=str(req.get("project_name") or req.get("projectName") or "").strip() or None,
        skill_root=_ROOT,
    )
    xlsx_info = export_device_checklist_xlsx(
        device_tasks=device_tasks,
        scene=scene_dict,
        output_dir=out_dir,
        project_display_name=display_name,
    )
    xlsx_info["longTableSaved"] = long_saved
    xlsx_info["longTableRows"] = len(device_tasks) if long_saved else 0
    return xlsx_info


def _run_plan_split(
    req: dict[str, Any],
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
) -> int:
    proj_id = str(req.get("project_id") or req.get("projectId") or "").strip() or None
    raw_pp = req.get("projects_json_path") or req.get("projectsPath")
    pp: Path | None = Path(str(raw_pp)).expanduser() if raw_pp else None
    scene, sync_err = sync_scene_from_projects(_ROOT, project_id=proj_id, projects_path=pp)
    if sync_err:
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": (
                        f"拆分前需从工作台同步场景（projects.json → scene.json）：{sync_err}\n"
                        "可在 skill_runtime_start 请求体中传入 `project_id`，或设置环境变量 "
                        "`SD_PROJECTS_JSON` 指向 registry 文件。"
                    ),
                    "cardId": "sd:plan_split_no_scene",
                },
            }
        )
        return 0

    pod_info = str((scene or {}).get("podInfo") or (scene or {}).get("pod_info") or "single_pod")
    tc_slot = resolve_slot("testcase", skill_root=_ROOT)
    if tc_slot.get("missing"):
        _hitl_file_request(
            thread_id=thread_id,
            skill_name=skill_name,
            request_id=request_id,
            run_id=run_id,
            purpose="sd-plan-split-testcase",
            card_id="sd:hitl:plan_split_testcase",
            title="上传项目验收用例（Word）",
            description=(
                "拆分前需要验收用例 .docx；将保存到 "
                f"`{_skill_upload_prefix()}/ProjectData/input/plan_split`。"
                "上传完成后请再次执行「拆分计划」或「一键重算调测计划」。"
            ),
            accept=".docx",
            save_relative_dir=f"{_skill_upload_prefix()}/ProjectData/input/plan_split",
            resume_action="plan_split",
            step_id="sd.plan.split.testcase",
        )
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": "已根据项目 profile 写入 scene.json；缺少验收用例 Word，已弹出上传卡片。",
                    "cardId": "sd:plan_split_need_testcase",
                },
            }
        )
        return 0

    if pod_info == "multi_pods":
        pm = resolve_slot("pod_map", skill_root=_ROOT)
        if pm.get("missing"):
            _hitl_file_request(
                thread_id=thread_id,
                skill_name=skill_name,
                request_id=request_id,
                run_id=run_id,
                purpose="sd-plan-split-pod-map",
                card_id="sd:hitl:plan_split_pod_map",
                title="上传机房-Pod 映射（多 Pod）",
                description=(
                    "当前项目为多 Pod 场景，请上传机房/Pod 映射表（.xlsx）；保存到 "
                    f"`{_skill_upload_prefix()}/ProjectData/input/plan_split`。"
                    "完成后请再次执行「拆分计划」或「一键重算调测计划」。"
                ),
                accept=".xlsx",
                save_relative_dir=f"{_skill_upload_prefix()}/ProjectData/input/plan_split",
                resume_action="plan_split",
                step_id="sd.plan.split.pod_map",
            )
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": "多 Pod 场景缺少映射表，已弹出上传卡片。",
                        "cardId": "sd:plan_split_need_pod_map",
                    },
                }
            )
            return 0

    gate = check_prerequisites(for_actions=["plan_split"])
    if not gate.get("ok"):
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": "拆分前缺少：" + "、".join(gate.get("blocking") or ["未知项"]),
                    "cardId": "sd:plan_split_blocked",
                },
            }
        )
        return 0
    second_tasks = load_second_tasks(_ROOT)
    if not second_tasks:
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": "未找到二级任务：请将「部署调测任务列表.xlsx」放入 plan_receive 目录。",
                    "cardId": "sd:plan_split_no_second",
                },
            }
        )
        return 0

    # 临时阶段：从 xlsx 刷新二级快照，保证 333 条写入 plan/Input
    persist_received_tasks(_ROOT, second_tasks)
    mark_step1_complete(
        _ROOT,
        second_tasks_path=_plan_dir() / "Input" / "second_level_tasks.json",
        task_count=len(second_tasks),
    )

    proj_id = str(req.get("project_id") or req.get("projectId") or "").strip() or "nanobot-local"
    task_map = load_second_to_third()
    try:
        report = split_plan_report(
            second_tasks,
            scene=scene or {},
            project_id=proj_id,
            skill_root=_ROOT,
        )
        third_rows = report.get("tasks") or []
        plan_tree = report.get("tree") or []
    except Exception as e:
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": f"拆分计划失败：{e}",
                    "cardId": "sd:plan_split_error",
                },
            }
        )
        return 0
    missing: list[str] = []
    for row in second_tasks:
        name = str(row.get("activityName") or row.get("name") or "").strip()
        if name and name not in task_map:
            missing.append(name)
    third_path = _plan_dir() / "Output" / "third_level_tasks.json"
    tree_path = _plan_dir() / "Output" / "plan_display_tree.json"
    _save_json(third_path, {"schemaVersion": 1, "tasks": third_rows})
    _save_json(
        tree_path,
        {
            "schemaVersion": 1,
            "secondCount": len(second_tasks),
            "thirdCount": len(third_rows),
            "tree": plan_tree,
            "rows": _split_plan.flatten_plan_tree(plan_tree),
        },
    )

    testcase_path = str(tc_slot.get("primary") or "").strip()
    testcase_note = "；验收用例 Word 已检查" if testcase_path else ""

    mark_step2_complete(
        _ROOT,
        third_tasks_path=third_path,
        third_task_count=len(third_rows),
        testcase_path=testcase_path or None,
    )
    scene_path = _ROOT / "ProjectData" / "plan" / "RunTime" / "scene.json"
    if scene_path.is_file():
        merge_chain(_ROOT, step1_scene_path="ProjectData/plan/RunTime/scene.json")

    suffix = testcase_note
    scene_fields = report.get("scene") or {}
    suffix += (
        f"；场景 train_infer={scene_fields.get('train_infer_scene')} "
        f"pod={scene_fields.get('pod_info')} cooling={scene_fields.get('cooling')}"
    )
    skipped = report.get("skippedNoDevice") or []
    if skipped:
        suffix += f"；跳过无设备清单 {len(skipped)} 项"
    if missing:
        uniq: list[str] = []
        for n in missing:
            if n not in uniq:
                uniq.append(n)
        suffix += f"；未命中映射 {len(uniq)} 项（{ '、'.join(uniq[:3]) }{'…' if len(uniq) > 3 else ''}）"
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": sd_done_payload(
                card_id="sd:plan_split_done",
                step=2,
                detail=f"已生成 {len(third_rows)} 条三级活动（二级 {len(second_tasks)} 条）{suffix}。",
                next_step=3,
                next_action="plan_dispatch",
                next_label="继续步骤 3：下发计划",
                skill_name=skill_name,
            ),
        }
    )
    sync_skill_dashboard(
        skill_root=_ROOT, thread_id=thread_id, skill_name=skill_name, run_id=run_id, timestamp_ms=_now_ms()
    )
    return 0


def _run_plan_dispatch(
    req: dict[str, Any],
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
) -> int:
    _ = req
    lld_primary = resolve_lld_path(_ROOT)
    lld = resolve_slot("lld_design", skill_root=_ROOT)
    if lld_primary:
        lld = {**lld, "primary": lld_primary, "missing": False, "resolved": [lld_primary]}
    if lld.get("missing"):
        _hitl_file_request(
            thread_id=thread_id,
            skill_name=skill_name,
            request_id=request_id,
            run_id=run_id,
            purpose="sd-plan-dispatch-lld",
            card_id="sd:hitl:plan_dispatch_lld",
            title="上传 LLD 设计文件",
            description=(
                "下发前需要 LLD 设计 .xlsx；将保存到 "
                f"`{_skill_upload_prefix()}/ProjectData/input/plan_dispatch`（可含 lld/ 子目录）。"
                "上传完成后请再次执行「下发计划」。"
            ),
            accept=".xlsx",
            save_relative_dir=f"{_skill_upload_prefix()}/ProjectData/input/plan_dispatch",
            resume_action="plan_dispatch",
            step_id="sd.plan.dispatch.lld",
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
                        "未在 `ProjectData/input/plan_dispatch` 找到 LLD；已弹出上传卡片。"
                        f"亦可手工放入：`{plan_dispatch_input_dir(_ROOT)}`。"
                    ),
                    "cardId": "sd:plan_dispatch_no_lld",
                    "actions": [
                        sd_runtime_action(label="下发计划（上传后继续）", action="plan_dispatch", skill_name=skill_name),
                    ],
                },
            }
        )
        return 0
    third_path = _plan_dir() / "Output" / "third_level_tasks.json"
    third_tasks: list[dict[str, Any]] = []
    if third_path.is_file():
        raw = json.loads(third_path.read_text(encoding="utf-8"))
        tasks = raw.get("tasks") if isinstance(raw, dict) else []
        if isinstance(tasks, list):
            third_tasks = [t for t in tasks if isinstance(t, dict)]

    if not third_tasks:
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": "下发前请先执行 plan_split，生成 third_level_tasks.json。",
                    "cardId": "sd:plan_dispatch_no_third",
                },
            }
        )
        return 0

    proj_id = str(req.get("project_id") or req.get("projectId") or "").strip() or "nanobot-local"
    second_tasks = load_second_tasks(_ROOT)
    scene_path = _ROOT / "ProjectData" / "plan" / "RunTime" / "scene.json"
    scene_dict: dict[str, Any] = {}
    if scene_path.is_file():
        scene_raw = json.loads(scene_path.read_text(encoding="utf-8"))
        if isinstance(scene_raw, dict):
            scene_dict = scene_raw
    try:
        result = dispatch_device_base(
            lld_path=str(lld.get("primary")),
            third_tasks=third_tasks,
            second_tasks=second_tasks,
            scene=scene_dict,
            project_id=proj_id,
        )
    except Exception as e:
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": f"下发计划失败（LLD 解析或设备底表展开）：{e}",
                    "cardId": "sd:plan_dispatch_lld_error",
                },
            }
        )
        return 1

    xlsx_info = _write_dispatch_outputs(
        result=result,
        scene_dict=scene_dict,
        req=req,
        proj_id=proj_id,
    )
    out_dir = _plan_dir() / "Output"
    dispatch_record = {
        "schemaVersion": 1,
        "lldPath": result["lldPath"],
        "thirdTaskCount": len(third_tasks),
        "devicePoolSummary": result["devicePoolSummary"],
        "deviceTaskRows": result["stats"]["rows"],
        "dispatchStats": result["stats"],
        "checklistExport": xlsx_info,
        "status": "issued",
    }
    # 设备底表（结构化）：用于后续状态回写、IP 更新等
    _save_json(
        out_dir / "device_base_table.json",
        {
            "schemaVersion": 1,
            # keep a stable key; matches runtime/reset_workspace.py cleanup list
            "tasks": result.get("deviceTasks") or [],
        },
    )
    _save_json(out_dir / "dispatch_record.json", dispatch_record)
    checklist_file = str(xlsx_info.get("filePath") or "").strip()
    if not checklist_file and xlsx_info.get("fileName"):
        checklist_file = str(out_dir / xlsx_info["fileName"])
    mark_step3_complete(
        _ROOT,
        lld_path=str(lld.get("primary") or ""),
        device_base_path=out_dir / "device_base_table.json",
        dispatch_record_path=out_dir / "dispatch_record.json",
        checklist_path=checklist_file or None,
    )
    pool = result["devicePoolSummary"]
    stats = result["stats"]
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
                "payload": sd_guidance_payload(
                    card_id="sd:plan_dispatch_to_cloudops",
                    step=4,
                    intro="步骤 3 已完成，进入步骤 4",
                    prev_done_step=3,
                    prev_detail=(
                        f"LLD 设备池 SERVER={pool.get('SERVER', pool.get('智算', 0))} / "
                        f"LQ_SWITCH={pool.get('LQ_SWITCH', pool.get('灵衢', 0))}；"
                        f"宽表 {xlsx_info.get('fileName')}（{xlsx_info.get('deviceRows', 0)} 台）已写入 plan/Output；"
                        f"进度已写入 **deploy_chain**（step3_plan_dispatch_at）。"
                    ),
                    body=(
                        "将读取 `input/plan_dispatch` 的 LLD，结合场景与模板生成 "
                        "`plan/Output/CloudOps初始配置.xlsx`。\n"
                        "确认后执行本步生成（仅一张引导卡，无重复确认框）。"
                    ),
                    action="cloudops_init_invoke",
                    action_label="确认并开始步骤 4：生成 CloudOps 初配",
                    skill_name=skill_name,
                ),
            }
        )
    sync_skill_dashboard(
        skill_root=_ROOT, thread_id=thread_id, skill_name=skill_name, run_id=run_id, timestamp_ms=_now_ms()
    )
    return 0


def _run_receive_invoke(
    req: dict[str, Any],
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
) -> int:
    try:
        tasks = load_second_tasks(_ROOT)
    except Exception as e:
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": f"读取二级任务失败：{e}",
                    "cardId": "sd:plan_receive_read_error",
                },
            }
        )
        return 0
    if not tasks:
        _hitl_file_request(
            thread_id=thread_id,
            skill_name=skill_name,
            request_id=request_id,
            run_id=run_id,
            purpose="sd-plan-receive-tasks",
            card_id="sd:hitl:plan_receive_tasks",
            title="上传部署调测二级任务",
            description=(
                "请上传「部署调测任务列表」Excel（.xlsx）或 second_level_tasks.json；"
                f"将保存到 `{_skill_upload_prefix()}/ProjectData/input/plan_receive`。"
                "上传完成后将自动执行接收。"
            ),
            accept=".xlsx,.json",
            save_relative_dir=f"{_skill_upload_prefix()}/ProjectData/input/plan_receive",
            resume_action="plan_receive_invoke",
            step_id="sd.plan.receive.upload",
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
                        "未找到二级任务：已弹出上传卡片。亦可手工放入 "
                        f"`{plan_receive_dir(_ROOT)}`。"
                    ),
                    "cardId": "sd:plan_receive_empty",
                },
            }
        )
        return 0
    persist_received_tasks(_ROOT, tasks)
    snap = _plan_dir() / "Input" / "second_level_tasks.json"
    mark_step1_complete(_ROOT, second_tasks_path=snap, task_count=len(tasks))
    names = "、".join(str(t.get("activityName", "") or "") for t in tasks[:5])
    suffix = "…" if len(tasks) > 5 else ""
    next_step, next_action, next_label = _effective_plan_next(1)
    detail = f"已接收 {len(tasks)} 条二级任务：{names}{suffix}。"
    if next_step > 2:
        chain = load_chain(_ROOT)
        tc = int(chain.get("step2_third_task_count") or 0)
        if tc:
            detail += (
                f"\n（步骤 2 此前已完成：三级计划 {tc} 条；"
                f"推荐继续步骤 {next_step}。输入「拆分计划」可回看或重跑步骤 2。）"
            )
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": sd_done_payload(
                card_id="sd:plan_received",
                step=1,
                detail=detail,
                next_step=next_step,
                next_action=next_action,
                next_label=next_label,
                skill_name=skill_name,
            ),
        }
    )
    sync_skill_dashboard(
        skill_root=_ROOT, thread_id=thread_id, skill_name=skill_name, run_id=run_id, timestamp_ms=_now_ms()
    )
    return 0


def _run_receive_start(
    req: dict[str, Any],
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
) -> int:
    if _is_step_confirmed(req, "receive_invoke"):
        return _run_receive_invoke(req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id)

    slot = resolve_slot("second_level_tasks", skill_root=_ROOT)
    inbox = plan_receive_dir(_ROOT)
    snap = _plan_dir() / "Input" / "second_level_tasks.json"
    lines = [
        "**步骤 1/6 · 接收二级任务**",
        "",
        f"收件箱：`{inbox}`",
        "",
        "检测到的材料：",
    ]
    if slot.get("primary"):
        lines.append(f"- 收件箱：{_file_line(str(slot['primary']))}")
    elif not slot.get("missing"):
        for p in (slot.get("resolved") or [])[:3]:
            lines.append(f"- 收件箱：{_file_line(str(p))}")
    else:
        lines.append("- 收件箱：（暂无）")
    if snap.is_file():
        lines.append(f"- 已接收快照：{_file_line(str(snap))}")
    lines.append("")
    has_tasks = not slot.get("missing")
    lines.append(material_footer(has_required=has_tasks))

    body = "\n".join(lines[3:])  # 材料列表 + 说明
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                **sd_guidance_payload(
                    card_id="sd:plan_receive_intro",
                    step=1,
                    body=body,
                    action="plan_receive_invoke",
                    action_label="确认执行步骤 1：接收二级任务",
                    skill_name=skill_name,
                ),
                "actions": [
                    sd_runtime_action(
                        label="用目录里的材料，继续接收" if has_tasks else "确认执行步骤 1：接收二级任务",
                        action="plan_receive_invoke",
                        skill_name=skill_name,
                    ),
                    sd_runtime_action(label="重新上传材料", action="plan_receive_reupload", skill_name=skill_name),
                ],
            },
        }
    )
    return 0


def _run_split_reupload(
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
) -> int:
    _hitl_file_request(
        thread_id=thread_id,
        skill_name=skill_name,
        request_id=request_id,
        run_id=run_id,
        purpose="sd-plan-split-testcase",
        card_id="sd:hitl:plan_split_reupload",
        title="重新上传验收用例（Word）",
        description=(
            f"保存到 `{_skill_upload_prefix()}/ProjectData/input/plan_split`，"
            "上传完成后请再次执行「拆分计划」。"
        ),
        accept=".docx",
        save_relative_dir=f"{_skill_upload_prefix()}/ProjectData/input/plan_split",
        resume_action="plan_split",
        step_id="sd.plan.split.reupload",
    )
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                "context": "已弹出上传卡片；上传完成后请点「拆分计划」或「已有前置依赖文件，继续拆分」。",
                "cardId": "sd:plan_split_reupload",
            },
        }
    )
    return 0


def _run_dispatch_reupload(
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
) -> int:
    _hitl_file_request(
        thread_id=thread_id,
        skill_name=skill_name,
        request_id=request_id,
        run_id=run_id,
        purpose="sd-plan-dispatch-lld",
        card_id="sd:hitl:plan_dispatch_reupload",
        title="重新上传 LLD 设计文档",
        description=(
            f"保存到 `{_skill_upload_prefix()}/ProjectData/input/plan_dispatch` 或 `lld/`，"
            "上传完成后请再次执行「下发设备底表」。"
        ),
        accept=".xlsx",
        save_relative_dir=f"{_skill_upload_prefix()}/ProjectData/input/plan_dispatch",
        resume_action="plan_dispatch",
        step_id="sd.plan.dispatch.reupload",
    )
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                "context": "已弹出上传卡片；上传完成后请点「下发设备底表」。",
                "cardId": "sd:plan_dispatch_reupload",
            },
        }
    )
    return 0


def _run_receive_reupload(
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
) -> int:
    _hitl_file_request(
        thread_id=thread_id,
        skill_name=skill_name,
        request_id=request_id,
        run_id=run_id,
        purpose="sd-plan-receive-tasks",
        card_id="sd:hitl:plan_receive_reupload",
        title="重新上传二级任务",
        description=f"保存到 `{_skill_upload_prefix()}/ProjectData/input/plan_receive`，上传完成后自动接收。",
        accept=".xlsx,.json",
        save_relative_dir=f"{_skill_upload_prefix()}/ProjectData/input/plan_receive",
        resume_action="plan_receive_invoke",
        step_id="sd.plan.receive.reupload",
    )
    _emit(
        {
            "event": "chat.guidance",
            "threadId": thread_id,
            "skillName": skill_name,
            "skillRunId": run_id,
            "timestamp": _now_ms(),
            "payload": {
                "context": "已弹出上传卡片；上传完成后将自动执行「确认接收」。",
                "cardId": "sd:plan_receive_reupload",
            },
        }
    )
    return 0


def _run_split_start(
    req: dict[str, Any],
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
) -> int:
    if _is_step_confirmed(req, "split_invoke"):
        return _run_plan_split(
            req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id
        )

    chain = load_chain(_ROOT)
    step2_done = bool(chain.get("step2_plan_split_at"))

    step = load_plan_runtime_step(_ROOT)
    if step == "idle":
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": "请先完成 **步骤 1：接收二级任务**。",
                    "cardId": "sd:plan_split_need_receive",
                    "actions": [sd_runtime_action(label="步骤 1：接收", action="plan_receive", skill_name=skill_name)],
                },
            }
        )
        return 0

    tc = resolve_slot("testcase", skill_root=_ROOT)
    pm = resolve_slot("pod_map", skill_root=_ROOT)
    third = _plan_dir() / "Output" / "third_level_tasks.json"
    lines = [
        "**步骤 2/6 · 拆分调测计划**",
        "",
        f"材料目录：`{plan_split_input_dir(_ROOT)}`",
        "",
        "检测到的材料：",
    ]
    if tc.get("primary"):
        lines.append(f"- 验收用例：{_file_line(str(tc['primary']))}")
    else:
        lines.append("- 验收用例：（待上传 .docx）")
    if not pm.get("missing") and pm.get("primary"):
        lines.append(f"- Pod 映射：{_file_line(str(pm['primary']))}")
    if third.is_file():
        suffix = "（重新执行将覆盖）" if step2_done else "（确认后将覆盖）"
        lines.append(f"- 已有三级产物：{_file_line(str(third))}{suffix}")
    lines.append("")
    has_tc = not tc.get("missing")
    if step2_done:
        done_at = str(chain.get("step2_plan_split_at") or "").strip()
        tc_n = int(chain.get("step2_third_task_count") or 0)
        lines.append(
            f"ℹ️ **本步此前已执行过**（{done_at or '—'}，三级 {tc_n} 条）。"
            "可 **重新执行拆分** 走完整流程并刷新产物，或直接进入步骤 3。"
        )
        lines.append("")
    lines.append(material_footer(has_required=has_tc))

    if step2_done and has_tc:
        invoke_label = "重新执行拆分"
    elif has_tc:
        invoke_label = "已有前置依赖文件，继续拆分"
    else:
        invoke_label = "确认执行步骤 2：拆分计划"

    payload = sd_guidance_payload(
        card_id="sd:plan_split_intro",
        step=2,
        body="\n".join(lines[3:]),
        action="plan_split_invoke",
        action_label=invoke_label,
        skill_name=skill_name,
    )
    if step2_done:
        next_step, next_action, next_label = _effective_plan_next(2)
        if next_step == 3:
            payload["actions"] = list(payload.get("actions") or []) + [
                sd_runtime_action(label=next_label, action=next_action, skill_name=skill_name),
            ]
    if has_tc:
        payload = append_reupload_action(
            payload, reupload_action="plan_split_reupload", skill_name=skill_name
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


def _run_dispatch_start(
    req: dict[str, Any],
    *,
    thread_id: str,
    skill_name: str,
    request_id: str,
    run_id: str,
) -> int:
    if _is_step_confirmed(req, "dispatch_invoke"):
        return _run_plan_dispatch(
            req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id
        )

    step = load_plan_runtime_step(_ROOT)
    if step not in {"split", "dispatched", "dispatch"}:
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": "请先完成 **步骤 2：拆分计划**（deploy_chain.step2_plan_split_at 未设置）。",
                    "cardId": "sd:plan_dispatch_need_split",
                    "actions": [sd_runtime_action(label="步骤 2：拆分", action="plan_split", skill_name=skill_name)],
                },
            }
        )
        return 0

    lld_primary = resolve_lld_path(_ROOT)
    lld = resolve_slot("lld_design", skill_root=_ROOT)
    if lld_primary:
        lld = {**lld, "primary": lld_primary, "missing": False}
    third = _plan_dir() / "Output" / "third_level_tasks.json"
    lines = [
        "**步骤 3/6 · 下发设备底表**",
        "",
        f"LLD 目录：`{plan_dispatch_input_dir(_ROOT)}`",
        "",
        "检测到的材料：",
    ]
    if lld.get("primary"):
        lines.append(f"- LLD：{_file_line(str(lld['primary']))}")
    else:
        lines.append("- LLD：（待上传 .xlsx）")
    if third.is_file():
        lines.append(f"- 三级计划：{_file_line(str(third))}")
    else:
        lines.append("- 三级计划：（需先拆分）")
    rec = _plan_dir() / "Output" / "dispatch_record.json"
    if rec.is_file():
        lines.append(f"- 已有下发记录：{_file_line(str(rec))}（确认后将覆盖宽表等产物）")
    lines.append("")
    has_lld = bool(lld.get("primary"))
    lines.append(material_footer(has_required=has_lld))

    payload = sd_guidance_payload(
        card_id="sd:plan_dispatch_intro",
        step=3,
        body="\n".join(lines[3:]),
        action="plan_dispatch_invoke",
        action_label="已有LLD文件，继续下发" if has_lld else "确认执行步骤 3：下发设备底表",
        skill_name=skill_name,
    )
    if has_lld:
        payload = append_reupload_action(
            payload, reupload_action="plan_dispatch_reupload", skill_name=skill_name
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


def main() -> int:
    try:
        req = json.loads(sys.stdin.read() or "{}")
    except Exception:
        req = {}

    thread_id = str(req.get("thread_id") or "thread-unknown")
    skill_name = str(req.get("skill_name") or "software_deployment")
    request_id = str(req.get("request_id") or "req-plan")
    action = str(req.get("action") or "").strip()
    if action.startswith("plan_"):
        action = action[5:]
    run_id = f"{request_id}:{_now_ms()}"

    if action in {"cold_start", "start"}:
        inbox = str(plan_receive_dir(_ROOT))
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {
                    "context": (
                        "步骤 1/4 · 接收二级任务。\n"
                        f"本步只检查 `input/plan_receive`；无文件时点击「接收任务」会弹出上传卡片。\n"
                        f"目录：`{inbox}`"
                    ),
                    "cardId": "sd:plan_start",
                    "actions": [
                        sd_runtime_action(label="步骤 1：接收任务", action="plan_receive", skill_name=skill_name),
                    ],
                },
            }
        )
        return 0

    if action in {"receive_invoke", "receive_invoke_done"}:
        return _run_receive_invoke(
            req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id
        )

    if action in {"receive", "receive_start"}:
        return _run_receive_start(
            req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id
        )

    if action == "receive_reupload":
        return _run_receive_reupload(
            thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id
        )

    if action == "split_reupload":
        return _run_split_reupload(
            thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id
        )

    if action == "dispatch_reupload":
        return _run_dispatch_reupload(
            thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id
        )

    if action in {"split_invoke", "split_invoke_done"}:
        return _run_plan_split(
            req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id
        )

    if action in {"split", "split_start"}:
        return _run_split_start(
            req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id
        )

    if action in {"dispatch_invoke", "dispatch_invoke_done"}:
        return _run_plan_dispatch(
            req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id
        )

    if action in {"dispatch", "dispatch_start"}:
        return _run_dispatch_start(
            req, thread_id=thread_id, skill_name=skill_name, request_id=request_id, run_id=run_id
        )

    if action == "regenerate_invoke":
        req = dict(req)
        req["confirm"] = True
        action = "regenerate"

    if action == "regenerate":
        prefer_inbox = bool(req.get("prefer_inbox", True))
        try:
            tasks = load_second_tasks(_ROOT, prefer_inbox=prefer_inbox)
        except Exception as e:
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": f"读取二级任务失败：{e}",
                        "cardId": "sd:plan_regenerate_read_error",
                    },
                }
            )
            return 0
        if not _is_step_confirmed(req, "regenerate_invoke"):
            if not tasks:
                _hitl_file_request(
                    thread_id=thread_id,
                    skill_name=skill_name,
                    request_id=request_id,
                    run_id=run_id,
                    purpose="sd-plan-receive-tasks",
                    card_id="sd:hitl:plan_regenerate_tasks",
                    title="上传部署调测二级任务",
                    description=(
                        "重新生成调测计划需要二级任务源。请上传 .xlsx / second_level_tasks.json，"
                        f"保存到 `{_skill_upload_prefix()}/ProjectData/input/plan_receive`。"
                    ),
                    accept=".xlsx,.json",
                    save_relative_dir=f"{_skill_upload_prefix()}/ProjectData/input/plan_receive",
                    resume_action="plan_regenerate_invoke",
                    step_id="sd.plan.regenerate.upload",
                )
                _emit(
                    {
                        "event": "chat.guidance",
                        "threadId": thread_id,
                        "skillName": skill_name,
                        "skillRunId": run_id,
                        "timestamp": _now_ms(),
                        "payload": {
                            "context": f"未找到二级任务源：已弹出上传卡片。亦可放入 `{plan_receive_dir(_ROOT)}`。",
                            "cardId": "sd:plan_regenerate_empty",
                        },
                    }
                )
                return 0
            slot = resolve_slot("second_level_tasks", skill_root=_ROOT)
            tc = resolve_slot("testcase", skill_root=_ROOT)
            body_lines = [
                "**一键重算**：将按当前 input 覆盖二级快照、三级计划与设备底表（若存在 LLD）。",
                "",
                "检测到的材料：",
                slot_bullet(slot, prefix="二级任务："),
                slot_bullet(tc, prefix="验收用例："),
                "",
                material_footer(has_required=True),
            ]
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": "\n".join(body_lines),
                        "cardId": "sd:plan_regenerate_intro",
                        "variant": "rows",
                        "actions": [
                            sd_runtime_action(
                                label="用目录里的材料，继续重算",
                                action="plan_regenerate_invoke",
                                skill_name=skill_name,
                            ),
                            sd_runtime_action(
                                label="重新上传二级任务",
                                action="plan_receive_reupload",
                                skill_name=skill_name,
                            ),
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
                "payload": {
                    "context": (
                        "正在根据当前 input 与 registry 场景刷新二级快照，并重新生成三级调测计划"
                        "（覆盖 `Output/third_level_tasks.json`）。"
                    ),
                    "cardId": "sd:plan_regenerate_begin",
                },
            }
        )
        persist_received_tasks(_ROOT, tasks)
        if (
            _run_plan_split(
                req,
                thread_id=thread_id,
                skill_name=skill_name,
                request_id=request_id,
                run_id=run_id,
            )
            != 0
        ):
            return 0

        raw_inc = req.get("include_dispatch", True)
        if isinstance(raw_inc, str) and raw_inc.strip().lower() in ("0", "false", "no", "off"):
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": "已按 `include_dispatch: false` 仅完成拆分；需要设备底表时请执行「下发计划」。",
                        "cardId": "sd:plan_regenerate_split_only",
                        "actions": [
                            sd_runtime_action(label="步骤 3：下发计划", action="plan_dispatch", skill_name=skill_name)
                        ],
                    },
                }
            )
            return 0
        if raw_inc is False:
            _emit(
                {
                    "event": "chat.guidance",
                    "threadId": thread_id,
                    "skillName": skill_name,
                    "skillRunId": run_id,
                    "timestamp": _now_ms(),
                    "payload": {
                        "context": "已按请求仅完成拆分；需要设备底表时请执行「下发计划」。",
                        "cardId": "sd:plan_regenerate_split_only",
                        "actions": [
                            sd_runtime_action(label="步骤 3：下发计划", action="plan_dispatch", skill_name=skill_name)
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
                "payload": {
                    "context": "拆分完成，继续根据 LLD 重新展开设备底表…",
                    "cardId": "sd:plan_regenerate_dispatch_begin",
                },
            }
        )
        req_dispatch = dict(req)
        req_dispatch["confirm"] = True
        return _run_plan_dispatch(
            req_dispatch,
            thread_id=thread_id,
            skill_name=skill_name,
            request_id=request_id,
            run_id=run_id,
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
                    f"plan 未识别 action={action}；支持 receive/split/dispatch（含 *_invoke）、regenerate"
                ),
                "cardId": "sd:plan_unknown",
            },
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
