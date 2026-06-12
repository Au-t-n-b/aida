"""系统设计 SkillContext · 路径走 project_paths.json（非 work_root/ProjectData 拼接）。"""
from __future__ import annotations

from pathlib import Path

from ..base import SkillContext
from .pipelines.path_manifest import (
    abs_artifacts_dir,
    abs_upload_dir,
    resolve_data_root,
)


class SystemDesignContext(SkillContext):
    @property
    def input_dir(self) -> Path:
        return abs_upload_dir()

    @property
    def output_dir(self) -> Path:
        return abs_artifacts_dir()

    def ensure_dirs(self) -> None:
        """不再批量 mkdir；各写入点按需 ensure_parent_dir。"""
        return


def as_sd_context(ctx: SkillContext) -> SystemDesignContext:
    if isinstance(ctx, SystemDesignContext):
        return ctx
    return SystemDesignContext(
        skill_id=ctx.skill_id,
        work_root=resolve_data_root(),
        run_id=ctx.run_id,
        project=ctx.project,
        llm_factory=ctx._llm_factory,
        emit_push=ctx.emit_push,
    )
