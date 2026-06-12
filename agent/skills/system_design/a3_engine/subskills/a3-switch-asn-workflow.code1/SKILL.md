---
name: a3-switch-asn-workflow
description: >-
  离线网络设备 ASN 规划：统一指令、按 LOOPBACK_CONFIG 与资源表自动识别待规划平面，
  确定性分配 BGP AS 并汇总导出 Excel（无 LLM）。
  对齐 a3_switch_loopback_ip_address.py 与 a3_switch_asn.py。
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_switch_asn_pipeline.py
  source_scripts:
    - src/manage_agent/sub_agents/LLD_IP/a3_switch_loopback_ip_address.py
    - src/manage_agent/sub_agents/LLD_IP/a3_switch_asn.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线完成「**网络设备 ASN 规划**」：

1. **分配**：按各网络平面从端口表解析 Leaf/Spine，读取资源表 `EBGP AS规划` 区间，写入内存网关表（等价于线上 `t_gateway_info`）。
2. **汇总**：导出 `网络平面 | 设备名称 | ASN`（等价于线上 `a3_switch_asn.a3_switch_loopback_generate`）。

用户只需一条指令（**不区分 L2/L3**；线上 `网络设备ASN规划_L2` 与 `_L3` 均调用同一入口，本 skill 与之保持一致）。

## 统一指令（用户侧）

- **网络设备ASN规划**
- 或提供端口互联表 + 项目信息收集表，要求生成交换机 ASN 规划

**不要**要求用户选择 L2/L3；本能力在源脚本中亦无层级分支。

## 自动识别：待规划平面（与线上一致的数据契约）

对齐 `LOOPBACK_CONFIG` + `WEB_NETWORK_TYPE_CONFIG`（`config.py`），在**单份 007 端口文件**中扫描 sheet：

| 条件 | 说明 |
|------|------|
| 端口表存在 LOOPBACK_CONFIG 键对应 sheet（名称完全匹配或互相包含） | 如 `存储管理面端口互联` |
| sheet 内可解析 Leaf（末列含 `keyword`）或 Spine（含 `spine`） | 同 `get_leaf_spine_data` |
| 资源表 `网络平面 == network_type` 行存在 | 同 `get_net_resource_info` |
| 该行 `EBGP AS规划` **含 `-`**（区间） | 无 `-` 则跳过（与分配脚本 `if '-' in as_range_str` 一致） |

按 `LOOPBACK_CONFIG` **固定顺序**依次分配，后序平面读取内存库中**其它平面**已占用 AS，避免冲突（对齐 `filtered_records = [r for r in gateway_info if r[3] != web_network_type_name]`）。

识别结果写入 `output/run_*/plane_detection.txt` 与 `run_meta.csv`。

### 与 L2/L3 的关系

- `main_flow` 对 `网络设备ASN规划` **不**做 `gateway == 'LEAF' → _L3` 后缀变换。
- 本 skill **不**读取 `网关位置*`，**不**区分 L2/L3。

## BGP AS 分配规则（严格对齐 `a3_switch_loopback_ip_generate`）

| 角色 | 规则 |
|------|------|
| **Leaf** | `as_number = as_start + idx`；若与库中其它平面已用 AS 冲突则 `as_number++` 且 `as_start++` |
| **Spine** | 默认 `max(leaf_as) + 1`，冲突则继续递增；若库中该 Spine 已有 AS（`SPINE` in name）则 **复用** `spine_as_dict` |
| **资源** | `EBGP AS规划` 形如 `65001-65099`，取 `split('-')` 后 `as_start` |
| **接口** | 明细含 `Loopback接口名称 = loopback0`（线上供 `_update_gateway_info` 合并；离线仅 ASN 时网关字段写 `NA`） |

> 线上 ASN 写入库发生在各「地址规划」流程的 `_update_gateway_info`；单独点「网络设备ASN规划」时仅执行 `a3_switch_asn` 汇总。本 skill **合并两步**，便于离线一次性出表。

## ASN 汇总规则（严格对齐 `a3_switch_asn`）

1. 读取内存网关全表
2. 过滤 `EBGP_AS != 'NA'`（tuple 下标 `6`）
3. 输出列：`网络平面`（scope）、`设备名称`、`ASN`
4. 写出 `A3交换机ASN规划.xlsx`，sheet `交换机ASN规划`

## Entrypoint

```bash
python scripts/offline_switch_asn_pipeline.py [--connect PATH] [--resource PATH] [--out-dir output]
```

工作目录（cwd）下放置输入 Excel，或使用参数指定（路径须在 cwd 内，除非 `--no-cwd-restrict`）。

## Dependencies

`pip install pandas openpyxl`（或 `pip install -r requirements.txt`）

## Parameters

