#!/usr/bin/env python3
"""Minimal CLI/import smoke for each subskills/*.code1 package (standalone layout)."""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

SUBSKILLS_ROOT = Path(__file__).resolve().parent.parent
SHARED_ROOT = SUBSKILLS_ROOT / "_runtime_shared"

SMOKE_TARGETS: dict[str, tuple[str, list[str]]] = {
    "a3-cc-glm-ip-workflow.code1": ("scripts/offline_cc_glm_pipeline.py", ["--help"]),
    "a3-cc-ybm-ip-workflow.code1": ("scripts/offline_cc_ybm_pipeline.py", ["--help"]),
    "a3-cc-ywm-ip-workflow.code1": ("scripts/offline_cc_ywm_pipeline.py", ["--help"]),
    "a3-compute-net-interconnect-l2-l3-workflow.code1": (
        "scripts/offline_net_interconnect_pipeline.py",
        ["--help"],
    ),
    "a3-cpm-lq-ip-workflow.code1": ("scripts/offline_cpm_lq_ip_pipeline.py", ["--help"]),
    "a3-csm-ip-workflow.code1": ("scripts/offline_csm_pipeline.py", ["--help"]),
    "a3-device-naming-workflow.code1": (
        "scripts/offline_device_naming_pipeline.py",
        ["--help"],
    ),
    "a3-dw-manage-ip-workflow.code1": ("scripts/offline_dw_manage_pipeline.py", ["--help"]),
    "a3-gcm-ip-workflow.code1": ("scripts/offline_gcm_pipeline.py", ["--help"]),
    "a3-generate-lq-open-workflow.code1": (
        "scripts/offline_generate_lq_open_pipeline.py",
        ["--help"],
    ),
    "a3-generate-ztp-cfg-workflow.code1": (
        "scripts/offline_generate_ztp_cfg_pipeline.py",
        ["--help"],
    ),
    "a3-generate-ztp-lld-workflow.code1": (
        "scripts/offline_generate_ztp_lld_pipeline.py",
        ["--help"],
    ),
    "a3-input-components-workflow.code1": (
        "scripts/offline_input_components_pipeline.py",
        ["--help"],
    ),
    "a3-l2-l3-ip-workflow.code1": ("scripts/offline_l2_l3_ip_pipeline.py", ["--help"]),
    "a3-lq-dw-manage-ip-workflow.code1": (
        "scripts/offline_lq_dw_manage_pipeline.py",
        ["--help"],
    ),
    "a3-net-dw-manage-ip-workflow.code1": (
        "scripts/offline_net_dw_manage_pipeline.py",
        ["--help"],
    ),
    "a3-net-interconnection-workflow.code1": ("scripts/offline_ni_pipeline.py", ["--help"]),
    "a3-storage-dw-manage-ip-workflow.code1": (
        "scripts/offline_storage_dw_manage_pipeline.py",
        ["--help"],
    ),
    "a3-switch-asn-workflow.code1": ("scripts/offline_switch_asn_pipeline.py", ["--help"]),
    "a3-ybm-ip-workflow.code1": ("scripts/ybm_offline_pipeline.py", ["--help"]),
    "a3-ywm-ip-workflow.code1": ("scripts/offline_ywm_pipeline.py", ["--help"]),
    "a3_LLD_generate_code1": ("scripts/offline_lld_generate_pipeline.py", ["--help"]),
    "ccae-planner.code1": ("scripts/run_ccae_planner.py", ["--help"]),
    "dme-planning.code1": ("scripts/generate_dme_plan.py", ["--help"]),
    "lld-dispatch-orchestrator.code1": ("scripts/offline_dispatch_pipeline.py", ["list"]),
    "net-dw-access-ip-workflow.code1": ("scripts/run_net_dw_access_ip.py", ["--help"]),
    "nce-planner.code1": ("scripts/run_nce_planner.py", ["--help"]),
    "oob-interconnect-workflow.code1": ("scripts/run_oob_interconnect.py", ["--help"]),
    "switch-mlag-planning-workflow.code1": ("scripts/run_switch_mlag.py", ["--help"]),
}

IMPORT_PROBES = [
    ("_runtime_shared.sheet007_resolver", "connect_sheet_for_intent"),
    ("_runtime_shared.network_access_plan", "emit_for_plane"),
]


def _pip_install(req: Path) -> tuple[str, str]:
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
        capture_output=True,
        text=True,
        cwd=str(SUBSKILLS_ROOT),
    )
    tail = (r.stderr or r.stdout or "")[-500:]
    return ("ok" if r.returncode == 0 else "fail", tail.strip())


