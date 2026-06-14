from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path(__file__).resolve().parent
SKILL_ROOT = RUNTIME_DIR.parent

from artifact_indexer import collect_artifacts_from_files
from command_registry import get_command, reload_command_registry, support_status
from event_builder import (
    artifact_publish,
    choice_request,
    confirm_request,
    dashboard_patch,
    file_request,
    guidance,
    patch_merge,
    task_progress_sync,
)
from input_checker import BASE_REQUIRED_INPUTS, collect_inputs, describe_missing, missing_required
from intent_router import recognize
from sd_actions import SD_COMMAND, NormalizedAction, normalize_action, sd_step3_plane_choices
from session_state import hitl_request_id, load_plane_progress, save_pipeline_state, save_plane_progress
from state import load_state, update_state

import sys as _sys
_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_SKILL_ROOT))
from path_config import ensure_dirs  # noqa: E402

from executors.l3_executor import execute_l3
from executors.dispatch_executor import execute_dispatch
from executors.conductor_executor import execute_conductor


DEFAULT_COMMAND = "计算带外管理地址规划"

# 不经意图识别、不触发 subprocess 执行的 action
_NON_EXECUTION_ACTIONS = frozenset({
    "sd_start",
    "start",
    "sd_after_input_upload",
    "resume_after_upload_inputs",
    "check_current_project",
    "sd_step3_plane_run",
    "sd_step6_skip_ztp",
    "fallback_cancel",
    "sd_cancel",
})


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_run_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "").strip("_")
    return safe or "run"


def _request_id(run_id: str, suffix: str, *, thread_id: str = "") -> str:
    if thread_id:
        return hitl_request_id(thread_id, suffix)
    return f"a3-opening:{_safe_run_id(run_id)}:{suffix}"


def _payload(req: dict[str, Any]) -> dict[str, Any]:
    intent = req.get("intent")
    if isinstance(intent, dict) and isinstance(intent.get("payload"), dict):
        return intent["payload"]
    payload = req.get("payload")
    return payload if isinstance(payload, dict) else {}


def _result(req: dict[str, Any]) -> dict[str, Any]:
    payload = _payload(req)
    for container in (payload, req):
        result = container.get("result")
        if isinstance(result, dict):
            return result
    return {}


def _selected_text(req: dict[str, Any]) -> str:
    result = _result(req)
    selected = result.get("selected") or result.get("selectedId") or result.get("value")
    if isinstance(selected, str):
        return selected
    selected_ids = result.get("selectedIds")
    if isinstance(selected_ids, list) and selected_ids:
        return _as_str(selected_ids[0])
    return ""


def _action(req: dict[str, Any]) -> str:
    payload = _payload(req)
    return _as_str(payload.get("action") or req.get("action")) or "start"


def _text(req: dict[str, Any]) -> str:
    payload = _payload(req)
    result = _result(req)
    return _as_str(
        payload.get("text")
        or payload.get("message")
        or result.get("text")
        or result.get("message")
        or result.get("command")
        or req.get("message")
        or req.get("text")
    )


# 对齐参考 HTML · sd-matrix 四组（非 6 Tab）
_MATRIX_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "id": "compute",
        "title": "计算面",
        "tone": "brand",
        "items": (
            ("计算带外管理面地址规划", "计算带外管理"),
            ("计算管理面地址规划", "计算管理面"),
            ("计算业务面地址规划", "计算业务面"),
            ("计算样本面地址规划", "计算样本面"),
            ("计算参数面地址规划", "计算参数面"),
        ),
    },
    {
        "id": "network",
        "title": "网络面",
        "tone": "info",
        "items": (
            ("网络带外管理面地址规划", "网络带外管理面"),
            ("网络互联规划", "网络互联"),
            ("网络接入规划", "网络接入"),
            ("SPINE 上行互联规划", "SPINE 上行互联"),
            ("交换机 MLAG 规划", "交换机 MLAG"),
        ),
    },
    {
        "id": "storage",
        "title": "存储面",
        "tone": "violet",
        "items": (
            ("存储带外管理面地址规划", "存储带外管理面"),
            ("存储管理面地址规划", "存储管理面"),
            ("存储业务面地址规划", "存储业务面"),
            ("存储业务面接入规划", "存储业务面接入"),
        ),
    },
    {
        "id": "manage",
        "title": "管理 / 衍生件",
        "tone": "amber",
        "items": (
            ("灵衢带外管理面地址规划", "灵衢带外管理面"),
            ("NCE 规划", "NCE"),
            ("CCAE 规划", "CCAE"),
            ("生成设备清单", "生成设备清单"),
        ),
    },
)

