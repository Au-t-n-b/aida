"""uniEx clone-boq 桥接 · subprocess 调用 Stage1/Stage2。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class UniExBoqError(RuntimeError):
    pass


def _run_id(project_id: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = project_id[:8] if project_id else "project"
    return f"{slug}-aida-{ts}-clone-boq@0.3.0"


def run_stage1(boq_dir: Path, parse_out_dir: Path, *, project_id: str) -> Path:
    """执行 clone-boq Stage1，将 normalized.json 同步到合同解析目录。"""
    from agent.skills.early_io.paths import clone_boq_skill_root

    skill_root = clone_boq_skill_root()
    if skill_root is None:
        raise UniExBoqError("UNIEX_BENCH_ROOT 未配置或 clone-boq 目录不存在")

    xlsx_files = sorted(boq_dir.glob("*.xlsx"))
    if not xlsx_files:
        raise UniExBoqError(f"BOQ 目录无 xlsx: {boq_dir}")

    run_id = _run_id(project_id)
    runs_dir = skill_root / "runs" / run_id
    stage1_script = skill_root / "skill" / "boq-plane-derivation" / "scripts" / "run_stage1.py"
    if not stage1_script.is_file():
        raise UniExBoqError(f"缺少 run_stage1.py: {stage1_script}")

    staging = skill_root / "runs" / "_aida_inputs" / (project_id or "default")
    staging.mkdir(parents=True, exist_ok=True)
    boq_rows: list[dict[str, str]] = []
    for src in xlsx_files:
        dst = staging / src.name
        if dst.resolve() != src.resolve():
            dst.write_bytes(src.read_bytes())
        boq_rows.append({"path": dst.relative_to(skill_root).as_posix(), "role": "boq"})

    manifest_tpl = {
        "project_name": project_id or "aida-project",
        "inputs": {"boq_files": boq_rows},
    }
    manifest_path = staging / f"{run_id}.manifest.json"
    manifest_path.write_text(json.dumps(manifest_tpl, ensure_ascii=False, indent=2), encoding="utf-8")

    parse_out_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONUTF8": "1"}
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(stage1_script),
        "--run-id",
        run_id,
        "--project",
        project_id or "aida-project",
        "--manifest",
        str(manifest_path),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(skill_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-2000:]
        raise UniExBoqError(f"clone-boq Stage1 失败 (exit {proc.returncode}): {tail}")

    artifacts = runs_dir / "artifacts" / "boq"
    if not artifacts.is_dir():
        raise UniExBoqError(f"Stage1 产物目录不存在: {artifacts}")

    copied: list[Path] = []
    for src in sorted(artifacts.glob("*.normalized.json")):
        dst = parse_out_dir / src.name
        dst.write_bytes(src.read_bytes())
        copied.append(dst)
    if not copied:
        raise UniExBoqError("Stage1 未产出任何 *.normalized.json")
    return runs_dir


def run_stage2(run_dir: Path, simulation_out: Path) -> tuple[Path, Path]:
    """执行 clone-boq Stage2，产出建模仿真设备信息表。"""
    from agent.skills.early_io.paths import clone_boq_skill_root

    skill_root = clone_boq_skill_root()
    if skill_root is None:
        raise UniExBoqError("UNIEX_BENCH_ROOT 未配置")

    stage2_script = skill_root / "skill" / "boq-device-info" / "scripts" / "run_stage2.py"
    if not stage2_script.is_file():
        raise UniExBoqError(f"缺少 run_stage2.py: {stage2_script}")

    simulation_out.mkdir(parents=True, exist_ok=True)
    out_md = simulation_out / "device_info_table.v0.md"
    out_json = simulation_out / "device_info_table.v0.json"
    env = {**os.environ, "PYTHONUTF8": "1"}
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(stage2_script),
        "--run-dir",
        str(run_dir),
        "--skip-api",
        "--out-md",
        str(out_md),
        "--out-json",
        str(out_json),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(skill_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-2000:]
        raise UniExBoqError(f"clone-boq Stage2 失败 (exit {proc.returncode}): {tail}")
    if not out_md.is_file():
        raise UniExBoqError(f"Stage2 未产出 {out_md}")
    return out_md, out_json
