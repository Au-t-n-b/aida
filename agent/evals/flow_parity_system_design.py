"""
system_design 流程一致性测试 · 原始 A3 skill vs LangGraph

对照 Raw Skill §14 测试场景，并行跑：
  - 原始 skill：a3-intelligent-network-opening/runtime/orchestrator.py
  - LangGraph：agent/skills/system_design/skill.py

用法：
  agent\\.venv\\Scripts\\python agent/evals/flow_parity_system_design.py
  agent\\.venv\\Scripts\\python agent/evals/flow_parity_system_design.py --scenario missing_inputs
  agent\\.venv\\Scripts\\python agent/evals/flow_parity_system_design.py --interactive
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# aida 根进 path
_AIDA_ROOT = Path(__file__).resolve().parents[2]
if str(_AIDA_ROOT) not in sys.path:
    sys.path.insert(0, str(_AIDA_ROOT))

A3_DATA_ROOT = Path(r"D:\h00503675\code\AIDA_test\new\a3-intelligent-network-opening")
A3_RUNTIME = A3_DATA_ROOT / "runtime"


@dataclass
class ScenarioResult:
    scenario_id: str
    title: str
    a3: dict[str, Any] = field(default_factory=dict)
    lg: dict[str, Any] = field(default_factory=dict)
    parity: str = "unknown"  # match | mismatch | partial | skip
    notes: list[str] = field(default_factory=list)


def _ok(cond: bool, label: str) -> tuple[bool, str]:
    return cond, ("PASS" if cond else "FAIL") + f" · {label}"


def _event_types(events: list[dict]) -> list[str]:
    return [str(e.get("event") or e.get("type") or "?") for e in events]


def _guidance(events: list[dict]) -> str:
    parts: list[str] = []
    for e in events:
        if e.get("event") == "chat.guidance":
            p = e.get("payload") or {}
            parts.append(str(p.get("content") or p.get("context") or ""))
    return "\n".join(parts)


def _import_a3_runtime():
    if str(A3_RUNTIME) not in sys.path:
        sys.path.insert(0, str(A3_RUNTIME))
    if str(A3_DATA_ROOT) not in sys.path:
        sys.path.insert(0, str(A3_DATA_ROOT))
    from orchestrator import run as a3_run  # noqa: E402
    from intent_router import recognize, NOT_NORMALIZED_MESSAGE  # noqa: E402
    return a3_run, recognize, NOT_NORMALIZED_MESSAGE


def _import_lg():
    os.environ["AIDA_CHECKPOINT"] = "memory"
    from agent.skills.system_design.skill import get_system_design_skill  # noqa: E402
    from agent.skills.system_design.pipelines.a3_bridge import resolve_execution_mode  # noqa: E402
    from agent.skills.system_design.pipelines.inputs import REQUIRED_DEFAULT, collect_inputs, missing_required  # noqa: E402
    from agent.skills.system_design.steps.intent_recognition import IntentRecognitionStep  # noqa: E402
    from agent.skills.system_design.a3_engine.runtime.input_checker import BASE_REQUIRED_INPUTS  # noqa: E402
    return (
        get_system_design_skill,
        resolve_execution_mode,
        REQUIRED_DEFAULT,
        BASE_REQUIRED_INPUTS,
        collect_inputs,
        missing_required,
        IntentRecognitionStep,
    )


def _run_lg_graph(
    skill,
    project: dict,
    thread_id: str,
    work_root: Path | None = None,
    *,
    isolate_data_root: bool = False,
) -> dict:
    if work_root:
        skill.work_root = work_root
        skill.work_root.mkdir(parents=True, exist_ok=True)
        if isolate_data_root:
            # collect_inputs 会优先扫 FIXED_INPUT_DIR（= get_a3_data_root()/Input）
            # 隔离测试时必须覆盖数据根，否则会读到样例工程里的真文件
            os.environ["SYSTEM_DESIGN_ROOT"] = str(work_root)
            os.environ["A3_ROOT"] = str(work_root)
    graph = skill.build_graph()
    init = {
        "run_id": thread_id,
        "skill_id": "system_design",
        "project": skill.initial_project(project),
        "steps": [],
        "logs": [],
        "overall_progress": 0,
    }
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(init, config)


def _lg_metrics(state: dict) -> dict:
    m: dict[str, Any] = {}
    for s in state.get("steps") or []:
        for k, v in (s.get("metrics") or {}).items():
            m[k] = v
    return m


def _make_stub_inputs(target: Path) -> None:
    """创建最小占位 xlsx（仅过门控，不保证规划计算成功）。"""
    try:
        from openpyxl import Workbook
    except ImportError:
        # 无 openpyxl 时创建空文件（collect_inputs 按后缀过滤）
        inp = target / "ProjectData" / "Input"
        inp.mkdir(parents=True, exist_ok=True)
        for name in (
            "项目信息收集表.xlsx",
            "建模仿真输出文档007-端口连线表.xlsx",
            "建模仿真输出文档001-设备信息表.xlsx",
            "建模仿真输出文档004-设备位置表.xlsx",
        ):
            (inp / name).write_bytes(b"")
        return

    inp = target / "ProjectData" / "Input"
    inp.mkdir(parents=True, exist_ok=True)
    stubs = {
        "项目信息收集表.xlsx": ["项目", "值"],
        "建模仿真输出文档007-端口连线表.xlsx": ["源设备", "目的设备", "端口"],
        "建模仿真输出文档001-设备信息表.xlsx": ["设备名", "角色"],
        "建模仿真输出文档004-设备位置表.xlsx": ["设备名", "机柜"],
    }
    for fname, headers in stubs.items():
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        wb.save(inp / fname)


# ── 场景实现 ─────────────────────────────────────────────────────────────

def scenario_missing_inputs(a3_run, get_skill, *_rest, **_kw) -> ScenarioResult:
    """§14 缺必需输入 → 补料 HITL，不执行规划。"""
    r = ScenarioResult("missing_inputs", "缺必需输入 → 补料 HITL")

    # A3: sd_start 无输入件
    ev = a3_run({"thread_id": "parity-missing", "action": "sd_start"}, skill_root=A3_DATA_ROOT)
    types = _event_types(ev)
    g = _guidance(ev)
    a3_hitl = "hitl.file_request" in types or "缺少" in g or "上传" in g
    r.a3 = {"hitl": a3_hitl, "events": types[:6], "guidance_snip": g[:200]}

    # LangGraph: 空 Input 目录（须在 import inputs 前覆盖数据根，否则 FIXED_INPUT_DIR 读到样例工程）
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "ProjectData" / "Input").mkdir(parents=True)
        os.environ["SYSTEM_DESIGN_ROOT"] = str(root)
        os.environ["A3_ROOT"] = str(root)
        import importlib
        from agent.skills.system_design.pipelines import inputs as inp_mod
        importlib.reload(inp_mod)
        skill = get_skill()
        skill.work_root = root
        state = _run_lg_graph(
            skill, {"text": "计算带外管理地址规划"}, "lg-missing", root,
        )
        hitl = state.get("hitl") or {}
        lg_hitl = hitl.get("step") == "input_check" and bool(hitl.get("need_files"))
        r.lg = {
            "hitl_step": hitl.get("step"),
            "need_files": hitl.get("need_files"),
            "current_step": state.get("current_step"),
        }

    if a3_hitl and lg_hitl:
        r.parity = "match"
    elif a3_hitl or lg_hitl:
        r.parity = "partial"
    else:
        r.parity = "mismatch"
    r.notes.append("期望：缺 4 件必选输入时均触发文件补料 HITL，且不进入平面规划")
    return r


def scenario_intent_standard(a3_run, get_skill, recognize, *_rest, **_kw) -> ScenarioResult:
    """§14 正常单条规划 · 意图：标准命令精准命中。"""
    r = ScenarioResult("intent_standard", "标准命令精准命中")
    cmd = "计算带外管理地址规划"

    ir = recognize(cmd)
    r.a3 = {"status": ir.status, "command": ir.command}

    skill = get_skill()
    step = IntentRecognitionStep()
    from agent.skills.base import SkillContext

    ctx = SkillContext(
        skill_id="system_design",
        work_root=skill.work_root,
        run_id="intent-std",
        project={"text": cmd},
        llm_factory=skill.llm_factory,
    )
    diff = step.run(ctx, {}, lambda m: None)
    m = diff.get("metrics") or {}
    r.lg = {"intent_command": m.get("intent_command"), "intent_status": m.get("intent_status")}

    if ir.status == "resolved" and ir.command == cmd and m.get("intent_command") == cmd:
        r.parity = "match"
    else:
        r.parity = "mismatch"
    r.notes.append("期望：两边均 RESOLVED 为同一标准命令")
    return r


def scenario_intent_unsupported(a3_run, get_skill, recognize, *_rest, **_kw) -> ScenarioResult:
    """§14 意图无法识别 · 防火墙互联（不支持范围）。"""
    r = ScenarioResult("intent_unsupported", "防火墙互联 → 不支持")
    raw = "帮我配防火墙互联"

    ir = recognize(raw)
    r.a3 = {"status": ir.status, "message_snip": (ir.message or "")[:120]}

    skill = get_skill()
    step = IntentRecognitionStep()
    from agent.skills.base import SkillContext

    ctx = SkillContext(
        skill_id="system_design",
        work_root=skill.work_root,
        run_id="intent-unsupported",
        project={"text": raw},
        llm_factory=skill.llm_factory,
    )
    diff = step.run(ctx, {}, lambda m: None)
    m = diff.get("metrics") or {}
    r.lg = {
        "intent_status": m.get("intent_status"),
        "intent_note": m.get("intent_note"),
        "intent_command": m.get("intent_command"),
    }

    # A3 driver 对 NL 返回 failed（需 Claw 先归一化）；LG 标记 failed/unsupported
    a3_fail = ir.status == "failed"
    lg_fail = m.get("intent_status") == "failed"
    r.parity = "match" if (a3_fail and lg_fail) else "partial"
    r.notes.append(
        "A3 driver 仅校验已归一化命令（NL→failed）；LangGraph 内置规则识别 unsupported→failed"
    )
    return r


def scenario_intent_rules(a3_run, get_skill, recognize, *_rest, **_kw) -> ScenarioResult:
    """口语经规则链归一化 · 对齐原始 lld-intent-recognition（intent-examples.md）。

    LangGraph 已内置原始 Claw 的确定性匹配链（精准/LLD/别名/关键词/消歧），
    逐条比对 examples.md 的期望输出。"""
    r = ScenarioResult("intent_rules", "规则链识别（对齐原始 examples）")
    # (输入, 期望状态, 期望命令)  —— 取自 intent-examples.md
    table = [
        ("交换机mlag规划", "resolved", "交换机MLAG规划"),
        ("生成LLD", "resolved", "生成完整LLD设计"),
        ("融合LLD设计", "resolved", "融合完整LLD设计"),
        ("计算带外管理面", "resolved", "计算带外管理地址规划"),
        ("存储业务面", "resolved", "存储业务面地址规划"),
        ("计算带外管理互联", "resolved", "计算带外管理互联规划"),
        ("交换机双活规划", "resolved", "交换机MLAG规划"),
        ("计算参数面IP规划", "resolved", "计算参数面地址规划"),
        ("帮我写一首诗", "failed", ""),
        ("帮我配防火墙互联", "failed", ""),
        ("LLD", "failed", ""),
    ]
    from agent.skills.base import SkillContext
    skill = get_skill()
    step = IntentRecognitionStep()

    rows = []
    ok = 0
    for raw, exp_status, exp_cmd in table:
        ctx = SkillContext(
            skill_id="system_design", work_root=skill.work_root, run_id="intent-rules",
            project={"text": raw}, llm_factory=None,  # 仅验证规则链（不触发 LLM 兜底）
        )
        diff = step.run(ctx, {}, lambda m: None)
        m = diff.get("metrics") or {}
        got_status = m.get("intent_status")
        got_cmd = m.get("intent_command", "")
        passed = (got_status == exp_status) and (exp_status != "resolved" or got_cmd == exp_cmd)
        ok += 1 if passed else 0
        rows.append({"in": raw, "exp": f"{exp_status}:{exp_cmd}", "got": f"{got_status}:{got_cmd}", "ok": passed})

    r.lg = {"passed": f"{ok}/{len(table)}", "rows": [x for x in rows if not x["ok"]] or "all pass"}
    r.a3 = {"note": "原始识别规则在 Claw lld-intent-recognition（MD）；LangGraph 已内置同一规则链"}
    r.parity = "match" if ok == len(table) else ("partial" if ok >= len(table) * 0.7 else "mismatch")
    r.notes.append("期望：LangGraph 规则链输出逐条对齐 intent-examples.md")
    return r


def scenario_intent_no_default(a3_run, get_skill, recognize, *_rest, **_kw) -> ScenarioResult:
    """核心改动 · 无法识别 → FAILED 固定话术，绝不降级默认命令。"""
    r = ScenarioResult("intent_no_default", "无法识别→FAILED（不降级默认）")
    from agent.skills.base import SkillContext
    skill = get_skill()
    step = IntentRecognitionStep()
    raw = "今天天气怎么样"
    ctx = SkillContext(
        skill_id="system_design", work_root=skill.work_root, run_id="intent-nodef",
        project={"text": raw}, llm_factory=None,
    )
    diff = step.run(ctx, {}, lambda m: None)
    m = diff.get("metrics") or {}
    hitl = diff.get("hitl") or {}
    r.lg = {
        "intent_status": m.get("intent_status"),
        "intent_command": m.get("intent_command", ""),
        "hitl_step": hitl.get("step"),
        "reason": (hitl.get("reason") or "")[:40],
    }
    # A3 原始：driver 对无法识别返回固定 FAILED 话术（不执行）
    ir = recognize(raw)
    r.a3 = {"status": ir.status, "message_snip": (ir.message or "")[:40]}

    lg_failed = (
        m.get("intent_status") == "failed"
        and not m.get("intent_command")        # 关键：没有降级成默认命令
        and hitl.get("step") == "intent_recognition"
    )
    a3_failed = ir.status == "failed"
    r.parity = "match" if (lg_failed and a3_failed) else "mismatch"
    r.notes.append("期望：两边均 FAILED；LangGraph 不再降级『生成完整LLD设计』，而是 HITL 等用户重输")
    return r


def scenario_intent_clarify(a3_run, get_skill, recognize, *_rest, **_kw) -> ScenarioResult:
    """多候选 → CLARIFYING 追问 HITL（不得擅自选定 · §13）。"""
    r = ScenarioResult("intent_clarify", "多候选→CLARIFYING 追问")
    from agent.skills.base import SkillContext
    from agent.skills.system_design.steps.intent_taxonomy import recognize as rule_recognize

    # 构造一个规则层多候选输入（带外管理面 + 地址/互联 并列）
    raw = "计算带外管理面地址还是互联"
    rm = rule_recognize(raw)
    skill = get_skill()
    step = IntentRecognitionStep()
    ctx = SkillContext(
        skill_id="system_design", work_root=skill.work_root, run_id="intent-clarify",
        project={"text": raw}, llm_factory=None,
    )
    diff = step.run(ctx, {}, lambda m: None)
    m = diff.get("metrics") or {}
    hitl = diff.get("hitl") or {}
    r.lg = {
        "rule_status": rm.status,
        "rule_candidates": rm.candidates,
        "intent_status": m.get("intent_status"),
        "hitl_step": hitl.get("step"),
        "need_inputs": bool(hitl.get("need_inputs")),
    }
    r.a3 = {"note": "原始 Claw：多候选输出一句追问话术（CLARIFYING），由会话层让用户选择"}
    lg_clarify = (
        m.get("intent_status") == "clarifying"
        and hitl.get("step") == "intent_recognition"
        and bool(hitl.get("need_inputs"))
    )
    r.parity = "match" if lg_clarify else ("partial" if rm.status == "clarifying" else "mismatch")
    r.notes.append("期望：多候选触发 CLARIFYING HITL（ChoiceCard 候选），不擅自选定")
    return r


def scenario_execution_mode(*_a, resolve_execution_mode=None, **_kw) -> ScenarioResult:
    """L1/L2/L3 执行模式映射（INTEGRATION.md ②）。"""
    r = ScenarioResult("execution_mode", "执行模式 single/batch/full")
    cases = {
        "计算带外管理地址规划": "single",
        "地址规划": "batch",
        "生成完整LLD设计": "full",
        "融合完整LLD设计": "full",
        "": "full",
    }
    results = {cmd: resolve_execution_mode(cmd) for cmd in cases}
    r.lg = results
    r.a3 = {"note": "原始 skill 为 dispatch 菜单式，无 sd_mode；等价为 action→command 直执"}
    ok = all(results[k] == v for k, v in cases.items())
    r.parity = "match" if ok else "mismatch"
    r.notes.append("LangGraph 独有：sd_mode 驱动 lld/ztp/naming 自跳过")
    return r


def scenario_required_inputs_count(*_a, REQUIRED_DEFAULT=None, BASE_REQUIRED_INPUTS=None, **_kw) -> ScenarioResult:
    """门控必选件数量一致性（A001）。"""
    r = ScenarioResult("required_inputs_count", "必选输入件数量")
    r.a3 = {"count": len(BASE_REQUIRED_INPUTS), "tags": list(BASE_REQUIRED_INPUTS)}
    r.lg = {"count": len(REQUIRED_DEFAULT), "tags": list(REQUIRED_DEFAULT)}
    if len(BASE_REQUIRED_INPUTS) == len(REQUIRED_DEFAULT):
        r.parity = "match"
    else:
        r.parity = "mismatch"
        r.notes.append(
            f"[WARN] 门控不一致：A3={len(BASE_REQUIRED_INPUTS)} 件，LangGraph REQUIRED_DEFAULT={len(REQUIRED_DEFAULT)} 件"
        )
    return r


def scenario_batch_mode(a3_run, get_skill, *_rest, **_kw) -> ScenarioResult:
    """一级批次「地址规划」→ batch 模式，菜单式直达 publish（真实输入件）。"""
    r = ScenarioResult("batch_mode", "一级批次 · 地址规划（直执即止）")
    skill = get_skill()
    state = _run_lg_graph(skill, {"text": "地址规划"}, "lg-batch-real", A3_DATA_ROOT)
    m = _lg_metrics(state)
    steps = {s.get("key"): s.get("status") for s in state.get("steps") or []}
    r.lg = {
        "sd_mode": m.get("sd_mode"),
        "plane_done": m.get("plane_done"),
        "steps": steps,
        "error": state.get("error"),
    }
    lg_ok = (
        m.get("sd_mode") == "batch"
        and steps.get("lld_integrate") == "skipped"
        and steps.get("publish") == "completed"
    )
    r.a3 = {"note": "原始 skill：地址规划 L1 → execute_dispatch 批次，跑完即止不串联 LLD"}
    r.parity = "match" if lg_ok else ("partial" if m.get("sd_mode") == "batch" else "mismatch")
    r.notes.append("期望：sd_mode=batch；批次跑完菜单式直达 publish，lld/ztp/naming skipped")
    return r


def scenario_happy_single_realdata(a3_run, get_skill, *_rest, **_kw) -> ScenarioResult:
    """§14 正常单条规划 · 使用样例工程真实 4 件输入。"""
    r = ScenarioResult("happy_single_realdata", "正常单条规划（真实输入件）")
    cmd = "计算带外管理地址规划"

    # A3: 直执 L3
    from input_checker import collect_inputs as a3_collect  # type: ignore

    found = a3_collect(A3_DATA_ROOT)
    r.a3["inputs_found"] = len(found)

    if len(found) < 4:
        r.parity = "skip"
        r.notes.append("样例工程 Input 不足 4 件，跳过")
        return r

    ev = a3_run(
        {"thread_id": "parity-happy-a3", "action": "run_command", "text": cmd},
        skill_root=A3_DATA_ROOT,
    )
    types = _event_types(ev)
    g = _guidance(ev)
    a3_exec = any(t in types for t in ("artifact.publish", "task_progress.sync")) and "缺少" not in g
    r.a3.update({"events_tail": types[-4:], "executed": a3_exec, "guidance_snip": g[:180]})

    skill = get_skill()
    state = _run_lg_graph(
        skill, {"text": cmd, "project_name": "parity-happy"}, "lg-happy-real", A3_DATA_ROOT,
    )
    m = _lg_metrics(state)
    steps = {s.get("key"): s.get("status") for s in state.get("steps") or []}
    r.lg = {
        "sd_mode": m.get("sd_mode"),
        "steps": steps,
        "plane_done": m.get("plane_done"),
        "lld_status": m.get("lld_status"),
        "error": state.get("error"),
        "hitl": state.get("hitl"),
    }

    # 菜单式直执即止：plane_planning 后 route_to publish，lld/ztp/naming 记 skipped
    lg_ok = (
        m.get("sd_mode") == "single"
        and steps.get("plane_planning") == "completed"
        and steps.get("lld_integrate") == "skipped"
        and steps.get("ztp_generate") == "skipped"
        and steps.get("naming_replace") == "skipped"
        and steps.get("publish") == "completed"
        and not state.get("hitl")
    )
    r.lg["route_aligned"] = lg_ok
    if a3_exec and lg_ok:
        r.parity = "match"
    elif a3_exec or lg_ok:
        r.parity = "partial"
    else:
        r.parity = "mismatch"
    r.notes.append("期望：单条 L3 执行后菜单式直达 publish；lld/ztp/naming 标记 skipped（原始 dispatch 不串联）")
    return r


SCENARIOS: dict[str, Callable[..., ScenarioResult]] = {
    "required_inputs_count": scenario_required_inputs_count,
    "intent_standard": scenario_intent_standard,
    "intent_unsupported": scenario_intent_unsupported,
    "intent_rules": scenario_intent_rules,
    "intent_no_default": scenario_intent_no_default,
    "intent_clarify": scenario_intent_clarify,
    "missing_inputs": scenario_missing_inputs,
    "execution_mode": scenario_execution_mode,
    "batch_mode": scenario_batch_mode,
    "happy_single_realdata": scenario_happy_single_realdata,
}


def run_all(selected: list[str] | None = None) -> list[ScenarioResult]:
    a3_run, recognize, NOT_NORMALIZED = _import_a3_runtime()
    (
        get_skill,
        resolve_execution_mode,
        REQUIRED_DEFAULT,
        BASE_REQUIRED_INPUTS,
        collect_inputs,
        missing_required,
        IntentRecognitionStep,
    ) = _import_lg()

    # 注入 IntentRecognitionStep 到 scenario 闭包（通过 globals 简化）
    globals()["IntentRecognitionStep"] = IntentRecognitionStep

    ids = selected or list(SCENARIOS.keys())
    results: list[ScenarioResult] = []
    for sid in ids:
        fn = SCENARIOS.get(sid)
        if not fn:
            continue
        try:
            res = fn(
                a3_run,
                get_skill,
                recognize,
                NOT_NORMALIZED,
                resolve_execution_mode=resolve_execution_mode,
                REQUIRED_DEFAULT=REQUIRED_DEFAULT,
                BASE_REQUIRED_INPUTS=BASE_REQUIRED_INPUTS,
                collect_inputs=collect_inputs,
                missing_required=missing_required,
            )
        except Exception as e:
            res = ScenarioResult(sid, sid, parity="skip", notes=[f"异常: {type(e).__name__}: {e}"])
        results.append(res)
    return results


def print_report(results: list[ScenarioResult]) -> int:
    print("=" * 60)
    print("system_design 流程一致性测试 · A3 skill vs LangGraph")
    print("=" * 60)
    fails = 0
    for r in results:
        icon = {"match": "OK", "partial": "~", "mismatch": "NG", "skip": "??", "unknown": "?"}.get(r.parity, "?")
        print(f"\n[{icon}] {r.scenario_id} · {r.title} · parity={r.parity}")
        if r.a3:
            print(f"    A3: {json.dumps(r.a3, ensure_ascii=False)[:300]}")
        if r.lg:
            print(f"    LG: {json.dumps(r.lg, ensure_ascii=False)[:300]}")
        for n in r.notes:
            print(f"    · {n}")
        if r.parity in ("mismatch", "skip"):
            fails += 1
    print("\n" + "=" * 60)
    match_n = sum(1 for r in results if r.parity == "match")
    partial_n = sum(1 for r in results if r.parity == "partial")
    print(f"合计 {len(results)} 场景 · match={match_n} · partial={partial_n} · mismatch/skip={fails}")
    return 1 if fails else 0


def interactive_loop() -> int:
    print("交互模式：输入场景 ID 运行（空行=全部，quit 退出）")
    print("可用:", ", ".join(SCENARIOS.keys()))
    while True:
        try:
            line = input("\nscenario> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.lower() in ("q", "quit", "exit"):
            break
        selected = [line] if line else None
        if selected and selected[0] not in SCENARIOS:
            print(f"未知场景: {line}")
            continue
        results = run_all(selected)
        print_report(results)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="A3 skill vs LangGraph 流程一致性测试")
    parser.add_argument("--scenario", "-s", action="append", help="只跑指定场景（可多次）")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互式逐场景测试")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args()

    if args.interactive:
        return interactive_loop()

    results = run_all(args.scenario)
    if args.json:
        payload = [
            {
                "scenario_id": r.scenario_id,
                "title": r.title,
                "parity": r.parity,
                "a3": r.a3,
                "lg": r.lg,
                "notes": r.notes,
            }
            for r in results
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return print_report(results)


if __name__ == "__main__":
    raise SystemExit(main())