_COMMAND_TO_MATRIX: dict[str, str] = {
    "计算带外管理地址规划": "计算带外管理面地址规划",
    "网络带外管理地址规划": "网络带外管理面地址规划",
    "存储带外管理地址规划": "存储带外管理面地址规划",
    "灵衢带外管理地址规划": "灵衢带外管理面地址规划",
    "计算管理面地址规划": "计算管理面地址规划",
    "计算管存面地址规划": "计算管存面地址规划",
    "计算业务面地址规划": "计算业务面地址规划",
    "计算样本面地址规划": "计算样本面地址规划",
    "计算参数面地址规划": "计算参数面地址规划",
    "存储管理面地址规划": "存储管理面地址规划",
    "存储业务面地址规划": "存储业务面地址规划",
    "互联规划": "网络互联规划",
    "接入规划": "网络接入规划",
    "网络设备ASN规划": "网络设备 ASN 规划",
    "交换机MLAG规划": "交换机 MLAG 规划",
    "NCE规划": "NCE 规划",
    "CCAE规划": "CCAE 规划",
    "生成完整LLD设计": "生成完整 LLD 设计",
    "融合完整LLD设计": "融合完整 LLD 设计",
    "替换设备名称": "设备名称替换",
}

_INPUT_SLOT_META: tuple[tuple[str, str, bool, bool, str], ...] = (
    ("resource", "项目信息收集表", True, False, "地址规划的数据底座，需手动上传"),
    ("007", "端口连线表", True, True, "设备端口互联关系，仿真自动输出"),
    ("001", "设备信息表", True, True, "设备型号 / 角色 / 序列号"),
    ("004", "设备位置表", True, True, "机房 / 机柜 / U 位"),
)


def _matrix_item_for_command(command: str) -> str | None:
    if not command:
        return None
    if command in _COMMAND_TO_MATRIX:
        return _COMMAND_TO_MATRIX[command]
    for group in _MATRIX_GROUPS:
        for key, _label in group["items"]:
            if command == key or command.replace(" ", "") == key.replace(" ", ""):
                return key
    return None


def _progress_map() -> dict[str, str]:
    data = load_plane_progress()
    planes = data.get("planes")
    if not isinstance(planes, dict):
        return {}
    return {str(k): str(v) for k, v in planes.items() if v}


def _mark_command(command: str, status: str = "done") -> None:
    item = _matrix_item_for_command(command)
    if not item:
        return
    data = load_plane_progress()
    planes = dict(data.get("planes") or {})
    planes[item] = status
    save_plane_progress({**data, "planes": planes})


def _stepper_steps(
    *,
    s1: str = "waiting",
    s2: str = "waiting",
    s3: str = "waiting",
    s4: str = "waiting",
    s5: str = "waiting",
    s6: str = "waiting",
) -> list[dict[str, Any]]:
    return [
        {"id": "s1", "title": "输入件准备", "status": s1},
        {"id": "s2", "title": "输入件检查", "status": s2},
        {"id": "s3", "title": "LLD 生成", "status": s3},
        {"id": "s4", "title": "设备名称替换", "optional": True, "status": s4},
        {"id": "s5", "title": "ZTP / 开局文件", "status": s5},
        {"id": "s6", "title": "发布完成", "status": s6},
    ]


def _matrix_groups_payload() -> list[dict[str, Any]]:
    progress = _progress_map()
    groups: list[dict[str, Any]] = []
    for group in _MATRIX_GROUPS:
        items = [
            {"key": key, "label": label, "done": progress.get(key) == "done"}
            for key, label in group["items"]
        ]
        groups.append(
            {
                "id": group["id"],
                "title": group["title"],
                "tone": group["tone"],
                "items": items,
            }
        )
    return groups


