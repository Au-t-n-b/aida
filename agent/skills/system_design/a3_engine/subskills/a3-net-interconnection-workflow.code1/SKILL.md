---
name: a3-net-interconnection-workflow
description: >-
  离线 A3 LEAF-SPINE 网络互连规划：统一互联规划指令、按资源表网关位置*自动识别 L2/L3，
  生成 A3网络互连规划.xlsx（确定性，无 LLM）。
  对齐 a3_l2_net_interconnection.py 与 a3_ni_ip_address.py。
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_ni_pipeline.py
  source_scripts:
    - src/manage_agent/sub_agents/LLD_IP/a3_l2_net_interconnection.py
    - src/manage_agent/sub_agents/LLD_IP/a3_ni_ip_address.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成 **LEAF ↔ SPINE 网络互连规划**（`A3网络互连规划.xlsx` / Sheet `网络互连规划`）。

用户只需一条 **互联规划三级指令**（**不带 `_L2` / `_L3` 后缀**），skill 根据项目信息表 **`网关位置*`** 自动选择二层或三层逻辑，**不调用 LLM**。

## 统一指令（用户侧）

示例（任选其一，须与 `INTERCONNECTION_INTENTS` 一致）：

- **计算业务面互联规划**
- **计算管理面互联规划**
- **存储业务面互联规划**
- **计算参数面互联规划**
- …（完整列表见 `--list-intents`）

**不要**要求用户选择 L2 或 L3。

## 自动识别：L2 / L3（与线上一致）

对齐 `main_flow.execute_three_instruction` / `execute_instruction` / `execute_secondary_instruction`：

```python
instruction += '_L3' if gateway == 'LEAF' else '_L2'
```

其中 `gateway = get_net_to_gateway_resource_info(...)[network_plane]`，`network_plane` 来自 `LEAF_SPINE_CONFIG[sheet]['network_type']`。

| 资源表 `网关位置*`（该网络平面行） | 层级 | 执行脚本 |
|-----------------------------------|------|----------|
| **LEAF** | **L3** | `a3_ni_ip_address.a3_ni_ip_generate` |
| **SPINE** 或其它非 LEAF | **L2** | `a3_l2_net_interconnection.a3_net_interconnection_generate` |

识别结果：`output/run_*/layer_detection.txt`、`run_meta.csv`（`layer`、`gateway_position`、`source_script`）。

### L2 与 L3 行为差异

| 能力点 | L2（二层互联） | L3（三层互联） |
|--------|----------------|----------------|
| 资源字段 | `VLAN*`（`utils.get_net_ni_resource_info`） | `内部网络设备互连地址段`（`a3_ni_ip_address.get_net_ni_resource_info`） |
| IP 分配 | 无（IP 列空） | 每条链路一个 **/30**：LEAF `.+1`，SPINE `.+2`，掩码 30 |
| 端口类型 | `trunk` | 空 |
| VLAN | 本端/对端填资源表 VLAN | 空 |
| ETH-TRUNK | MLAG 配对 + `assign_port_value`（从 2 递增） | 空 |
| 标签 | `INTER_LINK` | `INTER_LINK` |
| 容量校验 | 无 | `validate_network_range`（/30 子网数 ≥ 链路数） |
| MLAG 表 | `_get_all_switch_mlag_data` | 不需要 |

> 文件头注释「低速 127 / 高速 128」在当前 `allocate_connection` 实现中**未使用**；实际 trunk 从 **2** 起递增（与 `utils.generate_port` 一致）。

## 线上指令路由（谁在用这两个模块）

### 1. 三级指令 → L2/L3 后缀（`main_flow.py`）

用户说三级指令（无后缀）时，系统在以下入口 **追加 `_L2` 或 `_L3`** 后查表 `instruction_to_function`：

| 入口函数 | 触发条件 |
|----------|----------|
| `execute_three_instruction` | `instruction in three_level_instruction_set` |
| `execute_instruction` | `third_intent_list[0] in three_level_instruction_set` |
| `execute_secondary_instruction` | 二级「网络互联规划」等，按 sheet 展开多个三级指令 |

