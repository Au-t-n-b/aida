"""
device_install dc_paths · 数据中心语义寻址 SSOT（《数据中心 API 调用规范》§3.1）。

每个业务文件 = 一个 DcLoc：语义键（moduleCode + fileStage + folderSubPath + fileName）
+ 挂载盘降级相对目录（业务树 {AIDA_BUSINESS_ROOT}/project/<域>/<模块>/<阶段> 之内）。

模块代码（《05 数据目录与平台规范》）：
  pm-plan    交付/任务计划表→输出结果；到货信息表→输入文件
  ops-design 设备位置表→输出结果（folderSubPath=建模仿真）
  ops-install 本模块产物（责任人表/实施计划/SN扫码表/完工清单/完工报告）→输出结果
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.datacenter.types import SemanticFileRef

from .bridge import business_root

# 业务树内单项目根（路径整改通用规范：单数 project/，不含 project_id 段）
PROJECT_SUBDIR = "project"

MODULE_PM_PLAN = "pm-plan"
MODULE_OPS_DESIGN = "ops-design"
MODULE_OPS_INSTALL = "ops-install"

STAGE_INPUT = "输入文件"
STAGE_PARSE = "解析结果"
STAGE_OUTPUT = "输出结果"


@dataclass(frozen=True)
class DcLoc:
    """数据中心语义位置 + 挂载盘降级目录。"""

    module_code: str
    project_rel: str  # 业务树内相对 {root}/project/ 的目录（挂载盘降级 + 人读提示）
    file_stage: str | None = None
    folder_sub_path: str | None = None
    file_name: str | None = None

    def ref(self, project_id: str | None, *, file_name: str | None = None) -> SemanticFileRef:
        return SemanticFileRef(
            module_code=self.module_code,
            file_stage=self.file_stage,
            folder_sub_path=self.folder_sub_path,
            file_name=file_name or self.file_name,
            project_id=project_id or None,
        )

    def disk_dir(self) -> Path:
        """挂载盘降级目录: {AIDA_BUSINESS_ROOT}/project/<project_rel>。"""
        return (business_root() / PROJECT_SUBDIR / self.project_rel).resolve()

    def describe(self) -> str:
        """人读位置（HITL 提示 / 错误信息）。"""
        parts = [self.module_code]
        if self.file_stage:
            parts.append(self.file_stage)
        if self.folder_sub_path:
            parts.append(self.folder_sub_path)
        return "/".join(parts)


# ── 上游读取（3 表）──────────────────────────────────────────────────────────

def delivery_plan_loc() -> DcLoc:
    """《交付计划表》→ pm-plan/输出结果（项目管理/计划/输出结果）。"""
    return DcLoc(
        module_code=MODULE_PM_PLAN,
        file_stage=STAGE_OUTPUT,
        project_rel="项目管理/计划/输出结果",
    )


def arrival_loc() -> DcLoc:
    """《到货信息表》→ pm-plan/输入文件（项目管理/计划/输入文件）。"""
    return DcLoc(
        module_code=MODULE_PM_PLAN,
        file_stage=STAGE_INPUT,
        project_rel="项目管理/计划/输入文件",
    )


def position_loc() -> DcLoc:
    """《设备位置表》→ ops-design/输出结果/建模仿真（交付作业/规划设计/输出结果）。"""
    return DcLoc(
        module_code=MODULE_OPS_DESIGN,
        file_stage=STAGE_OUTPUT,
        folder_sub_path="建模仿真",
        project_rel="交付作业/规划设计/输出结果",
    )


# ── 本模块产物 ────────────────────────────────────────────────────────────────

def install_output_loc(file_name: str | None = None) -> DcLoc:
    """设备安装产物 → ops-install/输出结果（交付作业/设备安装/输出结果）。"""
    return DcLoc(
        module_code=MODULE_OPS_INSTALL,
        file_stage=STAGE_OUTPUT,
        project_rel="交付作业/设备安装/输出结果",
        file_name=file_name,
    )


def install_parse_loc(file_name: str | None = None) -> DcLoc:
    """设备安装解析结果（可选上传，运行态 JSON）→ ops-install/解析结果。"""
    return DcLoc(
        module_code=MODULE_OPS_INSTALL,
        file_stage=STAGE_PARSE,
        project_rel="交付作业/设备安装/解析结果",
        file_name=file_name,
    )


# 作业产物逻辑键前缀（SDUI artifact.path / /artifact 解析约定）
ARTIFACT_PREFIX = f"{MODULE_OPS_INSTALL}/{STAGE_OUTPUT}"


def artifact_key(file_name: str) -> str:
    """产物文件名 → 稳定逻辑键（ops-install/输出结果/<文件名>）。"""
    name = Path(str(file_name).replace("\\", "/")).name
    return f"{ARTIFACT_PREFIX}/{name}"


def artifact_key_name(key: str) -> str:
    """逻辑键 / 任意路径 → 文件名（/artifact 解析）。"""
    return Path(str(key).replace("\\", "/")).name


# ── project_id 解析 ──────────────────────────────────────────────────────────

_log = logging.getLogger("device_install.dc_paths")

# 数据中心 projectId 形态：UUID32（32 位十六进制，无连字符）；亦兼容带连字符 UUID（去字符后判定）。
_UUID32_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def _normalize_uuid32(raw: str) -> str:
    """规整为 UUID32：去连字符后须为 32 位 hex；否则返回空串（非法）。"""
    candidate = str(raw or "").strip().replace("-", "")
    return candidate.lower() if _UUID32_RE.match(candidate) else ""


def resolve_project_id(project: dict[str, Any] | None = None) -> str:
    """解析 projectId，**只认 UUID32**（《API 规范》§3.1 / §5.2 runtime-context）。

    来源优先级：run project 的 project_id/projectId/id → 环境变量 AIDA_PROJECT_ID。
    业务短码（project_code/projectCode 如 K1903）**不再作为 projectId**——
    它们不是数据中心语义寻址键，混用会导致跨模块 projectId 对不上。
    解析不到合法 UUID32 时返回空串（挂载盘降级不依赖 projectId）。
    """
    if project:
        for key in ("project_id", "projectId", "id"):
            raw = str(project.get(key) or "").strip()
            if not raw:
                continue
            norm = _normalize_uuid32(raw)
            if norm:
                return norm
            _log.warning(
                "device_install: run project.%s=%r 非 UUID32，已忽略（projectId 须为数据中心 UUID32）",
                key, raw,
            )
    for env_key in ("AIDA_PROJECT_ID", "AIDA_DEFAULT_PROJECT_ID"):
        raw = os.environ.get(env_key, "").strip()
        if not raw:
            continue
        norm = _normalize_uuid32(raw)
        if norm:
            return norm
        _log.warning(
            "device_install: %s=%r 非 UUID32，已忽略（请填数据中心 UUID32 projectId）",
            env_key, raw,
        )
    return ""