def _run_cli(pkg_dir: Path, script_rel: str, args: list[str]) -> tuple[str, str]:
    script = pkg_dir / script_rel
    if not script.is_file():
        return "skip", f"missing script {script_rel}"
    import os

    env = {**os.environ, "PYTHONPATH": str(SUBSKILLS_ROOT)}
    r = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=str(pkg_dir),
        env=env,
        timeout=120,
    )
    msg = (r.stderr or r.stdout or "").strip()
    if len(msg) > 500:
        msg = msg[:500] + "..."
    if r.returncode == 0:
        last = msg.splitlines()[-1] if msg else "exit 0"
        return "pass", last
    last = msg.splitlines()[-1] if msg else f"exit {r.returncode}"
    return "fail", last


def _import_probe(mod_name: str, attr: str) -> tuple[str, str]:
    if str(SUBSKILLS_ROOT) not in sys.path:
        sys.path.insert(0, str(SUBSKILLS_ROOT))
    try:
        mod = importlib.import_module(mod_name)
        getattr(mod, attr)
        return "pass", ""
    except Exception as e:
        return "fail", f"{type(e).__name__}: {e}"


def _legacy_sheet007_probe(pkg_dir: Path) -> tuple[str, str, list[str]]:
    """Fresh subprocess: legacy top-level import must fail until shim exists."""
    hits: list[str] = []
    scripts = pkg_dir / "scripts"
    if scripts.is_dir():
        for py in scripts.glob("*.py"):
            text = py.read_text(encoding="utf-8", errors="ignore")
            if "from sheet007_resolver import" in text:
                hits.append(py.name)
    if not hits:
        return "n/a", "", hits
    import os

    code = (
        "import importlib, sys; sys.path.insert(0, r'"
        + str(SUBSKILLS_ROOT).replace("\\", "\\\\")
        + "'); importlib.import_module('sheet007_resolver')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SUBSKILLS_ROOT)},
        timeout=30,
    )
    if r.returncode == 0:
        return "warn", "top-level import succeeded (shim?)", hits
    return "fail", "ModuleNotFoundError expected for standalone", hits


def main() -> int:
    reqs: list[Path] = []
    if (SHARED_ROOT / "requirements.txt").is_file():
        reqs.append(SHARED_ROOT / "requirements.txt")
    for pkg in sorted(SUBSKILLS_ROOT.glob("*.code1")):
        pr = pkg / "requirements.txt"
        if pr.is_file():
            reqs.append(pr)
    lld_req = SUBSKILLS_ROOT / "a3_LLD_generate_code1" / "requirements.txt"
    if lld_req.is_file():
        reqs.append(lld_req)

    print("=== pip install ===")
    for req in reqs:
        st, detail = _pip_install(req)
        print(f"[{st}] {req.relative_to(SUBSKILLS_ROOT)}")
        if st == "fail" and detail:
            print(f"  {detail}")

    print("\n=== shared import probes ===")
    for mod, attr in IMPORT_PROBES:
        st, detail = _import_probe(mod, attr)
        line = f"[{st}] {mod}.{attr}"
        if detail:
            line += f" — {detail}"
        print(line)

    print("\n=== legacy sheet007_resolver import ===")
    for pkg_name in sorted(SMOKE_TARGETS):
        pkg_dir = SUBSKILLS_ROOT / pkg_name
        if not pkg_dir.is_dir():
            continue
        st, detail, hits = _legacy_sheet007_probe(pkg_dir)
        if st == "n/a":
            continue
        print(f"[{st}] {pkg_name} ({', '.join(hits)})" + (f" - {detail}" if detail else ""))

    print("\n=== CLI smoke ===")
    rows: list[tuple[str, str, str]] = []
    for pkg_name in sorted(SMOKE_TARGETS):
        pkg_dir = SUBSKILLS_ROOT / pkg_name
        if not pkg_dir.is_dir():
            rows.append((pkg_name, "skip", "package dir missing"))
            print(f"[skip] {pkg_name} — package dir missing")
            continue
        script_rel, args = SMOKE_TARGETS[pkg_name]
        st, detail = _run_cli(pkg_dir, script_rel, args)
        rows.append((pkg_name, st, detail))
        print(f"[{st}] {pkg_name} :: {' '.join([script_rel, *args])}")
        if st == "fail" and detail:
            print(f"  {detail}")

    print("\n=== SUMMARY ===")
    for pkg, st, detail in rows:
        print(f"{st:4}  {pkg}" + (f"  |  {detail}" if st == "fail" and detail else ""))
    pass_n = sum(1 for _, s, _ in rows if s == "pass")
    fail_n = sum(1 for _, s, _ in rows if s == "fail")
    print(f"\nTotal: pass={pass_n} fail={fail_n} skip={sum(1 for _, s, _ in rows if s == 'skip')}")
    return 1 if fail_n else 0


if __name__ == "__main__":
    raise SystemExit(main())