def _input_slots_payload(found: dict[str, Any]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for tag, label, required, auto, desc in _INPUT_SLOT_META:
        item = found.get(tag)
        ready = item is not None
        slot: dict[str, Any] = {
            "tag": tag,
            "label": label,
            "required": required,
            "auto": auto,
            "desc": f"{item.path.name} · 已就绪" if ready else desc,
            "status": "ready" if ready else "missing",
        }
        if not auto:
            slot["primaryAction"] = {
                "label": "上传",
                "variant": "primary",
                "action": {
                    "kind": "post_user_message",
                    "text": (
                        '{"type":"chat_card_intent","verb":"skill_runtime_start",'
                        '"payload":{"type":"skill_runtime_start",'
                        '"skillName":"a3-intelligent-network-opening",'
                        '"requestId":"req-upload-inputs","action":"sd_query_inputs",'
                        '"text":"检查输入件是否妥当"}}'
                    ),
                },
            }
        else:
            preview_action: dict[str, Any] = {"kind": "preview_input", "inputTag": tag}
            if ready and item is not None:
                preview_action["path"] = str(item.path)
            slot["secondaryAction"] = {
                "label": "预览",
                "variant": "secondary",
                "action": preview_action,
            }
        slots.append(slot)
    return slots


def _output_files_payload(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for art in artifacts:
        files.append(
            {
                "id": art.get("artifactId") or art.get("id") or art.get("label"),
                "label": art.get("label") or "output.xlsx",
                "kind": art.get("kind") or "规划表",
                "rows": art.get("rows") or "已生成",
                "size": art.get("size") or "—",
                "path": art.get("path"),
                "corrected": bool(art.get("corrected")),
            }
        )
    return files


def _timeline_patch(*, banner: str = "请先完成输入件准备与检查。", tone: str = "info") -> dict[str, Any]:
    return patch_merge(
        "task-timeline",
        "TaskTimelineStrip",
        {
            "banner": {"text": banner, "tone": tone},
            "phaseLabel": "进行中",
            "phaseTone": "info",
        },
    )


def _output_tab_patch(count: int, artifacts: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    ops = [
        patch_merge("sect-outputs", "Text", {"content": f"规划输出件 · {count} 个"}),
    ]
    if count:
        ops.append(
            patch_merge(
                "output-empty",
                "EmptyState",
                {"title": "", "hint": "", "hidden": True},
            )
        )
        ops.append(
            patch_merge(
                "output-file-list",
                "OutputFileList",
                {"files": _output_files_payload(artifacts or [])},
            )
        )
    else:
        ops.append(
            patch_merge(
                "output-empty",
                "EmptyState",
                {
                    "title": "暂无输出件",
                    "hint": "完成任意规划任务后，结果文件将在此汇总，可随时下载或融合为完整 LLD。",
                },
            )
        )
        ops.append(patch_merge("output-file-list", "OutputFileList", {"files": []}))
    return ops


def _dashboard_core_ops(
    skill_root: Path,
    found: dict[str, Any],
    *,
    stepper: list[dict[str, Any]] | None = None,
    banner: str | None = None,
    banner_tone: str = "info",
    artifacts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    out_n = len(artifacts or [])
    ops: list[dict[str, Any]] = [
        _timeline_patch(banner=banner or "请先完成输入件准备与检查。", tone=banner_tone),
        patch_merge("stepper-main", "Stepper", {"steps": stepper or _stepper_steps()}),
        patch_merge("plane-matrix", "PlanningMatrix", {"groups": _matrix_groups_payload()}),
        patch_merge("input-slot-list", "InputSlotList", {"slots": _input_slots_payload(found)}),
        *_output_tab_patch(out_n, artifacts),
    ]
    return ops


def _initial_ops() -> list[dict[str, Any]]:
    return _dashboard_core_ops(Path("."), {}, stepper=_stepper_steps())


def _input_ops(skill_root: Path, found: dict[str, Any], summary: str) -> list[dict[str, Any]]:
    required_ready = all(tag in found for tag in BASE_REQUIRED_INPUTS)
    ready_count = len(found)
    s1 = "done" if ready_count else "running"
    s2 = "done" if required_ready else ("running" if ready_count else "waiting")
    banner = summary if summary else "请先完成输入件准备与检查。"
    tone = "success" if required_ready else ("warn" if ready_count else "info")
    return _dashboard_core_ops(
        skill_root,
        found,
        stepper=_stepper_steps(s1=s1, s2=s2),
        banner=banner,
        banner_tone=tone,
    )


def _planning_ops(_command: str, _group: str, _status: str, _summary: str) -> list[dict[str, Any]]:
    return [patch_merge("plane-matrix", "PlanningMatrix", {"groups": _matrix_groups_payload()})]


def _error_ops(_stage: str, _command: str, _source: str, message: str, *, found_count: int = 0) -> list[dict[str, Any]]:
    return [_timeline_patch(banner=message, tone="bad")]



def _request_upload_events(thread_id: str, run_id: str, command: str, missing: list[str]) -> list[dict[str, Any]]:
    missing_text = describe_missing(missing)
    return [
        guidance(
            f"执行 `{command}` 还缺少输入件：{missing_text}。请上传后我会先更新输入件检查结果。",
            thread_id=thread_id,
            run_id=run_id,
            card_id="a3-opening:missing-inputs",
        ),
        file_request(
            thread_id=thread_id,
            run_id=run_id,
            request_id=_request_id(run_id, "upload_inputs", thread_id=thread_id),
            title="请上传 A3 开局输入件",
            description=f"至少需要：{missing_text}。上传后只做输入件检查，不会自动执行 Skill。",
        ),
    ]


def _handle_check_inputs(req: dict[str, Any], *, thread_id: str, run_id: str, skill_root: Path) -> list[dict[str, Any]]:
    found = collect_inputs(skill_root, _result(req))
    missing = missing_required(found, BASE_REQUIRED_INPUTS)
    summary = "输入件检查完成。" if not missing else f"输入件不完整，缺少：{describe_missing(missing)}。"
    events = [dashboard_patch(_input_ops(skill_root, found, summary), thread_id=thread_id, run_id=run_id)]
    if missing:
        events.extend(_request_upload_events(thread_id, run_id, DEFAULT_COMMAND, missing))
    else:
        events.append(task_progress_sync(1, thread_id=thread_id, run_id=run_id))
        events.append(
            guidance(
                "输入件已满足执行条件。可输入 L3 命令（如 `计算带外管理地址规划`）或 L1 批次（如 `地址规划`、`互联规划`）。",
                thread_id=thread_id,
                run_id=run_id,
            )
        )
    return events


def _prepare_command(
    req: dict[str, Any],
    *,
    thread_id: str,
    run_id: str,
    skill_root: Path,
    command: str,
    auto_execute: bool = False,
) -> list[dict[str, Any]]:
    spec = get_command(command)
    status, group = support_status(command)
    if spec is None:
        message = f"`{command}` 已登记为 `{status}`，当前环境暂不可执行。"
        return [
            dashboard_patch(
                _planning_ops(command, group, status, message)
                + _error_ops("intent", command, "command_registry", "命令尚未接入可执行 adapter。"),
                thread_id=thread_id,
                run_id=run_id,
            ),
            guidance(message, thread_id=thread_id, run_id=run_id, card_id="a3-opening:not-ready"),
        ]

    found = collect_inputs(skill_root, _result(req))
    missing = missing_required(found, spec.required_inputs)
    update_state(skill_root, thread_id, command=command)
    ops = _input_ops(skill_root, found, "输入件检查完成。" if not missing else f"输入件不完整，缺少：{describe_missing(missing)}。")
    ready_msg = "已命中可执行命令，正在执行。" if auto_execute and not missing else "已命中可执行命令，正在检查输入件。"
    ops.extend(_planning_ops(command, spec.b2_group, "ready" if not missing else "blocked", ready_msg))
    events = [dashboard_patch(ops, thread_id=thread_id, run_id=run_id)]
    if missing:
        events.extend(_request_upload_events(thread_id, run_id, command, missing))
        return events
    if auto_execute:
        events.append(task_progress_sync(1, thread_id=thread_id, run_id=run_id))
        events.extend(_execute_command(req, thread_id=thread_id, run_id=run_id, skill_root=skill_root))
        return events
    events.append(task_progress_sync(1, thread_id=thread_id, run_id=run_id))
    events.append(
        confirm_request(
            thread_id=thread_id,
            run_id=run_id,
            request_id=_request_id(run_id, "confirm_start", thread_id=thread_id),
            command=command,
        )
    )
    return events


def _resolve_intent_text(
    req: dict[str, Any],
    norm: NormalizedAction,
    *,
    skill_root: Path,
    thread_id: str,
) -> str | None:
    """Derive user/command text for mandatory intent_router pass before execute."""
    if norm.action in _NON_EXECUTION_ACTIONS:
        return None

    payload_text = _text(req)
    if payload_text:
        return payload_text

    if norm.action in {"resume_after_clarify_intent", "sd_after_clarify_intent"}:
        selected = _selected_text(req)
        if selected in SD_COMMAND and SD_COMMAND[selected]:
            return SD_COMMAND[selected]
        if selected:
            return selected
        return None

    if norm.auto_execute or norm.action in {"confirm_start_planning", "sd_step_confirm"}:
        state = load_state(skill_root, thread_id)
        cmd = _as_str(state.get("command"))
        return cmd or None

    if norm.command:
        return norm.command

    mapped = SD_COMMAND.get(norm.action, "")
    if mapped:
        return mapped

    if norm.action in {"recognize_intent", "run_command", "sd_run_command"}:
        return payload_text or None

    return None


def _handle_intent(
    req: dict[str, Any],
    *,
    thread_id: str,
    run_id: str,
    skill_root: Path,
    text: str,
) -> list[dict[str, Any]]:
    """Mandatory pipeline: input text → intent_router → execute → output."""
    raw_text = (text or "").strip()
    if not raw_text:
        return [
            guidance(
                "请提供要执行的规划命令（自然语言或标准命令名）。",
                thread_id=thread_id,
                run_id=run_id,
                card_id="a3-opening:intent-empty",
            ),
        ]

    result = recognize(raw_text)
    save_pipeline_state(last_intent_input=raw_text, last_intent_status=result.status)

    if result.status == "resolved":
        save_pipeline_state(pending_command=result.command, current_step="intent_resolved")
        return _prepare_command(
            req,
            thread_id=thread_id,
            run_id=run_id,
            skill_root=skill_root,
            command=result.command,
            auto_execute=True,
        )
    if result.status == "clarifying":
        options = [{"id": candidate, "label": candidate} for candidate in result.candidates]
        return [
            dashboard_patch(
                _planning_ops("待澄清", "计算面", "clarifying", result.message),
                thread_id=thread_id,
                run_id=run_id,
            ),
            choice_request(
                thread_id=thread_id,
                run_id=run_id,
                request_id=_request_id(run_id, "clarify_intent", thread_id=thread_id),
                title=result.message,
                options=options,
            ),
        ]
    return [
        dashboard_patch(
            _planning_ops("未识别", "计算面", "failed", result.message)
            + _error_ops("intent", raw_text, "intent_router", result.message),
            thread_id=thread_id,
            run_id=run_id,
        ),
        guidance(result.message, thread_id=thread_id, run_id=run_id, card_id="a3-opening:intent-failed"),
    ]


def _execute_command(req: dict[str, Any], *, thread_id: str, run_id: str, skill_root: Path) -> list[dict[str, Any]]:
    state = load_state(skill_root, thread_id)
    command = _as_str(state.get("command")) or DEFAULT_COMMAND
    spec = get_command(command)
    if spec is None or spec.adapter not in {"l3", "dispatch", "conductor"}:
        return _handle_intent(req, thread_id=thread_id, run_id=run_id, skill_root=skill_root, text=command)

    found = collect_inputs(skill_root, _result(req))
    missing = missing_required(found, spec.required_inputs)
    if missing:
        events = [dashboard_patch(_input_ops(skill_root, found, f"输入件不完整，缺少：{describe_missing(missing)}。"), thread_id=thread_id, run_id=run_id)]
        events.extend(_request_upload_events(thread_id, run_id, command, missing))
        return events

    safe_run_id = _safe_run_id(run_id)
    sub_skill_label = spec.sub_skill or "subskills"
    adapter_labels = {"l3": "subprocess / L3", "dispatch": "subprocess / batch", "conductor": "subprocess / conductor"}
    start_ops = _planning_ops(
        command,
        spec.b2_group,
        "running",
        f"正在通过 {adapter_labels.get(spec.adapter, spec.adapter)} 调用 `{sub_skill_label}`。",
    )
    start_ops.extend(
        _dashboard_core_ops(
            skill_root,
            found,
            stepper=_stepper_steps(s1="done", s2="done", s3="running"),
            banner=f"正在执行：{command}",
            banner_tone="info",
        )
    )
    events = [dashboard_patch(start_ops, thread_id=thread_id, run_id=run_id)]

    extra: dict[str, Path] = {}
    if "access_plan" in found:
        extra["access_plan"] = found["access_plan"].path

    if spec.adapter == "l3":
        result = execute_l3(
            skill_root=skill_root,
            run_id=safe_run_id,
            command=command,
            input_007=found["007"].path,
            input_resource=found["resource"].path,
            extra_inputs=extra or None,
        )
    elif spec.adapter == "dispatch":
        result = execute_dispatch(
            skill_root=skill_root,
            run_id=safe_run_id,
            command=command,
            input_007=found["007"].path,
            input_resource=found["resource"].path,
            keep_going=True,
        )
    else:
        mode = spec.conductor_mode or "plan_run"
        result = execute_conductor(
            skill_root=skill_root,
            run_id=safe_run_id,
            command=command,
            mode=mode,
            input_007=found["007"].path,
            input_resource=found["resource"].path,
        )
    artifacts = collect_artifacts_from_files(
        skill_root=skill_root,
        files=result.output_files,
        command=command,
        sub_skill_name=result.sub_skill_name,
    )

    if result.status in ("ok", "partial"):
        _mark_command(command, "done")
        if spec.adapter == "dispatch":
            for task in getattr(result, "task_results", ()) or ():
                if getattr(task, "status", "") == "ok":
                    _mark_command(getattr(task, "intent", ""), "done")

        finish_ops = _planning_ops(command, spec.b2_group, "done", result.summary)
        finish_ops.extend(
            _dashboard_core_ops(
                skill_root,
                found,
                stepper=_stepper_steps(s1="done", s2="done", s3="done"),
                banner=result.summary,
                banner_tone="success",
                artifacts=artifacts,
            )
        )
        events.append(dashboard_patch(finish_ops, thread_id=thread_id, run_id=run_id))
        events.append(task_progress_sync(2, thread_id=thread_id, run_id=run_id))
        if artifacts:
            events.append(artifact_publish(artifacts, thread_id=thread_id, run_id=run_id))
        events.append(guidance(result.summary, thread_id=thread_id, run_id=run_id, card_id="a3-opening:done"))
        return events

    message = result.errors[0] if result.errors else result.summary
    fail_ops = _planning_ops(command, spec.b2_group, "failed", result.summary)
    fail_ops.extend(_error_ops("adapter", command, result.sub_skill_name, message, found_count=len(found)))
    if artifacts:
        fail_ops.extend(
            _dashboard_core_ops(
                skill_root,
                found,
                stepper=_stepper_steps(s1="done", s2="done", s3="failed"),
                banner=message,
                banner_tone="bad",
                artifacts=artifacts,
            )
        )
    events.append(dashboard_patch(fail_ops, thread_id=thread_id, run_id=run_id))
    if artifacts:
        events.append(artifact_publish(artifacts, thread_id=thread_id, run_id=run_id))
    events.append(guidance(result.summary, thread_id=thread_id, run_id=run_id, card_id="a3-opening:failed"))
    return events


def _handle_start(req: dict[str, Any], *, thread_id: str, run_id: str, skill_root: Path) -> list[dict[str, Any]]:
    ensure_dirs()
    update_state(skill_root, thread_id, command=DEFAULT_COMMAND)
    save_pipeline_state(current_step="sd_start", pending_command=None)
    return [
        guidance(
            "A3 智能网络开局总控 Skill 已启动（Skill-First / subprocess）。支持 L3 单命令、L1/L2 批次与 LLD Conductor。请先准备全部必选输入件（项目信息收集表、007 端口连线表、001 设备信息表、004 设备位置表）。",
            thread_id=thread_id,
            run_id=run_id,
        ),
        dashboard_patch(_initial_ops(), thread_id=thread_id, run_id=run_id),
        task_progress_sync(0, thread_id=thread_id, run_id=run_id),
        file_request(
            thread_id=thread_id,
            run_id=run_id,
            request_id=_request_id(run_id, "upload_inputs", thread_id=thread_id),
            title="请上传 A3 开局输入件",
            description="至少需要：项目信息收集表、007 端口连线表、001 设备信息表、004 设备位置表。",
        ),
    ]


def run(req: dict[str, Any], *, skill_root: Path) -> list[dict[str, Any]]:
    reload_command_registry(skill_root)
    ensure_dirs()
    thread_id = _as_str(req.get("thread_id") or req.get("threadId")) or "thread-unknown"
    run_id = _as_str(req.get("skillRunId") or req.get("request_id") or req.get("requestId")) or "run"
    norm = normalize_action(_action(req))

    if norm.action in {"sd_start", "start"}:
        return _handle_start(req, thread_id=thread_id, run_id=run_id, skill_root=skill_root)

    if norm.check_inputs_only or norm.action in {
        "sd_after_input_upload",
        "sd_query_inputs",
        "check_current_project",
        "resume_after_upload_inputs",
    }:
        return _handle_check_inputs(req, thread_id=thread_id, run_id=run_id, skill_root=skill_root)

    if norm.action == "sd_step3_plane_run":
        return [
            dashboard_patch(
                _planning_ops("平面地址规划", "计算面", "ready", "请选择要执行的平面地址规划子步骤。"),
                thread_id=thread_id,
                run_id=run_id,
            ),
            choice_request(
                thread_id=thread_id,
                run_id=run_id,
                request_id=_request_id(run_id, "plane_choice", thread_id=thread_id),
                title="选择平面地址规划步骤",
                options=sd_step3_plane_choices(),
            ),
        ]

    if norm.action == "sd_step6_skip_ztp":
        save_pipeline_state(current_step="sd_step6_skip_ztp", pending_command=None)
        return [
            guidance("已跳过 ZTP 步骤，可继续执行灵衢开局或融合 LLD。", thread_id=thread_id, run_id=run_id),
            dashboard_patch(
                _planning_ops("ZTP 已跳过", "管理 / 衍生件", "done", "用户选择跳过 ZTP。")
                + [
                    patch_merge(
                        "stepper-main",
                        "Stepper",
                        {"steps": _stepper_steps(s1="done", s2="done", s3="done", s4="skip", s5="skip", s6="waiting")},
                    )
                ],
                thread_id=thread_id,
                run_id=run_id,
            ),
            task_progress_sync(5, thread_id=thread_id, run_id=run_id),
        ]

    intent_text = _resolve_intent_text(req, norm, skill_root=skill_root, thread_id=thread_id)
    if intent_text is not None:
        return _handle_intent(
            req,
            thread_id=thread_id,
            run_id=run_id,
            skill_root=skill_root,
            text=intent_text,
        )

    if norm.action in {"recognize_intent", "run_command", "sd_run_command"}:
        return _handle_intent(req, thread_id=thread_id, run_id=run_id, skill_root=skill_root, text="")

    if norm.action == "fallback_cancel":
        return [
            guidance("已取消当前 A3 开局动作，保留已上传输入件和当前大盘状态。", thread_id=thread_id, run_id=run_id),
            dashboard_patch(_planning_ops("已取消", "计算面", "cancelled", "用户取消了当前动作。"), thread_id=thread_id, run_id=run_id),
        ]

    return [
        guidance(f"未识别 action=`{norm.action}`，请重新输入要执行的规划命令。", thread_id=thread_id, run_id=run_id),
        dashboard_patch(
            _error_ops("driver", norm.action, "orchestrator", "未识别的 action。"),
            thread_id=thread_id,
            run_id=run_id,
        ),
    ]
