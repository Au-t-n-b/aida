---
name: a3-csm-ip-workflow
description: >-
  离线计算参数面地址规划：统一指令、按端口表自动识别 A2/A3 场景，
  生成网段规划与 IP 地址规划 Excel（确定性，无 LLM）。
  对齐 csm_ip_address.py 与 a3_csm_ip_address.py。
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_csm_pipeline.py
  source_scripts:
    - src/manage_agent/sub_agents/LLD_IP/csm_ip_address.py
    - src/manage_agent/sub_agents/LLD_IP/a3_csm_ip_address.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成「**计算参数面**」地址分配结果。用户只需一条规划指令（**不区分 L2/L3**；线上 `计算参数面地址规划_L2` 与 `_L3` 均调用同一入口 `a3_csm_ip_generate`），skill 根据端口互联表**自动识别 A2 或 A3 服务器场景**，执行确定性网段规划与 IP 分配，**不调用 LLM**。

## 统一指令（用户侧）

用户可说：

- **计算参数面地址规划**
- 或提供「参数面端口互联」表 + 项目信息收集表，要求生成计算参数面地址规划

**不要**要求用户选择 L2/L3 或 A2/A3；由 skill 自动识别场景。

## 自动识别：A2 / A3（与线上一致）

对齐 `a3_csm_ip_generate` 中 `process_excel_or_db_data` + 设备命名列判断（等价于检查「起始端信息-设备命名」）：

1. 读端口互联表，取 **计算服务器**（表头行含「设备命名」后的首列）
2. 路由规则（**A2 优先**）：

| 端口表条件 | 场景 | 执行逻辑来源 |
|------------|------|----------------|
| 任一服务器名匹配 `AT800TA2\|AT800IA2\|AT900A2` | **A2** | `csm_ip_address.csm_ip_generate` |
| 否则任一匹配 `AT800TA3\|AT800IA3\|AT900A3` | **A3** | `a3_csm_ip_address` 内 A3 分支 |
| 两者均无 | 报错 | `计算参数面端口互联中未匹配到A2和A3机器` |

识别结果写入 `output/run_*/scenario_detection.txt` 与 `run_meta.csv`（`scenario`、`rail_mode`（仅 A3）、`source_script`）。

### A2 与 A3 行为差异

| 能力点 | A2 | A3 |
|--------|----|----|
| 拓扑过滤 | `SERVER_NAME_KEYWORD`（较宽） | 仅 `A3_SERVER_NAME_KEYWORD` |
| Leaf IP 需求统计 | 每 Leaf **行数** × 2（`groupby count`） | 每 Leaf **(服务器,端口) 去重链路数** × 2 |
| 网段规划 | I3：一 Leaf 一网段（替代 `switch_network_segment_info` LLM） | I3：一 Leaf 一网段（替代 `a3_i3_network_segment_tools` LLM） |
| 资源表网关列 | `网关位置*` | `网关地址*` |
| IP 分配 | 每服务器 **8 个 NPU**（`参数面NPU0`~`7`） | **DEVICE ID** + `参数面地址`（2/4/8 轨公式） |
| 输出 sheet 后缀 | `计算参数面地址_A2` | `计算参数面地址_A3` |

### A3 专有：轨数推断

`infer_rail_mode`：单台计算服务器下联 **不同 leaf 数** 的最大值 → 2 / 4 / 8 轨。分配时 `rail_idx = DEVICE_ID % R`，`host_step = DEVICE_ID // R`（`R` 为本机实际下联 leaf 数，可与全局轨数不同）。

### DEVICE ID

`DEVICE_ID = (8 - PIC通道号) + 8 * j`，`j ∈ {0,1}`（每物理端口两条记录）。

## Entrypoint

```bash
python scripts/offline_csm_pipeline.py [--connect PATH] [--resource PATH] [--out-dir output]
```

工作目录（cwd）下放置输入 Excel，或使用 `--connect` / `--resource` 指定（路径须在 cwd 内）。

## Dependencies

`pip install pandas openpyxl`（或 `pip install -r requirements.txt`）

## Parameters

| 参数 | 说明 |
|------|------|
| `--force-scenario a2\|a3\|auto` | 可选，强制场景（默认 `auto` 按端口表识别） |
| `--connect PATH` | 参数面端口互联表（可省略；cwd 自动探测含 `007`/`端口连线`/`端口互联` 的文件） |
| `--resource PATH` | 项目信息收集表（可省略；自动探测含 `项目信息收集`/`资源` 的文件） |
| `--sheet-connect` | 互联表 sheet（默认 `auto`：优先「参数面端口互联」） |
| `--sheet-res-index` | 资源表 sheet index（默认 `0`，优先 `网络资源需求表`） |
| `--out-dir output` | 输出根目录 |
| `--skip-prompt-check` | 跳过与 `a3_i3` prompt 文案一致性检查 |

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
2. 列：**计算服务器**（第1列）、**服务器端口**（第2列）、**leaf交换机**（最后一列）
3. A2 Leaf 需求：`groupby leaf` 对 `计算服务器` **count** × 2
4. A3 Leaf 需求：`(计算服务器, 服务器端口)` **去重** 链路数 × 2；leaf 顺序为表中 **首次出现顺序**

