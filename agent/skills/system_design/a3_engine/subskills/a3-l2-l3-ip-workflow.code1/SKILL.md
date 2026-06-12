---
name: a3-l2-l3-ip-workflow
description: Offline A3 计算管理面 gateway IP address planning. Use when generating deterministic 计算管理面 address, gateway segment, VLAN, and access-plan Excel results from 007 port-connection sheets plus 项目信息收集表; first reads the 计算管理面 row and chooses L2 when 网关位置*=SPINE or L3 when 网关位置*=LEAF.
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_l2_l3_ip_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成 A3 **计算管理面**网关地址规划结果，输入 `007 端口连线表 + 项目信息收集表/网络资源需求表`，输出地址规划 Excel。该流程为**确定性计算**，不依赖 LLM、EDM、数据库或前端展示 API。

业务口径：

- 先读取资源表第一列 `网络平面 == 计算管理面` 的行。
- 再读取该行 `网关位置*`。
- `网关位置* == SPINE`：执行 L2 规划，L2 规则保持 `a3_l2_ip_address.py` 口径不变。
- `网关位置* == LEAF`：执行 L3 计算管理面规划，整体流程参考 `a3_ywm_ip_address.py`，但网络平面固定为计算管理面。

## Entrypoint

`python scripts/offline_l2_l3_ip_pipeline.py [--mode auto|l2|l3] [--007 PATH] [--resource PATH] [--sheet NAME] [--resource-sheet SHEET] [--out-dir output]`

## Dependencies

`pip install pandas openpyxl`

## Parameters

- `--mode auto`：默认值。读取计算管理面 `网关位置*`，`SPINE` 自动走 L2，`LEAF` 自动走 L3。
- `--mode l2`：强制执行二层接入规划。
- `--mode l3`：强制执行三层接入规划。
- `--007 PATH`：007 端口连线表；省略时在 cwd 下按 `007` / `端口连线` / `端口互联` 自动探测。
- `--resource PATH`：项目信息收集表/网络资源需求表；省略时在 cwd 下按 `项目信息收集` / `信息收集表` / `资源` 自动探测。
- `--sheet NAME`：端口互联 sheet，默认 `计算管理面端口互联`。
- `--resource-sheet SHEET`：资源表 sheet，默认 `0`。
- `--out-dir output`：输出目录，必须位于 cwd 树下。

## Inputs Contract

### 007 端口连线表

- 定位包含 `设备命名` 的行。
- 该行之后为有效数据区。
- 首列作为 `起始端设备`。
- 末列作为 `目的端设备`。
- 服务器筛选使用 `SERVER_NAME_KEYWORD`：
  `AT900A3|AT900|AT800TA3|AT800IA3|AT800TA2|AT800IA2|CCAE|NCEFI|NCEFB|DME|K8SM|K8SW|MINDIE`

### 资源表

按 `--sheet` 映射资源表中的 `网络平面`，计算管理面默认读取：

| sheet | 网络平面 |
|---|---|
| `计算管理面端口互联` | `计算管理面` |

兼容映射如下：

| sheet | 网络平面 |
|---|---|
| `计算管理面端口互联` | `计算管理面` |
| `计算业务面端口互联` | `计算业务面` |
| `计算管存面端口互联` | `计算管存面` |
| `参数面端口互联` | `计算参数面` |
| `存储业务面端口互联` | `存储业务面` |
| `存储管理面端口互联` | `存储管理面` |

必填字段：

- `地址池*`：`A.B.C.D-E.F.G.H`
- `最小规划掩码`：整数掩码位
- `网关位置*`：`SPINE` 或 `LEAF`
- `网关地址*`：`网段起始位` / `网段结束位` / 具体 IP
- `VLAN*`：单个 VLAN 或 `start-end`

## L2 Allocation Rules

对应 `a3_l2_ip_address.py` 的 `a3_2Layer_spine_generate()` 与 `allocate_ips_and_generate_df()`。

1. 读取服务器链路，按 `起始端设备` 去重，保留第一条。
2. 从资源表读取地址池、掩码、网关配置、VLAN。
3. 根据服务器数量计算所需地址数 `num_nodes + 2`。
4. 从配置掩码开始向更大网段方向寻找可覆盖地址池的 CIDR。
5. 网关规则：
   - `网段起始位`：网段第一个可用地址。
   - `网段结束位`：广播地址前一个地址。
   - 具体 IP：直接使用。
