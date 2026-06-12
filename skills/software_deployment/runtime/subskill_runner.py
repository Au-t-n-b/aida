from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_subskill(
    subskill_id: str,
    action: str,
    request: dict[str, Any],
    *,
    skill_root: Path,
    python_executable: str | None = None,
) -> list[dict[str, Any]]:
    driver = skill_root / "runtime" / "subskills" / subskill_id / "runtime" / "driver.py"
    if not driver.is_file():
        raise FileNotFoundError(f"subskill driver not found: {driver}")

    payload = dict(request)
    payload["subskill"] = subskill_id
    payload["action"] = action
    payload.setdefault("paths", {})
    if isinstance(payload["paths"], dict):
        payload["paths"].setdefault("skillRoot", str(skill_root))
        payload["paths"].setdefault("planReceive", str(skill_root / "ProjectData" / "input" / "plan_receive"))
        payload["paths"].setdefault("planSplitInput", str(skill_root / "ProjectData" / "input" / "plan_split"))
        payload["paths"].setdefault("planDispatchInput", str(skill_root / "ProjectData" / "input" / "plan_dispatch"))
        payload["paths"].setdefault("cloudopsInput", str(skill_root / "ProjectData" / "input" / "cloudops"))
        payload["paths"].setdefault("projectData", str(skill_root / "ProjectData"))

    exe = python_executable or sys.executable
    proc = subprocess.run(
        [exe, str(driver)],
        cwd=str(skill_root),
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"subskill {subskill_id}/{action} failed: {err}")

    events: list[dict[str, Any]] = []
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events
