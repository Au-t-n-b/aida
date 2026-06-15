"""Self-verify LLD integrate path for system_design."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_AIDA_ROOT = Path(__file__).resolve().parents[2]
if str(_AIDA_ROOT) not in sys.path:
    sys.path.insert(0, str(_AIDA_ROOT))

from agent.skills.system_design.skill import get_system_design_skill
from agent.skills.system_design.pipelines.delivery import (
    has_mergeable_plane_artifacts,
    is_lld_delivery_intent,
    resolve_resume_route_to,
)
from agent.skills.system_design.pipelines.path_manifest import abs_artifacts_dir, reload_manifest
from agent.skills.system_design.pipelines.a3_bridge import run_command


def main() -> int:
    reload_manifest()
    out = abs_artifacts_dir()
    print("artifacts_dir:", out, "exists:", out.is_dir())
    if out.is_dir():
        xlsx = [p for p in out.rglob("*.xlsx") if not p.name.startswith("~$")]
        print("xlsx count:", len(xlsx))
        for p in xlsx[:30]:
            print(" ", p.name)
    print("has_mergeable:", has_mergeable_plane_artifacts(Path(".")))
    print("is_lld (spaced):", is_lld_delivery_intent("生成完整 LLD 设计"))

    skill = get_system_design_skill()
    prev = {
        "hitl": {"step": "plane_planning"},
        "steps": [{
            "key": "plane_planning",
            "status": "completed",
            "metrics": {
                "sd_mode": "single",
                "plan_commands": [{
                    "command": "calc_oob",
                    "status": "ok",
                    "files": ["A3_oob.xlsx"],
                }],
            },
        }],
        "files": {},
    }
    payload = {"choice": "生成完整 LLD 设计", "text": "生成完整 LLD 设计"}
    project = skill.apply_resume_payload({}, payload, "plane_planning")
    route = resolve_resume_route_to(
        hitl_step="plane_planning",
        project=project,
        payload=payload,
        prev_state=prev,
        work_root=skill.work_root,
    )
    print("route:", route, "project.text:", project.get("text"))
    extras, _ = skill.build_resume_init_state(prev, project, "plane_planning", payload)
    print("route_to:", extras.get("route_to"), "sd_mode:", extras.get("metrics", {}).get("sd_mode"))

    if not has_mergeable_plane_artifacts(skill.work_root):
        print("SKIP run_command: no mergeable plane artifacts on disk")
        return 0

    print("Running 融合完整LLD设计 ...")
    result = run_command("融合完整LLD设计", skill.work_root, emit=print)
    print("status:", result.status, "summary:", result.summary)
    print("output_files:", result.output_files[:5] if result.output_files else [])
    if result.errors:
        print("errors:", result.errors[:3])
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
