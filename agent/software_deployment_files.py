"""software_deployment ProjectData 文件检查与上传路由。

路径相对于 skill 工作区根（默认 ``AIDA/skills/software_deployment/``），
须与 ``runtime/paths.py`` 和 ``data/upstream_manifest.json`` 保持一致：
  ProjectData/input/plan_receive   二级任务
  ProjectData/input/plan_split     验收用例 / Pod 映射
  ProjectData/input/plan_dispatch  LLD
  ProjectData/input/cloudops       CloudOps 手工表 / 完工清单 / ZTP / 参数
"""
from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import Any

from fastapi import UploadFile


SLOT_DIRS: dict[str, str] = {
    "second_level_tasks": "ProjectData/input/plan_receive",
    "testcase": "ProjectData/input/plan_split",
    "pod_map": "ProjectData/input/plan_split",
    "scene_info": "ProjectData/input/plan_split",
    "personnel": "ProjectData/input/plan_split",
    "lld_design": "ProjectData/input/plan_dispatch",
    "cloudops_manual": "ProjectData/input/cloudops",
    "check_list": "ProjectData/input/cloudops",
    "cloudops_params": "ProjectData/input/cloudops",
    "ztp_bundle": "ProjectData/input/cloudops",
}

REQUIRED_SLOTS = ["second_level_tasks", "testcase", "lld_design", "cloudops_manual", "check_list"]


