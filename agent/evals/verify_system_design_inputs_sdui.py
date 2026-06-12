"""
system_design 输入件 SDUI 契约自检（离线 · 不依赖 Agent 进程）。

验证 merge 后三项 UX 契约：
  1. HITL「输入件准备」用 InputSlotList，不用 FilePicker（无弹框式 FilePicker）
  2. 左栏 HITL 槽位 id=cv-input-slots，就绪行带 fileName
  3. 右侧「输入件」页签 id=sd-inputs-list，就绪行带 previewPath（可预览）

    agent\\.venv\\Scripts\\python agent/evals/verify_system_design_inputs_sdui.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_AIDA = Path(__file__).resolve().parents[2]
if str(_AIDA) not in sys.path:
    sys.path.insert(0, str(_AIDA))

from agent.skills.system_design.sdui import project  # noqa: E402
from agent.skills.system_design.pipelines.inputs import FILE_CONFIG, label_of  # noqa: E402


def _walk(node, *, typ: str | None = None, id_: str | None = None):
    if isinstance(node, dict):
        if typ is None or node.get("type") == typ:
            if id_ is None or node.get("id") == id_:
                yield node
        for v in node.values():
            yield from _walk(v, typ=typ, id_=id_)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item, typ=typ, id_=id_)


def _sample_state() -> dict:
    return {
        "run_id": "verify-run",
        "hitl": {
            "step": "input_check",
            "need_files": ["项目信息收集表.xlsx"],
            "reason": "缺项目信息收集表",
        },
        "metrics": {
            "found_tags": [
                "resource",
                "Interconnection_Relationship",
                "Device_Info",
                "Location_Information",
                "Test_Case",
            ],
        },
        "files": {
            "input_Interconnection_Relationship": "input/端口连线表_for_all.xlsx",
            "input_Device_Info": "input/设备信息表.xlsx",
            "input_Location_Information": "input/设备位置表.xlsx",
            "input_Test_Case": "ht/测试用例.xlsx",
            "input_resource": "input/项目信息收集表模板CCAENCE-0104补齐IP(LEAF).xlsx",
        },
        "steps": [{"key": "input_check", "status": "paused"}],
    }


def verify() -> list[tuple[str, bool, str]]:
    doc = project(_sample_state())
    raw = json.dumps(doc, ensure_ascii=False)
    checks: list[tuple[str, bool, str]] = []

    checks.append((
        "无 FilePicker 节点",
        "FilePicker" not in raw,
        "HITL 应使用 InputSlotList 行内上传，避免 FilePicker 确认弹框",
    ))

    hitl = next(_walk(doc.get("root") or {}, id_="hitl-card"), None)
    checks.append((
        "存在 hitl-card「输入件准备」",
        bool(hitl) and hitl.get("title") == "输入件准备",
        str(hitl.get("title") if hitl else None),
    ))

    hitl_types = [c.get("type") for c in (hitl or {}).get("children", [])]
    checks.append((
        "HITL 子节点含 InputSlotList",
        "InputSlotList" in hitl_types,
        str(hitl_types),
    ))

    cv = next(_walk(doc.get("root") or {}, typ="InputSlotList", id_="cv-input-slots"), None)
    sd = next(_walk(doc.get("root") or {}, typ="InputSlotList", id_="sd-inputs-list"), None)

    auto_ready = [
        s for s in (cv or {}).get("slots", [])
        if s.get("source") == "auto" and s.get("ready")
    ]
    checks.append((
        "HITL 自动件就绪行有 fileName",
        len(auto_ready) >= 3 and all(s.get("fileName") for s in auto_ready),
        str([(s.get("label"), s.get("fileName")) for s in auto_ready]),
    ))

    tab_ready = [s for s in (sd or {}).get("slots", []) if s.get("ready")]
    checks.append((
        "输入件页签就绪行有 previewPath",
        len(tab_ready) >= 4 and all(s.get("previewPath") for s in tab_ready),
        str([(s.get("label"), s.get("previewPath")) for s in tab_ready]),
    ))

    checks.append((
        "Test_Case 展示名为「测试用例」",
        label_of("Test_Case") == "测试用例",
        label_of("Test_Case"),
    ))
    checks.append((
        "Test_Case 扫描支持 .xlsx",
        ".xlsx" in (FILE_CONFIG.get("Test_Case") or {}).get("extensions", []),
        str((FILE_CONFIG.get("Test_Case") or {}).get("extensions")),
    ))

    test_slot = next(
        (s for s in (sd or {}).get("slots", []) if s.get("slotTag") == "Test_Case"),
        None,
    )
    resource_slot = next(
        (s for s in (sd or {}).get("slots", []) if s.get("slotTag") == "resource"),
        None,
    )
    checks.append((
        "测试用例槽位展示名正确",
        bool(test_slot and test_slot.get("label") == "测试用例"),
        str(test_slot),
    ))
    checks.append((
        "项目信息收集表就绪行有 previewPath",
        bool(resource_slot and resource_slot.get("ready") and resource_slot.get("previewPath")),
        str(resource_slot),
    ))

    # step_retry 后 steps 同时含 hitl + completed，投影须仍能出「输入件检查完成」气泡
    retry_state = {
        **_sample_state(),
        "hitl": {},
        "steps": [
            {"key": "input_check", "status": "hitl"},
            {"key": "input_check", "status": "completed"},
        ],
    }
    retry_doc = project(retry_state)
    retry_raw = json.dumps(retry_doc, ensure_ascii=False)
    checks.append((
        "step_retry 后会话流含「输入件检查完成」",
        "cv-input-done" in retry_raw and "输入件检查完成" in retry_raw,
        "step_retry 追加 completed 记录后 _step_completed 须为 True",
    ))

    exec_state = {
        "run_id": "verify-exec",
        "project": {"chat": [{"role": "user", "text": "生成完整 LLD 设计"}]},
        "metrics": {"intent_command": "生成完整LLD设计"},
        "hitl": {
            "step": "exec_confirm",
            "command": "生成完整LLD设计",
            "io_reads": ["全部已生成的规划表", "项目信息收集表", "设备清单"],
            "io_writes": ["完整 LLD 设计文件"],
        },
        "steps": [
            {"key": "input_check", "status": "completed"},
            {"key": "exec_confirm", "status": "hitl"},
        ],
    }
    exec_doc = project(exec_state)
    exec_raw = json.dumps(exec_doc, ensure_ascii=False)
    checks.append((
        "exec_confirm 会话 + 确认卡",
        "cv-understood" in exec_raw
        and "已理解你的需求" in exec_raw
        and "IoConfirmPanel" in exec_raw,
        "须含「已理解你的需求」气泡与 IoConfirmPanel 确认卡",
    ))

    return checks


def main() -> int:
    checks = verify()
    ok = True
    for name, passed, detail in checks:
        tag = "PASS" if passed else "FAIL"
        print(f"  {tag} · {name} · {detail}")
        ok = ok and passed
    print(f"[verify system_design inputs SDUI] success={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
