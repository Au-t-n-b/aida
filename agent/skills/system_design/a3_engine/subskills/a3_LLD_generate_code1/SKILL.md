---
name: a3-lld-generate-workflow
description: >
  A3 LLD Conductor 子包。线上由 runtime/conductor_runner 经 sd_lld_generate 一键 subprocess 执行，Claw 不读本文件。
  离线维护：plan/collect/integrate CLI 与 workflow.yaml。
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_lld_generate_pipeline.py
  workflow: workflow.yaml
  default_mode: plan
  no_edm: true
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

> **模式 A · 线上 runtime（Claw）**  
> 只发 `sd_lld_generate` / `sd_lld_integrate`（见 [subskills/SKILL.md](../SKILL.md) Section D）。  
> **禁止** Read 本文件、**禁止**按 `workflow_plan.json` 逐步执行子 skill。
>
> **模式 B · 离线调试（开发 / 无 nanobot）**  
> 使用下方 CLI 与「离线 Agent Workflow」；产物见 `output/run_*` 或 `ProjectData/Work/*/conductor/`。

## 线上 runtime 契约

| 项 | 说明 |
|---|---|
| 入口 | [subskills/SKILL.md](../SKILL.md) Section D → `sd_lld_generate` |
| 执行 | `runtime/conductor_runner.execute_conductor(mode=plan_run)` |
| 23 步 | `run_conductor_steps` 内部 subprocess，Claw 不参与 |
| 产物 | `ProjectData/Work/{run_id}/conductor/`、`ProjectData/Output/` |

## Purpose

A3「生成完整LLD设计」离线总编排 skill（Conductor）。对齐 [`main_flow.py`](../main_flow.py) 的 `generate_all_lld_file()` 23 步顺序与 sheet 门控，以及 `integrate_lld_file()` 融合语义。

- **确定性编排**：不调用 LLM
- **纯本地 I/O**：不接入 EDM、项目 DB
- **首版零子 skill 预注册**：step 01–22 在 `workflow.yaml` 中 `enabled: false`；后续逐条接入

## Entrypoint

```bash
python scripts/offline_lld_generate_pipeline.py --mode {plan|collect|integrate} [options]
```

## Dependencies

```bash
pip install -r requirements.txt
```

## Parameters

| 参数 | 说明 |
|------|------|
| `--mode plan` | 默认；生成 `output/run_*/workflow_plan.json`（仅元数据） |
| `--mode collect` | 可选；`--source-dir` → `--scan-dir`（无 staging） |
| `--mode integrate` | **仅输出最终 LLD**；扫描 `--scan-dir` / `--out-dir` 中 `A3*.xlsx` |
| `--topology` | 007 端口连线表（可 autodetect） |
| `--resource` | 项目信息收集表（可 autodetect） |
| `--out-dir output` | 最终 LLD 输出目录 |
| `--run-id` | plan 元数据 run 目录（integrate 可选） |
| `--user-id` / `--project-id` / `--project-name` | 计划/LLD 文件名上下文 |
| `--scan-dir` | integrate/collect：扫描或写入部分产物的目录 |
| `--scan-dirs` | integrate：多个扫描目录（逗号分隔） |
| `--output` | 指定最终 LLD 路径（默认 `out-dir/{项目名}-LLD设计-*.xlsx`） |
| `--templates-dir` | 可选 LLD 模板目录 |
| `--simulation-dir` | 可选 001–007 仿真文件目录 |

## Path Rules (CWD Contract)

- 输入/输出路径须位于 **cwd**、**本 skill 根目录** 或 **`LLD_IP` 包目录** 下（便于 monorepo 引用 `../files/A3_files`）
- 007 autodetect：文件名含 `007` / `端口连线` / `端口互联`
- 资源表 autodetect：含 `项目信息收集` / `资源`

## Validation (Optional)

```bash
python scripts/validate_inputs.py [--topology PATH] [--resource PATH]
```

## 离线 Agent Workflow（Claw 禁止 · 无 runtime 时使用）

1. `--mode plan` → `output/run_*/workflow_plan.json`（仅编排元数据）
2. 对每个已接入步骤：本地 CLI 执行子 skill；产物落在 `--scan-dir` 或 `--out-dir`（**无 step_out / staging**）
3. `--mode integrate --scan-dir ...` → **仅生成** `output/{项目名}-LLD设计-*.xlsx`

对 `pending_no_handler`：跳过或提示在 `workflow.yaml` 接入子 skill。

## Integrate 输入规则

- 文件名含 `A3` 且为 `.xlsx`；**不强制** `{user_id}_{project_id}_` 前缀
- 按 **plane_key**（`A3{规划名}`）去重，同一平面取 **mtime 最新**
- 排除：`A3LLD设计`、`网络设备接入规划.xlsx`

## 子 skill 接入（workflow.yaml）

```yaml
  child_skill:
    package: ../a3-dw-manage-ip-workflow.code1
    skill_name: a3-dw-manage-ip-workflow
    entrypoint: scripts/offline_dw_manage_pipeline.py
    skill_md: SKILL.md
  cli_template: |
    python {entrypoint} --007 {topology} --resource {resource} --out-dir {out_dir}
  outputs:
    - pattern: "*A3计算带外管理地址规划.xlsx"
      source_glob: "计算带外管理地址.xlsx"
  enabled: true
```

## Implementation Notes

- `workflow.yaml`：23 步唯一事实来源
- `scripts/lld_workflow.py`：门控、L2/L3、plan 生成
- `scripts/lld_staging.py`：plane_key、collect、scan latest
- `scripts/offline_integrate_lld.py`：本地融合

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
