---
name: a3-cc-glm-ip-workflow
description: >-
  离线 A3 存储管理面地址规划：按资源表网关位置*自动识别 L2/L3，生成地址规划 Excel（确定性，无 LLM）。
  对齐 a3_l2_cc_glm_ip_address.py 与 a3_cc_glm_ip_address.py。
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_cc_glm_pipeline.py
  source_scripts:
    - src/manage_agent/sub_agents/LLD_IP/a3_l2_cc_glm_ip_address.py
    - src/manage_agent/sub_agents/LLD_IP/a3_cc_glm_ip_address.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成「**存储管理面**」地址分配结果。输入两份 Excel，**自动识别 L2/L3** 后执行确定性网段规划与 IP 分配，**不调用 LLM**。

## L2/L3 自动识别（与线上一致）

对齐 `main_flow.execute_three_instruction` / `glmdz_scene_recognition_prompt`：

1. 读资源表 sheet **`网络资源需求表`**（`utils.get_net_to_gateway_resource_info`）
2. 取 `网络平面 == 存储管理面` 行的 **`网关位置*`**
3. 路由规则（与 `instruction += '_L3' if gateway == 'LEAF' else '_L2'` 相同）：

| 网关位置* | LEAF 接入层级 | 层级 | 执行脚本 |
|-----------|---------------|------|----------|
| **LEAF** | 三层 | **L3** | `a3_cc_glm_ip_address.py` |
| **SPINE** 或其它 | 二层 | **L2** | `a3_l2_cc_glm_ip_address.py` |

识别结果写入 `output/run_*/layer_detection.txt` 与 `run_meta.csv`。

## Entrypoint

```bash
python scripts/offline_cc_glm_pipeline.py [--connect PATH] [--resource PATH] [--out-dir output]
```

## Dependencies

`pip install pandas openpyxl`（或 `pip install -r requirements.txt`）

## Parameters

| 参数 | 说明 |
|------|------|
| `--force-layer L2\|L3` | 可选，强制层级（默认按 `网关位置*` 自动识别） |
| `--connect PATH` | 存储管理面端口互联表（可省略；cwd 下自动探测含 `007`/`端口连线`/`端口互联` 的文件） |
| `--resource PATH` | 项目信息收集表（可省略；自动探测含 `项目信息收集`/`资源` 的文件） |
| `--sheet-connect` | 互联表 sheet（默认 `auto`：优先「存储管理面端口互联」；`0`/`1` 为索引而非 sheet 名） |
| `--sheet-res-index` | 资源表 sheet index（默认 `0`） |
| `--out-dir output` | 输出根目录 |
| `--skip-prompt-check` | 跳过与 `a3_i2`/`a3_i3` prompt 文案一致性检查 |

## Path Rules (CWD Contract)

- 输入/输出路径须在 **当前工作目录（cwd）** 树下
- 自动探测仅在 cwd 内 `rglob` Excel

## Validation (Optional)

```bash
python scripts/validate_inputs.py [--connect PATH] [--resource PATH]
```

## Inputs (Contract)

### 端口互联表（`--connect`）

对齐 `get_node_info` / `get_switch_info`：

1. 定位含 **「设备命名」** 的表头行，其下为数据
2. 列：**起始端设备**（第1列）、**起始端接口**（第2列）、**目的端设备**（最后一列）
3. 仅保留起始端设备名匹配 `STORAGE_NAME_KEYWORD`：
   `OSP9950`, `OSP9550`, `OSP9920`, `OSA800`, `OD1600T`, `OD1301`
4. **节点名称** = `起始端设备` + `-` + 接口中的 NODE 段（含 `node` 时取 `/` 前 `-` 前段，否则整段接口名）
5. **交换机 IP 需求** = 该 Leaf 下节点数 × **8**（与脚本 `IP数量 = 节点数量 * 8` 一致）

### 资源表（`--resource`）

- **优先** sheet：`网络资源需求表`（与线上一致）
- 取 `网络平面 == 存储管理面` 的行
- **层级识别**：`网关位置*`（LEAF→L3，SPINE 等→L2）
- **规划字段**：`地址池*`、`最小规划掩码`、`网关地址*`、`VLAN*`

## Outputs (Contract)

运行目录：`output/run_YYYYMMDD_HHMMSS/`

| 文件 | 对齐线上 | 说明 |
|------|----------|------|
| **`A3存储管理面网段规划.xlsx`** | `display_message("0-6", …网段规划…)` | sheet `存储管理面网段规划`：L3=Leaf 网段表；L2=Spine 网段表（另含 sheet `Leaf网段`） |
| **`A3存储管理面IP地址规划.xlsx`** | `display_message("0-7/0-8", …IP地址规划…)` | sheet `存储管理面IP地址规划`；若有 OSA800 则 `存储管理面IP地址规划(A800)` |
| `A3存储管理面地址规划.xlsx` | `get_file_path` / `upload_to_edm` | 与 IP 表内容相同，sheet 名为 `存储管理面地址规划`（及 A800） |
| `layer_detection.txt` / `run_meta.csv` | — | 自动 L2/L3 识别记录 |
| **`A3网络设备接入规划.xlsx`** | `merge_and_save_data` → `A3网络设备接入规划.xlsx` | sheet `网络设备接入规划`；`网络平面=存储管理面`；对齐 `_get_switch_mlag_data` + VLAN 映射 |

