# -*- coding: utf-8 -*-
"""本地调试：plan-dispatch 子 skill 下发 + 宽表 xlsx。"""
import json
import sys
from pathlib import Path

import os

sys.path.insert(0, str(Path(__file__).parent))
skill_root = Path(__file__).resolve().parent.parent
os.environ["SD_SKILL_ROOT"] = str(skill_root)

from sd_script_import import import_sd_script

_dispatch = import_sd_script(skill_root, "3_plan_dispatch", "dispatch_plan")
_lld = import_sd_script(skill_root, "3_plan_dispatch", "lld_resolve")
dispatch_device_base = _dispatch.dispatch_device_base
resolve_lld_path = _lld.resolve_lld_path
from checklist_export import export_device_checklist_xlsx, load_scene, resolve_project_display_name

lld_path = resolve_lld_path(skill_root)
if not lld_path:
    print("ERROR: 未在 plan_dispatch 找到含「LLD设计」的 xlsx")
    sys.exit(1)

print(f"Using LLD: {lld_path}")

third_tasks_path = skill_root / "ProjectData" / "plan" / "Output" / "third_level_tasks.json"
with open(third_tasks_path, "r", encoding="utf-8") as f:
    third_tasks = json.load(f)["tasks"]

second_tasks_path = skill_root / "ProjectData" / "plan" / "Input" / "second_level_tasks.json"
with open(second_tasks_path, "r", encoding="utf-8") as f:
    second_tasks = json.load(f)["tasks"]

scene = load_scene(skill_root)

result = dispatch_device_base(
    lld_path=lld_path,
    third_tasks=third_tasks,
    second_tasks=second_tasks,
    scene=scene,
)

print(f"Device pool summary: {result['devicePoolSummary']}")
print(f"Long table rows: {result['stats']['rows']}")

out_dir = skill_root / "ProjectData" / "plan" / "Output"
out_dir.mkdir(parents=True, exist_ok=True)

json_path = out_dir / "device_base_table.json"
json_path.write_text(
    json.dumps({"schemaVersion": 1, "tasks": result["deviceTasks"]}, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8",
)
print(f"Saved compact JSON: {json_path}")

display = resolve_project_display_name(scene=scene, skill_root=skill_root)
xlsx_info = export_device_checklist_xlsx(
    device_tasks=result["deviceTasks"],
    scene=scene,
    output_dir=out_dir,
    project_display_name=display,
)
print(f"Saved checklist xlsx: {xlsx_info['path']}")
print(f"Wide table: {xlsx_info['deviceRows']} devices x {xlsx_info['headerColumns']} activity columns")
