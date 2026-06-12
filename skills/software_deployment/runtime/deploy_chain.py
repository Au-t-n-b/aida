"""deploy_chain.json：记录步骤 ①～⑪ 进度（字段名与用户可见步骤号一致）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# 加载时迁移后剥离的旧键（含已删除的独立 ZTP 步骤与 12 步时代的偏移编号）
DEPRECATED_KEYS: tuple[str, ...] = (
    "step2_test_activities_path",
    "step2_test_activities_extracted_at",
    "step7_ztp_receive_at",
    "step7_ztp_path",
    "step7_ztp_source",
    "step8_executor_config_at",
    "step9_toolkit_import_at",
    "step10_init_install_at",
    "step11_subsystem_test_at",
    "step12_cluster_test_at",
)

_LEGACY_FIELD_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("step7_ztp_path", "step6_ztp_path"),
    ("step7_ztp_receive_at", "step6_ztp_at"),
    ("step7_ztp_source", "step6_ztp_source"),
    ("step8_executor_config_at", "step7_executor_config_at"),
    ("step9_toolkit_import_at", "step8_toolkit_import_at"),
    ("step10_init_install_at", "step9_init_install_at"),
    ("step11_subsystem_test_at", "step10_subsystem_test_at"),
    ("step12_cluster_test_at", "step11_cluster_test_at"),
)


def _chain_path(skill_root: Path) -> Path:
    return skill_root / "ProjectData" / "plan" / "RunTime" / "deploy_chain.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _migrate_legacy_fields(chain: dict[str, Any]) -> dict[str, Any]:
    """将旧字段迁入新 stepN_* 后剥离废弃键。"""
    for old_key, new_key in _LEGACY_FIELD_MIGRATIONS:
        if not chain.get(new_key) and chain.get(old_key):
            chain[new_key] = chain[old_key]
    for key in DEPRECATED_KEYS:
        chain.pop(key, None)
    return chain


def _defaults(skill_root: Path) -> dict[str, Any]:
    return {
        "schemaVersion": 3,
        "project_id": "",
        # ① 接收二级任务
        "step1_plan_receive_at": None,
        "step1_second_tasks_path": "",
        "step1_scene_path": "",
        "step1_task_count": 0,
        # ② 拆分（验收用例 Word 只做存在性检查；不再提取测试活动）
        "step2_plan_split_at": None,
        "step2_third_tasks_path": "",
        "step2_testcase_path": "",
        "step2_third_task_count": 0,
        # ③ 下发
        "step3_plan_dispatch_at": None,
        "step3_lld_path": "",
        "step3_device_base_path": "",
        "step3_dispatch_record_path": "",
        "step3_checklist_path": "",
        # ④～⑪ CloudOps / Toolkit / 下发调测
        "step4_cloudops_init_at": None,
        "step5_cloudops_supplement_at": None,
        "step6_cloudops_full_at": None,
        "step4_cloudops_output_path": "",
        "step4_cloudops_lld_source": "",
        "step5_cloudops_manual_path": "",
        "step5_checklist_detected": False,
        "step6_cloudops_full_path": "",
        "step6_materials_checked_at": None,
        "step6_materials_ready_at": None,
        "step6_ztp_at": None,
        "step6_ztp_path": "",
        "step6_ztp_source": "",
        "step6_params_at": None,
        "step6_params_path": "",
        "step7_executor_config_at": None,
        "step8_toolkit_import_at": None,
        "step9_init_install_at": None,
        "step10_subsystem_test_at": None,
        "step11_cluster_test_at": None,
        "updated_at": None,
    }


def load_chain(skill_root: Path) -> dict[str, Any]:
    p = _chain_path(skill_root)
    if not p.is_file():
        return _defaults(skill_root)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            out = _defaults(skill_root)
            out.update(raw)
            if out.get("schemaVersion", 1) < 3:
                out["schemaVersion"] = 3
            return _migrate_legacy_fields(out)
    except Exception:
        pass
    return _defaults(skill_root)


def save_chain(skill_root: Path, chain: dict[str, Any]) -> None:
    chain["updated_at"] = _iso_now()
    p = _chain_path(skill_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(chain, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_chain(skill_root: Path, **kwargs: Any) -> dict[str, Any]:
    c = load_chain(skill_root)
    for k, v in kwargs.items():
        if v is not None:
            c[k] = v
    save_chain(skill_root, c)
    return c


def clear_from_step(skill_root: Path, from_step: int = 4) -> dict[str, Any]:
    """from_step 1～3 清计划链；4～11 清 CloudOps/Toolkit。"""
    if from_step <= 3:
        from plan_chain import clear_plan_from_step

        return clear_plan_from_step(skill_root, from_step)

    c = load_chain(skill_root)
    step_keys: list[tuple[int, str, Any]] = [
        (4, "step4_cloudops_init_at", None),
        (4, "step4_cloudops_output_path", ""),
        (4, "step4_cloudops_lld_source", ""),
        (5, "step5_cloudops_supplement_at", None),
        (5, "step5_cloudops_manual_path", ""),
        (5, "step5_checklist_detected", False),
        (6, "step6_cloudops_full_at", None),
        (6, "step6_cloudops_full_path", ""),
        (6, "step6_materials_checked_at", None),
        (6, "step6_materials_ready_at", None),
        (6, "step6_ztp_at", None),
        (6, "step6_ztp_path", ""),
        (6, "step6_ztp_source", ""),
        (6, "step6_params_at", None),
        (6, "step6_params_path", ""),
        (7, "step7_executor_config_at", None),
        (8, "step8_toolkit_import_at", None),
        (9, "step9_init_install_at", None),
        (10, "step10_subsystem_test_at", None),
        (11, "step11_cluster_test_at", None),
    ]
    for step_no, key, default in step_keys:
        if step_no >= from_step:
            c[key] = default
    save_chain(skill_root, c)
    return c


def sync_step3_from_state(skill_root: Path) -> bool:
    """步骤 ③ 是否完成（deploy_chain.step3_plan_dispatch_at）。"""
    from plan_chain import is_step3_done, migrate_chain_from_state

    return is_step3_done(migrate_chain_from_state(skill_root))
