# -*- coding: utf-8 -*-
"""端到端验证：reset → ①～⑥ invoke → 检查 deploy_chain/产物。

用法：
  python runtime/e2e_verify.py              # 全量重置后跑 ①～⑥（离线，不调 Toolkit）
  python runtime/e2e_verify.py --no-reset   # 保留当前进度，只重跑 invoke 链
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
RUNTIME = SKILL_ROOT / "runtime"

_STEP_CHAIN_KEYS: dict[str, str] = {
    "plan_receive_invoke": "step1_plan_receive_at",
    "plan_split_invoke": "step2_plan_split_at",
    "plan_dispatch_invoke": "step3_plan_dispatch_at",
    "cloudops_init_invoke": "step4_cloudops_init_at",
    "cloudops_supplement_upload_done": "step5_cloudops_supplement_at",
    "cloudops_full_invoke": "step6_cloudops_full_at",
}


def _run_driver(driver: Path, action: str, *, extra: dict | None = None) -> tuple[int, str]:
    payload: dict[str, Any] = {
        "action": action,
        "thread_id": "e2e",
        "skill_name": "software_deployment",
        "request_id": f"e2e-{action}",
        "confirm": True,
    }
    if extra:
        payload.update(extra)
    proc = subprocess.run(
        [sys.executable, str(driver)],
        cwd=str(SKILL_ROOT),
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
    )
    out = (proc.stdout or b"").decode("utf-8", errors="replace")
    err = (proc.stderr or b"").decode("utf-8", errors="replace")
    text = (out + err).strip()
    last = text.splitlines()[-1] if text else ""
    return proc.returncode, text, last


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_checks() -> list[tuple[str, Path, bool]]:
    root = SKILL_ROOT
    return [
        ("① second_level_tasks.json", root / "ProjectData/plan/Input/second_level_tasks.json", True),
        ("② third_level_tasks.json", root / "ProjectData/plan/Output/third_level_tasks.json", True),
        ("③ dispatch_record.json", root / "ProjectData/plan/Output/dispatch_record.json", True),
        ("③ 完工清单宽表", root / "ProjectData/plan/Output/全量设备完工清单列表_latest.xlsx", True),
        ("④ CloudOps初配", root / "ProjectData/plan/Output/CloudOps初始配置.xlsx", False),
        ("⑥ CloudOps完整", root / "ProjectData/plan/Output/CloudOps完整配置文件.xlsx", True),
        ("deploy_chain.json", root / "ProjectData/plan/RunTime/deploy_chain.json", True),
        ("upstream_manifest.json", root / "data/upstream_manifest.json", True),
        ("state.json 已废弃（应不存在）", root / "ProjectData/plan/RunTime/state.json", False),
    ]


def _chain_field_checks(chain: dict) -> list[tuple[str, bool]]:
    return [
        ("① step1_plan_receive_at", bool(chain.get("step1_plan_receive_at"))),
        ("② step2_plan_split_at", bool(chain.get("step2_plan_split_at"))),
        ("③ step3_plan_dispatch_at", bool(chain.get("step3_plan_dispatch_at"))),
        ("④ step4_cloudops_init_at", bool(chain.get("step4_cloudops_init_at"))),
        ("⑤ step5_cloudops_supplement_at", bool(chain.get("step5_cloudops_supplement_at"))),
        ("⑥ step6_cloudops_full_at", bool(chain.get("step6_cloudops_full_at"))),
    ]


def _preflight_materials() -> bool:
    sys.path.insert(0, str(RUNTIME))
    from paths import resolve_slot  # noqa: WPS433

    ok = True
    print("\n=== MATERIAL SLOTS ===")
    for slot_id in ("second_level_tasks", "testcase", "lld_design", "cloudops_manual", "check_list"):
        info = resolve_slot(slot_id, skill_root=SKILL_ROOT)
        mark = "OK" if not info.get("missing") else "MISSING"
        if info.get("missing") and not info.get("optional"):
            ok = False
        primary = info.get("primary") or "(无)"
        print(f"  [{mark}] {slot_id}: {Path(str(primary)).name if primary != '(无)' else primary}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="software_deployment 离线流程验证（①～⑥）")
    parser.add_argument("--no-reset", action="store_true", help="不执行演示重置，保留 input 与当前 chain")
    args = parser.parse_args()

    sys.path.insert(0, str(RUNTIME))

    if not args.no_reset:
        from reset_workspace import reset_workspace  # noqa: WPS433

        reset = reset_workspace(SKILL_ROOT, scope="all")
        print("RESET:", reset.get("notes", [""])[0])
    else:
        print("SKIP RESET: 保留当前 ProjectData/plan 与 input")

    if not _preflight_materials():
        print("\n  [FAIL] 关键材料槽位缺失，请先补齐 ProjectData/input/*")

    plan_drv = SKILL_ROOT / "runtime/subskills/plan/runtime/driver.py"
    co_drv = SKILL_ROOT / "runtime/subskills/cloudops/runtime/driver.py"

    steps = [
        ("① 接收", plan_drv, "plan_receive_invoke"),
        ("② 拆分", plan_drv, "plan_split_invoke"),
        ("③ 下发", plan_drv, "plan_dispatch_invoke"),
        ("④ 初配", co_drv, "cloudops_init_invoke"),
        ("⑤ 补充", co_drv, "cloudops_supplement_upload_done"),
        ("⑥ 完整", co_drv, "cloudops_full_invoke"),
    ]

    results: list[dict[str, Any]] = []
    failed = False

    for label, driver, action in steps:
        chain_before = _read_json(SKILL_ROOT / "ProjectData/plan/RunTime/deploy_chain.json")
        code, full_text, last_line = _run_driver(driver, action)
        chain_after = _read_json(SKILL_ROOT / "ProjectData/plan/RunTime/deploy_chain.json")
        chain_key = _STEP_CHAIN_KEYS.get(action)
        chain_written = bool(chain_key and chain_after.get(chain_key))
        ok = code == 0 and chain_written
        if not ok:
            failed = True
        results.append(
            {
                "step": label,
                "action": action,
                "exit": code,
                "chain_written": chain_written,
                "ok": ok,
                "last": last_line[:200],
                "detail": full_text[:500] if not ok else "",
            }
        )

    chain = _read_json(SKILL_ROOT / "ProjectData/plan/RunTime/deploy_chain.json")

    print("\n=== CHAIN 进度字段（①～⑥）===")
    for label, ok in _chain_field_checks(chain):
        mark = "OK" if ok else "MISSING"
        if not ok:
            failed = True
        print(f"  [{mark}] {label}")
    print("\n=== CHAIN (路径) ===")
    for k in (
        "step2_testcase_path",
        "step3_lld_path",
        "step4_cloudops_output_path",
        "step6_cloudops_full_path",
    ):
        print(f"  {k}: {chain.get(k)}")

    print("\n=== ARTIFACTS ===")
    for name, path, required in _artifact_checks():
        exists = path.is_file()
        mark = "OK" if exists else ("MISSING" if required else "skip")
        print(f"  [{mark}] {name}: {path.name}")
        if required and not exists:
            failed = True

    print("\n=== DRIVER RUNS ===")
    for r in results:
        cw = "chain=OK" if r["chain_written"] else "chain=MISSING"
        print(f"  {r['step']}: exit={r['exit']} {cw} {'PASS' if r['ok'] else 'FAIL'}")
        if r.get("detail"):
            print(f"    hint: {r['detail'][:300]}")

    if not chain.get("step6_cloudops_full_at"):
        failed = True
        print("\n  [FAIL] deploy_chain.step6_cloudops_full_at 未写入（步骤 6 业务未完成）")

    print("\nRESULT:", "PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