### 资源表（`--resource`）

- **优先** sheet：`网络资源需求表`
- 取 `网络平面 == 计算参数面` 的行
- **规划**：`地址池*`、`最小规划掩码`、`VLAN*`
- **网关模式**：A2 读 `网关位置*`；A3 读 `网关地址*`（与两脚本 `get_net_resource_info` 一致）

## Outputs (Contract)

运行目录：`output/run_YYYYMMDD_HHMMSS/`

| 文件 | 对齐线上 | 说明 |
|------|----------|------|
| **`A2计算参数面网段规划.xlsx`** / **`A3…`** | `display_message("0-6", …网段规划…)` | sheet `计算参数面网段规划` |
| **`A2计算参数面IP地址规划.xlsx`** / **`A3…`** | `display_message("0-7", …IP地址规划…)` | A2：NPU 列；A3：DEVICE ID + 参数面地址 |
| **`A2计算参数面地址规划.xlsx`** / **`A3…`** | `get_file_path` / `upload_to_edm` | sheet `计算参数面地址_A2` 或 `_A3` |
| `scenario_detection.txt` / `run_meta.csv` | — | `scenario`、`rail_mode`（A3）、`source_script` |

### A2 地址规划列

`设备名称`、`参数面IP网关`、`参数面掩码`、`参数面NPU0`~`参数面NPU7`、`参数面VLAN`

### A3 地址规划列

`设备名称`、`DEVICE ID`、`参数面地址`、`参数面掩码`、`参数面网关`、`参数面VLAN`

排序：服务器 SP/序号 → DEVICE ID → IPv4 四段（网段 id + 主机位）。

## Deterministic Workflow

### 共用

1. `detect_csm_scenario` → A2 或 A3
2. 读资源表 → `split_ip_range` + `plan_switch_gateways_leaf_i3`（一 Leaf 一网段）
3. `network_segment_check` 关键规则
4. 按场景调用 `allocate_a2_csm_ips` 或 `generate_a3_ip_assignment_table`
5. 写出 Excel

### A2 专有

1. `get_a2_switch_demand_markdown` + `get_a2_server_leaf_df`（服务器–leaf 全表，不按 A3 过滤）
2. 每 leaf 子网内按设备行序 `i*8 … i*8+7` 分配 NPU IP

### A3 专有

1. `get_a3_topology` → `leaf_order`、`rail_mode`、`switch_to_servers`（含端口排序）
2. 全局 `used_ips` 去重；`rail_idx` / `host_step` 选网段与主机位

> 离线 skill **不**包含：`a3_switch_loopback_ip_generate`、MLAG 接入表、`upload_to_edm` / `display_message`、`_update_gateway_info`（需在线 Agent 环境）。

## Implementation Map

| 模块 | 职责 |
|------|------|
| `scripts/csm_io.py` | 端口表解析、A2/A3 识别、Leaf 需求、A3 拓扑与轨数 |
| `scripts/csm_segment_rules.py` | I3 网段规划、Markdown/DataFrame 输出 |
| `scripts/dw_manage_segment_rules.py` | 子网切分、网关、可用 IP 枚举 |
| `scripts/csm_ip_allocate.py` | A2 八 NPU / A3 DEVICE ID 分配 |
| `scripts/offline_csm_pipeline.py` | 主入口 |
| `scripts/validate_inputs.py` | 输入校验 |

## Prompt Parity Check (Optional, No LLM)

- `switch_network_segment_info.py`（A2 网段规划语义）
- `a3_i3_network_segment_tools_prompt.py`：`交接机不能共用网段`、`网段个数不足`、`vlan不足`

## Excel Error Literals (Do Not Change)

`网段个数不足`、`可用IP不足`、`vlan不足`

## Agent 执行指引

1. 进入本 skill 目录或将其作为 cwd
2. 确认两份 Excel 在 cwd 或传入 `--connect` / `--resource`
3. 运行 `python scripts/offline_csm_pipeline.py`（可加 `--skip-prompt-check`）
4. 将 `output/run_*/` 下 `A2` 或 `A3` 前缀的三个 xlsx 与 `scenario_detection.txt` 交给用户
5. 若失败，先运行 `python scripts/validate_inputs.py` 定位缺列或场景为空

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
