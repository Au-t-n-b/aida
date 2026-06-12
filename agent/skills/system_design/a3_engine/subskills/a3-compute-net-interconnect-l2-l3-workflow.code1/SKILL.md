---
name: a3-compute-net-interconnect-l2-l3-workflow
description: 离线确定性 A3 计算侧五类平面 Leaf–Spine 网络互联规划：依据项目信息收集表「网络资源需求表」第一列网络平面 +「网关位置*」（SPINE→L2，LEAF→L3）自动选层，007+资源表 → 单次 run 输出一份 A3网络互联规划.xlsx；亦支持显式 --mode/--sheet。无 LLM、无 EDM、无数据库。
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_net_interconnect_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

在 **cwd** 下以**纯代码**确定性执行；**推荐只指定 `--plane`**，由 **`项目信息收集表.xlsx`**（内 sheet **`网络资源需求表`**）决定 L2 或 L3，**每次运行只生成一份** `A3网络互联规划.xlsx`。

### 自动模式（`--plane`）

1. 在资源表 **`网络资源需求表`** 中，用**第一列**匹配 `--plane`（如 `计算样本面`），定位该行。  
2. 读取列名含 **`网关位置`** 的列（如 **`网关位置*`**）：  
   - **`SPINE`**（不区分大小写，去空格）→ 走 **L2** 互联规划（`VLAN*`、`INTER_LINK`，ETH-TRUNK 恒为 2）；  
   - **`LEAF`** → 走 **L3** 互联规划（`内部网络设备互连地址段`、`/30`）。  
3. 根据网络平面在 007 中**自动尝试**配置的 sheet 候选（见 `NETWORK_TYPE_TO_007_SHEET_CANDIDATES`），直至解析出 Leaf–Spine 连线。

### 显式模式（`--mode` + `--sheet`）

与旧版相同：自行指定 L2/L3 与 007 sheet，用于调试或与自动探测不一致时。

### 层级与业务对齐

- **L2**：接口/VLAN/列顺序对齐 `a3_l2_net_interconnection.py`；**本/对端 ETH-TRUNK 恒为 2**（skill 固定策略）。  
- **L3**：对齐 `a3_ni_ip_address.py`。

覆盖五类**计算**平面：`计算管理面`、`计算管存面`、`计算样本面`、`计算参数面`、`计算业务面`。

## Entrypoint（推荐）

```bash
python scripts/offline_net_interconnect_pipeline.py --plane 计算样本面 [--007 PATH] [--resource 项目信息收集表.xlsx]
```

显式（与旧版一致）：

```bash
python scripts/offline_net_interconnect_pipeline.py --mode l2 --sheet 计算管理面端口互联 [--007 PATH] [--resource PATH]
```

## Dependencies

```bash
pip install -r requirements.txt
```

（`pandas` / `openpyxl`；`ipaddress` 为标准库。）

## Parameters

| 参数 | 说明 |
|------|------|
| **`--plane`** | **推荐**：网络平面字符串，须与 **`网络资源需求表` 第一列**某行取值完全一致（如 `计算样本面`）。据此行 **`网关位置*`** 自动选 **L2（SPINE）** 或 **L3（LEAF）**，并只输出 **一份** Excel。 |
| `--007 PATH` | 007 端口连线表；**省略**时在 cwd 下自动探测 |
| `--resource PATH` | **`项目信息收集表.xlsx`**（或其它含 `网络资源需求表` 的文件）；**`--plane` 时省略则优先 cwd 下 `项目信息收集表.xlsx`**，否则按文件名探测 |
| `--resource-sheet` | 资源内子表名（默认 `网络资源需求表`） |
| `--out-dir` | 输出根目录（默认 `output`）；写入 `out-dir/run_*/A3网络互联规划.xlsx` |
| `--merge-from PATH` | 可选：合并前删除同 **`网络平面`** 旧行 |
| `--mode` | 与 **`--sheet` 同时**指定时使用：`l2` 或 `l3`（与 `--plane` 互斥） |
| `--sheet` | 007 中端口互联 sheet 名（仅与 `--mode` 联用） |

## Path Rules (CWD Contract)

- **`--007` / `--resource` / `--out-dir` 解析后的路径必须位于当前工作目录（cwd）树下**（与 `a3-cpm-lq-ip-workflow` 一致）。
- 在 skill 目录内执行时，请先 **`cd` 到含输入 Excel 的工作目录**，再带 `scripts/` 相对路径调用；或使用绝对路径指向 cwd 树内文件。

## Validation (Optional)

```bash
python scripts/validate_inputs.py --plane 计算样本面 --007 PATH --resource PATH [--resource-sheet 网络资源需求表]
```

或显式：

```bash
python scripts/validate_inputs.py --mode l2 --007 PATH --resource PATH --sheet SHEET
```

仅校验连线行与资源行（及 L3 网段容量），不写输出。

## Supported `--sheet` keys（与仓库 `LEAF_SPINE_CONFIG` 子集一致）

| 007 `sheet_name` | `keyword` | `network_type` |
|------------------|-----------|----------------|
| `计算业务面端口互联` | `YWM-LEAF` | `计算业务面` |
| `计算管理面端口互联` | `GLM-LEAF` | `计算管理面` |
| `计算管存面端口互联` | `GCM-LEAF` | `计算管存面` |
| `样本面端口互联`（config 中带竖线的全名亦支持，见规则模块） | `ZSYBM-LEAF` | `计算样本面` |
| `参数面端口互联` | `LEAF` | `计算参数面` |

