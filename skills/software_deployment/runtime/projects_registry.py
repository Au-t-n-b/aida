"""Load projects registry and map ``profile`` → plan ``scene.json``.

默认读 AIDA 仓库 ``skills/software_deployment/data/projects.json``；
可用 ``SD_PROJECTS_JSON`` 覆盖。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_SKILL_PKG_ROOT = Path(__file__).resolve().parents[1]


def registry_projects_path() -> Path:
    env = (os.environ.get("SD_PROJECTS_JSON") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    sd_root = (os.environ.get("SD_SKILL_ROOT") or os.environ.get("SOFTWARE_DEPLOYMENT_ROOT") or "").strip()
    if sd_root:
        candidate = Path(sd_root).expanduser().resolve() / "data" / "projects.json"
        if candidate.is_file():
            return candidate
    return (_SKILL_PKG_ROOT / "data" / "projects.json").resolve()


def load_projects_doc(path: Path | None = None) -> dict[str, Any]:
    p = path or registry_projects_path()
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def pick_project(doc: dict[str, Any], project_id: str | None) -> dict[str, Any] | None:
    projects = doc.get("projects")
    if not isinstance(projects, list):
        return None
    pid = (project_id or "").strip()
    if pid:
        for item in projects:
            if isinstance(item, dict) and str(item.get("projectId") or "") == pid:
                return item
    for item in projects:
        if isinstance(item, dict):
            return item
    return None


def profile_to_scene(profile: dict[str, Any], *, project_id: str | None = None) -> dict[str, Any]:
    """Map v2 profile (Chinese enums) to keys used by plan ``scene.json`` / agent_impl."""
    ps = str(profile.get("productSpecification") or "").strip().upper()
    cooling_zh = str(profile.get("coolingScene") or "").strip()
    cooling = "air_cooling" if cooling_zh == "风冷" else "liquid_cooling"

    ti_zh = str(profile.get("trainInferScene") or "").strip()
    ti_map = {"推理": "infer", "训练": "train", "训推": "train_infer"}
    train_infer_scene = ti_map.get(ti_zh, "infer")

    pod_zh = str(profile.get("podScene") or "单Pod").strip()
    pod_info = "multi_pods" if pod_zh == "多Pod" else "single_pod"

    scene: dict[str, Any] = {
        "productSpecification": ps,
        "cooling": cooling,
        "coolingScene": cooling_zh,
        "trainInferScene": ti_zh,
        "train_infer_scene": train_infer_scene,
        "podInfo": pod_info,
        "pod_info": pod_info,
        "pod_scene": pod_zh,
        "projectCode": str(profile.get("projectCode") or "").strip(),
        "language": str(profile.get("language") or "zh").strip(),
        "source": "projects.json",
    }
    if project_id:
        scene["projectId"] = project_id
    if profile.get("startDate"):
        scene["startDate"] = profile.get("startDate")
    if profile.get("siteReadyDate"):
        scene["siteReadyDate"] = profile.get("siteReadyDate")
    return scene


def sync_scene_from_projects(
    skill_root: Path,
    *,
    project_id: str | None = None,
    projects_path: Path | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Write ``ProjectData/plan/RunTime/scene.json`` from registry. Returns (scene, error)."""
    doc = load_projects_doc(projects_path)
    proj = pick_project(doc, project_id)
    if not proj:
        return None, (
            "未找到项目：请确认 data/projects.json 存在且含 projects[]，"
            "或设置 SD_PROJECTS_JSON / 在请求中传入 project_id。"
        )
    prof = proj.get("profile")
    if not isinstance(prof, dict):
        return None, "项目缺少 profile 字段，无法生成场景。"
    pid = str(proj.get("projectId") or project_id or "").strip() or None
    scene = profile_to_scene(prof, project_id=pid)
    out = skill_root / "ProjectData" / "plan" / "RunTime" / "scene.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    return scene, None
