from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any

from input_registry import get_active_file


def skill_root_from_cwd() -> Path:
    return Path.cwd().resolve()


def plan_receive_dir(skill_root: Path | None = None) -> Path:
    """HITL / 手工放置：部署二级任务列表（与 job_management 风格 inbox 对齐）。"""
    root = skill_root or skill_root_from_cwd()
    return root / "ProjectData" / "input" / "plan_receive"


def plan_split_input_dir(skill_root: Path | None = None) -> Path:
    """拆分阶段：验收用例 Word、多 Pod 映射等上传目录。"""
    root = skill_root or skill_root_from_cwd()
    return root / "ProjectData" / "input" / "plan_split"


def plan_dispatch_input_dir(skill_root: Path | None = None) -> Path:
    """下发计划：LLD 等放入此目录（可含子目录 ``lld/``）。"""
    root = skill_root or skill_root_from_cwd()
    return root / "ProjectData" / "input" / "plan_dispatch"


def cloudops_input_dir(skill_root: Path | None = None) -> Path:
    """CloudOps 链：完工清单、手工表、参数模板、ZTP 等。"""
    root = skill_root or skill_root_from_cwd()
    return root / "ProjectData" / "input" / "cloudops"


def _slot_input_bases(slot_id: str, root: Path) -> list[Path]:
    """仅扫描 ``ProjectData/input/...``，不再使用「前置文件临时目录」。"""
    if slot_id == "second_level_tasks":
        return [plan_receive_dir(root)]
    if slot_id in {"testcase", "pod_map", "scene_info", "personnel"}:
        return [plan_split_input_dir(root)]
    if slot_id == "lld_design":
        return [plan_dispatch_input_dir(root)]
    if slot_id in {"check_list", "cloudops_manual", "cloudops_params", "ztp_bundle"}:
        return [cloudops_input_dir(root)]
    return []


