"""
第 6 步：CloudOps 完整配置编排。

- 发现 Manual / 完工清单路径（``file_sync``）
- SN 填充与写回：Skill 内 vendored ``ChecklistToCloudOpsConfig``（对齐 Agent 源码）
"""
from __future__ import annotations

import glob
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

def _checklist_to_cloudops_mod():
    root = Path(os.environ.get("SD_SKILL_ROOT", Path.cwd())).resolve()
    rt = root / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    from sd_script_import import import_sd_script  # noqa: WPS433

    return import_sd_script(root, "6_cloudops_full", "checklist_to_cloudops")


_cto = _checklist_to_cloudops_mod()
ChecklistToCloudOpsConfig = _cto.ChecklistToCloudOpsConfig
get_check_list_df = _cto.get_check_list_df


def _skill_root(skill_dir: str) -> Path:
    root = Path(skill_dir).resolve()
    os.environ.setdefault("SD_SKILL_ROOT", str(root))
    return root


def _co_constants(skill_dir: str):
    root = _skill_root(skill_dir)
    rt = root / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    from sd_script_import import import_sd_script  # noqa: WPS433

    return import_sd_script(root, "4_cloudops_init", "constants")


def _supplement_mod(skill_dir: str):
    root = _skill_root(skill_dir)
    rt = root / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    from sd_script_import import import_sd_script  # noqa: WPS433

    return import_sd_script(root, "5_cloudops_supplement", "supplement")


def _file_sync_mod(skill_dir: str):
    root = _skill_root(skill_dir)
    rt = root / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    from sd_script_import import import_sd_script  # noqa: WPS433

    return import_sd_script(root, "5_cloudops_supplement", "file_sync")

FULL_FILE_BASENAME = "CloudOps完整配置文件.xlsx"

_C0 = _co_constants(os.environ.get("SD_SKILL_ROOT", str(Path.cwd())))
CloudopsConfigColumns = _C0.CloudopsConfigColumns
CloudopsConfigSheets = _C0.CloudopsConfigSheets


@dataclass
class FullConfigResult:
    ok: bool
    message: str
    output_path: str = ""
    output_bytes_len: int = 0
    server_rows: int = 0
    switch_rows: int = 0
    checklist_source: str = ""
    checklist_files: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)


def _skills_root(skill_dir: str) -> str:
    return os.path.abspath(os.path.join(skill_dir, os.pardir))


def _workspace_root(skill_dir: str) -> str:
    return os.path.abspath(os.path.join(_skills_root(skill_dir), os.pardir))


def default_full_output_path(skill_dir: str) -> str:
    return os.path.join(
        os.path.abspath(skill_dir), "ProjectData", "plan", "Output", FULL_FILE_BASENAME
    )


def _manual_workbook_score(path: str) -> tuple[int, int, float]:
    """优先 Agent 模板：含「主机名称」、磁盘分区行数多、较新。"""
    try:
        disk_rows = len(pd.read_excel(path, sheet_name="磁盘分区"))
        srv_cols = pd.read_excel(path, sheet_name="服务器信息", nrows=0).columns
        host_ok = 1 if CloudopsConfigColumns.HOST_NAME in srv_cols else 0
    except Exception:
        return (0, 0, 0.0)
    bn = os.path.basename(path).lower()
    bonus = 0
    if "手工补充新" in bn:
        bonus += 4
    if "初始配置" in bn and "完整" not in bn:
        bonus += 2
    return (host_ok + bonus, disk_rows, os.path.getmtime(path))


def _discover_manual_candidates(skill_dir: str, chain: dict[str, Any]) -> list[str]:
    found: list[str] = []
    rel = str(chain.get("step5_cloudops_manual_path") or "").strip()
    if rel:
        p = os.path.join(_workspace_root(skill_dir), rel.replace("/", os.sep))
        if os.path.isfile(p):
            found.append(p)
    cloudops_in = os.path.join(os.path.abspath(skill_dir), "ProjectData", "input", "cloudops")
    if os.path.isdir(cloudops_in):
        for pat in ("*手工补充新*.xlsx", "CloudOps初始配置手工补充*.xlsx", "*手工补充*.xlsx"):
            for p in glob.glob(os.path.join(cloudops_in, pat)):
                if os.path.isfile(p) and not os.path.basename(p).startswith("~$"):
                    found.append(p)
    default_out = _supplement_mod(skill_dir).default_manual_output_path(skill_dir)
    if os.path.isfile(default_out):
        found.append(default_out)
    out_dir = os.path.join(os.path.abspath(skill_dir), "ProjectData", "plan", "Output")
    if os.path.isdir(out_dir):
        for pat in ("*手工补充*.xlsx",):
            for p in glob.glob(os.path.join(out_dir, pat)):
                if os.path.isfile(p) and not os.path.basename(p).startswith("~$"):
                    found.append(p)
    # 去重保序
    seen: set[str] = set()
    unique: list[str] = []
    for p in found:
        norm = os.path.normcase(os.path.abspath(p))
        if norm not in seen:
            seen.add(norm)
            unique.append(p)
    return unique


def resolve_manual_path(skill_dir: str, chain: dict[str, Any]) -> str:
    candidates = _discover_manual_candidates(skill_dir, chain)
    if not candidates:
        return ""
    candidates.sort(key=_manual_workbook_score, reverse=True)
    return candidates[0]


