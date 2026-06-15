from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from skill_root import resolve_capability_root
from command_registry import get_command
from naming_input_resolver import (
    find_ztp_lld,
    resolve_generate_list_inputs,
    resolve_lld_replace_inputs,
    resolve_ztp_replace_inputs,
)
from subprocess_runner import run_l3_subprocess
from ztp_prereq import ensure_ztp_lld, project_data_dir


@dataclass(frozen=True)
class L3ExecutionResult:
    status: str
    command: str
    sub_skill_name: str
    run_dir: Path
    output_files: tuple[Path, ...]
    summary: str
    errors: tuple[str, ...] = ()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _reset_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _copy_input(src: Path, work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    dst = work_dir / src.name
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)
    return dst


def _copy_products_to_output(product_files: tuple[Path, ...], output_dir: Path, timestamp: str) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for src in product_files:
        dst = output_dir / f"{src.stem}_{timestamp}{src.suffix}"
        if dst.exists():
            stem, suffix = dst.stem, dst.suffix
            counter = 2
            while dst.exists():
                dst = output_dir / f"{stem}_{counter}{suffix}"
                counter += 1
        shutil.copy2(src, dst)
        copied.append(dst)
    return tuple(copied)


def execute_l3(
    *,
    skill_root: Path,
    run_id: str,
    command: str,
    input_007: Path,
    input_resource: Path,
    extra_inputs: dict[str, Path] | None = None,
) -> L3ExecutionResult:
    try:
        capability_root = resolve_capability_root(skill_root)
    except FileNotFoundError as exc:
        return L3ExecutionResult(
            status="error",
            command=command,
            sub_skill_name="",
            run_dir=skill_root / "ProjectData" / "Output",
            output_files=(),
            summary="未找到 subskills 业务能力库。",
            errors=(str(exc),),
        )

    output_dir = skill_root / "ProjectData" / "Output"
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = skill_root / "ProjectData" / "Work" / run_id
    raw_output_dir = _reset_dir(work_dir / "raw_output")

    copied_007 = _copy_input(input_007, work_dir)
    copied_resource = _copy_input(input_resource, work_dir)

    pass_prior: list[str] = []
    spec = get_command(command)
    if spec is not None and spec.args_style in {"ztp_scan", "lq_open_scan"}:
        scan_dir = project_data_dir(skill_root)
    elif spec is not None and spec.args_style == "input_check":
        scan_dir = skill_root / "ProjectData" / "Input"
    else:
        scan_dir = skill_root / "ProjectData" / "Output"
    if extra_inputs and "access_plan" in extra_inputs:
        pass_prior.append("access")

    ztp_lld: Path | None = None
    name_mapping: Path | None = None
    device_list: Path | None = None
    lld_design: Path | None = None
    location_004: Path | None = None

    if spec is not None and spec.args_style == "device_naming":
        if command == "生成设备清单":
            naming = resolve_generate_list_inputs(skill_root, work_dir)
            location_004 = naming.get("location_004")
            if location_004 is None:
                return L3ExecutionResult(
                    status="error",
                    command=command,
                    sub_skill_name="a3-device-naming-workflow.code1",
                    run_dir=output_dir,
                    output_files=(),
                    summary="生成设备清单缺少 004 设备位置表。",
                    errors=("missing 004 location file",),
                )
        elif command == "替换设备名称":
            naming = resolve_lld_replace_inputs(skill_root, work_dir)
            lld_design = naming.get("lld_design")
            device_list = naming.get("device_list")
            if lld_design is None:
                return L3ExecutionResult(
                    status="error",
                    command=command,
                    sub_skill_name="a3-device-naming-workflow.code1",
                    run_dir=output_dir,
                    output_files=(),
                    summary="设备名称替换缺少 LLD 设计文件。请先执行「融合完整LLD设计」。",
                    errors=("missing LLD design",),
                )
            if device_list is None:
                return L3ExecutionResult(
                    status="error",
                    command=command,
                    sub_skill_name="a3-device-naming-workflow.code1",
                    run_dir=output_dir,
                    output_files=(),
                    summary="设备名称替换缺少设备清单。请先上传 004 或执行「生成设备清单」。",
                    errors=("missing device list",),
                )
        elif command.startswith("ZTP名称替换"):
            if find_ztp_lld(skill_root) is None:
                generated = ensure_ztp_lld(
                    skill_root,
                    run_id=run_id,
                    input_007=copied_007,
                    input_resource=copied_resource,
                )
                if generated is None:
                    return L3ExecutionResult(
                        status="error",
                        command=command,
                        sub_skill_name="a3-device-naming-workflow.code1",
                        run_dir=output_dir,
                        output_files=(),
                        summary=(
                            "ZTP名称替换缺少 ZTP_LLD，且自动执行「生成ZTP设计文件」失败。"
                            "请确认 007、项目信息收集表、004 设备位置表已上传，或先手动生成 ZTP 设计文件。"
                        ),
                        errors=("missing ZTP_LLD; auto-prereq failed",),
                    )
            naming = resolve_ztp_replace_inputs(skill_root, work_dir)
            ztp_lld = naming.get("ztp_lld")
            name_mapping = naming.get("name_mapping")
            if ztp_lld is None:
                return L3ExecutionResult(
                    status="error",
                    command=command,
                    sub_skill_name="a3-device-naming-workflow.code1",
                    run_dir=output_dir,
                    output_files=(),
                    summary="ZTP名称替换缺少 ZTP_LLD。",
                    errors=("missing ZTP_LLD",),
                )
            if name_mapping is None:
                return L3ExecutionResult(
                    status="error",
                    command=command,
                    sub_skill_name="a3-device-naming-workflow.code1",
                    run_dir=output_dir,
                    output_files=(),
                    summary=(
                        "ZTP名称替换缺少 source/target 映射表。"
                        "请上传 devicename-mapping.csv（含 source、target 列），"
                        "或先「生成设备清单」并填写「客户定义设备名称」。"
                    ),
                    errors=("missing name mapping",),
                )

    result = run_l3_subprocess(
        command,
        capability_root=capability_root,
        skill_root=skill_root,
        topology=copied_007,
        resource=copied_resource,
        out_dir=raw_output_dir,
        pass_prior=pass_prior or None,
        scan_dir=scan_dir,
        ztp_lld=ztp_lld,
        name_mapping=name_mapping,
        device_list=device_list,
        lld_design=lld_design,
        location_004=location_004,
    )

    timestamp = _timestamp()
    output_files = _copy_products_to_output(result.output_files, output_dir, timestamp)

    if result.status != "ok":
        errors = result.errors or (result.summary,)
        return L3ExecutionResult(
            status="error",
            command=command,
            sub_skill_name=result.sub_skill_name,
            run_dir=output_dir,
            output_files=output_files,
            summary=result.summary,
            errors=errors,
        )

    if not output_files:
        return L3ExecutionResult(
            status="error",
            command=command,
            sub_skill_name=result.sub_skill_name,
            run_dir=output_dir,
            output_files=(),
            summary="执行完成但未发现输出产物。",
            errors=("empty output",),
        )

    return L3ExecutionResult(
        status="ok",
        command=command,
        sub_skill_name=result.sub_skill_name,
        run_dir=output_dir,
        output_files=output_files,
        summary=result.summary,
    )
