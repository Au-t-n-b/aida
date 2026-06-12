---
name: a3-cc-ywm-ip-workflow
description: >-
  离线 A3 存储业务面地址规划：统一指令、按资源表网关位置*自动识别 L2/L3，
  按端口表自动识别 OSP/OSA800/混合场景，生成地址规划 Excel（确定性，无 LLM）。
  对齐 a3_l2_cc_ywm_ip_address.py 与 a3_cc_ywm_ip_address.py。
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_cc_ywm_pipeline.py
  source_scripts:
    - src/manage_agent/sub_agents/LLD_IP/a3_l2_cc_ywm_ip_address.py
    - src/manage_agent/sub_agents/LLD_IP/a3_cc_ywm_ip_address.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成「**存储业务面**」地址分配结果。用户只需一条规划指令（**不区分 L2/L3**），skill 根据项目信息表与端口互联表**自动识别层级与设备场景**，执行确定性网段规划与 IP 分配，**不调用 LLM**。

在线入口（参考）：`main_flow.py` 中 `存储业务面地址规划_L2` / `存储业务面地址规划_L3` 均对应 sheet **`存储业务面端口互联`**，本 skill 合并为同一离线流程。

## 统一指令（用户侧）

用户可说：

- **存储业务面地址规划**
- 或提供端口互联表 + 项目信息收集表，要求生成存储业务面地址规划

**不要**要求用户选择 L2 或 L3；由 skill 自动识别并执行对应脚本逻辑。

## 自动识别 1：L2 / L3（与线上一致）

对齐 `main_flow.execute_three_instruction` / `utils.get_net_to_gateway_resource_info` / `a3-cc-glm-ip-workflow`：

1. 读资源表 sheet **`网络资源需求表`**（无则退化为 index 0）
2. 取 `网络平面 == 存储业务面` 行的 **`网关位置*`**
3. 路由规则（与 `instruction += '_L3' if gateway == 'LEAF' else '_L2'` 相同）：

| 网关位置* | LEAF 接入层级 | 层级 | 执行逻辑来源 |
|-----------|---------------|------|----------------|
| **LEAF** | 三层 | **L3** | `a3_cc_ywm_ip_address.py` |
| **SPINE** 或其它 | 二层 | **L2** | `a3_l2_cc_ywm_ip_address.py` |

识别结果写入 `output/run_*/layer_detection.txt` 与 `run_meta.csv` 的 `layer`、`gateway_position`、`source_script`。

### L2 与 L3 行为差异（网段与网关）

| 能力点 | L3 | L2 |
|--------|----|----|
| 网段规划算法 | I3：一 Leaf 一网段（`plan_switch_gateways_leaf_i3`） | I2：多 Leaf 可共用网段，累加 **起始端设备数×8**（`plan_switch_gateways_glm_i2`） |
| 网段展示（0-6） | Leaf 网段表 | Spine 网段表（`transfer_gateways_to_spines`）+ 附 `Leaf网段` |
| `network_segment_check` 语义 | `"leaf"` | `"spine"` |
| OSA800 仅设备 | 固定 **bond4** | 读 **`组网场景`**：含 `bond` → bond4，否则 **多IP**（奇偶物理口分网段） |
| OSP+OSA800 混合 | OSA800 固定 bond4 + `find_available_ip_vlan_range` | 同左 |

## 自动识别 2：设备场景（三分支）

对齐 `a3_cc_ywm_ip_address_generate` 主分支：

| `device_scenario` | 端口表条件 | 流程 |
|-------------------|------------|------|
| **osp_only** | 有 OSP9950/OSP9550，无 OSA800 | `allocate_osp_ips` |
| **osa800_only** | 仅有 OSA800 | 网段规划 + `allocate_osa800_ips`（全池 `parse_ip_vlan_pool`） |
| **mixed** | 两者都有 | 先 OSP 占网段 → `find_available_ip_vlan_range` → OSA800 bond4 |

`get_node_info` 规则：

- **OSP**：`起始端设备` 匹配 `OSP9950|OSP9550` → `节点名称 = 设备名 + NODE段`
- **OSA800**：`起始端设备` 含 `OSA800` → 保留 `起始端设备`、`起始端接口名称`、`目的端设备`

## Entrypoint

```bash
python scripts/offline_cc_ywm_pipeline.py [--connect PATH] [--resource PATH] [--out-dir output]
```

工作目录（cwd）下放置输入 Excel，或使用 `--connect` / `--resource` 指定（路径须在 cwd 内）。

## Dependencies

`pip install pandas openpyxl`（或 `pip install -r requirements.txt`）

## Parameters

| 参数 | 说明 |
|------|------|
| `--force-layer L2\|L3` | 可选，强制层级（默认按 `网关位置*` 自动识别） |
| `--connect PATH` | 存储业务面端口互联表（可省略；cwd 自动探测含 `007`/`端口连线`/`端口互联` 的文件） |
| `--resource PATH` | 项目信息收集表（可省略；自动探测含 `项目信息收集`/`资源` 的文件） |
| `--sheet-connect` | 互联表 sheet（默认 `auto`：优先「存储业务面端口互联」） |
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
3. **Leaf 需求统计**（`get_switch_info`）：存储类起始设备（`STORAGE_NAME_KEYWORD`）按 **起始端设备去重**，每 Leaf 的 **IP数量 = 设备数 × 8**
4. OSP 分配按 **节点名称**（含 NODE）在对应 Leaf 子网内顺序取可用 IP