### 地址规划表字段

**普通存储节点**（非 OSA800）：

- `集群`、`硬盘池`、`设备名称`、`节点`
- `存储管理面地址`、`存储管理面掩码`、`存储管理面网关`、`存储管理面VLAN`
- 每台 **设备** 的**首个节点**额外：`集群模块管理地址1`、`集群模块管理地址2`（占用 `usable_ips[i+offset+8/9]`，`offset` 每设备 +2）

**OSA800**（节点名含 `OSA800`）：

- `设备名称`、`本端端口`、`存储管理面地址/掩码/网关/VLAN`、`组网模式=独立IP`

## Deterministic Workflow（与源码逐步对应）

### 共用步骤（L2 + L3）

1. `get_node_info` → `equipment_info_df`（按节点名称去重）
2. `get_switch_info` 语义 → `switch_to_nodes`，`IP数量 = len(nodes)×8`
3. `get_net_resource_info` → 地址池、掩码、网关模式、VLAN
4. **网段规划**（替代 `invoke_llm_tools`）：
   - 地址池 + 掩码 → `split_ip_range(..., max_switch_count=len(leaf))`
   - **L3**：`plan_switch_gateways_leaf_i3`（一 Leaf 一网段，对齐 `a3_i3_network_segment_tools_prompt`）
   - **L2**：`plan_switch_gateways_glm_i2`（共用网段，累加 **IP 需求** 而非裸节点数，对齐 `a3_i2_network_segment_tools_prompt`）
5. `network_segment_check` 关键规则（首网段起始于地址池、行数一致、`网段个数不足` 报错）
6. 按 Leaf 循环 `allocate_storage_manage_ips`（对齐 `a3_cc_glm_ip_address_generate` 内层循环）：
   - `usable_ips` = 子网 hosts ∩ 地址池范围，排除网关
   - 先 **OSA800**，再普通节点；`目的端设备 == leaf` 过滤
7. 写出 Excel（对齐 `get_file_path` 命名：`A3{存储管理面}地址规划.xlsx`）

### L2 专有（`a3_l2_cc_glm_ip_address.py`）

1. `get_leaf_spine_info`：互联表第1列=Leaf、最后一列=Spine，且 Leaf 在规划列表中
2. 映射为空时：sheet 名 **「存储」→「计算」** 再查（`计算管理面端口互联`）
3. `transfer_gateways_to_spines` → 仅保留 `spine` in `name.lower()` → 写出 spine 网段文件
4. **IP 仍按 Leaf 子网分配**（`switch_network_segment_info` 为 Leaf 级，与线上一致）

> 离线 skill **不**包含：`a3_switch_loopback_ip_generate`、MLAG 接入表、`upload_to_edm`/`display_message`、`_update_dw_gatewayinfo` / `_update_gateway_info`（需在线 Agent 环境）。

### L3 专有（`a3_cc_glm_ip_address.py`）

- 无 Leaf→Spine 转换
- 网段结果即 Leaf Markdown（对应线上 `display_message("0-6", ..., switch_info)` 内容）

## Implementation Map

| 模块 | 职责 |
|------|------|
| `scripts/cc_glm_io.py` | `get_node_info`、`get_switch_to_nodes`、资源表、Leaf-Spine 映射 |
| `scripts/cc_glm_segment_rules.py` | I2 GLM 共用网段（×8 需求）、`transfer_gateways_to_spines` |
| `scripts/dw_manage_segment_rules.py` | 子网切分、网关、I3 一机一网段、可用 IP 枚举 |
| `scripts/cc_glm_ip_allocate.py` | OSA800 / 集群模块管理地址 / 偏移分配 |
| `scripts/offline_cc_glm_pipeline.py` | 主入口 |
| `scripts/validate_inputs.py` | 输入校验 |

## Prompt Parity Check (Optional, No LLM)

主流程可校验仓库内 prompt 三引号块是否含关键短语（`--skip-prompt-check` 可跳过）：

- `a3_i2_network_segment_tools_prompt.py`：`多个或所有交换机使用同一网段`、`顺次累加节点数量`
- `a3_i3_network_segment_tools_prompt.py`：`交接机不能共用网段`、`网段个数不足`、`vlan不足`

## Excel Error Literals (Do Not Change)

`网段个数不足`、`可用IP不足`、`vlan不足`

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