def load_upstream_manifest(skill_root: Path | None = None) -> dict[str, Any]:
    root = skill_root or skill_root_from_cwd()
    path = root / "data" / "upstream_manifest.json"
    if not path.is_file():
        return {"slots": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _match_patterns(base: Path, patterns: list[str]) -> list[Path]:
    if not base.is_dir():
        return []
    found: list[Path] = []
    seen: set[str] = set()
    for pattern in patterns:
        if "**" in pattern:
            for p in base.glob(pattern):
                if p.is_file():
                    key = str(p.resolve())
                    if key not in seen:
                        seen.add(key)
                        found.append(p)
        else:
            for p in base.iterdir():
                if not p.is_file():
                    continue
                if p.name.startswith("~$") or p.name.startswith("."):
                    continue
                if fnmatch.fnmatch(p.name, pattern):
                    key = str(p.resolve())
                    if key not in seen:
                        seen.add(key)
                        found.append(p)
            for p in base.rglob("*"):
                if p.is_file() and fnmatch.fnmatch(p.name, pattern):
                    if p.name.startswith("~$") or p.name.startswith("."):
                        continue
                    key = str(p.resolve())
                    if key not in seen:
                        seen.add(key)
                        found.append(p)
    return sorted(found, key=lambda x: x.name)


def _pick_primary(files: list[Path], slot_id: str) -> Path | None:
    if not files:
        return None
    if slot_id == "lld_design":
        ranked: list[Path] = []
        for p in files:
            name = p.name
            low = name.lower()
            if "cloudops" in low or "task_params" in low or "完工清单" in name:
                continue
            # 与 Agent ``get_lld_path`` 一致：文件名含「LLD设计」子串即可
            if "LLD设计" in name or ("lld" in low and "设计" in name):
                ranked.append(p)
        if ranked:
            return sorted(
                ranked,
                key=lambda x: (-("LLD设计" in x.name), -x.stat().st_mtime, x.name),
            )[0]
    return sorted(files, key=lambda x: x.name)[0]


def resolve_slot(
    slot_id: str,
    *,
    skill_root: Path | None = None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = skill_root or skill_root_from_cwd()
    manifest = manifest or load_upstream_manifest(root)
    slots = manifest.get("slots") if isinstance(manifest.get("slots"), dict) else {}
    slot = slots.get(slot_id)
    if not isinstance(slot, dict):
        return {"slotId": slot_id, "resolved": [], "missing": True, "optional": True}

    if slot_id == "lld_design":
        active = get_active_file(root, "lld_design")
        active_path = str(active.get("absPath") or "")
        if active_path:
            optional = bool(slot.get("optional"))
            return {
                "slotId": slot_id,
                "label": str(slot.get("label") or slot_id),
                "resolved": [active_path],
                "primary": active_path,
                "missing": False,
                "optional": optional,
                "requiredFor": slot.get("requiredFor") or [],
                "futureSource": str(slot.get("futureSource") or ""),
                "source": str(active.get("source") or "registry"),
                "version": active.get("version"),
                "originalName": str(active.get("originalName") or Path(active_path).name),
            }

    bases = _slot_input_bases(slot_id, root)

    patterns = slot.get("patterns")
    if not isinstance(patterns, list):
        patterns = []
    pattern_strs = [str(p) for p in patterns]

    files: list[Path] = []
    seen: set[str] = set()
    for base in bases:
        for p in _match_patterns(base, pattern_strs):
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                files.append(p)
        for pattern in patterns:
            pat = str(pattern)
            if "/" in pat or "\\" in pat:
                for p in base.glob(pat):
                    if not p.is_file():
                        continue
                    key = str(p.resolve())
                    if key not in seen:
                        seen.add(key)
                        files.append(p)
    files = sorted(files, key=lambda x: x.name)

    optional = bool(slot.get("optional"))
    return {
        "slotId": slot_id,
        "label": str(slot.get("label") or slot_id),
        "resolved": [str(p) for p in files],
        "primary": str(_pick_primary(files, slot_id) or (files[0] if files else "")),
        "missing": len(files) == 0,
        "optional": optional,
        "requiredFor": slot.get("requiredFor") or [],
        "futureSource": str(slot.get("futureSource") or ""),
    }


def load_plan_runtime_step(skill_root: Path | None = None) -> str:
    """计划粗粒度 step；真值 deploy_chain.step1_*～step3_*。"""
    root = skill_root or skill_root_from_cwd()
    from plan_chain import derive_plan_step, migrate_chain_from_state

    return derive_plan_step(migrate_chain_from_state(root))


def plan_action_for_step(step: str) -> str:
    """根据运行状态返回「下一步」应执行的 plan action（不含 plan_ 前缀）。"""
    s = (step or "idle").strip().lower()
    if s == "received":
        return "split"
    if s == "split":
        return "dispatch"
    if s in {"dispatched", "dispatch"}:
        return "regenerate"
    return "receive"


def plan_runtime_action_name(step: str) -> str:
    """返回带 ``plan_`` 前缀的 skill_runtime_start action。"""
    sub = plan_action_for_step(step)
    return f"plan_{sub}"


def check_prerequisites(
    *,
    for_actions: list[str] | None = None,
    skill_root: Path | None = None,
) -> dict[str, Any]:
    root = skill_root or skill_root_from_cwd()
    manifest = load_upstream_manifest(root)
    slots = manifest.get("slots") if isinstance(manifest.get("slots"), dict) else {}
    actions = for_actions or ["plan_receive", "plan_split", "plan_dispatch"]

    items: list[dict[str, Any]] = []
    blocking: list[str] = []
    for slot_id, slot in slots.items():
        if not isinstance(slot, dict):
            continue
        required_for = slot.get("requiredFor") or []
        if not any(a in required_for for a in actions):
            continue
        info = resolve_slot(slot_id, skill_root=root, manifest=manifest)
        items.append(info)
        if info["missing"] and not info["optional"]:
            blocking.append(str(info["label"]))

    return {
        "planReceiveDir": str(plan_receive_dir(root)),
        "planSplitInputDir": str(plan_split_input_dir(root)),
        "planDispatchInputDir": str(plan_dispatch_input_dir(root)),
        "cloudopsInputDir": str(cloudops_input_dir(root)),
        "forActions": actions,
        "slots": items,
        "ok": len(blocking) == 0,
        "blocking": blocking,
    }


def load_second_to_third(skill_root: Path | None = None) -> dict[str, list[str]]:
    root = skill_root or skill_root_from_cwd()
    path = root / "data" / "rules" / "second_to_third.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "map" in raw and isinstance(raw["map"], dict):
        return {str(k): list(v) for k, v in raw["map"].items() if isinstance(v, list)}
    if isinstance(raw, dict):
        return {str(k): list(v) for k, v in raw.items() if isinstance(v, list)}
    return {}