权威定义见 **`scripts/net_interconnect_rules.py`** 中 `LEAF_SPINE_COMPUTE_PLANES`；若与仓库 `config.py` 漂移，**以仓库为准并同步本字典**。

## Inputs (Contract)

### 007 端口连线表

- 使用 **`header=None`** 读入整张 sheet，在任意行中查找包含 **`设备命名`** 的单元格，该行作为表头行，**下一行起**为数据（与两脚本一致）。
- **筛选**：`leaf交换机` 列含 **`keyword`**，且 `spine交换机` 列含 **`spine`**（不区分大小写）；去重。
- **L2 `get_switch_data`**：列重命名含带宽列（与 `a3_l2_net_interconnection.get_switch_data` 一致）。
- **L3 `get_switch_data`**：列重命名不含带宽列（与 `a3_ni_ip_address.get_switch_data` 一致）。

### 网络资源需求表（`--plane` 时）

- Sheet 默认 **`网络资源需求表`**（通常在 **`项目信息收集表.xlsx`** 内）。
- **第一列**：与 `--plane` 做字符串 trim 后**全等匹配**，定位一行。
- **`网关位置*`**（列名含「网关位置」）：`SPINE` → L2；`LEAF` → L3。
- L2 行须含有效 **`VLAN*`**；L3 行须含有效 **`内部网络设备互连地址段`**（`起始IP-结束IP`）。

### 网络资源需求表（显式 `--mode` 时）

- 取 **`网络平面` == `network_type`** 的一行（`network_type` 由 `--sheet` 映射）。

**L2**：读取 **`VLAN*`**，写入 `本端VLAN` / `对端VLAN`（相同）；`PVID` 空字符串；`标签` = **`INTER_LINK`**；`端口类型` = **`trunk`**；**`本端ETH-TRUNK` / `对端ETH-TRUNK` 恒为 `2`**。

**L3**：读取 **`内部网络设备互连地址段`**，格式 **`起始IP-结束IP`**（IPv4 点分十进制，中间单个 `-`；离线解析使用 **`split('-', 1)`** 以兼容段内其它写法）。先 **`validate_network_range`** 再分配。

## L2 Allocation Rules（对齐 `a3_l2_net_interconnection.py` 的接口与 VLAN 语义；ETH-TRUNK 为 skill 固定策略）

1. **`本端接口`** = `iloc[:,2].fillna('') + iloc[:,1].fillna('')` 后 `strip`；**`对端接口`** = `iloc[:,5] + iloc[:,7]` 后 `strip`。
2. **`本端ETH-TRUNK` / `对端ETH-TRUNK`**：本 skill **不**再调用线上 `assign_port_value` / MLAG 配对递增逻辑；输出表中**每一行**两列均写为整数 **`2`**。
3. 输出列顺序与线上一致（见下节）。

## L3 Allocation Rules（对齐 `a3_ni_ip_address.py`）

1. 起始 IP **对齐到 4 的倍数**。
2. 每行链路：`ip1 = base+1`，`ip2 = base+2`，掩码 **30**，`current_ip += 4`。
3. 地址不足时 **warning 并跳过该行**（与线上一致）。

## Outputs (Contract)

- **`out-dir/run_*/A3网络互联规划.xlsx`**
- Sheet：**`网络互联规划`**
- 列名集合与线上一致：  
  `网络平面, 本端设备, 本端接口, 本端接口IP地址, 本端接口掩码, 本端ETH-TRUNK, 本端VLAN, 对端设备, 对端接口, 对端接口IP地址, 对端接口掩码, 对端ETH-TRUNK, 对端VLAN, PVID, 端口类型, 标签`

## Implementation Notes

- **`scripts/net_interconnect_rules.py`**：`LEAF_SPINE_COMPUTE_PLANES`、`NETWORK_TYPE_TO_007_SHEET_CANDIDATES`、第一列匹配、`gateway_column_name` / `resolve_gateway_mode`、`find_working_007_sheet`、`allocate_connection`（ETH-TRUNK 恒 2）/ `allocate_ips`、资源读取与网段校验。
- **`scripts/offline_net_interconnect_pipeline.py`**：CLI、路径约束、自动探测、写 Excel。
- **`scripts/validate_inputs.py`**：可选输入校验。

线上编排仍见 **`src/manage_agent/sub_agents/LLD_IP/main_flow.py`** 与 **`a3_l2_net_interconnection.py` / `a3_ni_ip_address.py`**；本 skill **不调用** `upload_to_edm`、`display_message` 等。

## Errors（与线上一致或子集）

- `sheet_name '...' 没有对应的配置项（本 skill 仅支持计算侧五类平面）`
- `未找到包含'设备命名'的行`
- `未找到从LEAF到SPINE的物理连线`
- L2：`未找到{network_type}所在行`、`VLAN* 为空`
- `--plane`：`资源表第一列未找到网络平面`、`网关位置为空`、`网关位置无法识别`、`资源表中未找到含「网关位置」的列`、`007 中未能为 ... 解析出 Leaf–Spine 连线`
- L3：地址段为空、格式无效、`validate_network_range` 抛出的 `/30` 容量不足等

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
