"""
系统设计 ProjectData 文件补齐 / 上传路由（文件型 HITL · 与 zhgk_files.py 同契约）。

系统设计 4 件必需输入件（见 skills/system_design/pipelines/inputs.py FILE_CONFIG）：
  - 项目信息收集表（手动上传，地址规划数据底座）
  - 端口连线表(007) / 设备信息表(001) / 设备位置表(004)（建模仿真产出）

落盘统一进 ProjectData/Input/；识别按文件名关键词（collect_inputs 同源）。
4 函数契约：infer_upload_kind / check_project_files / check_need_files / save_upload。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from .skills.system_design.pipelines.inputs import (
    FILE_CONFIG, REQUIRED_DEFAULT, collect_inputs, label_of, missing_required,
)
from .skills.system_design.pipelines.path_manifest import (
    abs_artifacts_dir,
    abs_upload_dir,
    ensure_parent_dir,
    relpath_for_artifact,
    relpath_from_data_root,
    resolve_artifact_file,
    resolve_data_root,
)

# 展示名 → FILE_CONFIG tag（与 SD_INPUT_SLOTS / 前端 systemDesignUpload.ts 对齐）
_LABEL_TO_TAG: dict[str, str] = {
    "项目信息收集表": "resource",
    "端口连线表": "Interconnection_Relationship",
    "设备信息表": "Device_Info",
    "设备位置表": "Location_Information",
    "测试用例": "Test_Case",
    "验收用例": "Test_Case",
}


def _tag_from_label(label: str) -> str:
    text = (label or "").strip()
    if not text:
        return ""
    if text in _LABEL_TO_TAG:
        return _LABEL_TO_TAG[text]
    for display, tag in _LABEL_TO_TAG.items():
        if display in text or text in display:
            return tag
    return ""


def _resolve_upload_tag(kind: str, filename: str, label_hint: str = "") -> str:
    """kind(slotTag) → 文件名关键词 → 槽位 label，解析 FILE_CONFIG tag。"""
    hinted = (kind or "").strip()
    if hinted in FILE_CONFIG:
        return hinted
    from_name = infer_upload_kind(filename or "")
    if from_name in FILE_CONFIG:
        return from_name
    from_label = _tag_from_label(label_hint)
    if from_label in FILE_CONFIG:
        return from_label
    return ""


def infer_upload_kind(filename: str) -> str:
    """按文件名关键词推断 tag（resource / Interconnection_Relationship / ...）；
    命中不了则兜底 'input'。所有 kind 最终都落 ProjectData/Input/。"""
    name = filename or ""
    for tag, cfg in FILE_CONFIG.items():
        if any(kw in name for kw in cfg["keywords"]):
            return tag
    return ""  # 无关键词命中 · 须由 slotTag 指定


def _canonical_name(kind: str, filename: str) -> str:
    """保证落盘文件名带得上识别关键词；原名已含则原样保留。"""
    cfg = FILE_CONFIG.get(kind)
    ext_candidates = tuple(cfg.get("extensions") or [".xlsx", ".xls"]) if cfg else (".xlsx", ".xls")
    default_ext = ext_candidates[0].lstrip(".")
    fname = filename or f"uploaded.{default_ext}"
    if cfg and not any(kw in fname for kw in cfg["keywords"]):
        stem, dot, ext = fname.rpartition(".")
        ext = ext if dot else default_ext
        base = stem if dot else fname
        # 用 label 兜一个能被 collect_inputs 命中的名字
        fname = f"{cfg['label']}_{base}.{ext}"
    return fname


def _rel_to_root(root: Path, path: Path) -> str:
    _ = root
    return relpath_from_data_root(path)


async def save_upload(
    root: Path,
    kind: str,
    file: UploadFile,
    *,
    label_hint: str = "",
) -> dict[str, Any]:
    """单文件落盘到 project_paths.json → upload.save_dir，返回 {ok, kind, filename, path, size}。"""
    _ = root
    dest_dir = abs_upload_dir()
    tag = _resolve_upload_tag(kind, file.filename or "", label_hint)
    if tag not in FILE_CONFIG:
        return {
            "ok": False,
            "kind": tag or "unknown",
            "filename": file.filename,
            "error": (
                f"无法识别输入件类型（{file.filename}）。"
                "请从对应槽位点击「上传」，或确保文件名含类型关键词（如 项目信息收集、007）。"
            ),
        }
    fname = _canonical_name(tag, file.filename or "")
    dest = dest_dir / fname
    content = await file.read()
    ensure_parent_dir(dest)
    if not content:
        return {
            "ok": False,
            "kind": tag,
            "filename": file.filename,
            "error": f"文件为空（{file.filename}）",
        }
    dest.write_bytes(content)
    rel = relpath_for_artifact(dest)
    return {
        "ok": True,
        "kind": tag,
        "filename": fname,
        "path": rel,
        "abs_path": str(dest),
        "upload_dir": str(dest_dir),
        "size": len(content),
    }


def sync_inputs_into_state(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    """重扫磁盘，把输入件写入 run state（不重跑 LangGraph）。"""
    root = Path(root).resolve()
    found = collect_inputs(root)
    files = dict(state.get("files") or {})
    for tag in FILE_CONFIG:
        key = f"input_{tag}"
        if tag in found:
            files[key] = relpath_for_artifact(found[tag].path)
        else:
            files.pop(key, None)

    metrics_patch = {
        "input_found": len(found),
        "input_total": len(REQUIRED_DEFAULT),
        "input_ready": not missing_required(found, REQUIRED_DEFAULT),
        "found_tags": sorted(found.keys()),
    }

    hitl = dict(state.get("hitl") or {})
    found_paths = [relpath_for_artifact(entry.path) for entry in found.values()]
    if hitl.get("step") == "input_check":
        missing = missing_required(found, REQUIRED_DEFAULT)
        hitl["found_files"] = found_paths
        if missing:
            hitl["need_files"] = [str(abs_upload_dir() / label_of(t)) for t in missing]
        else:
            hitl["need_files"] = []
            # 必需输入件已齐备：清除 input_check HITL，避免「需要确认」弹框残留
            state.pop("hitl", None)
            hitl = {}

    # 刷新 input_check 步 metrics（若已跑过），供 SDUI 投影读取
    steps = state.get("steps") or []
    for step in steps:
        if step.get("key") == "input_check":
            sm = dict(step.get("metrics") or {})
            sm.update(metrics_patch)
            step["metrics"] = sm
            break

    state["files"] = files
    if hitl.get("step"):
        state["hitl"] = hitl

    return {
        "found_count": len(found),
        "found_tags": metrics_patch["found_tags"],
        "files": files,
        "check": check_project_files(root),
    }


def sync_outputs_into_state(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    """重扫 output/ 磁盘，清除 run state 中已不存在的产物引用（不重跑 LangGraph）。"""
    from agent.skills.system_design.pipelines.path_manifest import scan_artifacts_rel_paths

    _ = root
    disk_out = scan_artifacts_rel_paths()
    disk_basenames = {Path(p).name for p in disk_out}
    files = dict(state.get("files") or {})
    for key in list(files.keys()):
        if key.startswith("out::") or key.startswith("plane_") or key in ("lld_file", "ztp_file"):
            files.pop(key, None)
    for rel in disk_out:
        files[f"out::{rel}"] = rel
    if any("LLD" in bn.upper() for bn in disk_basenames):
        lld_rel = next(r for r in disk_out if "LLD" in Path(r).name.upper())
        files["lld_file"] = lld_rel
    state["files"] = files

    top = dict(state.get("metrics") or {})
    if not disk_out:
        for k in list(top.keys()):
            if k.startswith("lld_") or k in ("lld_file", "ztp_file"):
                top.pop(k, None)
    else:
        lld_rel = next((r for r in disk_out if "LLD" in Path(r).name.upper()), "")
        if lld_rel:
            top["lld_file"] = lld_rel
            top["lld_status"] = "ok"
        elif "lld_file" in top:
            top.pop("lld_file", None)
            top.pop("lld_status", None)
    state["metrics"] = top

    for step in state.get("steps") or []:
        if step.get("key") != "plane_planning":
            continue
        sm = dict(step.get("metrics") or {})
        if not disk_out:
            sm["plan_commands"] = []
            step["metrics"] = sm
            if step.get("status") == "completed":
                step["status"] = "pending"
            break
        step["metrics"] = sm
        break

    if not disk_out:
        for step in state.get("steps") or []:
            if step.get("key") == "lld_integrate" and step.get("status") == "completed":
                step["status"] = "pending"
                step["metrics"] = {}

    return {"output_count": len(disk_out), "output_paths": disk_out}


def merge_run_patch(root: Path, run_state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """POST /run-patch · action=sync_inputs 时重扫输入件并刷新 SDUI。"""
    action = str(payload.get("action") or "").strip()
    if action != "sync_inputs":
        return {"ok": False, "error": f"unknown action: {action}"}
    summary = sync_inputs_into_state(Path(root), run_state)
    out_summary = sync_outputs_into_state(Path(root), run_state)
    return {"ok": True, **summary, **out_summary}


def _required_items(root: Path) -> tuple[list[dict[str, Any]], int]:
    """按 4 件必需输入件逐项报齐备状态（基于 collect_inputs 的关键词识别）。"""
    found = collect_inputs(root)
    items: list[dict[str, Any]] = []
    found_count = 0
    for tag in REQUIRED_DEFAULT:
        entry = found.get(tag)
        ok = entry is not None
        if ok:
            found_count += 1
        items.append({
            "id": tag,
            "label": label_of(tag),
            "path": str(abs_upload_dir() / label_of(tag)),
            "hint": "" if ok else f"请上传到 {abs_upload_dir()}（文件名含 {FILE_CONFIG[tag]['keywords'][0]} 等关键词）",
            "found": ok,
            "matched": (relpath_for_artifact(entry.path) if ok else None),
        })
    return items, found_count


def check_project_files(root: Path) -> dict[str, Any]:
    """扫描工作区，返回 4 件必需输入件的齐备状态。"""
    items, found_count = _required_items(root)
    total = len(REQUIRED_DEFAULT)
    return {
        "ok": found_count == total,
        "found_count": found_count,
        "total": total,
        "items": items,
        "system_design_root": str(resolve_data_root()),
        "upload_dir": str(abs_upload_dir()),
    }


def check_need_files(root: Path, need_files: list[str]) -> dict[str, Any]:
    """按当前 HITL 的 need_files 检查。系统设计的 need 即 4 件必需输入件的子集，
    统一走关键词识别（need 文案形如 'ProjectData/Input/端口连线表(007)'）。"""
    items, _ = _required_items(root)
    # 仅保留 need 涉及到的项（按 label 子串匹配）；need 为空则全量
    if need_files:
        wanted = [n for n in need_files]
        def _hit(it: dict[str, Any]) -> bool:
            return any(it["label"] in n or n in it["path"] for n in wanted)
        items = [it for it in items if _hit(it)] or items
    found_count = sum(1 for it in items if it["found"])
    total = len(items)
    return {
        "ok": found_count == total if total else True,
        "found_count": found_count,
        "total": total,
        "items": items,
        "system_design_root": str(resolve_data_root()),
        "upload_dir": str(abs_upload_dir()),
    }


def resolve_artifact_path(work_root: Path, path: str) -> Path:
    """系统设计输入件/产物预览路径解析（允许 input/jmfz/ht/output 布局）。"""
    _ = work_root
    return resolve_artifact_file(path)


def _clear_dir_files(target: Path, removed: list[str]) -> None:
    """清空一个目录下的全部文件与空子目录（保留目录本身，跳过 ~$ 临时锁文件）。"""
    if not target.is_dir():
        return
    # 自底向上删：先删文件再删空目录，保留根目录本身
    for p in sorted(target.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if p.name.startswith("~$"):
            continue
        try:
            if p.is_file() or p.is_symlink():
                p.unlink()
                removed.append(relpath_from_data_root(p))
            elif p.is_dir():
                p.rmdir()  # 仅删空目录（文件已先行删除）
        except OSError:
            pass


def reset_workspace(root: Path) -> dict[str, Any]:
    """重置会话：清空 output/ 产物 + input/ 用户上传件。

    系统设计数据布局为 project_paths.json 绝对路径（input 用户上传 / jmfz 仿真产出 /
    ht 测试用例 / output 产物）。重置清两处：
      - output/：本次运行生成的产物（LLD / ZTP / 平面规划表等）；
      - input/ ：用户上传的输入件（如「项目信息收集表」），便于重新上传重测。
    上游的 jmfz（仿真三表）/ ht（测试用例）属于建模仿真链路产出，不在此清除。

    清理后由前端 handleResetSession 清掉持久化 run_id 回到启动页；下次启动得到全新
    run（input_check 重新检查输入件，缺「项目信息收集表」会回到「输入件准备」HITL）。
    """
    _ = root
    removed: list[str] = []
    _clear_dir_files(abs_artifacts_dir(), removed)  # output/
    _clear_dir_files(abs_upload_dir(), removed)      # input/

    return {
        "ok": True,
        "removed_count": len(removed),
        "removed": removed,
        "message": "已清空产物（output/）与用户上传件（input/）。可重新启动系统设计作业并重新上传。",
    }
