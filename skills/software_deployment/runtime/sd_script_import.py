"""从 ``software_deployment/<序号>_*/scripts/*.py`` 加载子 skill 脚本（目录名以数字开头，不能常规 import）。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_CACHE: dict[str, ModuleType] = {}


def sd_business_root(skill_root: Path) -> Path:
    return Path(skill_root).resolve() / "software_deployment"


def import_sd_script(skill_root: Path, step_folder: str, module_stem: str) -> ModuleType:
    """
    ``step_folder`` 如 ``1_plan_receive``、``2_plan_split``；
    ``module_stem`` 为文件名不含 ``.py``。
    """
    key = f"{Path(skill_root).resolve()}::{step_folder}/{module_stem}"
    if key in _CACHE:
        return _CACHE[key]

    base_dir = sd_business_root(skill_root) / Path(step_folder)
    scripts_dir = base_dir / "scripts"
    path = scripts_dir / f"{module_stem}.py"
    if not path.is_file():
        # 少数 shared 模块直接放在目录根（如 report_aggregate.py）
        alt = base_dir / f"{module_stem}.py"
        if alt.is_file():
            path = alt
            scripts_dir = base_dir
        else:
            raise FileNotFoundError(f"子 skill 脚本不存在: {path}")

    # 先加载同目录 constants，避免 ``from . import constants`` 在单文件加载时失败
    if module_stem != "constants":
        const_py = scripts_dir / "constants.py"
        if const_py.is_file():
            const_key = f"{Path(skill_root).resolve()}::{step_folder}/constants"
            if const_key not in _CACHE:
                import_sd_script(skill_root, step_folder, "constants")

    pkg_scripts = f"sd_{step_folder.replace('-', '_').replace('/', '_')}_scripts"
    if pkg_scripts not in sys.modules:
        pkg = importlib.util.module_from_spec(
            importlib.util.spec_from_loader(pkg_scripts, loader=None)
        )
        pkg.__path__ = [str(scripts_dir)]  # type: ignore[attr-defined]
        sys.modules[pkg_scripts] = pkg

    fq_name = f"{pkg_scripts}.{module_stem}"
    spec = importlib.util.spec_from_file_location(fq_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载: {path}")

    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = pkg_scripts
    sys.modules[fq_name] = mod
    spec.loader.exec_module(mod)
    _CACHE[key] = mod
    return mod
