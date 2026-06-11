"""address_plan pipeline · 地址批规划（进程内，无 subprocess）。

策略：各平面的 a3 源码 pipeline 函数（generate_*_xlsx）通过 importlib + 临时 sys.path
直接调用 ——  不涉及 LLM，全是确定性计算（IP allocate / segment_rules），符合 AGENTS.md 铁律。
等 a3 子能力完全搬入 xtsj/pipelines/ 后再删除 importlib 路径魔法。

每个「平面」用 PlaneSpec 描述；run_plane() 执行并返回 PlaneResult。
"""
from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── 工作区路径解析 ────────────────────────────────────────────────────────────

def _a3_subskill_root() -> Path | None:
    """返回 a3-intelligent-network-opening 子技能根目录（subskills/），不存在返回 None。"""
    import os
    raw = os.environ.get("A3_ROOT", "").strip()
    if raw:
        p = Path(raw)
    else:
        # 默认路径：桌面工程 或 nanobot workspace
        candidates = [
            Path.home() / "Desktop" / "a3-intelligent-network-opening" / "a3-intelligent-network-opening",
            Path.home() / ".nanobot" / "workspace" / "skills" / "a3-intelligent-network-opening",
        ]
        p = next((c for c in candidates if c.is_dir()), None)
    if p is None or not p.is_dir():
        return None
    return (p / "subskills").resolve() if (p / "subskills").is_dir() else p.resolve()


# ── 平面规格 ──────────────────────────────────────────────────────────────────

@dataclass
class PlaneSpec:
    """单个网络平面的移植规格。"""
    key: str           # 唯一 key，用于 PlaneMatrix cell
    label: str         # 显示名（如「存储管理面」）
    group: str         # 分组（如「存储面」「计算面」）
    subskill_dir: str  # subskills/ 下的子目录名
    scripts_dir: str   # 子目录内脚本子目录（通常 scripts/）
    entry_func: str    # 入口函数名（如 generate_cc_glm_ip_address_xlsx）
    entry_module: str  # 入口脚本名（不含 .py，如 offline_cc_glm_pipeline）
    # 自动探测的输入文件特征（用于 check_plane_ready）
    connect_sheet_hint: str = ""   # 在 007 连线表里找这个 sheet 名关键字
    resource_plane_name: str = ""  # 资源表 "网络平面" 列里找这个值


# 当前已有对应 a3 subskill 的平面（PoC 先实装 cc_glm）
PLANE_SPECS: list[PlaneSpec] = [
    PlaneSpec(
        key="cc_glm", label="存储管理面", group="存储面",
        subskill_dir="a3-cc-glm-ip-workflow.code1/scripts",
        scripts_dir="",
        entry_func="generate_cc_glm_ip_address_xlsx",
        entry_module="offline_cc_glm_pipeline",
        connect_sheet_hint="存储管理面端口互联",
        resource_plane_name="存储管理面",
    ),
    # 后续平面按相同格式追加
    PlaneSpec(
        key="cc_ybm", label="存储业务面", group="存储面",
        subskill_dir="a3-cc-ybm-ip-workflow.code1/scripts",
        scripts_dir="",
        entry_func="generate_cc_ybm_ip_address_xlsx",
        entry_module="offline_cc_ybm_pipeline",
        connect_sheet_hint="存储业务面端口互联",
        resource_plane_name="存储业务面",
    ),
    PlaneSpec(
        key="csm", label="计算参数面", group="计算面",
        subskill_dir="a3-csm-ip-workflow.code1/scripts",
        scripts_dir="",
        entry_func="generate_csm_ip_address_xlsx",
        entry_module="offline_csm_pipeline",
        connect_sheet_hint="参数面端口互联",
        resource_plane_name="计算参数面",
    ),
    PlaneSpec(
        key="cpm_lq", label="计算管理面", group="计算面",
        subskill_dir="a3-cpm-lq-ip-workflow.code1/scripts",
        scripts_dir="",
        entry_func="generate_cpm_lq_ip_address_xlsx",
        entry_module="offline_cpm_lq_pipeline",
        connect_sheet_hint="计算管理面端口互联",
        resource_plane_name="计算管理面",
    ),
]


# ── 结果 ──────────────────────────────────────────────────────────────────────

@dataclass
class PlaneResult:
    spec: PlaneSpec
    status: str = "pending"          # pending / running / done / error / skipped
    output_file: str = ""
    note: str = ""
    error: str = ""


