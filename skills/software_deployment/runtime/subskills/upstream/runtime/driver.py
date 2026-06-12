from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

# skill cwd = software_deployment root
_ROOT = Path.cwd().resolve()
if str(_ROOT / "runtime") not in sys.path:
    sys.path.insert(0, str(_ROOT / "runtime"))

from guidance_actions import sd_runtime_action  # noqa: E402
from paths import (  # noqa: E402
    check_prerequisites,
    load_plan_runtime_step,
    plan_action_for_step,
    plan_dispatch_input_dir,
    plan_receive_dir,
    plan_runtime_action_name,
    plan_split_input_dir,
    resolve_slot,
)

# 每步只检查本步 action 在 manifest 中声明的槽位（不一次性扫全流程）
_STEP_META: dict[str, dict[str, str]] = {
    "receive": {
        "title": "步骤 1/6 · 接收二级任务",
        "hint": "点「接收」会先列出已有文件，确认（plan_receive_invoke）后才写入；无文件则上传。",
        "label": "接收任务",
        "for_action": "plan_receive",
        "input_dir_fn": "plan_receive",
    },
    "split": {
        "title": "步骤 2/6 · 拆分调测计划",
        "hint": "点「拆分」先确认材料（plan_split_invoke）再生成三级计划；缺验收用例/映射表会弹出上传。",
        "label": "拆分计划",
        "for_action": "plan_split",
        "input_dir_fn": "plan_split",
    },
    "dispatch": {
        "title": "步骤 3/6 · 下发设备底表",
        "hint": "点「下发」先确认 LLD（plan_dispatch_invoke）再展开宽表；无 LLD 会提示上传。",
        "label": "下发计划",
        "for_action": "plan_dispatch",
        "input_dir_fn": "plan_dispatch",
    },
    "regenerate": {
        "title": "步骤 4 · 重算或已完成",
        "hint": "下发已完成。可在同套 input 材料下「一键重算」覆盖三级计划与设备底表。",
        "label": "一键重算调测计划",
        "for_action": "plan_regenerate",
        "input_dir_fn": "plan_receive",
    },
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _emit(evt: dict[str, Any]) -> None:
    line = (json.dumps(evt, ensure_ascii=False) + "\n").encode("utf-8", errors="replace")
    sys.stdout.buffer.write(line)
    sys.stdout.buffer.flush()


def _input_dir_for_step(sub_action: str) -> str:
    if sub_action == "split":
        return str(plan_split_input_dir(_ROOT))
    if sub_action == "dispatch":
        return str(plan_dispatch_input_dir(_ROOT))
    return str(plan_receive_dir(_ROOT))


def _step_guidance(*, step: str, skill_name: str) -> dict[str, Any]:
    sub = plan_action_for_step(step)
    meta = _STEP_META.get(sub, _STEP_META["receive"])
    for_action = meta["for_action"]
    runtime_action = plan_runtime_action_name(step)

    report = check_prerequisites(for_actions=[for_action], skill_root=_ROOT)
    lines = [
        meta["title"],
        "",
        meta["hint"],
        "",
        f"本步输入目录：`{_input_dir_for_step(sub)}`",
        "",
    ]

    # 只列出本步相关的槽位（不展示 CloudOps / 其他阶段文件）
    step_slots = report.get("slots") or []
    if step_slots:
        lines.append("本步材料：")
        for slot in step_slots:
            if not isinstance(slot, dict):
                continue
            if slot.get("optional") and slot.get("missing"):
                continue
            mark = "[已就绪]" if not slot.get("missing") else "[待补齐]"
            if slot.get("missing"):
                detail = "点击本步按钮后将提示上传"
            else:
                detail = str(slot.get("primary") or "已找到")
            lines.append(f"- {mark} {slot.get('label')}：{detail}")
    else:
        lines.append("本步无额外 manifest 槽位检查。")

    missing_required = [s for s in step_slots if isinstance(s, dict) and s.get("missing") and not s.get("optional")]
    if missing_required:
        labels = "、".join(str(s.get("label") or "") for s in missing_required)
        lines.append("")
        lines.append(f"本步尚缺：{labels}。请点「{meta['label']}」，按卡片上传到上述目录。")
    elif sub != "regenerate":
        lines.append("")
        lines.append(f"本步材料已齐，可点「{meta['label']}」继续执行。")

    actions = [sd_runtime_action(label=meta["label"], action=runtime_action, skill_name=skill_name)]
    if sub == "regenerate":
        actions.append(sd_runtime_action(label="重新接收任务", action="plan_receive", skill_name=skill_name))

    return {
        "context": "\n".join(lines),
        "cardId": f"sd:step_guide:{sub}",
        "actions": actions,
    }


def main() -> int:
    try:
        req = json.loads(sys.stdin.read() or "{}")
    except Exception:
        req = {}

    thread_id = str(req.get("thread_id") or "thread-unknown")
    skill_name = str(req.get("skill_name") or "software_deployment")
    request_id = str(req.get("request_id") or "req-upstream")
    action = str(req.get("action") or "check").strip()
    run_id = f"{request_id}:{_now_ms()}"

    if action in {"check", "upstream_check", "cold_start"}:
        step = load_plan_runtime_step(_ROOT)
        payload = _step_guidance(step=step, skill_name=skill_name)
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

    if action == "resolve":
        slot_id = str((req.get("result") or {}).get("slotId") or "").strip()
        info = resolve_slot(slot_id) if slot_id else {}
        _emit(
            {
                "event": "chat.guidance",
                "threadId": thread_id,
                "skillName": skill_name,
                "skillRunId": run_id,
                "timestamp": _now_ms(),
                "payload": {"context": json.dumps(info, ensure_ascii=False, indent=2), "cardId": "sd:resolve"},
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
                "context": f"upstream 未识别 action={action}，支持 check / upstream_check / resolve",
                "cardId": "sd:upstream_unknown",
            },
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
