"""交付阶段续跑路由 · LLD 完成后执行 ZTP / 发布时跳过前置规划步骤。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .path_manifest import abs_artifacts_dir
from .lld_artifacts import canonical_lld_abs, resolve_project_name
from .lld_merge import should_skip_integrate

# 与 SystemDesignSkill.steps[] 顺序一致
DELIVERY_STEP_KEYS: list[str] = [
    "input_check",
    "intent_recognition",
    "exec_confirm",
    "plane_planning",
    "lld_integrate",
    "stage_select",
    "naming_replace",
    "ztp_generate",
    "publish_confirm",
    "publish",
]

_ZTP_HINTS = ("ztp", "开局", "生成ztp", "skip_ztp", "rename_ztp")

_STAGE_SELECT_REASON = (
    "完整 LLD 设计已融合完成。请选择下一步执行计划：\n"
    "· 设备名称替换（可选）：把规划设备名替换为现网命名，再生成 ZTP 设计文件与 ZTP 配置文件；\n"
    "· 直接 ZTP：跳过名称替换，生成 ZTP 设计文件 + ZTP 配置文件（zip 开局包）。"
)


def stage_select_hitl() -> dict[str, Any]:
    """stage_select 确认门 HITL 载荷（step / reconcile / SDUI 共用）。"""
    return {
        "step": "stage_select",
        "reason": _STAGE_SELECT_REASON,
        "need_files": [],
        "need_inputs": [{
            "id": "stage",
            "label": "选择下一步执行计划",
            "options": [
                {
                    "label": "设备名称替换 + 生成 ZTP（设计文件 + 配置文件）",
                    "value": "rename_ztp",
                },
                {
                    "label": "跳过名称替换，直接生成 ZTP（设计文件 + 配置文件）",
                    "value": "skip_ztp",
                },
            ],
        }],
    }


def step_index(key: str) -> int:
    try:
        return DELIVERY_STEP_KEYS.index(key)
    except ValueError:
        return -1


def should_skip_step(step_key: str, route_to: str) -> bool:
    """当前 step 是否位于 route_to 之前（交付续跑时应快速跳过）。"""
    if not route_to or step_key == route_to:
        return False
    i, j = step_index(step_key), step_index(route_to)
    return i >= 0 and j >= 0 and i < j


def lld_artifact_exists(work_root: Path | str, prev_state: dict[str, Any] | None = None) -> bool:
    """磁盘或上轮 state 中是否已有完整 LLD 产物。"""
    _ = work_root
    prev_state = prev_state or {}
    if str((prev_state.get("files") or {}).get("lld_file") or "").strip():
        return True
    for step in prev_state.get("steps") or []:
        m = step.get("metrics") or {}
        if str(m.get("lld_file") or "").strip() and step.get("status") == "completed":
            return True
    canon = canonical_lld_abs(resolve_project_name(work_root))
    if canon.is_file():
        return True
    out = abs_artifacts_dir()
    if not out.is_dir():
        return False
    for p in out.rglob("*"):
        if not p.is_file() or p.name.startswith("~$"):
            continue
        if p.suffix.lower() not in (".xlsx", ".xls"):
            continue
        upper = p.name.upper()
        if "LLD" in upper and "ZTP" not in upper:
            return True
    return False


def is_ztp_delivery_intent(text: str) -> bool:
    t = str(text or "").strip().lower().replace(" ", "")
    if not t:
        return False
    if t in ("生成ztp设计文件", "ztp", "skip_ztp", "rename_ztp"):
        return True
    return any(h in t for h in _ZTP_HINTS)


def is_lld_delivery_intent(text: str) -> bool:
    """用户显式要求生成/融合完整 LLD。"""
    t = str(text or "").strip().replace(" ", "")
    if not t:
        return False
    if t in ("生成完整LLD设计", "融合完整LLD设计"):
        return True
    return ("完整" in t and "LLD" in t.upper()) or ("生成" in t and "LLD" in t.upper())


# 与 lld_config.INTEGRATE_PLANE_FILENAME_ALIASES / EXCLUDE 对齐（无 A3 前缀的平面表）
_MERGEABLE_PLANE_ALIASES = frozenset({"超平面网络规划.xlsx"})
_MERGEABLE_EXCLUDE_NAMES = frozenset({
    "网络设备接入规划.xlsx",
    "A3网络设备接入规划.xlsx",
})


def has_mergeable_plane_artifacts(work_root: Path | str) -> bool:
    """Output 下是否存在可融合的平面规划表（A3*.xlsx 或已知别名；排除 LLD/ZTP/接入底表）。"""
    _ = work_root
    out = abs_artifacts_dir()
    if not out.is_dir():
        return False
    skip_tokens = ("LLD", "ZTP", "接入查询", "设备清单", "命名映射")
    for p in out.rglob("*.xlsx"):
        if not p.is_file() or p.name.startswith("~$"):
            continue
        if p.name in _MERGEABLE_EXCLUDE_NAMES:
            continue
        if p.name in _MERGEABLE_PLANE_ALIASES:
            return True
        upper = p.name.upper()
        if not upper.startswith("A3"):
            continue
        if any(tok in upper for tok in skip_tokens):
            continue
        return True
    return False


def _payload_intent_text(
    project: dict[str, Any],
    payload: dict[str, Any],
) -> str:
    return str(
        payload.get("choice") or payload.get("value")
        or payload.get("text") or payload.get("command")
        or (project or {}).get("text") or ""
    ).strip()


def _plane_planning_done(prev_state: dict[str, Any]) -> bool:
    for rec in reversed(prev_state.get("steps") or []):
        if rec.get("key") != "plane_planning":
            continue
        if rec.get("status") not in ("completed", "hitl"):
            return False
        m = rec.get("metrics") or {}
        if m.get("plan_commands") or int(m.get("plane_done") or 0) > 0:
            return True
        return rec.get("status") == "completed"
    return False


def resolve_resume_route_to(
    *,
    hitl_step: str,
    project: dict[str, Any],
    payload: dict[str, Any],
    prev_state: dict[str, Any],
    work_root: Path,
) -> str | None:
    """根据 HITL 步骤与用户选择，决定 full_restart 应从哪个 step 续跑（route_to）。"""
    text = _payload_intent_text(project, payload)
    if is_lld_delivery_intent(text):
        normalized = text.replace(" ", "")
        if normalized == "生成完整LLD设计":
            skip, _ = should_skip_integrate(work_root)
            if skip and lld_artifact_exists(work_root, prev_state):
                return "stage_select"
            return "plane_planning"
        if hitl_step == "plane_planning":
            return "lld_integrate"
        if has_mergeable_plane_artifacts(work_root) or _plane_planning_done(prev_state):
            return "lld_integrate"

    if hitl_step == "stage_select":
        stage = dict(project.get("stage") or {})
        if stage.get("chosen") and not stage.get("naming"):
            return "ztp_generate"
        return "naming_replace"

    if hitl_step == "publish_confirm":
        choice = str(
            payload.get("choice") or payload.get("value") or payload.get("text") or ""
        ).strip()
        if choice in ("confirm", "确认发布", "确认"):
            return "publish"
        return "publish_confirm"

    if not hitl_step and lld_artifact_exists(work_root, prev_state):
        if is_ztp_delivery_intent(text):
            stage = dict(project.get("stage") or {})
            if not stage.get("chosen"):
                low = text.lower()
                stage["chosen"] = True
                stage["naming"] = ("rename" in low or "名称" in text) and "skip" not in low
                project["stage"] = stage
            return "naming_replace" if stage.get("naming") else "ztp_generate"

    return None
