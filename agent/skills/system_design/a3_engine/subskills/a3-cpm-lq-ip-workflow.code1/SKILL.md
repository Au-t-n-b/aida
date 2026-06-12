---
name: a3-cpm-lq-ip-workflow
description: Offline A3 超平面（灵衢 L1/L2）LoopBack 与 BGP AS 规划：007 + 项目信息收集表 → output/run_*/超平面网络规划.xlsx（确定性，无 LLM；与 a3_cpm_lq_ip_address.py 业务逻辑、a3_cpm_L1_ip_prompt.py / a3_cpm_L2_ip_prompt.py 提示词严格对齐）。
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_cpm_lq_ip_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成「A3 超平面（灵衢 L1/L2 平面）」LoopBack 地址 + BGP AS 分配结果，输入两份 Excel，输出一份结果 Excel。该流程为**确定性计算**（不依赖 LLM），严格遵循：

- `a3_cpm_L1_ip_prompt.py`：每台 L1 配 7 个连续 LoopBack；BGP AS 范围 `start-end` 按设备递增；`灵衢L1/L2平面 = 1`
- `a3_cpm_L2_ip_prompt.py`：每台 L2 配 2 个连续 LoopBack；所有 L2 共享同一个 BGP AS；`灵衢L1/L2平面 = 2`

## Entrypoint

`python scripts/offline_cpm_lq_ip_pipeline.py [--007 PATH] [--resource PATH] [--out-dir output] [--skip-prompt-check]`

## Dependencies

`pip install pandas openpyxl`

## Parameters

- `--007 PATH`：007 端口连线表（可省略；省略时在 cwd 下自动探测）
- `--resource PATH`：项目信息收集表/网络资源需求表（可省略；省略时在 cwd 下自动探测）
- `--out-dir output`：输出目录（默认 `output`，必须位于 cwd 树下）
- `--sheet007 SHEET`：007 的 sheet（默认 `"0"`；解析失败时自动扫描所有 sheet 兜底）
- `--sheet-resource NAME`：资源表 sheet 名（默认 `网络资源需求表`；传纯数字按 index 解析）
- `--net-plane-l1 NAME`：L1 网络平面行名（默认 `L1交换机LoopBack地址`）
- `--net-plane-l2 NAME`：L2 网络平面行名（默认 `L2交换机LoopBack地址`）
- `--skip-prompt-check`：跳过 prompt 文本一致性检查

## Path Rules (CWD Contract)

- 输入/输出路径必须位于当前工作目录（cwd）树下
- 省略路径时在 cwd 下自动探测：
  - 007：文件名包含 `007` 或 `端口连线` 或 `端口互联`
  - 资源：文件名包含 `项目信息收集` 或 `信息收集表` 或 `资源`

## Validation (Optional)

`python scripts/validate_inputs.py`（参数与主流程同源）。

## Inputs (Contract)

| 来源 | 要点 |
|------|------|
| 007（默认 sheet=`"0"`） | 找「设备命名」行；**首列 = L1 交换机**、**末列 = L2 交换机**；按设备名中 `-spN-`（不区分大小写）把 L1、L2 各自按超节点分组，分组内保留出现顺序 |
| 资源表（默认 sheet 名=`网络资源需求表`） | 取两行：`网络平面 == "L1交换机LoopBack地址"` 与 `网络平面 == "L2交换机LoopBack地址"`，每行需要 `地址池*` 与 `EBGP AS 规划` |

### 资源表字段格式

- L1 行：
  - `地址池*`：`A.B.C.D` 或 `A.B.C.D-E.F.G.H`
  - `EBGP AS 规划`：`start-end`（范围）
- L2 行：
  - `地址池*`：同上
  - `EBGP AS 规划`：单个整数

## Allocation Rules (Fixed)

### L1（i_per_device=7，AS 递增）

```text
base_ip = L1.地址池起始IP + 1
for i in [0, max_l1_per_sp):
    LoopBack起始IP = base_ip + i * 7
    LoopBack结束IP = base_ip + i * 7 + 6
    BGP AS号       = L1.AS.start + i      # 超过 L1.AS.end 抛 "ebgp as 数量不足"
    灵衢L1/L2平面  = 1
```

- `max_l1_per_sp` = 各 sp 中 L1 数量的最大值
- 校验：`max_l1_per_sp > 48` 抛 "单超节点最大节点数 X，超过最大规格 48"
- 模板复用：每个 sp 的 L1 设备按 sp 内 0..N-1 序号映射到模板的对应槽位（IP/AS 在 sp 间复用）