def _write_bytes_safely(output_path: str, data: bytes) -> None:
    """写入目标路径；若被 Excel 占用则写入同目录带时间戳的备用文件。"""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    try:
        with open(output_path, "wb") as f:
            f.write(data)
        return
    except PermissionError:
        base, ext = os.path.splitext(output_path)
        alt = f"{base}_生成_{os.getpid()}{ext}"
        with open(alt, "wb") as f:
            f.write(data)
        raise PermissionError(
            f"无法覆盖 `{output_path}`（文件可能正被 Excel 打开）。"
            f"已改写入：`{alt}`。请关闭占用后重试或改用该文件。"
        ) from None


def generate_full_config(
    *,
    manual_path: str,
    checklist_paths: list[str],
    output_path: str,
    checklist_source: str = "",
    on_progress: Callable[[str], None] | None = None,
) -> FullConfigResult:
    logs: list[str] = []

    def _log(m: str) -> None:
        logs.append(m)
        if on_progress:
            on_progress(m)

    if not manual_path or not os.path.isfile(manual_path):
        return FullConfigResult(ok=False, message="未找到 CloudOps 手工补充文件（CloudOps_Config_Manual）", logs=logs)
    if not checklist_paths:
        return FullConfigResult(
            ok=False,
            message=(
                "未找到设备安装完工清单（Device_Checklist）。"
                "请将「设备安装完工清单」放入 "
                "`ProjectData/Input/Device_Checklist/`，"
                "勿与 LLD/CPQ 等 xlsx 混放在 Input 根目录。"
            ),
            logs=logs,
        )

    _log("正在读取手工补充配置…")
    config_sheets = pd.read_excel(manual_path, sheet_name=None)
    _log(f"正在合并完工清单（{len(checklist_paths)} 个文件，来源：{checklist_source or '未知'}）…")
    for p in checklist_paths[:8]:
        _log(f"  - {os.path.basename(p)}")
    if len(checklist_paths) > 8:
        _log(f"  - …共 {len(checklist_paths)} 个文件")

    check_list_df = get_check_list_df(checklist_paths)
    if check_list_df.empty:
        return FullConfigResult(
            ok=False,
            message="完工清单中没有有效数据（需含列：设备名称、ESN）",
            logs=logs,
            checklist_source=checklist_source,
        )

    engine = ChecklistToCloudOpsConfig(config_sheets, manual_path=manual_path, on_progress=_log)
    try:
        out_bytes = engine.generate(check_list_df)
    except Exception as e:
        return FullConfigResult(ok=False, message=str(e), logs=logs, checklist_source=checklist_source)

    try:
        _write_bytes_safely(output_path, out_bytes)
    except PermissionError as e:
        return FullConfigResult(ok=False, message=str(e), logs=logs, checklist_source=checklist_source)

    server_rows = _count_sn_rows(out_bytes, CloudopsConfigSheets.SERVER_INFO)
    switch_rows = _count_sn_rows(out_bytes, CloudopsConfigSheets.SWITCH_INFO)
    _log(f"已写入 {output_path}（服务器 {server_rows} 行含 SN，交换机 {switch_rows} 行含 SN）")

    # 文件已落盘即视为生成成功；SN 行数为质量提示（与 Agent 一致：无 SN 的行不会写入 sheet）
    msg = "CloudOps 完整配置文件已生成"
    if server_rows == 0 and switch_rows == 0:
        msg += (
            "；但服务器/交换机 sheet 未匹配到 SN，请核对清单中的设备名称、"
            "设备大类（智算/交换机）与手工补充表是否一致。"
        )
    elif server_rows == 0 or switch_rows == 0:
        msg += f"（服务器 SN 行 {server_rows}，交换机 SN 行 {switch_rows}）"

    return FullConfigResult(
        ok=True,
        message=msg,
        output_path=output_path,
        output_bytes_len=len(out_bytes),
        server_rows=server_rows,
        switch_rows=switch_rows,
        checklist_source=checklist_source,
        checklist_files=list(checklist_paths),
        logs=logs,
    )


def _count_sn_rows(xlsx_bytes: bytes, sheet: str) -> int:
    import io

    try:
        df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name=sheet, dtype=str).fillna("")
        if df.empty:
            return 0
        sn_col = CloudopsConfigColumns.SERIAL_NUMBER
        if sn_col not in df.columns:
            return 0
        return int(df[sn_col].astype(str).str.strip().ne("").sum())
    except Exception:
        return 0


def run_full_config_for_project(
    *,
    skill_dir: str,
    chain: dict[str, Any],
) -> FullConfigResult:
    manual = resolve_manual_path(skill_dir, chain)
    checklist_paths, checklist_source = _file_sync_mod(skill_dir).resolve_checklist_paths(skill_dir)
    out = default_full_output_path(skill_dir)
    try:
        result = generate_full_config(
            manual_path=manual,
            checklist_paths=checklist_paths,
            output_path=out,
            checklist_source=checklist_source,
        )
    except Exception as e:
        return FullConfigResult(ok=False, message=f"生成完整配置异常：{e}", logs=[str(e)])

    if checklist_source and result.logs:
        result.logs.insert(0, f"完工清单来源：{checklist_source}")

    return result
