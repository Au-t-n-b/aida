"""A3 子 skill 进程内执行桥 · 统一调用 vendored a3 subskills 全部 offline pipeline。

策略（对齐 A3-MIGRATION-PLAN 铁律②）：
  - **不 subprocess**：在 step.run() 内通过 runpy 执行 entrypoint 脚本（等价于原 runtime/subprocess_runner，
    但在 AIDA 进程内完成，LangGraph trace 不断）。
  - **代码 vendored**：子 skill + runtime 已复制进 AIDA `system_design/a3_engine/`（见 a3_paths）。
  - 命令路由与 a3 一致：l3_skill_index.yaml + dispatch_tree.yaml + skill_registry.yaml。

两种执行入口：
  - run_command(intent)            ：执行单条 l3_skill_index 标准命令（②单命令 dispatch 基元）
  - run_dispatch(l1_or_l2_intent)  ：①整包接入 offline_dispatch_pipeline —— 用 a3 编排器
                                     plan（L2 策略 / pass_prior / 007 裁剪）后逐 task 进程内执行
"""
from __future__ import annotations

import os
import runpy
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .a3_paths import get_a3_root, get_runtime_root, get_subskills_root
from .a3_registry import (
    L3SkillDef, expand_dispatch, load_dispatch_tree, load_l3_index, resolve_package_dir,
)
from .inputs import collect_inputs
from .exec_log import append_log, extract_actionable_error
from .path_manifest import abs_artifacts_dir, abs_upload_dir, ensure_dir
from .sheet007_preflight import check_connect_sheet_preflight, is_skippable_007_error

_SKIP_OUTPUT_NAMES = frozenset({
    "dispatch_plan.json", "workflow_plan.json", "manifest.json",
    "steps.md", "a3_opening_result.md",
    "run_meta.csv", "scenario_detection.txt", "layer_detection.txt", "plane_detection.txt",
})

# 线性 DAG 默认：意图为「生成完整 LLD」时 plane_planning 跑地址批次
_DEFAULT_PLANE_BATCH = "地址规划"

# intent_command → L1 批次（无法直执 L3 时的回退）
_INTENT_TO_L1: dict[str, str] = {
    "地址规划": "地址规划",
    "互联规划": "互联规划",
    "接入规划": "接入规划",
    "网管规划": "网管规划",
    "生成完整LLD设计": _DEFAULT_PLANE_BATCH,
    "融合完整LLD设计": _DEFAULT_PLANE_BATCH,
}

_RUNTIME_BOOTSTRAPPED = False


@dataclass
class A3RunResult:
    command: str
    status: str  # ok | error | skipped
    summary: str = ""
    output_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    sub_skill: str = ""
    log_tail: str = ""


def _bootstrap_a3_runtime() -> None:
    """把 a3 runtime/ 加入 sys.path，供 argv_builder / registry_loader 复用。"""
    global _RUNTIME_BOOTSTRAPPED
    if _RUNTIME_BOOTSTRAPPED:
        return
    for p in (get_runtime_root(), get_subskills_root()):
        sp = str(p.resolve())
        if p.is_dir() and sp not in sys.path:
            sys.path.insert(0, sp)
    _RUNTIME_BOOTSTRAPPED = True