核心代码（`main_flow.py` 约 1143–1148、1209–1216、1105–1109 行）：

```text
net_for_lld = INSTRUCTION_NETWORK_TYPE_CONFIG[instruction]
net_name = WEB_NETWORK_TYPE_CONFIG[net_for_lld]   # 网络平面中文名
gateway = get_net_to_gateway_resource_info(...)[net_name]
instruction += '_L3' if gateway == 'LEAF' else '_L2'
```

### 2. 后缀指令 → 脚本（`instruction_to_function`）

以下 **`_L2`** 调用 `a3_l2_net_interconnection.a3_net_interconnection_generate`，**`_L3`** 调用 `a3_ni_ip_address.a3_ni_ip_generate`（带外「互联」走 `a3_network_access_plan`，**不在本 skill**）：

| 三级指令（无后缀） | 端口连线表 Sheet（`INSTRUCTION_NETWORK_TYPE_CONFIG`） |
|-------------------|------------------------------------------------------|
| 计算业务面互联规划 | 计算业务面端口互联 |
| 计算管理面互联规划 | 计算管理面端口互联 |
| 计算管存面互联规划 | 计算管存面端口互联 |
| 计算样本面互联规划 | 存储面端口互联 \| 样本面端口互联 |
| 计算参数面互联规划 | 参数面端口互联 |
| 存储管理面互联规划 | 存储管理面端口互联 |
| 存储业务面互联规划 | 存储业务面端口互联 |
| 存储样本面互联规划 | 样本面端口互联 \| 数据面端口互联 |
| 计算/存储/网络/灵衢 **带外管理互联规划**（及「面」别名） | 对应 `*带外管理面端口互联` |

**未走本 skill 的相近指令：**

- `带外管理面互联规划` → `a3_network_access_plan`（非 LEAF-SPINE /30）
- `SPINE上行互联规划` → sheet 仍为占位 `todo待做`
- `防火墙互联规划` → 临时绑定存储管理面 sheet（待产品修正）
- `存储样本面地址规划_L2` → 误绑 `a3_ni_ip_generate`（地址规划，非互联）

### 3. 二级「网络互联规划」→ 自动展开三级指令

`config.WLHL_SHEET_NAME_TO_INTENT_CONFIG` + `SECOND_TO_THIRD_INSTRUCTION_CONFIG["网络互联规划"]`：

端口表中存在的 sheet → 对应互联规划三级指令 → 再按网关位置追加 `_L2`/`_L3`。

| 端口表 Sheet | 可识别的三级指令 |
|--------------|------------------|
| 计算带外管理面端口互联 | 计算带外管理互联规划 |
| 存储带外管理面端口互联 | 存储带外管理互联规划 |
| 网络带外管理面端口互联 | 网络带外管理互联规划 |
| 灵衢带外管理面端口互联 | 灵衢带外管理互联规划 |
| 计算业务面端口互联 | 计算业务面互联规划 |
| 计算管理面端口互联 | 计算管理面互联规划 |
| 存储面端口互联 / 样本面端口互联 | 计算样本面互联规划 |
| 参数面端口互联 | 计算参数面互联规划 |
| 计算管存面端口互联 | 计算管存面互联规划 |
| 存储业务面端口互联 | 存储业务面互联规划 |
| 数据面端口互联 | 存储样本面互联规划 |
| 存储管理面端口互联 | 存储管理面互联规划 |

意图识别 Prompt：`prompt/wlhl_scene_recognition_prompt.py`（二级「网络互联规划」）。

### 4. LEAF-SPINE 筛选（两脚本共用）

`config.LEAF_SPINE_CONFIG`：`sheet_name` → `keyword` + `network_type`。

连线表解析：找含 **「设备命名」** 表头行 → 筛 `leaf交换机` 含 keyword 且 `spine交换机` 含 `spine` → 去重。

## Entrypoint

