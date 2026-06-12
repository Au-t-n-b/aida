"""发现 Skill 本地设备安装完工清单路径（供 checklist_to_cloudops 读取）。"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path


def _co_constants():
    root = Path(os.environ.get("SD_SKILL_ROOT", Path.cwd())).resolve()
    rt = root / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    from sd_script_import import import_sd_script  # noqa: WPS433

    return import_sd_script(root, "4_cloudops_init", "constants")


_c = _co_constants()
DeviceCheckListColumns = _c.DeviceCheckListColumns

_CHECKLIST_NAME_PATTERNS = (
    "*设备安装完工清单*.xlsx",
    "*完工清单*.xlsx",
)


def _skill_project_data(skill_dir: str) -> str:
    return os.path.join(os.path.abspath(skill_dir), "ProjectData")


def _is_checklist_basename(name: str) -> bool:
    if "完工清单" in name or "设备安装完工清单" in name:
        return True
    low = name.lower()
    if "cloudops" in low or "lld" in low or "cpq" in low or "到货" in low or "人员" in low:
        return False
    return False


def _glob_checklists_in_dir(folder: str, *, allow_any_xlsx: bool = False) -> list[str]:
    if not os.path.isdir(folder):
        return []
    found: list[str] = []
    patterns = list(_CHECKLIST_NAME_PATTERNS)
    if allow_any_xlsx:
        patterns.append("*.xlsx")
    for pat in patterns:
        found.extend(glob.glob(os.path.join(folder, pat)))
    out: list[str] = []
    for p in found:
        base = os.path.basename(p)
        if not base.lower().endswith(".xlsx"):
            continue
        if "手工补充" in base or "初始配置" in base or "完整配置" in base:
            continue
        if allow_any_xlsx or _is_checklist_basename(base):
            out.append(p)
    return out


def _dedupe_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for p in sorted(paths, key=os.path.getmtime, reverse=True):
        key = os.path.normcase(os.path.abspath(p))
        if key in seen or not os.path.isfile(key):
            continue
        seen.add(key)
        out.append(p)
    return out


def collect_local_checklist_paths(skill_dir: str) -> list[str]:
    """只收集 ``ProjectData/input`` 下文件名明确的完工清单。"""
    root = os.path.abspath(skill_dir)
    paths: list[str] = []
    for folder in (
        os.path.join(root, "ProjectData", "input", "cloudops"),
        os.path.join(root, "ProjectData", "input"),
        os.path.join(root, "ProjectData", "Input", "Device_Checklist"),
        os.path.join(root, "ProjectData", "Input"),
    ):
        paths.extend(_glob_checklists_in_dir(folder, allow_any_xlsx=False))
    return _dedupe_paths(paths)


def resolve_checklist_paths(skill_dir: str) -> tuple[list[str], str]:
    """解析完工清单路径（本地 input 目录，本地上传优先于同名旧文件）。"""
    paths = collect_local_checklist_paths(skill_dir)
    if paths:
        return paths, f"local:{len(paths)}"
    return [], ""


def _filter_valid_checklist_paths(paths: list[str]) -> list[str]:
    """仅保留表头含「设备名称」「ESN」的文件。"""
    import pandas as pd

    valid: list[str] = []
    for p in paths:
        if not os.path.isfile(p):
            continue
        try:
            header = pd.read_excel(p, sheet_name=0, nrows=0)
            cols = list(header.columns)
        except Exception:
            continue
        if DeviceCheckListColumns.SERIAL_NUMBER not in cols:
            for alt in ("SN", "sn", "序列号"):
                if alt in cols:
                    break
            else:
                continue
        if DeviceCheckListColumns.DEVICE_NAME not in cols:
            continue
        valid.append(p)
    return valid


def probe_checklist(*, skill_dir: str) -> tuple[bool, str]:
    """探测是否存在可用完工清单。"""
    paths, src = resolve_checklist_paths(skill_dir)
    valid = _filter_valid_checklist_paths(paths)
    if not valid:
        return False, ""
    names = [os.path.basename(p) for p in valid[:3]]
    hint = "、".join(names)
    if len(valid) > 3:
        hint += f" 等 {len(valid)} 个"
    return True, f"local:{len(valid)}（{hint}）"


def is_valid_checklist_dataframe(columns: list[str]) -> bool:
    """完工清单至少须含设备名称与 ESN 列。"""
    cols = {str(c).strip() for c in columns}
    need = {DeviceCheckListColumns.DEVICE_NAME, DeviceCheckListColumns.SERIAL_NUMBER}
    return need.issubset(cols)