| 参数 | 说明 |
|------|------|
| `--connect PATH` | 端口互联表（可省略；自动探测含 `007`/`端口连线`/`端口互联`） |
| `--resource PATH` | 项目信息收集表（可省略；自动探测含 `项目信息收集`/`资源`） |
| `--only-plane KEY` | 仅处理单个 LOOPBACK_CONFIG 键，如 `存储管理面端口互联` |
| `--gateway-snapshot PATH` | 导入已有网关 CSV（列 `scope,name,ebgp_as,...`）后再分配或仅导出 |
| `--export-only` | 仅根据 `--gateway-snapshot` 导出 ASN（不跑分配） |
| `--as-range 平面=65001-65099` | 资源表 `EBGP AS规划` 为空时临时覆盖（可多次指定） |
| `--deliverable-dir PATH` | 额外复制 `A3交换机ASN规划.xlsx` 到指定目录 |
| `--sheet-res-index` | 资源表 sheet index（默认 `0`，优先 `网络资源需求表`） |
| `--out-dir output` | 输出根目录 |

## Path Rules (CWD Contract)

- 输入/输出路径须在 **当前工作目录（cwd）** 树下（默认）
- 自动探测仅在 cwd 内 `rglob` Excel

## Validation (Optional)

```bash
python scripts/validate_inputs.py [--connect PATH] [--resource PATH]
```

## Inputs (Contract)

### 端口互联表（`--connect`）

对齐 `get_leaf_spine_data`：

1. 每个平面使用独立 sheet（见 `LOOPBACK_CONFIG` 键名）
2. 定位含 **「设备命名」** 的表头行
3. 末列重命名为 **交换机**：Leaf 行含 `keyword`（如 `CCGLM-LEAF`），Spine 行含 `spine`

### 资源表（`--resource`）

- **优先** sheet：`网络资源需求表`
- 每个平面取 `网络平面 == network_type` 行
- **必需**：`EBGP AS规划` 为 `起始-结束` 区间（含 `-`）

## Outputs (Contract)

运行目录：`output/run_YYYYMMDD_HHMMSS/`

| 文件 | 对齐线上 | 说明 |
|------|----------|------|
| **`A3交换机ASN规划.xlsx`** | `upload_to_edm` sheet `交换机ASN规划` | 列：网络平面、设备名称、ASN；同时复制到 cwd 或 `--deliverable-dir` |
| `交换机ASN分配明细.xlsx` | `a3_switch_loopback_ip_generate` 返回值 | 每网络平面一 sheet：`设备名称`、`Loopback接口名称`、`BGP AS` |
| `gateway_snapshot.csv` | `t_gateway_info` 离线等价 | 供其它 skill 链接 |
| `asn_preview.md` | `display_message` + `df_to_markdown_limited` | Markdown 预览 |
| `plane_detection.txt` / `run_meta.csv` | — | 自动平面识别记录 |

## Deterministic Workflow

1. `detect_plane_plans` → 待处理平面列表
2. 对每个平面：`allocate_bgp_as_for_plane` → 更新 `InMemoryGatewayStore`
3. `export_asn_dataframe` → `A3交换机ASN规划.xlsx`

## Implementation Map

| 模块 | 职责 |
|------|------|
| `scripts/switch_asn_io.py` | LOOPBACK 配置、端口/资源读取、平面识别、内存网关表 |
| `scripts/switch_asn_allocate.py` | BGP AS 分配（对齐 `a3_switch_loopback_ip_generate`） |
| `scripts/switch_asn_export.py` | ASN 汇总（对齐 `a3_switch_asn`） |
| `scripts/offline_switch_asn_pipeline.py` | 主入口 |
| `scripts/validate_inputs.py` | 输入校验 |

## 线上不包含（离线替代说明）

| 线上 | 离线 |
|------|------|
| `gateway_info_db` MySQL | `InMemoryGatewayStore` + 可选 `gateway_snapshot.csv` |
| `display_message` / `upload_to_edm` / `display_file` | 写 `asn_preview.md` + 本地 xlsx |
| `file_path` / `net_resource_path` 入参（`a3_switch_asn` 未使用） | 自动探测 + `--connect`/`--resource` |

## Agent 执行指引

1. 进入本 skill 目录作为 cwd
2. 确认 007 端口表与项目信息收集表在 cwd 或传入路径
3. `python scripts/offline_switch_asn_pipeline.py`
4. 将 `output/run_*/A3交换机ASN规划.xlsx` 与 `plane_detection.txt` 交给用户
5. 失败时先运行 `python scripts/validate_inputs.py`

## 常见问题：EBGP AS规划 为空

模板「项目信息收集表」中 **计算/存储各平面** 的 `EBGP AS规划` 常为空（仅灵衢 L1/L2 行有值），与线上一致会导致无法分配。

**处理方式（二选一）：**

1. 在资源表 `网络资源需求表` 为各 `网络平面` 填写区间，如 `65001-65099`
2. 使用 CLI 覆盖（不改 Excel）：

```bash
python scripts/offline_switch_asn_pipeline.py --only-plane "存储管理面端口互联" --as-range "存储管理面=65001-65099"
```

失败时会在 `output/run_*/missing_ebgp_as_help.txt` 写出完整说明。

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
