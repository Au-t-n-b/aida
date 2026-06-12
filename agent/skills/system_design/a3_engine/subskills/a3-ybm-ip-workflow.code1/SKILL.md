---
name: a3-ybm-ip-workflow
description: 离线 A3 YBM IP 规划：007 + 项目信息收集表 → output/run_*/{网络平面}_地址规划.xlsx（确定性，无 LLM）。i2 单网段 / i3 按接入交换机一机一网段。
disable-model-invocation: true
metadata:
  entrypoint: scripts/ybm_offline_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成「YBM」地址分配结果：输入两份 Excel，输出一份结果 Excel。该流程为**确定性计算**（不依赖 LLM）。

- **i2**：所有服务器共用 1 个 IPv4 子网，按去重后的顺序依次分配
- **i3**：按 007 末列「接入交换机」一机一网段（每台交换机独立子网）

## What You Get

- **输出一个结果表**：每台服务器的 `地址/掩码/网关/VLAN/绑定模式`
- **可重复、可审计**：同一份输入 + 同一组参数 → 输出稳定一致
- **失败可定位**：输入不匹配或容量不足时，终端会提示“失败原因 + 建议排查/修改”

## Entrypoint

`python scripts/ybm_offline_pipeline.py --topology i2|i3 [--network-plane NAME] [--007 PATH] [--resource PATH] [--out-dir output] [--no-server-filter]`

## Dependencies

`pip install pandas openpyxl`

## Quickstart

在包含两份 Excel（007 与资源表）的目录执行：

- i3（推荐，按接入交换机一机一网段）：

`python a3_ybm/scripts/ybm_offline_pipeline.py --topology i3 --network-plane "计算样本面" --out-dir output --skip-prompt-check`

样本/不确定服务器命名时，可加 `--no-server-filter` 禁用默认过滤。

- i2（单网段，所有服务器共用一个子网）：

`python a3_ybm/scripts/ybm_offline_pipeline.py --topology i2 --network-plane "计算样本面" --out-dir output --skip-prompt-check`

默认策略为 **fail-fast**：若规划结果出现 `网段个数不足/可用IP不足/vlan不足` 任意标记，会直接停止生成并打印汇总问题。
如需仍然生成 Excel 并在表内标记，追加 `--allow-insufficient`。

若 007 自动识别/解析失败，优先尝试指定 sheet 与关闭/调整过滤（示例）：

`python a3_ybm/scripts/ybm_offline_pipeline.py --topology i3 --sheet007 11 --no-server-filter --network-plane "计算样本面" --out-dir output --skip-prompt-check`

## Directory Contract

- `a3_ybm/scripts/ybm_offline_pipeline.py`：主入口（CLI；读入 → 规划 → 输出 Excel）
- `scripts/ybm_offline_pipeline.py`：主入口（同上，路径别名）
- `scripts/ybm_excel_io.py`：Excel IO（自动探测 007/资源表；解析 007 映射；读取资源表网络平面行）
- `scripts/ybm_network_planning_rules.py`：通用网络规划规则（地址池切分、网关、VLAN、i3 网段规划、spine/leaf 混合共享策略）
- `scripts/ybm_allocate_i2_flat.py`：i2 单网段顺序分配算法（按地址池裁剪可用 IP 并按设备顺序分配）
- `scripts/ybm_validate_inputs.py`：输入校验脚本（可选；提前检查 007/资源表基本格式与网络平面匹配）

## Parameters

- `--topology i2|i3`：必选，选择二层单网段或三层一机一网段
- `--network-plane NAME`：资源表「网络平面」列取值（默认 `计算样本面`；请按现场表项修改）
- `--007 PATH`：007 端口连线表（可省略；省略时自动探测）
- `--resource PATH`：项目信息收集表/资源表（可省略；省略时自动探测）
- `--out-dir output`：输出目录（默认 `output`）
- `--sheet007 SHEET`：007 的 sheet（默认 `"0"`；脚本内部失败会扫描所有 sheet 兜底）
- `--sheet-res-index INDEX`：资源表 sheet index（默认 `0`）
- `--server-substring SUBSTR`：仅保留服务器名含该子串的行（默认 `AT800T`；空字符串表示不过滤）
- `--no-server-filter`：禁用 007 首列服务器名过滤（等价于 `--server-substring ""`；用于 PowerShell 下不便传空值的场景）
- `--i3-split-spine-leaf`：仅 i3 生效：名单中区分 SPINE/LEAF，SPINE 可走 i2「共享网段累加」，LEAF 走一机一网段
- `--allow-insufficient`：允许容量不足时继续生成 Excel，并在表内标记 `网段个数不足/可用IP不足/vlan不足`（默认：发现这些标记即停止生成并打印汇总）
- `--prompt-spine-file PATH`：可选，启用 prompt 关键短语校验（i2/SPINE）
- `--prompt-leaf-file PATH`：可选，启用 prompt 关键短语校验（i3/LEAF）
- `--skip-prompt-check`：强制跳过 prompt 关键短语校验

## Path Rules (CWD Contract)

- 输入/输出路径默认要求位于当前工作目录（cwd）树下
- 省略路径时在 cwd 下自动探测：
  - 007：文件名包含 `007` 或 `端口连线` 或 `端口互联`
  - 资源：文件名包含 `项目信息收集` 或 `信息收集表` 或 `资源`

## Validation (Optional)

`python scripts/ybm_validate_inputs.py --network-plane "计算样本面"`

## Inputs (Contract)

| 来源 | 要点 |
|------|------|
| 007 | 找「设备命名」行；首列服务器、末列接入交换机；去掉服务器名列含 LEAF/SPINE 的行；可选按 `--server-substring` 过滤（或用 `--no-server-filter` 关闭过滤） |
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

## Excel Error Literals (Do Not Change)

`网段个数不足`、`可用IP不足`、`vlan不足`（定义见 `scripts/ybm_network_planning_rules.py`）。

## Troubleshooting (User-Facing)

常见问题与建议修改点：

- **007 解析失败 / 过滤后无数据**
  - **现象**：提示找不到「设备命名」，或“过滤后无可用数据 / 无法得到接入交换机→服务器映射”
  - **修改**：用 `--sheet007` 指定正确 sheet；不确定服务器命名时用 `--no-server-filter`；或将 `--server-substring` 改为能命中首列服务器名的子串

- **资源表找不到网络平面行**
  - **现象**：提示找不到 `网络平面 == --network-plane`
  - **修改**：把 `--network-plane` 改成资源表「网络平面」列中的真实取值；必要时调整 `--sheet-res-index`

- **网段不足 / 地址池切不出子网（i3）**
  - **现象**：提示“地址池无法切出满足 /mask 的子网”，或输出出现 `网段个数不足`
  - **修改**：扩大资源表 `地址池*` 范围，或调整 `最小规划掩码`（会同时影响每网段大小与可切分网段数量）

- **可用 IP 不足（i3）**
  - **现象**：输出 `可用IP不足`
  - **修改**：扩大 `地址池*`，或让单网段更大（调整 `最小规划掩码`），或减少该接入交换机关联的服务器数量

- **VLAN 不足**
  - **现象**：输出 `vlan不足`
  - **修改**：扩大资源表 `VLAN*` 区间（例如 `100-199`），或改为固定 VLAN（单值）

- **希望容量不足时仍生成 Excel（并标记问题）**
  - **做法**：加 `--allow-insufficient`

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
