---
name: a3-cc-ybm-ip-workflow
description: >-
  离线 A3 存储样本面地址规划：统一指令、按资源表网关位置*自动识别 L2/L3，
  按端口表自动识别 OD1600T/OSA800/OSP 场景，生成地址规划 Excel（确定性，无 LLM）。
  对齐 a3_cc_ybm_ip_address.py（L3）；L2 网段按 I2 规则、分配逻辑同源。
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_cc_ybm_pipeline.py
  source_scripts:
    - src/manage_agent/sub_agents/LLD_IP/a3_cc_ybm_ip_address.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成「**存储样本面**」地址分配结果。用户只需一条规划指令（**不区分 L2/L3**），skill 根据项目信息表与端口互联表**自动识别层级与设备场景**，执行确定性网段规划与 IP 分配，**不调用 LLM**。

在线入口（参考）：`main_flow.py` 中 `存储样本面地址规划_L3` → sheet **`样本面端口互联 | 数据面端口互联`** → `a3_cc_ybm_ip_address_generate`；`存储样本面地址规划_L2` 在线暂走 `a3_ni_ip_generate`，本 skill 的 L2 分支按 **I2 网段 + 与 L3 相同的分配函数** 实现（与待开发的 `a3_l2_cc_ybm_ip_address` 设计意图一致）。

## 统一指令（用户侧）

用户可说：

- **存储样本面地址规划**
- 或提供「样本面端口互联 | 数据面端口互联」表 + 项目信息收集表，要求生成存储样本面地址规划

**不要**要求用户选择 L2 或 L3，也不要要求选择 OD1600T / OSA800 / OSP；由 skill 自动识别。

## 自动识别 1：L2 / L3（与线上一致）

对齐 `main_flow.execute_three_instruction` / `a3-cc-ywm-ip-workflow` / `a3-cc-glm-ip-workflow`：

1. 读资源表 sheet **`网络资源需求表`**（无则退化为 index 0）
2. 取 `网络平面 == 存储样本面` 行的 **`网关位置*`**
3. 路由规则（与 `instruction += '_L3' if gateway == 'LEAF' else '_L2'` 相同）：

| 网关位置* | LEAF 接入层级 | 层级 | 执行逻辑 |
|-----------|---------------|------|----------|
| **LEAF** | 三层 | **L3** | I3 一 Leaf 一网段 + `a3_cc_ybm` 分配 |
| **SPINE** 或其它 | 二层 | **L2** | I2 共用网段（×8 累加）+ 同上分配 |

识别结果写入 `output/run_*/layer_detection.txt`、`scenario_detection.txt` 与 `run_meta.csv`。

### L2 与 L3 行为差异（网段）

| 能力点 | L3 | L2 |
|--------|----|----|
| 网段规划 | I3：一 Leaf 一网段 | I2：多 Leaf 可共用网段，累加 **起始端设备数×8** |
| 网段展示 | Leaf 网段表 | Spine 网段表 + 附 `Leaf网段` |
| IP 分配（OSP/OSA800） | 与 `a3_cc_ybm_ip_address.py` 相同 | 相同（子网取自 Leaf 规划结果） |

## 自动识别 2：设备场景（三分支，互斥优先级）

对齐 `a3_cc_ybm_ip_address_generate`：

| `device_scenario` | 端口表条件 | 流程 |
|-------------------|------------|------|
| **od1600t** | 节点名含 `OD1600T`（**最高优先级**） | `od1600t_ip_address_generate`：资源平面 **OceanDisk样本面**，点对点 /30，无 Leaf 网段表 |
| **osa800_only** | 含 `OSA800`，且无 OD1600T | 网段规划 + **独立 IP**（全局地址池动态掩码，每节点 1 IP） |
| **osp_only** | 默认（OSP9950/9550/9920 等） | Leaf 网段 + **双样本面接口 + 控制接口**（控制段为子网 mask+1 的第 2 子网） |

> 与存储业务面 skill 不同：存储样本面 **无 OSP+OSA800 混合** 分支；存在 OSA800 时仅处理 OSA800。

## Entrypoint

```bash
python scripts/offline_cc_ybm_pipeline.py [--connect PATH] [--resource PATH] [--out-dir output]
```

工作目录（cwd）下放置输入 Excel，或使用 `--connect` / `--resource` 指定（路径须在 cwd 内）。

## Dependencies

`pip install pandas openpyxl`（或 `pip install -r requirements.txt`）

## Parameters

| 参数 | 说明 |
|------|------|
| `--force-layer L2\|L3` | 可选，强制层级（默认按 `网关位置*` 自动识别） |
| `--connect PATH` | 样本面\|数据面端口互联表（可省略；cwd 自动探测含 `007`/`端口连线`/`端口互联` 的文件） |
| `--resource PATH` | 项目信息收集表（可省略；自动探测含 `项目信息收集`/`资源` 的文件） |
| `--sheet-connect` | 互联表 sheet（默认 `auto`：优先「样本面端口互联 \| 数据面端口互联」） |
| `--sheet-res-index` | 资源表 sheet index（默认 `0`，优先 `网络资源需求表`） |
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

