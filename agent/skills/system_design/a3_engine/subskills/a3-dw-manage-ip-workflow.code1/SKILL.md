---
name: a3-dw-manage-ip-workflow
description: Offline A3 计算带外管理面规划：007 + 项目信息收集表 → output/run_*/计算带外管理地址.xlsx（确定性，无 LLM）。
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_dw_manage_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成「计算带外管理面」地址分配结果，输入两份 Excel，输出一份结果 Excel。该流程为**确定性计算**（不依赖 LLM）。

## Entrypoint

`python scripts/offline_dw_manage_pipeline.py [--007 PATH] [--resource PATH] [--out-dir output] [--skip-prompt-check]`

## Dependencies

`pip install pandas openpyxl`

## Parameters

- `--007 PATH`：007 端口连线表（可省略；省略时自动探测）
- `--resource PATH`：项目信息收集表/资源表（可省略；省略时自动探测）
- `--out-dir output`：输出目录（默认 `output`）
- `--sheet007 SHEET`：007 的 sheet（默认 `"0"`；脚本内部会在失败时扫描所有 sheet 兜底）
- `--sheet-res-index INDEX`：资源表 sheet index（默认 `0`）
- `--skip-prompt-check`：跳过 prompt 文本一致性检查（见下文）

## Path Rules (CWD Contract)

- 输入/输出路径必须位于当前工作目录（cwd）树下
- 省略路径时在 cwd 下自动探测：
  - 007：文件名包含 `007` 或 `端口连线`
  - 资源：文件名包含 `项目信息收集` 或 `资源`

## Validation (Optional)

`python scripts/validate_inputs.py`（参数与主流程同源）。

## Inputs (Contract)

| 来源 | 要点 |
|------|------|
| 007 | 找「设备命名」行；首列服务器、末列接入交换机；去掉服务器名为 LEAF/SPINE 的行 |
| 资源表（默认 sheet index=0） | 取 `网络平面 == 计算带外管理面` 的行：`地址池*`、`最小规划掩码`、`网关地址*`、`VLAN*` |

## Outputs (Contract)

- `output/run_YYYYMMDD_HHMMSS/计算带外管理地址.xlsx`
- sheet：`计算带外管理地址`
- `output/run_YYYYMMDD_HHMMSS/A3网络设备接入规划.xlsx`（与项目 `a3_l2_dw_manage_ip_address.py` 一致；sheet `网络设备接入规划`，`网络平面=计算带外管理面`，按平面合并追加）

输出字段（列）来自脚本生成，常见包含：`设备名称`、`带外管理地址`、`带外管理掩码`、`带外管理网关`、`带外管理VLAN`、`接口名称`、`超节点ID`、`超节点规模`、`计算节点ID`。

## Implementation Notes (Rules)

- `scripts/dw_manage_segment_rules.py`
  - **网段切分**：`split_ip_range`
  - **网关语义**：`compute_gateway`
  - **SPINE 共享网段**（i2 语义）、**LEAF 一机一网段**（i3）
  - **可用 IP 枚举**：`enumerate_usable_ips_in_pool`
- `scripts/offline_dw_manage_pipeline.py`：主流程（读取输入 → 规划网段/VLAN/网关 → 分配可用 IP → 写出 Excel）
- `scripts/validate_inputs.py`：输入校验（可选）

## Prompt Parity Check (Optional, No LLM)

若仓库根目录存在以下文件，则主流程会校验其三引号字符串中是否包含关键短语（用于确保文案/规则描述一致）。可用 `--skip-prompt-check` 跳过。

- `a3_i2_network_segment_tools_prompt.py`
- `a3_i3_network_segment_tools_prompt.py`

## Excel Error Literals (Do Not Change)

`网段个数不足`、`可用IP不足`、`vlan不足`（定义见 `dw_manage_segment_rules.py`）。

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
