"""Map project-relative filesystem paths ↔ datacenter SemanticFileRef / logicalPath."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.datacenter.types import SemanticFileRef

IPO_STAGES = frozenset({"输入文件", "解析结果", "输出结果"})

# (domain, module_dir) → moduleCode; flat modules have no fileStage
_MODULE_MAP: dict[tuple[str, str], str] = {
    ("早期介入", "合同"): "contract",
    ("早期介入", "交付预案"): "proposal",
    ("孪生世界", "算力底座孪生"): "twin-foundation",
    ("孪生世界", "项目孪生"): "twin-project",
    ("项目管理", "计划"): "pm-plan",
    ("项目管理", "基本信息"): "pm-basic",
    ("项目管理", "任务"): "pm-task",
    ("项目管理", "风险"): "pm-risk",
    ("项目管理", "问题"): "pm-issue",
    ("项目管理", "假设"): "pm-assumption",
    ("项目管理", "变更"): "pm-change",
    ("交付作业", "智慧工勘"): "ops-survey",
    ("交付作业", "规划设计"): "ops-design",
    ("交付作业", "设备安装"): "ops-install",
    ("交付作业", "部署调测"): "ops-deploy",
    ("交付方案", "交付方案"): "delivery-scheme",
    ("项目复盘", "项目复盘"): "retro",
}

# flat modules: no IPO stage layer
_FLAT_MODULES = frozenset({"pm-basic", "program-docs", "org-assets"})


@dataclass(frozen=True)
class MappedPath:
    relative: str
    logical_path: str
    ref: SemanticFileRef


def normalize_relative(relative: str) -> str:
    return relative.replace("\\", "/").strip("/")


def org_assets_relative(relative: str) -> MappedPath | None:
    """Map org-assets/… or legacy 组织资产/… paths."""
    normalized = normalize_relative(relative)
    for prefix in ("org-assets/", "组织资产/"):
        if normalized.startswith(prefix):
            tail = normalized[len(prefix) :]
            parts = tail.split("/")
            file_name = parts[-1] if parts and "." in parts[-1] else None
            folder = "/".join(parts[:-1]) if file_name else "/".join(parts)
            ref = SemanticFileRef(
                module_code="org-assets",
                folder_sub_path=folder or None,
                file_name=file_name,
            )
            logical = f"org-assets/{tail}"
            return MappedPath(relative=normalized, logical_path=logical, ref=ref)
    return None


def map_project_relative(project_id: str, relative: str) -> MappedPath | None:
    """Parse projects/{id}/<relative> into datacenter semantic keys."""
    org = org_assets_relative(relative)
    if org:
        return org

    normalized = normalize_relative(relative)
    if not normalized:
        return None

    parts = normalized.split("/")
    if len(parts) < 2:
        return None

    domain, module_dir = parts[0], parts[1]
    module_code = _MODULE_MAP.get((domain, module_dir))
    if not module_code:
        return None

    rest = parts[2:]
    if module_code in _FLAT_MODULES or module_code == "program-docs":
        # flat: 项目管理/基本信息/xxx.xlsx
        file_name = rest[-1] if rest and "." in rest[-1] else None
        folder = "/".join(rest[:-1]) if file_name else "/".join(rest)
        ref = SemanticFileRef(
            project_id=project_id,
            module_code=module_code,
            folder_sub_path=folder or None,
            file_name=file_name,
        )
        logical = normalized
        return MappedPath(relative=normalized, logical_path=logical, ref=ref)

    if not rest or rest[0] not in IPO_STAGES:
        return None

    file_stage = rest[0]
    tail = rest[1:]
    file_name = tail[-1] if tail and "." in tail[-1] else None
    folder = "/".join(tail[:-1]) if file_name else "/".join(tail)

    ref = SemanticFileRef(
        project_id=project_id,
        module_code=module_code,
        file_stage=file_stage,
        folder_sub_path=folder or None,
        file_name=file_name,
    )
    return MappedPath(relative=normalized, logical_path=normalized, ref=ref)


def map_local_file(project_id: str, local_root: Path, file_path: Path) -> MappedPath | None:
    try:
        rel = file_path.relative_to(local_root).as_posix()
    except ValueError:
        return None
    return map_project_relative(project_id, rel)


def ref_for_relative(project_id: str, relative: str, *, file_name: str | None = None) -> SemanticFileRef:
    """Resolve a project-relative path; optional file_name override for directory targets."""
    mapped = map_project_relative(project_id, relative)
    if mapped is None:
        raise ValueError(f"cannot map project path: {relative}")
    ref = mapped.ref
    if file_name:
        return SemanticFileRef(
            project_id=ref.project_id,
            module_code=ref.module_code,
            file_stage=ref.file_stage,
            folder_sub_path=ref.folder_sub_path,
            file_name=file_name,
        )
    return ref