1. 定位含 **「设备命名」** 的表头行
2. 列：**起始端设备**（第1列）、**起始端接口**（第2列）、**目的端设备**（最后一列）
3. 筛选 `STORAGE_NAME_KEYWORD`：`OSP9950`, `OSP9550`, `OSP9920`, `OSA800`, `OD1600T`, `OD1301`
4. **节点名称** = `起始端设备` + `-` + 接口中 NODE 段（如 `NODE0`）
5. **Leaf 需求统计**：按起始端设备去重，每 Leaf **IP数量 = 设备数 × 8**

### 资源表（`--resource`）

- **OSP / OSA800**：`网络平面 == 存储样本面` → `地址池*`、`最小规划掩码`、`网关地址*`、`VLAN*`、`网关位置*`（层级）
- **OD1600T**：另需 `网络平面 == OceanDisk样本面` 一行（地址池、掩码默认 30、VLAN 池）

## Outputs (Contract)

运行目录：`output/run_YYYYMMDD_HHMMSS/`

| 文件 | 对齐线上 | 说明 |
|------|----------|------|
| **`A3存储样本面网段规划.xlsx`** | `display_message("0-6", …网段规划…)` | OSP/OSA800；OD1600T 不生成 |
| **`A3存储样本面IP地址规划.xlsx`** | `display_message("0-7", …IP地址规划…)` | sheet `存储样本面IP地址规划` |
| **`A3存储样本面地址规划.xlsx`** | `get_file_path` / `upload_to_edm` | 与 IP 表同结构 |
| `layer_detection.txt` / `scenario_detection.txt` / `run_meta.csv` | — | `layer`、`device_scenario`、`source_script` |

### OSP 地址规划列

`集群`、`硬盘池`、`设备名称`、`节点`、`存储样本面接口1`、`存储样本面接口2`、`控制接口`、`存储样本面掩码`、`存储样本面网关`、`存储样本面VLAN`

### OSA800 独立 IP 列

`设备名称`、`本端端口`、`IP`、`掩码`、`网关`、`VLAN`、`组网模式=独立IP`

### OD1600T 列

`本端设备名称`、`本端接口名称`、`本端地址`、`对端地址`、`VLAN ID`、`对端接口名称`、`对端设备名称`

## Deterministic Workflow

### 共用

1. `detect_cc_ybm_layer` → L2 或 L3
2. `get_node_info` → `classify_device_scenario`
3. 若 **od1600t** → `allocate_od1600t_ips` → 写 Excel → 结束
4. `get_switch_to_nodes` → I2/I3 网段规划（替代 `invoke_llm_tools`）
5. `network_segment_check` 关键规则
6. **osa800_only** → `allocate_osa800_independent_ips`；**osp_only** → `allocate_osp_ybm_ips`
7. 写出 Excel

## Implementation Map

| 模块 | 职责 |
|------|------|
| `scripts/cc_ybm_io.py` | 节点解析、Leaf×8 需求、资源表、L2/L3 识别、场景分类、Leaf-Spine |
| `scripts/cc_ybm_segment_rules.py` | I2/I3 网段（×8）、Spine 网关迁移 |
| `scripts/dw_manage_segment_rules.py` | 子网切分、网关、可用 IP |
| `scripts/cc_ybm_ip_allocate.py` | OSP / OSA800 / OD1600T 分配 |
| `scripts/offline_cc_ybm_pipeline.py` | 主入口 |
| `scripts/validate_inputs.py` | 输入校验 |

## Prompt Parity Check (Optional, No LLM)

- `a3_i2_network_segment_tools_prompt.py`：`多个或所有交换机使用同一网段`、`顺次累加节点数量`
- `a3_i3_network_segment_tools_prompt.py`：`交接机不能共用网段`、`网段个数不足`、`vlan不足`

## Excel Error Literals (Do Not Change)

`网段个数不足`、`可用IP不足`、`vlan不足`

## Agent 执行指引

1. 进入本 skill 目录或将其作为 cwd
2. 确认两份 Excel 在 cwd 或传入 `--connect` / `--resource`
3. 运行 `python scripts/offline_cc_ybm_pipeline.py`（可加 `--skip-prompt-check`）
4. 将 `output/run_*/` 下 xlsx 与 `scenario_detection.txt` 交给用户
5. 若失败，先运行 `python scripts/validate_inputs.py` 定位缺列或场景为空

## 与在线 Agent 的差异

离线覆盖：**拓扑解析、网段规划、三分支 IP 分配、Excel 产出**。以下在线能力不执行：

- `a3_switch_loopback_ip_generate` / `a3_cc_ybm_ywm_switch_loopback_ip_generate`
- `process_switch_mlag_data` → `A3网络设备接入规划.xlsx`
- `_update_gateway_info`、`upload_to_edm`、`display_message`、`invoke_llm_tools`

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
