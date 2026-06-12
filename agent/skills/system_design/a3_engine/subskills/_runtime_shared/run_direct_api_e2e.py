#!/usr/bin/env python3
"""Direct Python API e2e (no CLI): call generate_* and verify output xlsx exists."""
from __future__ import annotations

import importlib.util
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Optional

SUBSKILLS_ROOT = Path(__file__).resolve().parent.parent
E2E_ROOT = Path(__file__).resolve().parent / "e2e_direct_api"


def _load_module(scripts_dir: Path, module_name: str):
    path = scripts_dir / f"{module_name}.py"
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(f"_e2e_{module_name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    if str(SUBSKILLS_ROOT) not in sys.path:
        sys.path.insert(0, str(SUBSKILLS_ROOT))
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _first_existing(*paths: Path) -> Optional[Path]:
    for p in paths:
        if p.is_file():
            return p
    return None


def _find_007_resource(pkg: Path) -> tuple[Optional[Path], Optional[Path]]:
    p007 = _first_existing(
        pkg / "reference" / "建模仿真输出文档007-端口连线表.xlsx",
        pkg / "reference" / "建模仿真输出文档007-端口连线表for all4.xlsx",
        pkg / "建模仿真输出文档007-端口连线表.xlsx",
        pkg / "建模仿真输出文档007-端口连线表for all4.xlsx",
        pkg / "建模仿真输出文档007-端口连线表(2) (2).xlsx",
    )
    res = _first_existing(
        pkg / "reference" / "项目信息收集表.xlsx",
        pkg / "项目信息收集表.xlsx",
        pkg / "项目信息收集表模板CCAENCE-0104补齐IP(LEAF).xlsx",
    )
    return p007, res


def _run_case(
    name: str,
    pkg_rel: str,
    module: str,
    func: str,
    kwargs: dict[str, Any],
) -> tuple[str, str, Optional[Path]]:
    pkg = SUBSKILLS_ROOT / pkg_rel
    out_dir = E2E_ROOT / name
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    kwargs = {**kwargs, "out_dir": out_dir}
    try:
        mod = _load_module(pkg / "scripts", module)
        fn = getattr(mod, func)
        result = fn(**kwargs)
        out_path = Path(result) if result is not None else None
        if out_path is None or not out_path.is_file():
            xlsx = sorted(out_dir.rglob("*.xlsx"))
            if not xlsx:
                return "fail", "no xlsx under out_dir", None
            out_path = xlsx[-1]
        return "pass", str(out_path.relative_to(SUBSKILLS_ROOT)), out_path
    except Exception as e:
        tb = traceback.format_exc(limit=3)
        return "fail", f"{type(e).__name__}: {e}\n{tb}", None


def _build_cases() -> list[tuple[str, str, str, str, dict[str, Any]]]:
    cases: list[tuple[str, str, str, str, dict[str, Any]]] = []

    def add(name: str, pkg: str, mod: str, fn: str, kw: dict[str, Any]) -> None:
        cases.append((name, pkg, mod, fn, kw))

    # --- packages with bundled sample xlsx ---
    for short, pkg in (
        ("ywm", "a3-ywm-ip-workflow.code1"),
        ("ybm", "a3-ybm-ip-workflow.code1"),
        ("dw", "a3-dw-manage-ip-workflow.code1"),
        ("l2l3", "a3-l2-l3-ip-workflow.code1"),
        ("cc-glm", "a3-cc-glm-ip-workflow.code1"),
    ):
        p = SUBSKILLS_ROOT / pkg
        p007, res = _find_007_resource(p)
        if not p007 or not res:
            continue
        base = {
            "path_007": p007,
            "resource": res,
            "restrict_to_cwd": False,
        }
        if short == "ywm":
            add(
                "ywm_i3",
                pkg,
                "offline_ywm_pipeline",
                "generate_ywm_ip_xlsx",
                {
                    **base,
                    "topology": "i3",
                    "fail_on_insufficient": False,
                    "server_substring": "",
                    "prompt_spine_file": None,
                    "prompt_leaf_file": None,
                },
            )
        elif short == "ybm":
            add(
                "ybm_i3",
                pkg,
                "ybm_offline_pipeline",
                "generate_ybm_ip_xlsx",
                {
                    **base,
                    "topology": "i3",
                    "server_substring": "",
                    "fail_on_insufficient": False,
                    "prompt_spine_file": None,
                    "prompt_leaf_file": None,
                },
            )
        elif short == "dw":
            add(
                "dw_manage",
                pkg,
                "offline_dw_manage_pipeline",
                "generate_dw_manage_ip_address_xlsx",
                {
                    **base,
                    "prompt_spine_file": None,
                    "prompt_leaf_file": None,
                },
            )
        elif short == "l2l3":
            add(
                "l2l3_auto",
                pkg,
                "offline_l2_l3_ip_pipeline",
                "generate_l2_l3_planning_xlsx",
                {**base, "mode": "auto", "sheet": "计算管理面端口互联"},
            )
        elif short == "cc-glm":
            add(
                "cc_glm",
                pkg,
                "offline_cc_glm_pipeline",
                "generate_cc_glm_ip_address_xlsx",
                {
                    "path_connect": p007,
                    "resource": res,
                    "restrict_to_cwd": False,
                    "prompt_i2_file": None,
                    "prompt_i3_file": None,
                    "layer": None,
                },
            )

    return cases


def _run_oob() -> tuple[str, str, Optional[Path]]:
    oob_pkg = SUBSKILLS_ROOT / "oob-interconnect-workflow.code1"
    p007, res = _find_007_resource(oob_pkg)
    if not p007 or not res:
        return "skip", "no sample xlsx in oob package", None
    out_dir = E2E_ROOT / "oob_l3"
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "A3网络互联规划.xlsx"
    if str(oob_pkg) not in sys.path:
        sys.path.insert(0, str(oob_pkg))
    try:
        from oob_interconnect.pipeline import run_l3

        run_l3(
            topology_path=p007,
            sheet_name="计算带外管理互联规划",
            resource_path=res,
            output_path=out_file,
        )
        if not out_file.is_file():
            return "fail", "run_l3 finished but no output file", None
        return "pass", str(out_file.relative_to(SUBSKILLS_ROOT)), out_file
    except Exception as e:
        return "fail", f"{type(e).__name__}: {e}", None


def main() -> int:
    if str(SUBSKILLS_ROOT) not in sys.path:
        sys.path.insert(0, str(SUBSKILLS_ROOT))
    E2E_ROOT.mkdir(parents=True, exist_ok=True)

    print("=== Direct API e2e (Python call generate_*, no CLI) ===")
    print(f"SUBSKILLS_ROOT={SUBSKILLS_ROOT}")
    print(f"E2E_OUT={E2E_ROOT}\n")

    rows: list[tuple[str, str, str]] = []

    for name, pkg, module, func, kwargs in _build_cases():
        st, detail, _ = _run_case(name, pkg, module, func, kwargs)
        rows.append((name, st, detail))
        print(f"[{st}] {name}")
        if st == "fail":
            print(detail)

    st, detail, _ = _run_oob()
    rows.append(("oob_l3", st, detail))
    print(f"[{st}] oob_l3")
    if st == "fail":
        print(detail)

    print("\n=== SUMMARY ===")
    for name, st, detail in rows:
        line = f"{st:4}  {name}"
        if st == "pass" and detail:
            line += f"  ->  {detail}"
        elif st in ("fail", "skip"):
            line += f"  |  {detail[:120]}"
        print(line)

    fail_n = sum(1 for _, s, _ in rows if s == "fail")
    pass_n = sum(1 for _, s, _ in rows if s == "pass")
    print(f"\npass={pass_n} fail={fail_n} skip={sum(1 for _, s, _ in rows if s == 'skip')}")
    return 1 if fail_n else 0


if __name__ == "__main__":
    raise SystemExit(main())