```bash
python scripts/offline_ni_pipeline.py --intent "计算业务面互联规划" [--connect PATH] [--resource PATH] [--out-dir output]
```

列出支持的 `--intent`：

```bash
python scripts/offline_ni_pipeline.py --list-intents
```

## Dependencies

`pip install pandas openpyxl`（或 `pip install -r requirements.txt`）

## Parameters

| 参数 | 说明 |
|------|------|
| `--intent` | **必填**。三级互联规划指令（无 `_L2`/`_L3`） |
| `--force-layer L2\|L3` | 强制层级（默认按 `网关位置*` 自动） |
| `--connect` | 007 端口连线表（cwd 可自动探测） |
| `--resource` | 项目信息收集表 |
| `--sheet-connect` | 默认 `auto`（按 intent 映射 sheet 名匹配） |
| `--prior-connect` | 已有互连规划 xlsx（平面覆盖 + L2 trunk 占用） |
| `--prior-access` | 已有接入规划 xlsx（L2 trunk 占用，对齐 `assigned_trunk_list`） |
| `--out-dir output` | 输出根目录 |

## Path Rules (CWD Contract)

输入/输出路径须在 **cwd** 树下；自动探测仅 `rglob` cwd 内 Excel。

## Validation

```bash
python scripts/validate_inputs.py --intent "计算业务面互联规划" --connect PATH --resource PATH
```

## Inputs (Contract)

### 端口互联表

- 表头行含 **「设备命名」**
- L2 解析多 **带宽** 列；L3 不依赖带宽列
- 筛 **LEAF（keyword）↔ SPINE** 互联行

### 资源表（`网络资源需求表`）

- `网络平面` = 该平面的 `network_type`（如 `计算业务面`）
- L2：**`VLAN*`** 必填
- L3：**`内部网络设备互连地址段`** 格式 `起始IP-结束IP`
- 层级：**`网关位置*`**（`LEAF` → L3，否则 L2）

## Outputs

`output/run_YYYYMMDD_HHMMSS/`：

| 文件 | 说明 |
|------|------|
| **`A3网络互连规划.xlsx`** | Sheet `网络互连规划`；同平面覆盖写入 |
| `layer_detection.txt` | layer / gateway / rule / source_script |
| `run_meta.csv` | 结构化元数据 |

输出列（两层级一致）：`网络平面`、`本端设备`、`本端接口`、`本端接口IP地址`、`本端接口掩码`、`本端ETH-TRUNK`、`本端VLAN`、`对端设备`、`对端接口`、`对端接口IP地址`、`对端接口掩码`、`对端ETH-TRUNK`、`对端VLAN`、`PVID`、`端口类型`、`标签`。

## Deterministic Workflow

1. `resolve_intent` → sheet_key、`network_type`
2. `detect_ni_layer` → L2 或 L3
3. `get_switch_data_l2` / `get_switch_data_l3`
4. L3：`read_interconnect_pool` → `validate_network_range` → `allocate_ips_l3`
5. L2：`read_vlan` → `build_mlag` → `allocate_connection_l2`
6. 合并历史平面 → 写 Excel

> 离线 skill **不包含**：`display_message`、`upload_to_edm`、`assigned_trunk_list` 读 EDM（可用 `--prior-*` 替代）。

## Implementation Map

| 模块 | 职责 |
|------|------|
| `scripts/ni_io.py` | intent/sheet 映射、层级识别、连线表/资源表读取 |
| `scripts/ni_l2_allocate.py` | L2 trunk + VLAN |
| `scripts/ni_l3_allocate.py` | L3 /30 分配与网段校验 |
| `scripts/offline_ni_pipeline.py` | 主入口 |
| `scripts/validate_inputs.py` | 输入校验 |

## Agent 执行指引

1. `cd skill_staging/a3-net-interconnection-workflow.code1`
2. 放置 007 连线表 + 项目信息收集表于 cwd
3. `python scripts/offline_ni_pipeline.py --intent "<互联规划指令>"`
4. 交付 `output/run_*/A3网络互连规划.xlsx` 与 `layer_detection.txt`

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