### L2（i_per_device=2，AS 共享）

```text
base_ip = L2.地址池起始IP + 1
shared_as = L2.AS（单个整数）
for i in [0, max_l2_per_sp):
    LoopBack起始IP = base_ip + i * 2
    LoopBack结束IP = base_ip + i * 2 + 1
    BGP AS号       = shared_as
    灵衢L1/L2平面  = 2
```

- `max_l2_per_sp` = 各 sp 中 L2 数量的最大值
- 模板复用同 L1

### IP 连续语义

与 `a3_cpm_lq_ip_address.py` 一致，使用 `IPv4Address` 整数加法逐 IP 递增；**跨 /24 边界时不跳过 `.0` 与 `.255`**。提示词中"IP 超过 254 进入新网段，跳过网络/广播"的描述与原 python 实现不一致，本 skill 选择**对齐 python 实现**（确定性计算口径）。

## Outputs (Contract)

- `output/run_YYYYMMDD_HHMMSS/超平面网络规划.xlsx`
- sheet：`超平面网络规划`

输出列（严格按 python 脚本对齐）：

| 列名 | 来源 |
|---|---|
| `设备名称` | 该 sp 的 L1 / L2 实际设备名 |
| `LoopBack起始IP` | 模板 `i * 7 + base` (L1) 或 `i * 2 + base` (L2) |
| `LoopBack结束IP` | 起始 + 6 (L1) 或 起始 + 1 (L2) |
| `BGP AS号` | L1：`AS.start + i`；L2：`shared_as` |
| `灵衢L1/L2平面` | L1=`1`，L2=`2` |
| `超节点ID` | 设备名 `-spN-` 提取数字 |
| `超节点规模` | 该 sp 内 L1 设备数 × 8 |
| `设备ESN` | 空字符串 |
| `交换机ID` | 该 sp 内 0 起递增（L1/L2 各自计数） |

## Implementation Notes (Rules)

- `scripts/cpm_lq_loopback_rules.py`
  - `parse_ip_pool_start` / `parse_ip_pool_end_optional`：地址池字段解析
  - `parse_as_range_l1` / `parse_as_single_l2`：AS 字段解析
  - `extract_sp_id_from_switch_name`：从设备名提取 sp 数字
  - `build_l1_template` / `build_l2_template`：构建按"最大 sp 设备数"长度的模板
  - `map_template_to_sp_devices`：把模板按序号映射到 sp 实际设备
- `scripts/offline_cpm_lq_ip_pipeline.py`：主流程（读取 → 模板 → 分配 → 写 Excel）
- `scripts/validate_inputs.py`：输入校验（可选）
- `scripts/cpm_lq_segment_rules.py`：**已废弃**（上一版 i2/i3 路线产物，import 时直接抛错；正式部署时请删除该文件）

## Prompt Parity Check (Optional, No LLM)

若 cwd 下存在以下文件，则主流程会校验其三引号字符串中是否包含关键短语，确保 prompt 文本未漂移；可用 `--skip-prompt-check` 跳过。

- `a3_cpm_L1_ip_prompt.py`：必须包含 `每一个设备，要配7个loopback地址`、`起始地址为从网络资源信息表的地址池ip+1`、`BGP AS号根据设备数量`、`灵衢L1/L2平面的字段为1`
- `a3_cpm_L2_ip_prompt.py`：必须包含 `每一个设备，要配2个loopback地址`、`所有交换机共用一个AS号`、`灵衢L1/L2平面的字段为2`

> 说明：另两个提示词 `a3_i2_network_segment_tools_prompt.py` / `a3_i3_network_segment_tools_prompt.py` 描述的是"网段/网关/VLAN"规划业务（leaf/spine），与本 skill 的 LoopBack/AS 业务不属同一类，**不参与 parity check**。

## Errors (Do Not Change)

- `单超节点最大节点数 X（spY），超过最大规格 48`
- `ebgp as 数量不足无法分配`
- `resource: L1 行（网络平面=...）的 地址池* 为空 / EBGP AS 规划 为空`
- `resource: L2 行（网络平面=...）的 地址池* 为空 / EBGP AS 规划 为空`
- `007 sheet: no -SP<n>- pattern found in either first or last column`

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