# ── 输入件探测 ────────────────────────────────────────────────────────────────

def _find_input_files(work_root: Path) -> tuple[Path | None, Path | None]:
    """在 work_root/ProjectData/Input 下找 007 连线表 + 资源需求表。"""
    search_dirs = [
        work_root / "ProjectData" / "Input",
        work_root / "Input",
        work_root,
    ]
    connect_path: Path | None = None
    resource_path: Path | None = None

    for d in search_dirs:
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.name.startswith("~$") or not f.suffix.lower() in (".xlsx", ".xls"):
                continue
            n = f.name
            if connect_path is None and ("007" in n or "端口连线" in n or "端口互联" in n):
                connect_path = f
            if resource_path is None and ("项目信息收集" in n or "资源需求" in n or "资源表" in n):
                resource_path = f
        if connect_path and resource_path:
            break

    return connect_path, resource_path


def discover_available_planes(work_root: Any) -> dict[str, str]:
    """扫描工作区，返回 {plane_key: 'available' | 'no_input' | 'no_subskill'}。"""
    root = Path(work_root) if not isinstance(work_root, Path) else work_root
    connect_path, resource_path = _find_input_files(root)
    a3_root = _a3_subskill_root()

    result: dict[str, str] = {}
    for spec in PLANE_SPECS:
        # 检查是否有 a3 源码
        if a3_root is None:
            result[spec.key] = "no_subskill"
            continue
        scripts_path = a3_root / spec.subskill_dir
        if not scripts_path.is_dir():
            result[spec.key] = "no_subskill"
            continue
        # 检查输入文件（简单：有 007 + 资源表就认为可运行）
        if connect_path and resource_path:
            result[spec.key] = "available"
        else:
            result[spec.key] = "no_input"
    return result


# ── 单平面执行 ────────────────────────────────────────────────────────────────

def _load_pipeline_func(spec: PlaneSpec, a3_root: Path):
    """通过 importlib 加载 a3 源码平面 pipeline 入口函数（临时路径魔法）。"""
    scripts_path = str((a3_root / spec.subskill_dir).resolve())
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    try:
        module = importlib.import_module(spec.entry_module)
        importlib.reload(module)           # 保证每次用最新版
        return getattr(module, spec.entry_func)
    finally:
        if scripts_path in sys.path:
            sys.path.remove(scripts_path)


def run_plane(
    spec: PlaneSpec,
    work_root: Path,
    connect_path: Path,
    resource_path: Path,
    a3_root: Path,
    out_dir: Path,
) -> PlaneResult:
    """执行单个平面的 IP 规划，返回 PlaneResult。"""
    result = PlaneResult(spec=spec, status="running")
    try:
        fn = _load_pipeline_func(spec, a3_root)
        out_xlsx = fn(
            path_connect=connect_path,
            resource=resource_path,
            out_dir=out_dir,
            restrict_to_cwd=False,
        )
        result.status = "done"
        result.output_file = str(out_xlsx)
        result.note = f"→ {Path(out_xlsx).name}"
    except ImportError as e:
        # 依赖库缺失（pandas/openpyxl），说明环境未就绪
        result.status = "error"
        result.error = f"依赖库缺失：{e}（请在 agent venv 下安装 pandas openpyxl）"
    except Exception as e:  # noqa: BLE001
        result.status = "error"
        result.error = str(e)[:200]
    return result


def run_address_plan(work_root: Any) -> list[PlaneResult]:
    """主入口：扫描可运行平面 → 挨个跑 → 返回全部 PlaneResult。"""
    root = Path(work_root) if not isinstance(work_root, Path) else work_root
    connect_path, resource_path = _find_input_files(root)
    a3_root = _a3_subskill_root()
    out_dir = root / "ProjectData" / "Output" / "AddressPlan"

    results: list[PlaneResult] = []
    for spec in PLANE_SPECS:
        # 无 a3 源码 → skipped
        if a3_root is None or not (a3_root / spec.subskill_dir).is_dir():
            results.append(PlaneResult(spec=spec, status="skipped", note="a3 源码未找到"))
            continue
        # 无输入文件 → pending
        if connect_path is None or resource_path is None:
            results.append(PlaneResult(spec=spec, status="pending",
                                       note="缺少 007 连线表或资源需求表"))
            continue
        results.append(run_plane(
            spec=spec,
            work_root=root,
            connect_path=connect_path,
            resource_path=resource_path,
            a3_root=a3_root,
            out_dir=out_dir,
        ))
    return results
