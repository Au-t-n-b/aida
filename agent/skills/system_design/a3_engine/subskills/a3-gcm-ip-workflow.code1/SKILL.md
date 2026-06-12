---
name: a3-gcm-ip-workflow
description: 离线 A3 管存面（GCM）IP 规划：007 + 项目信息收集表 → output/run_*/{网络平面}_地址规划.xlsx（确定性，无 LLM）。i2 单网段 / i3 按接入交换机一机一网段。
disable-model-invocation: true
metadata:
  package: a3-gcm-ip-workflow.code1/
  entrypoint: scripts/offline_gcm_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成「管存面（GCM）」地址分配结果：输入两份 Excel，输出一份结果 Excel。该流程为**确定性计算**（不依赖 LLM）。

- **i2**：所有服务器共用 1 个 IPv4 子网，按去重后的顺序依次分配
- **i3**：按 007 末列「接入交换机」一机一网段（每台交换机独立子网）

**网络平面与 skill 名称**：文档标题里的「管存面（GCM）」表示本 skill 的流程归属；**本次规划的是哪一类网络**完全由资源表「网络平面」列与参数 `--network-plane` 决定（输出文件名与列名中的 `{网络平面}` 均取自该参数）。`offline_gcm_pipeline.py` 与 `validate_gcm_inputs.py` 的默认值统一为 `计算管存面`，与「管存面」语义一致；**该字符串必须与资源表中对应行的「网络平面」单元格完全一致**。若你使用的资源表（含仓库内旧版 `reference` 示例）里该行仍为其它名称，请在命令中显式传入与表内一致的 `--network-plane`，或先在表中把该行改名为 `计算管存面` 并补齐地址池等字段。

## What You Get

- **输出一个结果表**：每台服务器的 `地址/掩码/网关/VLAN/绑定模式`
- **可重复、可审计**：同一份输入 + 同一组参数 → 输出稳定一致
- **失败可定位**：输入不匹配或容量不足时，终端会提示“失败原因 + 建议修改哪里”

## Entrypoint

`python scripts/offline_gcm_pipeline.py --topology i2|i3 [--network-plane NAME] [--007 PATH] [--resource PATH] [--out-dir output]`

## Dependencies

`pip install pandas openpyxl`

## Quickstart

在包含两份 Excel（007 与资源表）的目录执行。下列命令中的 `--network-plane "计算管存面"` 与**脚本默认值**一致；请确认资源表「网络平面」列中存在该取值的一行（否则改为表中实际字符串）。

- i3（推荐，按接入交换机一机一网段）：

`python scripts/offline_gcm_pipeline.py --topology i3 --network-plane "计算管存面" --out-dir output --skip-prompt-check`

- i2（单网段，所有服务器共用一个子网）：

`python scripts/offline_gcm_pipeline.py --topology i2 --network-plane "计算管存面" --out-dir output --skip-prompt-check`

默认策略为 **fail-fast**：若规划结果出现 `网段个数不足/可用IP不足/vlan不足` 任意标记，会直接停止生成并打印汇总问题。
如需仍然生成 Excel 并在表内标记，追加 `--allow-insufficient`。

若 007 自动识别/解析失败，优先尝试指定 sheet 与过滤子串（示例）：

`python scripts/offline_gcm_pipeline.py --topology i3 --sheet007 1 --server-substring "D01" --network-plane "计算管存面" --out-dir output --skip-prompt-check`

## Directory Contract

本 skill 运行时假设目录结构如下（与当前仓库一致）：

- `scripts/offline_gcm_pipeline.py`：主入口
- `scripts/*.py`：GCM（管存面）离线逻辑
- `scripts/dw_manage_segment_rules.py`：通用网段切分/网关/VLAN 规则（供 i3 与部分 i2 复用）

## Parameters

