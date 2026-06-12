"""Load workflow.yaml, gate eligibility, build workflow_plan.json / steps.md."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from lld_config import INSTRUCTION_NETWORK_TYPE_CONFIG, MLAG_TOPOLOGY_SHEETS
from lld_layer_resolver import load_net_to_gateway, resolve_instruction_with_layer
from lld_path_utils import SKILL_ROOT, workflow_yaml_path


@dataclass
class StepDef:
    id: str
    instruction: str
    gate_sheet: Optional[str]
    step_type: str
    layer_from_resource: bool
    web_network_key: Optional[str] = None
    expected_output_pattern: Optional[str] = None
    child_skill: Optional[dict] = None
    cli_template: Optional[str] = None
    outputs: List[dict] = field(default_factory=list)
    enabled: bool = False
    handler: Optional[str] = None


def load_workflow(path: Optional[Path] = None) -> List[StepDef]:
    wf_path = path or workflow_yaml_path()
    raw = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    steps: List[StepDef] = []
    for item in raw.get("steps", []):
        steps.append(
            StepDef(
                id=str(item["id"]),
                instruction=item["instruction"],
                gate_sheet=item.get("gate_sheet"),
                step_type=item.get("step_type", "address"),
                layer_from_resource=bool(item.get("layer_from_resource", False)),
                web_network_key=item.get("web_network_key"),
                expected_output_pattern=item.get("expected_output_pattern"),
                child_skill=item.get("child_skill"),
                cli_template=item.get("cli_template"),
                outputs=list(item.get("outputs") or []),
                enabled=bool(item.get("enabled", False)),
                handler=item.get("handler"),
            )
        )
    return steps


def is_step_eligible(step: StepDef, sheet_names: List[str]) -> bool:
    if step.step_type == "integrate":
        return True
    gate = step.gate_sheet
    if gate == "__mlag__":
        return any(s in sheet_names for s in MLAG_TOPOLOGY_SHEETS)
    if not gate:
        task_sheet = INSTRUCTION_NETWORK_TYPE_CONFIG.get(step.instruction, "互联")
    else:
        task_sheet = gate
    return (
        task_sheet in sheet_names
        or task_sheet == "互联"
        or ("样本面端口互联" in task_sheet and "样本面端口互联" in sheet_names)
    )


def _render_cli(template: str, ctx: dict) -> str:
    return template.format(**ctx).strip()


def _build_cli_context(
    step: StepDef,
    topology: Path,
    resource: Path,
    run_dir: Path,
    user_id: str,
    project_id: str,
    out_dir: Path,
) -> dict:
    skill_root = SKILL_ROOT
    package = (step.child_skill or {}).get("package", "")
    package_path = (skill_root / package).resolve() if package else skill_root
    entrypoint = (step.child_skill or {}).get("entrypoint", "")
    return {
        "topology": str(topology),
        "resource": str(resource),
        "user_id": user_id,
        "project_id": project_id,
        "run_dir": str(run_dir),
        "out_dir": str(out_dir),
        "entrypoint": str(package_path / entrypoint) if entrypoint else "",
        "package_dir": str(package_path),
    }


def build_plan_step(
    step: StepDef,
    sheet_names: List[str],
    net_to_gateway: dict,
    ctx_base: dict,
) -> dict:
    eligible = is_step_eligible(step, sheet_names)
    resolved, layer = resolve_instruction_with_layer(
        step.instruction,
        step.layer_from_resource,
        net_to_gateway,
        step.web_network_key,
    )
    expected = []
    if step.expected_output_pattern:
        pat = step.expected_output_pattern.replace("{project_name}", ctx_base.get("project_name", ""))
        expected.append(pat)

    status = "skipped_not_eligible"
    cli_command = None
    child_skill_out = None
    agent_hint = ""

    if not eligible:
        agent_hint = "007 sheet 门控未通过，跳过本步"
    elif step.step_type == "integrate":
        status = "pending_integrate"
        agent_hint = "全部规划步骤完成后执行: --mode integrate"
    elif not step.enabled:
        status = "pending_no_handler"
        agent_hint = f"子 skill 未接入：在 workflow.yaml step {step.id} 填写 child_skill 并设 enabled:true"
    elif not step.child_skill or not step.cli_template:
        status = "pending_no_handler"
        agent_hint = f"step {step.id} enabled 但缺少 child_skill/cli_template"
    else:
        status = "pending"
        cli_command = _render_cli(step.cli_template, ctx_base)
        cs = step.child_skill
        child_skill_out = {
            "package": cs.get("package"),
            "skill_md": cs.get("skill_md", "SKILL.md"),
            "entrypoint": cs.get("entrypoint"),
            "skill_name": cs.get("skill_name"),
        }
        agent_hint = (
            f"[runtime] conductor_runner subprocess step {step.id}; "
            f"cli_command 已生成；Claw 勿 Read child SKILL.md、勿自行执行"
        )

    return {
        "id": step.id,
        "instruction": step.instruction,
        "resolved_instruction": resolved,
        "layer": layer,
        "step_type": step.step_type,
        "eligible": eligible,
        "enabled": step.enabled,
        "status": status,
        "child_skill": child_skill_out,
        "cli_command": cli_command,
        "expected_outputs": expected,
        "agent_hint": agent_hint,
        "handler": step.handler,
        "outputs": step.outputs,
    }


def build_workflow_plan(
    topology: Path,
    resource: Path,
    run_dir: Path,
    out_dir: Path,
    user_id: str,
    project_id: str,
    project_name: str,
    sheet_names: List[str],
) -> dict:
    steps_def = load_workflow()
    net_to_gateway = load_net_to_gateway(resource)
    ctx_base = {
        "topology": str(topology),
        "resource": str(resource),
        "user_id": user_id,
        "project_id": project_id,
        "project_name": project_name,
        "run_dir": str(run_dir),
        "out_dir": str(out_dir),
    }
    plan_steps = []
    for step in steps_def:
        step_ctx = {
            **ctx_base,
            **_build_cli_context(step, topology, resource, run_dir, user_id, project_id, out_dir),
        }
        plan_steps.append(build_plan_step(step, sheet_names, net_to_gateway, step_ctx))

    run_id = run_dir.name.replace("run_", "", 1) if run_dir.name.startswith("run_") else run_dir.name
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "topology": str(topology),
        "resource": str(resource),
        "user_id": user_id,
        "project_id": project_id,
        "project_name": project_name,
        "out_dir": str(out_dir),
        "final_lld_pattern": f"{project_name}-LLD设计-*.xlsx",
        "sheet_names": sheet_names,
        "steps": plan_steps,
    }


def write_steps_md(plan: dict, path: Path) -> None:
    lines = [
        "# LLD Workflow Steps",
        "",
        f"- run_id: `{plan['run_id']}`",
        f"- topology: `{plan['topology']}`",
        f"- resource: `{plan['resource']}`",
        f"- out_dir (最终 LLD 输出目录): `{plan['out_dir']}`",
        f"- final_lld: `{plan.get('final_lld_pattern', '')}`",
        "",
    ]
    for s in plan["steps"]:
        lines.append(f"## Step {s['id']}: {s['instruction']}")
        lines.append(f"- eligible: {s['eligible']}")
        lines.append(f"- enabled: {s['enabled']}")
        lines.append(f"- status: `{s['status']}`")
        if s.get("resolved_instruction"):
            lines.append(f"- resolved: `{s['resolved_instruction']}`")
        if s.get("cli_command"):
            lines.append(f"- cli: `{s['cli_command']}`")
        lines.append(f"- hint: {s['agent_hint']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def save_workflow_plan(plan: dict, run_dir: Path) -> Path:
    out = run_dir / "workflow_plan.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    write_steps_md(plan, run_dir / "steps.md")
    return out


def get_step_def(step_id: str) -> Optional[StepDef]:
    for step in load_workflow():
        if step.id == step_id:
            return step
    return None
