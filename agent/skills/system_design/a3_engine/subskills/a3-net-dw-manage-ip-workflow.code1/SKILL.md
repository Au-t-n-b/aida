---
name: a3-net-dw-manage-ip-workflow
description: Offline A3 网络带外管理地址规划。Use when generating deterministic 网络带外管理 address/gateway/VLAN Excel from 007 port-connection sheets plus 项目信息收集表; reads 网络带外管理面 row and chooses L2 when 网关位置*=SPINE or L3 when 网关位置*=LEAF. Strictly aligned with a3_net_dw_manage_ip_address.py and a3_l3_net_dw_manage_ip_address.py.
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_net_dw_manage_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成 A3 **网络带外管理**地址规划结果。输入 `007 端口连线表 + 项目信息收集表/网络资源需求表`，输出一份地址规划 Excel。该流程为**确定性计算**（不依赖 LLM、EDM、数据库或前端展示 API）。

业务口径（与线上一致）：

- 在资源表第一列 `网络平面` 中精确识别 **`网络带外管理面`** 行；若未命中且仅存在一个含「带外管理」的候选行，则使用该候选，否则报错要求显式指定 `--net-plane`。
- 读取该行 `网关位置*`（列名含「网关位置」即可）。
- **`网关位置* == SPINE`**：执行 **L2** 规划（`a3_net_dw_manage_ip_address.py`）。
- **`网关位置* == LEAF`**：执行 **L3** 规划（`a3_l3_net_dw_manage_ip_address.py`）。

## Entrypoint

`python scripts/offline_net_dw_manage_pipeline.py [--mode auto|l2|l3] [--007 PATH] [--resource PATH] [--sheet NAME] [--resource-sheet SHEET] [--out-dir output]`

## Dependencies

`pip install pandas openpyxl`

## Parameters

- `--mode auto`：默认值。读取 `网络带外管理面` 行的 `网关位置*`，`SPINE` → L2，`LEAF` → L3。
- `--mode l2` / `--mode l3`：强制执行对应层。
- `--007 PATH`：007 端口连线表；省略时在 cwd 下按 `007` / `端口连线` / `端口互联` 自动探测。
- `--resource PATH`：项目信息收集表；省略时在 cwd 下按 `项目信息收集` / `信息收集表` / `资源` 自动探测。
- `--sheet NAME`：007 端口互联 sheet，默认 `网络带外管理面端口互联`。
- `--resource-sheet SHEET`：资源表 sheet，默认 `网络资源需求表`（纯数字按 index）。
- `--net-plane NAME`：资源表网络平面行名，默认 `网络带外管理面`。
- `--out-dir output`：输出目录，必须位于 cwd 树下（**仅** `output/`，不使用 `output_retest`；执行成功后会自动清理 cwd 下遗留的 `output_retest`）。

## Path Rules (CWD Contract)

- 输入/输出路径必须位于当前工作目录（cwd）树下。
- 省略 `--007` / `--resource` 时在 cwd 下自动探测同名 Excel。

## Inputs (Contract)

### 007 端口连线表（默认 sheet=`网络带外管理面端口互联`）

| 步骤 | 规则 |
|------|------|
| 定位表头 | 找包含 `设备命名` 的行 |
| 设备映射 | **首列** → `网络设备`，**末列** → `接入交换机` |
| LEAF 统计 | `接入交换机` 含 `LEAF`（不区分大小写） |
| L2 设备过滤 | **不过滤** 网络设备名中的 `-sp数字-`（0929 口径：均需分配） |
| L3 设备过滤 | **排除** 网络设备名匹配 `-sp\d+-` |
| 特殊 LEAF | 结构化表 `目的端信息-设备命名` 含 `LEAF` 的去重列表 → `wldw_leaf_list` |

### 项目信息收集表 / 网络资源需求表

| 字段 | 说明 |
|------|------|
| `网络平面` | 优先精确等于 `网络带外管理面` |
| `地址池*` | `A.B.C.D-E.F.G.H` |
| `最小规划掩码` | 整数掩码位（列名可模糊匹配） |
| `网关位置*` | `SPINE`（L2）或 `LEAF`（L3） |
| `网关地址*` | `网段起始位` / `网段结束位` / 具体 IP |
| `VLAN*` | 单个数字或 `start-end` |

## L2 Allocation Rules（`a3_net_dw_manage_ip_address.py`）

### 1. 网段规划（替代 `invoke_llm_tools` + `a3_i2_network_segment_tools_prompt`）

1. 统计每台 LEAF 的 `节点数量`（`count_leaf_switches`，不过滤 `-sp`）。
2. 调用确定性 `split_ip_range`（`ip_range_str=地址池*`，`target_prefix=最小规划掩码`，`max_switch_count=LEAF 台数`）。
3. 从第一台 LEAF 起**顺次累加**节点数；未超过当前网段可用 IP 则**共用**网段/网关/VLAN；累加超限则当前 LEAF 作为**新网段起点**（i2 步骤 3）。
4. 网关：`网段起始位` → 网络地址+1；`网段结束位` → 广播地址-1；否则为配置 IP。
5. VLAN：单值 → 全部分配相同；`start-end` → 每个网段组递增一个 VLAN；不足 → `vlan不足`。
6. 每台 LEAF 输出一行 `SwitchGateway`（多 LEAF 可同网段）。

