---
name: dme-planning
description: Generates deterministic DME deployment planning from project Excel inputs. Use when the user triggers DME规划 or asks to produce A3 DME deployment plans from port interconnect and network resource spreadsheets.
disable-model-invocation: true
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

# DME Planning

## Purpose

Use this skill when the stage trigger is `DME规划`.

The skill generates `A3DME部署规划.xlsx` from the same input/output shape used by the project, but the planning logic is deterministic and can run outside the project. Do not rely on LLM output as the planning result.

## Inputs

Required:

- Port interconnect Excel: the current project's `端口互联关系.xlsx`.
- Network resource / project information Excel: the current project's network resource table.
- Output directory.
- DataTurbo value, either as an explicit parameter or parseable from the input workbook.

Optional:

- MLAG value. If not provided and not parseable, treat it as disabled.

## Output

Create:

- File: `A3DME部署规划.xlsx`
- Sheet: `DME部署方案`

Columns must be:

`设备名称, 网络平面, 接口名称, IP地址, 掩码, 网关, VLAN, Bond模式, 目的网段, 目的掩码`

Return a summary with output path, row count, scenario, validation messages, and a preview table.

## Deterministic Rules

Use `dme_new_plan.md` as the primary rule source. Keep project input/output compatibility where it does not conflict with the new DME rules.

- Trigger must be `DME规划`.
- DME devices are read from the port interconnect workbook sheets `计算带外管理面端口互联` and `存储带外管理面端口互联`, filtering device names that contain `DME`.
- Supported DME node counts are `1`, `3`, `5`, and `8`.
- Network resources are read from the resource workbook by matching `网络平面`:
  - `DME带外管理` for out-of-band management.
  - `DME带内管理` for in-band management.
  - `DME业务` or `DME数据` for the data network.
- Data network is planned only when `DataTurbo=true` and a DME data/business address pool exists.
- Gateway is always the first IP in the address pool.
- Allocate IPs in ascending order from each pool, excluding network address, broadcast address, gateway, and already allocated IPs.
- Floating IPs are assigned concrete IP addresses and written to the output.
- Scenario C, where only in-band management and data network exist without an out-of-band pool, does not generate the three out-of-band floating usage rows.
- Management Bond mode is `mode4` when MLAG is enabled; otherwise `mode1`.
- Out-of-band interface is `bond0`; in-band interface is `bond1`; data network interface is empty.
- Out-of-band destination network/mask is `0.0.0.0` / `0.0.0.0`; in-band and data destination network/mask are empty strings.

## State Machine

| state | action | trigger condition | output event |
|---|---|---|---|
| `INIT` | `detect_trigger` | Stage instruction is provided | `TRIGGER_ACCEPTED` / `TRIGGER_REJECTED` |
| `LOAD_INPUTS` | `load_excel_inputs` | Trigger accepted and paths exist | `INPUTS_LOADED` / `INPUT_LOAD_FAILED` |
| `VALIDATE_INPUTS` | `validate_required_fields` | Excel files are loaded | `INPUTS_VALID` / `INPUTS_INVALID` |
| `RESOLVE_CONTEXT` | `resolve_scenario_dataturbo_mlag` | Required fields are valid | `CONTEXT_RESOLVED` / `CONTEXT_INVALID` |
| `PLAN_DME_NETWORKS` | `allocate_node_and_floating_ips` | Scenario, DataTurbo, and MLAG are resolved | `PLAN_BUILT` / `PLAN_FAILED` |
| `WRITE_OUTPUT` | `write_excel_and_preview` | Planning table is built | `OUTPUT_WRITTEN` / `OUTPUT_WRITE_FAILED` |
| `DONE` | `return_result_summary` | Excel file is written | `SKILL_COMPLETED` |
| `FAILED` | `return_error_report` | Any step fails | `SKILL_FAILED` |

## Script

Run the standalone deterministic implementation:

```bash
python scripts/generate_dme_plan.py --trigger DME规划 --port-file input/端口互联关系.xlsx --resource-file input/项目信息收集表.xlsx --output-dir output --dataturbo true
```

Use `--dataturbo auto` only when the input workbook contains a parseable DataTurbo value. Use `--mlag true` to force `mode4`; if omitted or `auto` cannot parse MLAG, the script uses `mode1`.

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