def _collect_outputs(out_dir: Path) -> list[Path]:
    patterns = (".xlsx", ".xls", ".md", ".docx", ".json", ".zip")
    if not out_dir.is_dir():
        return []
    return sorted(
        p for p in out_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in patterns
        and p.name not in _SKIP_OUTPUT_NAMES
        and "计算参数面网段规划" not in p.name
        and not p.name.startswith("~$")
    )


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _copy_products_to_output(sources: list[Path], out_dir: Path) -> list[Path]:
    """对齐原始 runtime/l3_executor：仅把子 pipeline 声明的产物拷入 Output 并加时间戳。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = _timestamp()
    copied: list[Path] = []
    for src in sources:
        if not src.is_file():
            continue
        dst = out_dir / f"{src.stem}_{ts}{src.suffix}"
        if dst.exists():
            stem, suffix = dst.stem, dst.suffix
            n = 2
            while dst.exists():
                dst = out_dir / f"{stem}_{n}{suffix}"
                n += 1
        shutil.copy2(src, dst)
        copied.append(dst.resolve())
    return copied


def _pipeline_products(raw_dir: Path, args_style: str, command: str) -> list[Path]:
    """从隔离工作目录收集 ZTP/灵衢 子 skill 产物（不含 LLD 融合件）。"""
    if not raw_dir.is_dir():
        return []
    cmd = (command or "").strip()
    found: list[Path] = []
    if args_style == "ztp_scan":
        # 生成ZTP配置文件 → zip（L1/L2 cfg + ztp.ini）；前置链式生成的 ZTP_LLD.xlsx 是中间件，不能当本命令产物。
        if cmd == "生成ZTP配置文件":
            zips = [
                p.resolve()
                for p in sorted(
                    raw_dir.rglob("*.zip"),
                    key=lambda x: x.stat().st_mtime if x.is_file() else 0,
                )
                if p.is_file()
                and not p.name.startswith("~$")
                and "ZTP" in p.name.upper()
            ]
            return zips[-1:] if zips else []
        # 生成ZTP设计文件 → ZTP_LLD.xlsx
        for p in sorted(raw_dir.rglob("*")):
            if not p.is_file() or p.name.startswith("~$"):
                continue
            upper = p.name.upper()
            if p.suffix.lower() in (".xlsx", ".xls") and "ZTP" in upper and "LLD" in upper:
                found.append(p.resolve())
        if not found:
            for p in sorted(raw_dir.rglob("ZTP_LLD.xlsx")):
                if p.is_file():
                    found.append(p.resolve())
    elif args_style == "lq_open_scan":
        for p in sorted(raw_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".zip", ".json"):
                found.append(p.resolve())
    if found:
        return found
    # 兜底：run_* 子目录内最新匹配扩展名（排除 LLD 设计项目文件）
    for p in sorted(raw_dir.rglob("*"), key=lambda x: x.stat().st_mtime if x.is_file() else 0, reverse=True):
        if not p.is_file() or p.name.startswith("~$"):
            continue
        upper = p.name.upper()
        if "LLD设计" in upper and "ZTP" not in upper:
            continue
        if args_style == "ztp_scan" and p.suffix.lower() in (".xlsx", ".xls") and "ZTP" in upper:
            return [p.resolve()]
        if args_style == "lq_open_scan" and p.suffix.lower() in (".zip", ".json"):
            return [p.resolve()]
    return []


def _resolve_io_paths(work_root: Path) -> dict[str, Path | None]:
    _ = work_root
    found = collect_inputs()
    topo = found.get("Interconnection_Relationship")
    resource = found.get("resource")
    loc = found.get("Location_Information")
    out_dir = abs_artifacts_dir()
    return {
        "topology": topo.path if topo else None,
        "resource": resource.path if resource else None,
        "location_004": loc.path if loc else None,
        "out_dir": out_dir,
        # scan_dir 必须覆盖全部输入来源：新路径把 007/001/004 放 xmfz、resource 放 input、
        # 规划产物落 output，分散在 data_root 的不同子目录。ztp_scan / lq_open_scan / input_check
        # 子 skill 按 scan_dir 递归 rglob 查找输入件，故取 data_root（input/xmfz/output 的共同父目录）；
        # 只扫 abs_upload_dir()（input）会漏掉 xmfz 的 004 设备位置表与 output 的规划产物 → ZTP 报缺件。
        "scan_dir": get_a3_root(),
    }


def _find_artifact(out_dir: Path, *patterns: str) -> Path | None:
    if not out_dir.is_dir():
        return None
    for pat in patterns:
        for p in sorted(out_dir.rglob("*")):
            if p.is_file() and pat in p.name and not p.name.startswith("~$"):
                return p
    return None


def run_command(
    intent: str,
    work_root: Path | str,
    *,
    emit: Callable[[str], None] | None = None,
    pass_prior: list[str] | None = None,
) -> A3RunResult:
    """执行一条 l3_skill_index 标准命令（进程内 runpy）。"""
    root = Path(work_root).resolve()
    cmd = (intent or "").strip()
    res = A3RunResult(command=cmd, status="error", summary=f"未执行：{cmd}")

    if not get_a3_root().is_dir():
        res.errors.append(f"A3 工程不存在：{get_a3_root()}")
        res.summary = "A3 工程路径无效"
        append_log(root, res.summary, level="ERROR", command=cmd, detail=res.errors[0])
        return res

    index = load_l3_index()
    skill = index.get(cmd)
    if skill is None:
        res.errors.append(f"unknown intent: {cmd}")
        res.summary = f"未在 l3_skill_index 注册：{cmd}"
        return res
    if skill.unsupported or skill.pending:
        res.status = "skipped"
        res.summary = skill.note or f"`{cmd}` 标记为 unsupported/pending"
        return res
    if not skill.package or not skill.entrypoint:
        res.errors.append("missing package/entrypoint")
        res.summary = f"`{cmd}` 缺少 package/entrypoint"
        return res

    package_dir = resolve_package_dir(skill.package)
    entrypoint = (package_dir / skill.entrypoint).resolve()
    if not entrypoint.is_file():
        res.errors.append(f"missing entrypoint: {entrypoint}")
        res.summary = f"未找到脚本：{entrypoint}"
        return res

    io = _resolve_io_paths(root)
    out_dir: Path = io["out_dir"]  # type: ignore[assignment]
    ensure_dir(out_dir)

    _bootstrap_a3_runtime()
    try:
        from argv_builder import build_argv, find_prior_paths, _find_access_plan  # a3 runtime
        from registry_loader import L3SkillDef as _A3Def  # noqa: F401 — 类型兼容
    except ImportError as e:
        res.errors.append(f"无法加载 a3 runtime：{e}")
        res.summary = "a3 runtime 导入失败"
        append_log(root, res.summary, level="ERROR", command=cmd, exc=e)
        return res

    # 接入查询类命令强依赖 A3网络设备接入规划.xlsx；缺失时提前失败并写日志（避免 13 条连环 FileNotFoundError）
    if skill.args_style == "access_query":
        prior_paths = find_prior_paths(out_dir, list(pass_prior or []))
        access_plan = prior_paths.get("prior_access") or _find_access_plan(out_dir)
        if not access_plan.is_file():
            msg = (
                f"缺少接入规划底表 {access_plan.name}（路径：{access_plan}）。"
                "请先执行「地址规划」批次生成该文件，再执行网络接入规划。"
            )
            res.errors.append(msg)
            res.summary = msg
            append_log(root, msg, level="ERROR", command=cmd)
            return res

    # 007 端口互联 sheet 缺失 → 跳过该平面（不执行子 skill、不报错）
    should_run, skip_reason = check_connect_sheet_preflight(
        command=cmd,
        args_style=skill.args_style,
        topology=io["topology"],  # type: ignore[arg-type]
        default_sheet=skill.default_sheet,
    )
    if not should_run:
        res.status = "skipped"
        res.summary = skip_reason
        append_log(root, skip_reason, level="INFO", command=cmd)
        if emit:
            _safe_emit(emit, f"[a3] - {cmd} 跳过 · {skip_reason}")
        return res

    # argv_builder 期望 registry_loader.L3SkillDef；字段一致，构造兼容对象
    a3_skill = skill  # 字段对齐，build_argv 只读属性

    ztp_lld = _find_artifact(out_dir, "ZTP_LLD")
    lld_design = _find_artifact(out_dir, "LLD设计", "-LLD设计-")
    device_list = _find_artifact(out_dir, "设备清单")
    name_mapping = _find_artifact(out_dir, "命名映射", "naming")

    # ZTP/灵衢：对齐原始 runtime/l3_executor —— 子 pipeline 写入隔离目录，仅拷贝声明产物到 Output
    raw_work: Path | None = None
    exec_out_dir = out_dir
    if skill.args_style in ("ztp_scan", "lq_open_scan"):
        raw_work = Path(tempfile.mkdtemp(prefix="aida_ztp_", dir=str(root)))
        exec_out_dir = raw_work

    argv = build_argv(
        a3_skill,  # type: ignore[arg-type]
        cmd,
        exec_out_dir,
        topology=io["topology"],
        resource=io["resource"],
        pass_prior=pass_prior,
        scan_dir=io["scan_dir"],
        ztp_lld=ztp_lld,
        name_mapping=name_mapping,
        device_list=device_list,
        lld_design=lld_design,
        location_004=io["location_004"],
    )

    if emit:
        _safe_emit(emit, f"[a3] > {cmd} · {package_dir.name}/{entrypoint.name}")
        if argv:
            _safe_emit(emit, f"[a3]   argv: {' '.join(argv[:8])}{'…' if len(argv) > 8 else ''}")

    before_mtimes = {
        str(p.resolve()): p.stat().st_mtime
        for p in _collect_outputs(out_dir)
    }
    old_cwd = os.getcwd()
    old_argv = sys.argv[:]
    old_path = sys.path[:]
    exit_code = 0
    log_buf: list[str] = []
    copied_products: list[Path] = []

    # 捕获 pipeline print 到 log_tail（best-effort）
    class _Tee:
        def __init__(self, stream: Any):
            self._stream = stream
        def write(self, s: str) -> int:
            if s.strip():
                log_buf.append(s.rstrip())
            return self._stream.write(s)
        def flush(self) -> None:
            self._stream.flush()

    scripts_dir = str(entrypoint.parent.resolve())
    try:
        # 对齐 a3 subprocess_runner：cwd=skill_root（数据根），否则 pipeline 的
        # require_under_cwd(007/resource) 会因路径不在 cwd 下而 exit=1。
        os.chdir(str(root))
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        sys.argv = [entrypoint.name, *argv]
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = _Tee(old_stdout)  # type: ignore[assignment]
        sys.stderr = _Tee(old_stderr)  # type: ignore[assignment]
        try:
            runpy.run_path(str(entrypoint), run_name="__main__")
        except SystemExit as se:
            exit_code = int(se.code) if isinstance(se.code, int) else (0 if se.code is None else 1)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    except Exception as e:  # noqa: BLE001
        exit_code = 1
        res.errors.append(f"{type(e).__name__}: {e}")
    finally:
        os.chdir(old_cwd)
        sys.argv = old_argv
        sys.path = old_path

    # 对齐原始 runtime/l3_executor：子 pipeline 写入隔离目录 → 先拷贝声明产物到 Output，再清理
    if exit_code == 0 and raw_work is not None:
        products = _pipeline_products(raw_work, skill.args_style, cmd)
        if products:
            copied_products = _copy_products_to_output(products, out_dir)

    if raw_work is not None:
        shutil.rmtree(raw_work, ignore_errors=True)

    if copied_products:
        new_files = [str(p) for p in copied_products]
    else:
        after = _collect_outputs(out_dir)
        new_files = []
        for p in after:
            key = str(p.resolve())
            mtime = p.stat().st_mtime
            prev = before_mtimes.get(key)
            if prev is None or mtime > prev + 0.001:
                new_files.append(key)

    res.sub_skill = package_dir.name
    res.log_tail = "\n".join(log_buf[-20:])
    res.output_files = new_files

    if exit_code != 0:
        actionable = extract_actionable_error(log_tail=res.log_tail, errors=res.errors)
        if is_skippable_007_error(actionable):
            res.status = "skipped"
            res.summary = f"007 缺少对应 sheet，跳过 `{cmd}`"
            res.errors = [actionable]
            append_log(root, res.summary, level="INFO", command=cmd, detail=actionable)
            if emit:
                _safe_emit(emit, f"[a3] - {cmd} 跳过 · {actionable[:120]}")
            return res
        res.status = "error"
        res.summary = f"`{cmd}` 执行失败（exit={exit_code}）"
        res.errors = [actionable]
        append_log(
            root, res.summary, level="ERROR", command=cmd,
            detail=actionable + ("\n--- log_tail ---\n" + res.log_tail if res.log_tail else ""),
        )
        return res

    if not new_files and skill.args_style not in ("input_check", "lld_generate"):
        res.status = "error"
        res.summary = f"`{cmd}` 完成但未发现新产物"
        res.errors.append("empty output")
        append_log(root, res.summary, level="ERROR", command=cmd, detail=res.log_tail)
        return res

    res.status = "ok"
    res.summary = f"`{cmd}` 完成，产物 {len(new_files)} 个"
    append_log(root, res.summary, level="INFO", command=cmd)
    if emit:
        _safe_emit(emit, f"[a3] OK {res.summary}")
    return res


def run_commands(
    commands: list[str],
    work_root: Path | str,
    *,
    emit: Callable[[str], None] | None = None,
    keep_going: bool = True,
) -> list[A3RunResult]:
    """串行执行多条 L3 命令（keep_going=True 对齐 a3 dispatch keep-going）。"""
    results: list[A3RunResult] = []
    for cmd in commands:
        r = run_command(cmd, work_root, emit=emit)
        results.append(r)
        if r.status == "error" and not keep_going:
            break
    return results


def resolve_plan_commands(intent_command: str | None) -> list[str]:
    """根据 intent_recognition 归一化命令，解析 plane_planning 应执行的 L3 列表（兜底用）。"""
    cmd = (intent_command or "").strip()
    index = load_l3_index()

    if cmd in index and not index[cmd].unsupported and not index[cmd].pending:
        if cmd in ("生成完整LLD设计", "融合完整LLD设计"):
            return expand_dispatch(_DEFAULT_PLANE_BATCH)
        return [cmd]

    l1 = _INTENT_TO_L1.get(cmd)
    if l1:
        expanded = expand_dispatch(l1)
        if expanded:
            return expanded

    return expand_dispatch(_DEFAULT_PLANE_BATCH)


# ── ① L1/L2 dispatch 编排器整包接入（offline_dispatch_pipeline）────────────────────

# intent_command → dispatch 锚点（L1/L2 标准命令，喂给 a3 编排器 expand_dispatch）
_INTENT_TO_DISPATCH_ANCHOR: dict[str, str] = {
    "生成完整LLD设计": "地址规划",
    "融合完整LLD设计": "地址规划",
    "地址规划": "地址规划",
    "互联规划": "互联规划",
    "接入规划": "接入规划",
    "网管规划": "网管规划",
    "路由规划": "路由规划",
}


def build_dispatch_plan(anchor_intent: str, work_root: Path | str) -> dict[str, Any]:
    """调用 vendored a3 编排器 plan_dispatch，得到 L2 分相 + task 计划（不执行）。

    复用 a3 原版 dispatch_expander：含 L2 策略（children/direct/nested）、pass_prior、
    按 l3_skill_index/entrypoint 存在性裁剪 —— 整包接入而非自己摊平 YAML。
    """
    root = Path(work_root).resolve()
    io = _resolve_io_paths(root)
    out_dir: Path = io["out_dir"]  # type: ignore[assignment]
    ensure_dir(out_dir)

    _bootstrap_a3_runtime()
    from dispatch_runner import plan_dispatch  # vendored a3 runtime

    topo = io["topology"]
    resource = io["resource"]
    if topo is None or resource is None:
        return {
            "anchor_intent": anchor_intent,
            "phases": [],
            "errors": ["缺少 007 端口连线表或项目信息收集表，无法规划 dispatch 批次"],
        }

    return plan_dispatch(
        anchor_intent,
        capability_root=get_subskills_root(),
        topology=topo,            # type: ignore[arg-type]
        resource=resource,        # type: ignore[arg-type]
        out_dir=out_dir,
    )


def run_dispatch(
    anchor_intent: str,
    work_root: Path | str,
    *,
    emit: Callable[[str], None] | None = None,
    keep_going: bool = True,
) -> tuple[list[A3RunResult], dict[str, Any]]:
    """① 整包接入：按 a3 编排器 plan 的 phase/task 顺序，进程内执行各 L3 子 skill。

    返回 (results, plan)。plan 保留 a3 编排器的 phase/pass_prior/skipped/errors 结构，
    供 SDUI 投影批次进度。执行用进程内 run_command（不 subprocess）。
    """
    plan = build_dispatch_plan(anchor_intent, work_root)
    results: list[A3RunResult] = []

    if plan.get("errors") and not plan.get("phases"):
        if emit:
            emit(f"[dispatch] ✗ 规划失败：{plan['errors']}")
        return results, plan

    phases = plan.get("phases") or []
    total_ready = sum(
        1 for ph in phases for t in (ph.get("tasks") or []) if t.get("status") == "ready"
    )
    if emit:
        emit(f"[dispatch] 锚点「{plan.get('anchor_intent', anchor_intent)}」→ "
             f"{len(phases)} 个 L2 相 / {total_ready} 个可执行 L3")

    for phase in phases:
        l2 = phase.get("l2_intent", "")
        pass_prior = list(phase.get("pass_prior") or [])
        for task in phase.get("tasks") or []:
            intent = str(task.get("intent", ""))
            if task.get("status") != "ready":
                note = task.get("note") or task.get("status")
                results.append(A3RunResult(
                    command=intent, status="skipped",
                    summary=f"[{l2}] 跳过：{note}",
                ))
                if emit:
                    emit(f"[dispatch] ○ {intent} 跳过（{note}）")
                continue
            r = run_command(intent, work_root, emit=emit, pass_prior=pass_prior)
            results.append(r)
            if r.status == "error" and not keep_going:
                if emit:
                    emit(f"[dispatch] ✗ 在 {intent} 处中断（keep_going=False）")
                return results, plan

    ok_n = sum(1 for r in results if r.status == "ok")
    if emit:
        emit(f"[dispatch] ✓ 批次完成：{ok_n}/{len(results)} 步成功")
    return results, plan


def _dispatch_anchors() -> set[str]:
    """dispatch_tree 中全部合法批次锚点：L1（顶层）+ L2（次级）。
    用于把「网络接入规划 / 网络互联规划 / 带外管理地址规划」等 L2 聚合命令识别为批次锚点，
    而非误判为未知命令兜底到完整 LLD（对齐原始 a3 dispatch 编排器：L1/L2 均可作锚点展开）。"""
    tree = load_dispatch_tree()
    anchors: set[str] = set()
    for l1, subtree in (tree or {}).items():
        if l1:
            anchors.add(str(l1))
        if isinstance(subtree, dict):
            anchors.update(str(k) for k in subtree if k)
    return anchors


def resolve_dispatch_anchor(intent_command: str | None) -> str:
    """intent_command → dispatch 锚点（L1/L2）。
    1) 显式映射（生成完整LLD设计 → 地址规划 等）；
    2) 命令本身就是 dispatch_tree 的 L1/L2 锚点（如 网络接入规划）→ 直接用它展开对应子树；
    3) 兜底地址规划。"""
    cmd = (intent_command or "").strip()
    if cmd in _INTENT_TO_DISPATCH_ANCHOR:
        return _INTENT_TO_DISPATCH_ANCHOR[cmd]
    if cmd in _dispatch_anchors():
        return cmd
    # 按规划类型推断 L1 锚点（聚合命令未直接命中 tree 时，仍走对应类别批次，
    # 不再一律兜底地址规划：如「带外管理互联规划」→ 互联规划批次）
    if "互联" in cmd:
        return "互联规划"
    if "接入" in cmd:
        return "接入规划"
    if "ASN" in cmd or "路由" in cmd:
        return "路由规划"
    if any(k in cmd for k in ("CCAE", "NCE", "DME", "网管")):
        return "网管规划"
    return "地址规划"


# ── ② intent_command 驱动的单命令 dispatch 模式 ────────────────────────────────────

# 完整交付（跑完 LLD/ZTP/命名/发布）的意图
_FULL_DELIVERY_INTENTS = frozenset({
    "生成完整LLD设计", "融合完整LLD设计",
})
# L1 批次意图（dispatch 一组 L3，跑完即止，不进 LLD 融合）
_L1_BATCH_INTENTS = frozenset(_INTENT_TO_DISPATCH_ANCHOR.keys()) - _FULL_DELIVERY_INTENTS


def resolve_execution_mode(intent_command: str | None) -> str:
    """决定 system_design 本次 run 的执行模式（驱动下游 step 是否自跳过）。

    返回：
      'full'   ：完整交付一条龙（plane→lld→ztp→naming→publish）
      'batch'  ：L1/L2 批次 dispatch（仅平面规划，跑完即发布）
      'single' ：单条 L3 命令（菜单式触发，仅执行该命令，跑完即发布）
    """
    cmd = (intent_command or "").strip()
    # 完整交付仅限：无指令（建模仿真串联直跑）或显式「生成/融合完整 LLD」
    if not cmd or cmd in _FULL_DELIVERY_INTENTS:
        return "full"
    # 可直执的单条 L3 命令（菜单式触发）
    index = load_l3_index()
    skill = index.get(cmd)
    if skill is not None and not skill.unsupported and not skill.pending:
        return "single"
    # L1 / L2 批次锚点（地址规划 / 互联规划 / 网络接入规划 / 网络互联规划 …）→ 批次 dispatch
    if cmd in _L1_BATCH_INTENTS or cmd in _dispatch_anchors():
        return "batch"
    # 兜底：作为批次锚点交编排器判定（展不开则无任务、停在 LLD 生成阶段），
    # 严禁未知命令直接兜底到完整 LLD（否则第二条指令会被误执行成生成 LLD）。
    return "batch"


# ── 接入规划前置：A3网络设备接入规划.xlsx 由地址规划副产物 emit_for_plane 生成 ──────
# 原始 skill 业务逻辑：接入规划是对「A3网络设备接入规划.xlsx」的按平面查询，该底表在
# 地址规划各平面 pipeline 内通过 emit_for_plane 累积生成。故执行接入规划前若底表缺失，
# 需先跑地址规划批次补齐，否则每条接入查询都会 FileNotFoundError（整步失败）。
_ACCESS_PLAN_FILENAME = "A3网络设备接入规划.xlsx"
_CSM_ADDR_MARKERS = ("A3计算参数面地址规划",)
_CPM_ADDR_MARKERS = ("A3超平面网络规划", "超平面网络规划")
_PARAM_SHEET = "参数面端口互联"
_HYPER_SHEET = "超平面端口互联"
# Output 已有平面地址表但缺接入底表时，按 (地址表文件名关键词, plane_key, 007 sheet) 补写 emit
_ACCESS_EMIT_SPECS: tuple[tuple[str, str, str], ...] = (
    ("A3计算参数面地址规划", "计算参数面", "参数面端口互联"),
    ("A3计算管理面地址规划", "计算管理面", "计算管理面端口互联"),
    ("A3计算业务面地址规划", "计算业务面", "计算业务面端口互联"),
    ("A3计算样本面地址规划", "计算样本面", "存储面端口互联"),
    ("A3计算管存面地址规划", "计算管存面", "计算管存面端口互联"),
    ("A3存储管理面地址规划", "存储管理面", "存储管理面端口互联"),
    ("A3存储业务面地址规划", "存储业务面", "存储业务面端口互联"),
    ("A3存储样本面地址规划", "存储样本面", "样本面端口互联"),
    ("A3计算带外管理面地址规划", "计算带外管理面", "计算带外管理面端口互联"),
    ("A3存储带外管理面地址规划", "存储带外管理面", "存储带外管理面端口互联"),
    ("A3网络带外管理面地址规划", "网络带外管理面", "网络带外管理面端口互联"),
    ("A3灵衢带外管理面地址规划", "灵衢带外管理面", "灵衢带外管理面端口互联"),
)


def _safe_emit(emit: Callable[[str], None] | None, msg: str) -> None:
    """Windows 控制台/SSE 推送时避免 emoji 导致编码异常中断整批 dispatch。"""
    if not emit:
        return
    try:
        emit(msg)
    except (UnicodeEncodeError, UnicodeError):
        emit(
            msg.replace("\u25b6", ">")
            .replace("\u2713", "OK")
            .replace("\u25cb", "-")
            .replace("\u274c", "X")
            .replace("\u26a0", "!")
        )


def _007_sheet_names(topology: Path | None) -> set[str]:
    if topology is None or not topology.is_file():
        return set()
    try:
        import pandas as pd

        return set(pd.ExcelFile(topology).sheet_names)
    except Exception:
        return set()


def _output_has_markers(out_dir: Path, markers: tuple[str, ...]) -> bool:
    if not out_dir.is_dir():
        return False
    for p in out_dir.rglob("*.xlsx"):
        if not p.is_file() or p.name.startswith("~$"):
            continue
        if any(m in p.name for m in markers):
            return True
    return False


def ensure_plane_address_repairs(
    work_root: Path | str,
    *,
    emit: Callable[[str], None] | None = None,
) -> list[A3RunResult]:
    """007 含参数面/超平面 sheet 但 Output 缺对应 A3 规划表时，强制补跑单条 L3 命令。"""
    root = Path(work_root).resolve()
    io = _resolve_io_paths(root)
    out_dir: Path = io["out_dir"]  # type: ignore[assignment]
    sheets = _007_sheet_names(io.get("topology"))  # type: ignore[arg-type]
    repairs: list[A3RunResult] = []

    if _PARAM_SHEET in sheets and not _output_has_markers(out_dir, _CSM_ADDR_MARKERS):
        msg = "007 含「参数面端口互联」但 Output 缺少 A3 参数面规划表，补跑「计算参数面地址规划」"
        append_log(root, msg, level="WARN", command="计算参数面地址规划")
        _safe_emit(emit, f"[plane-repair] {msg}")
        repairs.append(run_command("计算参数面地址规划", root, emit=emit))

    if _HYPER_SHEET in sheets and not _output_has_markers(out_dir, _CPM_ADDR_MARKERS):
        msg = "007 含「超平面端口互联」但 Output 缺少超平面规划表，补跑「计算超平面地址规划」"
        append_log(root, msg, level="WARN", command="计算超平面地址规划")
        _safe_emit(emit, f"[plane-repair] {msg}")
        repairs.append(run_command("计算超平面地址规划", root, emit=emit))

    return repairs


def rebuild_access_plan_from_outputs(
    work_root: Path | str,
    *,
    emit: Callable[[str], None] | None = None,
) -> bool:
    """地址规划产物已在 Output 但缺 ``A3网络设备接入规划.xlsx`` 时，按已有平面地址表补写接入底表。"""
    root = Path(work_root).resolve()
    if access_plan_exists(root):
        return True
    io = _resolve_io_paths(root)
    topo = io.get("topology")
    out_dir: Path = io["out_dir"]  # type: ignore[assignment]
    if topo is None or not out_dir.is_dir():
        return False

    sheets = _007_sheet_names(topo)  # type: ignore[arg-type]
    _bootstrap_a3_runtime()
    sp = str(get_subskills_root())
    if sp not in sys.path:
        sys.path.insert(0, sp)
    try:
        import pandas as pd
        from _runtime_shared.network_access_plan import (  # noqa: WPS433
            emit_for_plane,
            filter_assignable_address_rows,
        )
    except ImportError as e:
        append_log(root, f"接入底表补写失败：无法加载 network_access_plan（{e}）", level="ERROR")
        return False

    emitted = False
    for addr_marker, plane_key, sheet in _ACCESS_EMIT_SPECS:
        if sheet not in sheets:
            continue
        candidates = [
            p for p in out_dir.rglob("*.xlsx")
            if p.is_file() and addr_marker in p.name and not p.name.startswith("~$")
        ]
        if not candidates:
            continue
        addr_path = max(candidates, key=lambda p: p.stat().st_mtime)
        try:
            ip_df = pd.read_excel(addr_path, sheet_name=0)
        except Exception as exc:
            append_log(
                root,
                f"接入底表补写跳过 {plane_key}：无法读取 {addr_path.name}（{exc}）",
                level="WARN",
            )
            continue
        msg = f"补写接入底表：{plane_key} ← {addr_path.name}"
        append_log(root, msg, level="INFO", command="A3网络设备接入规划")
        _safe_emit(emit, f"[access-rebuild] {msg}")
        emit_for_plane(
            out_dir,
            plane_key=plane_key,
            connect_path=Path(topo),  # type: ignore[arg-type]
            connect_sheet=sheet,
            address_df=filter_assignable_address_rows(ip_df),
            search_dirs=[out_dir],
        )
        emitted = True

    if access_plan_exists(root):
        append_log(root, "接入底表 A3网络设备接入规划.xlsx 已补写完成", level="INFO")
        _safe_emit(emit, "[access-rebuild] A3网络设备接入规划.xlsx 已生成")
        return True
    if emitted:
        append_log(root, "接入底表补写已执行但未生成文件（可能无有效接入行）", level="WARN")
    return False


def access_plan_exists(work_root: Path | str) -> bool:
    _ = work_root
    out_dir = abs_artifacts_dir()
    return bool(out_dir.is_dir() and any(out_dir.rglob(_ACCESS_PLAN_FILENAME)))


def intent_needs_access_plan(intent_command: str | None) -> bool:
    """该意图是否依赖接入规划底表（接入规划 / 含「接入」的单命令）。"""
    return "接入" in (intent_command or "")


def ensure_access_plan(
    work_root: Path | str,
    *,
    emit: Callable[[str], None] | None = None,
) -> list[A3RunResult]:
    """接入规划前置补齐：底表缺失则先跑「地址规划」批次生成 A3网络设备接入规划.xlsx。
    返回补齐过程的地址规划结果（用于并入产物/进度展示）；底表已存在则返回空列表。"""
    root = Path(work_root).resolve()
    if access_plan_exists(root):
        return []
    if emit:
        emit(f"[access] 缺少 {_ACCESS_PLAN_FILENAME}（接入规划底表），先执行「地址规划」批次补齐")
    append_log(root, f"缺少 {_ACCESS_PLAN_FILENAME}，启动地址规划批次前置补齐", level="WARN")
    results, _plan = run_dispatch("地址规划", root, emit=emit, keep_going=True)
    ok = sum(1 for r in results if r.status == "ok")
    if access_plan_exists(root):
        append_log(root, f"地址规划前置补齐完成：{ok}/{len(results)} 步成功，底表已生成", level="INFO")
    else:
        errs = [f"{r.command}: {(r.errors or [''])[0]}" for r in results if r.status == "error"]
        append_log(
            root,
            f"地址规划前置补齐完成但底表仍缺失：{ok}/{len(results)} 步成功",
            level="ERROR",
            detail="\n".join(errs[:15]) if errs else None,
        )
    if emit:
        emit(f"[access] 地址规划前置补齐完成：{ok}/{len(results)} 步成功"
             f"（底表{'已生成' if access_plan_exists(root) else '仍缺失'}）")
    return results