### 2. Leaf → Spine 网关转移

- `get_leaf_spine_mapping`：007 首列 LEAF（在 leaf 网段列表中）→ 末列 Spine。
- `transfer_gateways_to_spines`：按 VLAN 将网段/网关绑定到 Spine（对齐 `ip_address_models`）。
- 该步骤用于保持与原脚本的 L2 业务语义一致；离线 skill 的对外交付只输出地址规划表，不额外输出网关中间 Excel。

### 3. 设备 IP 分配

1. `接入交换机` → `网络设备[]` 映射（不过滤 `-sp`）。
2. 按 `network_segment` 分组，汇总该网段下所有 LEAF 的网络设备。
3. `usable_ips` = 网段 host 地址 ∩ 地址池范围，**排除网关**。
4. 分配列表 = 网络设备 + `wldw_leaf_list`（追加在末尾）。
5. 接口与地址：
   - 在 `wldw_leaf_list`：`接口名称=vlanif{VLAN}`，**`带外管理地址` = 分配到的 IP**（L2 不强制等于网关）。
   - 其他：`接口名称=MGMT`，`带外管理地址` = 分配 IP。

## L3 Allocation Rules（`a3_l3_net_dw_manage_ip_address.py`）

### 1. 网段规划（替代 `a3_i3_network_segment_tools_prompt`）

1. 统计 LEAF 节点数（**过滤** `-sp\d+-` 网络设备）。
2. 从地址池起始 IP 起，按配置掩码**连续**生成子网，**一 LEAF 一网段**（i3 步骤 2）。
3. 网段不足 → 该 LEAF 行 `网段个数不足` 并抛错终止分配。
4. 网关/VLAN 规则同 L2。

### 2. 无 Spine 转移

- L3 网关保留 **Leaf** 维度；离线 skill 的对外交付只输出地址规划表。

### 3. 设备 IP 分配

1. `接入交换机` → `网络设备[]`（**过滤** `-sp\d+-`）。
2. 分组与可用 IP 逻辑同 L2。
3. 接口与地址（L3 特殊）：
   - 在 `wldw_leaf_list`：`接口名称=vlanif{VLAN}`，**`带外管理地址` = 网关 IP**。
   - 其他：`接口名称=MGMT`，`带外管理地址` = 分配 IP。

## Outputs (Contract)

目录：`output/run_YYYYMMDD_HHMMSS/`

只输出一份文件：

| 文件 | Sheet | 说明 |
|------|-------|------|
| `A3网络带外管理地址规划.xlsx` | `网络带外管理地址` | 主结果，对齐线上输出列 |

主结果列（严格对齐 python）：

| 列名 | 说明 |
|------|------|
| `设备名称` | 网络设备或特殊 LEAF |
| `带外管理地址` | L2：分配 IP；L3 特殊 LEAF：网关 IP |
| `带外管理掩码` | 掩码位数 |
| `带外管理网关` | 该网段网关 |
| `带外管理VLAN` | 整数 VLAN |
| `接口名称` | `vlanif{N}` 或 `MGMT` |

## Implementation Notes

- `scripts/net_dw_manage_rules.py`：解析、网段生成、Spine 转移、IP 分配。
- `scripts/offline_net_dw_manage_pipeline.py`：主流程（读表 → 选 L2/L3 → 写 Excel）。
- `scripts/validate_inputs.py`：输入校验（可选）。

## L2 vs L3 差异速查

| 项 | L2（SPINE） | L3（LEAF） |
|----|-------------|------------|
| 源脚本 | `a3_net_dw_manage_ip_address.py` | `a3_l3_net_dw_manage_ip_address.py` |
| 网段模型 | 多 LEAF 可共用网段（累加节点） | 一 LEAF 一网段 |
| `-sp\d+-` 设备 | 保留 | 排除 |
| 网关中间表 | Spine（转移后） | Leaf |
| 特殊 LEAF 地址 | 仍用分配 IP | **强制网关 IP** |

## Validation

`python scripts/validate_inputs.py --007 PATH --resource PATH [--sheet NAME] [--resource-sheet SHEET]`

## Error Messages（与线上一致）

- `未找到包含'设备命名'的行，请检查表格内容`
- `未找到网络平面含「带外管理」...`
- `网络带外管理面 网关位置* 必须为 SPINE 或 LEAF`
- `地址池格式错误，应为 起始IP-结束IP`
- `网段个数不足`
- `网段 {net_seg} 中可用 IP 不足，请检查！`
- `未找到交换机 {name} 的网关信息`
- `vlan 无法转换为整数`（分配阶段 VLAN 非数字时）

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