- `--topology i2|i3`：必选，选择二层单网段或三层一机一网段
- `--network-plane NAME`：须与资源表「网络平面」列某一行的取值**完全一致**。脚本与 `validate_gcm_inputs.py` 的默认值为 `计算管存面`；若表中无此行名，请传入表中真实字符串（含沿用旧示例表时）。
- `--007 PATH`：007 端口连线表（可省略；省略时自动探测）
- `--resource PATH`：项目信息收集表/资源表（可省略；省略时自动探测）
- `--out-dir output`：输出目录（默认 `output`）
- `--sheet007 SHEET`：007 的 sheet（默认 `"0"`；脚本内部失败会扫描所有 sheet 兜底）
- `--sheet-res-index INDEX`：资源表 sheet index（默认 `0`）
- `--server-substring SUBSTR`：仅保留服务器名含该子串的行（默认 `AT800T`；空字符串表示不过滤）
- `--i3-split-spine-leaf`：仅 i3 生效：名单中区分 SPINE/LEAF，SPINE 可走 i2「共享网段累加」，LEAF 走一机一网段（与 `scripts/offline_dw_manage_pipeline.py` 同源）
- `--allow-insufficient`：允许容量不足时继续生成 Excel，并在表内标记 `网段个数不足/可用IP不足/vlan不足`（默认：发现这些标记即停止生成并打印汇总）
- `--prompt-spine-file PATH`：可选，启用 prompt 关键短语校验（i2/SPINE）
- `--prompt-leaf-file PATH`：可选，启用 prompt 关键短语校验（i3/LEAF）
- `--skip-prompt-check`：强制跳过 prompt 关键短语校验

## Path Rules (CWD Contract)

- 输入/输出路径必须位于当前工作目录（cwd）树下
- 省略路径时在 cwd 下自动探测：
  - 007：文件名包含 `007` 或 `端口连线` 或 `端口互联`
  - 资源：文件名包含 `项目信息收集` 或 `信息收集表` 或 `资源`

## Validation (Optional)

`python scripts/validate_gcm_inputs.py --network-plane "计算管存面"`

其中 `--network-plane` 须与你要校验的资源表行一致（与 `offline_gcm_pipeline.py` 默认值一致时为 `计算管存面`）。

## Inputs (Contract)

| 来源 | 要点 |
|------|------|
| 007 | 找「设备命名」行；首列服务器、末列接入交换机；去掉服务器名列含 LEAF/SPINE 的行；可选按 `--server-substring` 过滤 |
| 资源表（默认 sheet index=0） | 取 `网络平面 == --network-plane` 的行：`地址池*`、`最小规划掩码`、`网关地址*`、`VLAN*` |

## Outputs (Contract)

- `output/run_YYYYMMDD_HHMMSS/{网络平面}_地址规划.xlsx`
- sheet：`{网络平面}地址规划`（自动截断至 Excel 31 字符）

输出字段（列）：

- `设备名称`
- `{网络平面}地址` / `{网络平面}掩码` / `{网络平面}网关` / `{网络平面}VLAN`
- `绑定模式`（离线版固定 `bond1`）

## Prompt Parity Check (Optional, No LLM)

该检查**默认不启用**，仅在传入 `--prompt-spine-file/--prompt-leaf-file` 时才会读取文件做短语校验。

因此即便删除以下文件，离线脚本仍可运行：

- `a3_i2_network_segment_tools_prompt.py`
- `a3_i3_network_segment_tools_prompt.py`
- `a3_l2_ip_address.py`
- `a3_ywm_ip_address.py`

## Excel Error Literals (Do Not Change)

`网段个数不足`、`可用IP不足`、`vlan不足`（定义见 `scripts/dw_manage_segment_rules.py`）。

## Troubleshooting (User-Facing)

常见问题与建议修改点：

- **007 解析失败 / 过滤后无数据**
  - **现象**：提示找不到「设备命名」，或“过滤后无可用数据 / 无法得到接入交换机→服务器映射”
  - **修改**：用 `--sheet007` 指定正确 sheet；若使用了 `--server-substring`，改成能命中首列服务器名的子串（不确定就不传该参数）

- **资源表找不到网络平面行**
  - **现象**：提示找不到 `网络平面 == --network-plane`
  - **修改**：把 `--network-plane` 改成资源表「网络平面」列中的真实取值；必要时调整 `--sheet-res-index`

- **网段不足 / 地址池切不出子网（i3）**
  - **现象**：提示“地址池无法切出满足 /mask 的子网”，或输出出现 `网段个数不足`
  - **修改**：扩大资源表 `地址池*` 范围，或调整 `最小规划掩码`（同时会影响每网段大小与可切分的网段数量）

- **可用 IP 不足（i3）**
  - **现象**：输出 `可用IP不足`
  - **修改**：扩大 `地址池*`，或让单网段更大（调整 `最小规划掩码`），或减少该接入交换机关联的服务器数量

- **VLAN 不足**
  - **现象**：输出 `vlan不足`
  - **修改**：扩大资源表 `VLAN*` 区间（例如 `100-199`），或改为固定 VLAN（单值）

- **希望容量不足时直接失败（不生成 Excel）**
  - **做法**：默认即是该行为（fail-fast）
  - **如需仍生成并标记**：加 `--allow-insufficient`

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