6. 可用地址排除网络地址、广播地址、网关地址，并限制在地址池范围内。
7. 服务器按去重后的原始顺序分配 IP。
8. Leaf 到 Spine 匹配：取 007 首列在服务器目的端 Leaf 列表中的行，末列包含 `spine` 或 `HXHJ-CSW` 的设备作为 Spine，最多展示前 2 台。

L2 地址规划输出列：

- `设备名称`
- `{网络平面}地址`
- `{网络平面}掩码`
- `{网络平面}网关`
- `{网络平面}VLAN`

L2 网段规划输出列：

- `交换机`
- `网段`
- `网关`
- `VLAN`
- `掩码位数`

## L3 Allocation Rules

对应计算管理面 L3 地址规划。流程参考 `a3_ywm_ip_address.py` 的 `ywm_ip_address_generate()` 与 `network_segment_generate()`，用确定性计算替代原脚本中的 LLM 工具调用，并把业务面字段替换为计算管理面字段。

1. 读取服务器链路，按 `起始端设备` 去重，保留第一条。
2. 按 `目的端设备` 统计每台 Leaf 下挂服务器数量。
3. 从资源表读取地址池、掩码、网关配置、VLAN。
4. 从地址池起始 IP 所属网段开始，按配置掩码连续生成 Leaf 网段。
5. 每台 Leaf 分配一个网段，顺序与 Leaf 首次出现顺序一致。
6. 网关规则同 L2。
7. VLAN 规则：
   - 单个数字：所有 Leaf 使用同一个 VLAN。
   - `start-end`：按 Leaf 网段顺序递增，一个 Leaf 网段对应一个 VLAN。
   - VLAN 不足或格式不合法：输出 `vlan不足`。
8. 每台服务器只在其 Leaf 网段内取可用 IP，可用 IP 排除网关并限制在原地址池范围内。
9. 绑定模式：
   - 原脚本根据 `_get_switch_mlag_data()` 中 `ETH-TRUNK != "NA"` 判断 `bond4`。
   - 离线流程无数据库 trunk 分配，确定性替代规则为：同一服务器在当前 sheet 中连接多个不同 Leaf 时标记 `bond4`，否则 `bond1`。

L3 地址规划输出列：

- `设备名称`
- `{网络平面}地址`
- `{网络平面}掩码`
- `{网络平面}网关`
- `{网络平面}VLAN`
- `绑定模式`

L3 网段规划输出列：

- `leaf交换机`
- `网段`
- `网关`
- `VLAN`
- `掩码位数`

## Outputs Contract

输出路径：

- `output/run_YYYYMMDD_HHMMSS/A3计算管理面L2地址规划.xlsx`
- `output/run_YYYYMMDD_HHMMSS/A3计算管理面L3地址规划.xlsx`

同目录另生成（与项目 `a3_l2_ip_address.py` 合并写入口径一致）：

- `A3网络设备接入规划.xlsx`（sheet `网络设备接入规划`；`网络平面=计算管理面`；多平面按 `网络平面` 列合并）

每个 Excel 包含：

- `{网络平面}网段规划`
- `{网络平面}地址规划`
- `网络设备接入规划`

`网络设备接入规划` 列：

- `网络平面`
- `本端设备`
- `本端接口`
- `对端设备`
- `对端接口`
- `ETH-TRUNK`
- `绑定模式`
- `vlan`
- `pvid`
- `端口类型`
- `标签`

## Validation

`python scripts/validate_inputs.py --007 PATH --resource PATH [--sheet NAME] [--resource-sheet SHEET]`

校验内容：

- 007 是否能定位 `设备命名` 行。
- 是否存在匹配服务器关键字的行。
- 资源表是否存在目标 `网络平面`。
- `地址池*`、`最小规划掩码`、`网关地址*`、`VLAN*` 是否符合格式。

## Error Messages

- `地址池格式错误，应为 起始IP-结束IP`
- `起始 IP 不应大于终止 IP`
- `节点数量 X 大于地址池可用 IP 数量 Y`
- `无法找到合适的子网掩码，使得地址池中的IP能够容纳所有节点`
- `地址池中可用 IP 数量 X 不足于分配给 Y 个节点`
- `网段个数不足`
- `网段中可用IP数：X，小于待分配设备数`

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
