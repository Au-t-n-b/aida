from __future__ import annotations

import json
import time
from typing import Any

import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))
from path_config import SKILL_UPLOAD_REL  # noqa: E402


SKILL_NAME = "a3-intelligent-network-opening"
DOC_ID = "dashboard:a3-intelligent-network-opening"
DATA_FILE = "skills/a3-intelligent-network-opening/data/dashboard.json"
SYNTHETIC_PATH = f"skill-ui://SduiView?dataFile={DATA_FILE}"


def now_ms() -> int:
    return int(time.time() * 1000)


def patch_merge(node_id: str, node_type: str, fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "op": "merge",
        "target": {"by": "id", "nodeId": node_id},
        "value": {"type": node_type, "id": node_id, **fields},
    }


def envelope(event: str, payload: dict[str, Any], *, thread_id: str, run_id: str) -> dict[str, Any]:
    return {
        "event": event,
        "threadId": thread_id,
        "skillName": SKILL_NAME,
        "skillRunId": run_id,
        "timestamp": now_ms(),
        "payload": payload,
    }


def guidance(content: str, *, thread_id: str, run_id: str, card_id: str = "a3-opening:guidance") -> dict[str, Any]:
    return envelope(
        "chat.guidance",
        {"context": content, "content": content, "actions": [], "cardId": card_id},
        thread_id=thread_id,
        run_id=run_id,
    )


def dashboard_patch(ops: list[dict[str, Any]], *, thread_id: str, run_id: str) -> dict[str, Any]:
    return envelope(
        "dashboard.patch",
        {"syntheticPath": SYNTHETIC_PATH, "docId": DOC_ID, "ops": ops, "isPartial": True},
        thread_id=thread_id,
        run_id=run_id,
    )


def file_request(*, thread_id: str, run_id: str, request_id: str, title: str, description: str) -> dict[str, Any]:
    return envelope(
        "hitl.file_request",
        {
            "requestId": request_id,
            "cardId": request_id,
            "purpose": "a3-opening-inputs",
            "title": title,
            "description": description,
            "accept": ".xlsx,.xls,.csv,.json,.zip",
            "mount": "workspace://a3-intelligent-network-opening/input",
            "multiple": True,
            "mode": "append",
            "resumeAction": "sd_after_input_upload",
            "legacyResumeAction": "resume_after_upload_inputs",
            "onCancelAction": "sd_cancel",
            "legacyOnCancelAction": "fallback_cancel",
            "saveRelativeDir": SKILL_UPLOAD_REL,
            "skillName": SKILL_NAME,
            "stateNamespace": SKILL_NAME,
            "stepId": "a3-opening.input.upload",
            "expiresAt": now_ms() + 60 * 60 * 1000,
        },
        thread_id=thread_id,
        run_id=run_id,
    )


def choice_request(
    *,
    thread_id: str,
    run_id: str,
    request_id: str,
    title: str,
    options: list[dict[str, str]],
) -> dict[str, Any]:
    return envelope(
        "hitl.choice_request",
        {
            "requestId": request_id,
            "cardId": request_id,
            "title": title,
            "mode": "single",
            "options": options,
            "resumeAction": "sd_after_clarify_intent",
            "legacyResumeAction": "resume_after_clarify_intent",
            "onCancelAction": "sd_cancel",
            "legacyOnCancelAction": "fallback_cancel",
            "skillName": SKILL_NAME,
            "stateNamespace": SKILL_NAME,
            "stepId": "a3-opening.intent.clarify",
            "expiresAt": now_ms() + 30 * 60 * 1000,
        },
        thread_id=thread_id,
        run_id=run_id,
    )


def confirm_request(*, thread_id: str, run_id: str, request_id: str, command: str) -> dict[str, Any]:
    return envelope(
        "hitl.confirm_request",
        {
            "requestId": request_id,
            "cardId": request_id,
            "title": f"确认执行：{command}",
            "description": "输入件已满足执行条件。确认后将通过 subprocess 调用子 Skill，并把产物统一发布到右侧预览。",
            "confirmLabel": "开始执行",
            "cancelLabel": "取消",
            "resumeAction": "sd_step_confirm",
            "legacyResumeAction": "confirm_start_planning",
            "onCancelAction": "sd_cancel",
            "legacyOnCancelAction": "fallback_cancel",
            "skillName": SKILL_NAME,
            "stateNamespace": SKILL_NAME,
            "stepId": "a3-opening.planning.confirm",
            "expiresAt": now_ms() + 60 * 60 * 1000,
        },
        thread_id=thread_id,
        run_id=run_id,
    )


def artifact_publish(items: list[dict[str, Any]], *, thread_id: str, run_id: str) -> dict[str, Any]:
    return envelope(
        "artifact.publish",
        {"syntheticPath": SYNTHETIC_PATH, "docId": DOC_ID, "artifactsNodeId": "artifacts", "items": items},
        thread_id=thread_id,
        run_id=run_id,
    )


def task_progress_sync(done: int, *, thread_id: str, run_id: str) -> dict[str, Any]:
    tasks = [
        ("start", "待启动"),
        ("input_ready", "输入件已准备"),
        ("network_plan", "网络规划已完成"),
        ("lld_fusion", "融合LLD已生成"),
        ("rename_device", "设备名称已替换"),
        ("ztp", "ZTP/开局文件已生成"),
        ("publish", "发布完成"),
    ]
    return envelope(
        "task_progress.sync",
        {
            "schemaVersion": 1,
            "updatedAt": now_ms(),
            "modules": [
                {
                    "moduleId": "a3_intelligent_network_opening",
                    "moduleName": "A3 智能网络开局",
                    "updatedAt": now_ms(),
                    "tasks": [
                        {"name": name, "displayName": display, "completed": index <= done}
                        for index, (name, display) in enumerate(tasks)
                    ],
                }
            ],
        },
        thread_id=thread_id,
        run_id=run_id,
    )


def error_row(stage: str, command: str, source: str, message: str) -> dict[str, str]:
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    return {
        "time": ts,
        "stage": stage,
        "command": command,
        "source": source,
        "message": message,
        "status": "待处理",
    }


def dumps_event(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8", errors="replace")