`STORAGE_NAME_KEYWORD`：`OSP9950`, `OSP9550`, `OSP9920`, `OSA800`, `OD1600T`, `OD1301`

### 资源表（`--resource`）

- **优先** sheet：`网络资源需求表`
- 取 `网络平面 == 存储业务面` 的行
- **层级**：`网关位置*`（LEAF→L3，SPINE 等→L2）
- **规划**：`地址池*`、`最小规划掩码`、`网关地址*`（网段起始位/结束位）、`VLAN*`
- **L2 OSA800**：`组网场景`（含 bond → bond4，否则多IP）

## Outputs (Contract)

运行目录：`output/run_YYYYMMDD_HHMMSS/`

| 文件 | 对齐线上 | 说明 |
|------|----------|------|
| **`A3存储业务面网段规划.xlsx`** | `display_message("0-6", …网段规划…)` | L3=Leaf；L2=Spine + `Leaf网段` |
| **`A3存储业务面IP地址规划.xlsx`** | `0-7` OSP / `0-9` OSA800 | sheet `存储业务面IP地址规划`；混合时另含 `…(OSA800)` |
| **`A3存储业务面地址规划.xlsx`** | `get_file_path` / `upload_to_edm` | 与 IP 表同结构，sheet 名为「地址规划」 |
| `layer_detection.txt` / `run_meta.csv` | — | `layer`、`device_scenario`、`source_script` |

### OSP 地址规划列

`集群`、`硬盘池`、`设备名称`、`节点`、`存储业务面地址`、`存储业务面掩码`、`存储业务面网关`、`存储业务面VLAN`

- **集群**：设备名首段字母后数字（如 `CL1` → `1`）
- **硬盘池**：设备名中 `DPx` 的数字，默认 `1`

### OSA800 bond4 列

`设备名称`、`本端端口`、`IP1`、`VLAN1`、`网关1`、`IP2`、`VLAN2`、`网关2`、`掩码`、`组网模式=bond4（负载均衡）`

- `L0.*` → bond0，`R0.*` → bond1；每设备两 bond 各 2 IP（来自连续两个子网）
- **VLAN2 = VLAN1 + 1**

### OSA800 多IP 列（仅 L2 且组网场景不含 bond）

`设备名称`、`本端端口`、`IP`、`VLAN`、`网关`、`掩码`、`组网模式=多IP`

- 物理口编号 **偶数** → 子网1 + VLAN1；**奇数** → 子网2 + VLAN2

## Deterministic Workflow

### 共用

1. `detect_cc_ywm_layer` → L2 或 L3
2. `get_node_info` → OSP / OSA800 DataFrame；`classify_device_scenario`
3. `get_switch_to_nodes` → Leaf → 起始端设备列表（×8 需求）
4. `split_ip_range` + I2/I3 网段规划（替代 `invoke_llm_tools`）
5. `network_segment_check` 关键规则
6. 按场景调用 `allocate_osp_ips` / `allocate_osa800_ips`
7. 写出 Excel

### L2 专有

1. `resolve_leaf_spine_mapping`（空则尝试「计算管理面端口互联」等 fallback）
2. `transfer_gateways_to_spines` → 展示 Spine 网段
3. OSA800-only：`get_net_mode` 决定 bond4 vs 多IP

### 混合场景 OSA800

`find_available_ip_vlan_range`：在 OSP 已占用 IP 网段与 VLAN 后，取地址池内第一段连续空闲 IP + 首个未用 VLAN，再 **bond4** 分配（与两脚本 mixed 分支一致）。

## Implementation Map

| 模块 | 职责 |
|------|------|
| `scripts/cc_ywm_io.py` | 节点解析、Leaf 需求、资源表、L2/L3 识别、场景分类、Leaf-Spine |
| `scripts/cc_ywm_segment_rules.py` | I2/I2 网段（×8）、Spine 网关迁移 |
| `scripts/dw_manage_segment_rules.py` | 子网切分、网关、I3 一机一网段、可用 IP |
| `scripts/cc_ywm_ip_allocate.py` | OSP / OSA800 bond4 / 多IP / `find_available_ip_vlan_range` |
| `scripts/offline_cc_ywm_pipeline.py` | 主入口 |
| `scripts/validate_inputs.py` | 输入校验 |

## Prompt Parity Check (Optional, No LLM)

- `a3_i2_network_segment_tools_prompt.py`：`多个或所有交换机使用同一网段`、`顺次累加节点数量`
- `a3_i3_network_segment_tools_prompt.py`：`交接机不能共用网段`、`网段个数不足`、`vlan不足`

## Excel Error Literals (Do Not Change)

`网段个数不足`、`可用IP不足`、`vlan不足`

## Agent 执行指引

1. 进入本 skill 目录或将其作为 cwd
2. 确认两份 Excel 在 cwd 或传入 `--connect` / `--resource`
3. 运行 `python scripts/offline_cc_ywm_pipeline.py`（可加 `--skip-prompt-check`）
4. 将 `output/run_*/` 下三个 `A3存储业务面*.xlsx` 与 `layer_detection.txt` 交给用户
5. 若失败，先运行 `python scripts/validate_inputs.py` 定位缺列或场景为空

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