def _manifest(root: Path) -> dict[str, Any]:
    path = root / "data" / "upstream_manifest.json"
    if not path.is_file():
        return {"slots": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {"slots": {}}
    except Exception:
        return {"slots": {}}


def _slot_specs(root: Path) -> dict[str, dict[str, Any]]:
    slots = _manifest(root).get("slots") or {}
    return {k: v for k, v in slots.items() if isinstance(v, dict)}


def infer_upload_kind(filename: str) -> str:
    """由文件名推断上传槽位。"""
    name = filename or ""
    low = name.lower()
    if "部署调测任务列表" in name or "交付计划" in name or "second_level" in low:
        return "second_level_tasks"
    if name.endswith(".docx"):
        return "testcase"
    if "LLD设计" in name or ("lld" in low and "设计" in name):
        return "lld_design"
    if "完工清单" in name:
        return "check_list"
    if "CloudOps" in name and ("手工" in name or "补充" in name):
        return "cloudops_manual"
    if "测试参数" in name:
        return "cloudops_params"
    if "ZTP" in name.upper():
        return "ztp_bundle"
    if "Pod" in name or "pod" in low:
        return "pod_map"
    if "场景" in name:
        return "scene_info"
    if "人员" in name:
        return "personnel"
    if re.search(r"\.xlsx?$", name, re.I):
        return "second_level_tasks"
    return "second_level_tasks"


def _match_patterns(base: Path, patterns: list[str]) -> list[Path]:
    if not base.is_dir():
        return []
    out: list[Path] = []
    seen: set[str] = set()
    for pattern in patterns:
        candidates = base.glob(pattern) if "**" in pattern else base.rglob("*")
        for p in candidates:
            if not p.is_file() or p.name.startswith(("~$", ".")):
                continue
            if "**" not in pattern and not fnmatch.fnmatch(p.name, pattern):
                continue
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                out.append(p)
    return sorted(out, key=lambda x: x.name)


def _slot_status(root: Path, slot_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    rel_dir = SLOT_DIRS.get(slot_id, "ProjectData/input")
    patterns = [str(p) for p in (spec.get("patterns") or ["*"])]
    matches = _match_patterns(root / rel_dir, patterns)
    if slot_id == "lld_design":
        active = _active_registry_file(root, slot_id)
        if active and active.is_file():
            matches = [active] + [p for p in matches if p.resolve() != active.resolve()]
    label = str(spec.get("label") or slot_id)
    optional = bool(spec.get("optional"))
    return {
        "id": slot_id,
        "label": label,
        "path": f"{rel_dir}/" + (" | ".join(patterns)),
        "hint": f"上传后保存到 {rel_dir}",
        "found": bool(matches),
        "matched": str(matches[0].relative_to(root)).replace("\\", "/") if matches else None,
        "optional": optional,
    }


def _active_registry_file(root: Path, slot_id: str) -> Path | None:
    path = root / "ProjectData" / "input" / "input_registry.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    slots = raw.get("slots") if isinstance(raw, dict) else {}
    slot = slots.get(slot_id) if isinstance(slots, dict) else {}
    active = slot.get("active") if isinstance(slot, dict) else {}
    rel = active.get("path") if isinstance(active, dict) else ""
    if not rel:
        return None
    p = root / str(rel).replace("\\", "/")
    return p.resolve()


def _slot_from_need(raw: str) -> str | None:
    text = raw or ""
    if "二级" in text or "部署调测任务列表" in text or "plan_receive" in text:
        return "second_level_tasks"
    if "验收" in text or "Word" in text or ".docx" in text or "plan_split" in text:
        return "testcase"
    if "LLD" in text or "plan_dispatch" in text:
        return "lld_design"
    if "手工" in text or "补充表" in text:
        return "cloudops_manual"
    if "完工清单" in text:
        return "check_list"
    if "测试参数" in text:
        return "cloudops_params"
    if "ZTP" in text.upper():
        return "ztp_bundle"
    return None


def check_need_files(root: Path, need_files: list[str]) -> dict[str, Any]:
    """按 HITL 的 need_files 逐项检查。"""
    specs = _slot_specs(root)
    items: list[dict[str, Any]] = []
    found_count = 0
    for i, raw in enumerate(need_files):
        slot_id = _slot_from_need(raw)
        if slot_id and slot_id in specs:
            item = _slot_status(root, slot_id, specs[slot_id])
        else:
            rel = re.split(r"[（(]", raw or "", maxsplit=1)[0].strip().replace("\\", "/")
            full = root / rel
            found = full.is_file()
            item = {
                "id": f"need-{i}",
                "label": Path(rel).name if rel else raw,
                "path": raw,
                "hint": "请按提示上传或将文件放入对应 ProjectData/input 子目录",
                "found": found,
                "matched": str(full.relative_to(root)).replace("\\", "/") if found else None,
            }
        if item.get("found"):
            found_count += 1
        items.append(item)
    total = len(items)
    return {
        "ok": found_count == total if total else True,
        "found_count": found_count,
        "total": total,
        "items": items,
        "software_deployment_root": str(root),
    }


def slot_disk_status(root: Path, slot_id: str) -> tuple[bool, str | None]:
    """扫描单个槽位在 ProjectData/input 是否已有匹配文件。返回 (found, 相对路径文件名)。"""
    specs = _slot_specs(root)
    spec = specs.get(slot_id)
    if not spec:
        return False, None
    item = _slot_status(root, slot_id, spec)
    matched = str(item.get("matched") or "").strip()
    if not item.get("found") or not matched:
        return False, None
    return True, Path(matched).name


def check_project_files(root: Path) -> dict[str, Any]:
    """扫描主线必需材料和可选材料。"""
    specs = _slot_specs(root)
    items = [_slot_status(root, slot_id, spec) for slot_id, spec in specs.items()]
    required = [item for item in items if item["id"] in REQUIRED_SLOTS]
    found_count = sum(1 for item in required if item.get("found"))
    total = len(required)
    return {
        "ok": found_count == total,
        "found_count": found_count,
        "total": total,
        "items": items,
        "software_deployment_root": str(root),
    }


async def save_upload(root: Path, kind: str, file: UploadFile) -> dict[str, Any]:
    """按槽位保存上传文件。"""
    slot = kind if kind in SLOT_DIRS else infer_upload_kind(file.filename or "")
    dest_dir = root / SLOT_DIRS.get(slot, "ProjectData/input/plan_receive")
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = file.filename or f"uploaded-{slot}"
    dest = dest_dir / fname
    content = await file.read()
    dest.write_bytes(content)
    return {
        "ok": True,
        "kind": slot,
        "filename": fname,
        "path": str(dest.relative_to(root)).replace("\\", "/"),
        "size": len(content),
    }


def reset_workspace(root: Path) -> dict[str, Any]:
    """重置会话：清空运行态与中间产物，保留 ProjectData/input/ 用户上传的源文件。

    清除 plan/Output、plan/RunTime、plan/Input、results、顶层 Output/RunTime/Start/Images；
    不清 input/ 下各槽位文件与 input_registry.json。
    """
    root = Path(root).resolve()
    pd = root / "ProjectData"
    removed: list[str] = []

    def _clear_dir(path: Path, *, keep_names: frozenset[str] = frozenset()) -> None:
        if not path.is_dir():
            return
        for p in list(path.iterdir()):
            if p.name in keep_names or p.name.startswith("~$"):
                continue
            try:
                if p.is_file():
                    p.unlink()
                    removed.append(str(p.relative_to(root)).replace("\\", "/"))
                elif p.is_dir():
                    for child in list(p.rglob("*")):
                        if child.is_file() and not child.name.startswith("~$"):
                            child.unlink()
                            removed.append(str(child.relative_to(root)).replace("\\", "/"))
                    if not any(p.iterdir()):
                        p.rmdir()
            except OSError:
                pass

    for rel in (
        "plan/Output",
        "plan/RunTime",
        "plan/Input",
        "results",
        "Output",
        "RunTime",
        "Start",
        "Images",
    ):
        keep = frozenset({"gateway.json.example", "gateway.json"}) if rel == "plan/RunTime" else frozenset()
        _clear_dir(pd / rel, keep_names=keep)

    return {
        "ok": True,
        "removed_count": len(removed),
        "removed": removed,
        "message": "已清空部署调测运行态与产物（input 源文件已保留），可重新从步骤 1 启动。",
    }
