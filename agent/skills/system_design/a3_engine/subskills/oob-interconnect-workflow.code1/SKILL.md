---
name: oob-interconnect-workflow
description: 多网络平面互联规划离线工具。输入《建模仿真输出文档007-端口连线表.xlsx》+《项目信息收集表.xlsx》，按用户指定平面输出 L2（VLAN+ETH-Trunk）或 L3（/30 互连地址）规划表。平面配置可由 JSON/字典覆盖。
disable-model-invocation: true
metadata:
  package: oob_interconnect/
  cli: scripts/run_oob_interconnect.py
  config_example: plane_config.example.json
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## 概述

- **输入**：《建模仿真输出文档007-端口连线表.xlsx》、《项目信息收集表.xlsx》、用户指定的互联规划名称、平面配置（可选 JSON）。
- **输出**：默认文件名 `A3网络互联规划.xlsx`；列结构固定，L2/L3 共享列名。
- **执行**：单平面（`--plan` / `--sheet`）或多平面（`--sheets a,b` / `--all-planes`）；多平面在内存合并后一次写入。
- **输出策略**：默认整表覆盖；需要贴近项目脚本时加 `--merge-existing`，会读取旧 `--out`、删除本次网络平面后追加新结果。

## 适用范围

当前默认支持多个 **互联规划平面**。用户输入以下任一规划名称时，先查默认平面配置，得到对应的 007 sheet、设备筛选关键字和资源表「网络平面」，再生成对应输出：

| 用户输入规划名称 | 007 sheet | 资源表网络平面 | 本端关键字 |
|------|------|------|------|
| `计算带外管理互联规划` | `计算带外管理面端口互联` | `计算带外管理面` | `DWGL-LEAF` |
| `存储带外管理互联规划` | `存储带外管理面端口互联` | `存储带外管理面` | `DWGL-LEAF` |
| `网络带外管理互联规划` | `网络带外管理面端口互联` | `网络带外管理面` | `DWGL-LEAF` |
| `灵衢带外管理互联规划` | `灵衢带外管理面端口互联` | `灵衢带外管理面` | `DWGL-LEAF` |
| `计算管理面互联规划` | `计算管理面端口互联` | `计算管理面` | `GLM-LEAF` |
| `计算管存面互联规划` | `计算管存面端口互联` | `计算管存面` | `GCM-LEAF` |
| `计算业务面互联规划` | `计算业务面端口互联` | `计算业务面` | `YWM-LEAF` |
| `计算样本面互联规划` | `存储面端口互联 \| 样本面端口互联` | `计算样本面` | `ZSYBM-LEAF` |
| `计算参数面互联规划` | `参数面端口互联` | `计算参数面` | `LEAF` |
| `存储管理面互联规划` | `存储管理面端口互联` | `存储管理面` | `CCGLM-LEAF` |
| `存储业务面互联规划` | `存储业务面端口互联` | `存储业务面` | `CCYWM-LEAF` |
| `存储样本面互联规划` | `样本面端口互联 \| 数据面端口互联` | `存储样本面` | `CCYBM-LEAF` |
| `SPINE上行互联规划` | `超平面端口互联` | `网络互联地址` | `SP1-JHB`，对端关键字 `SP1-LQS` |
| `SPINE上行端口互联` | `SPINE上行端口互联` | `防火墙互联地址` | `FW-` |

同一套算法也可通过「平面配置」扩展到其他互联条目，只需给出对应 `sheet_name` / `keyword` / `network_type`：

- **L2**：填 VLAN + ETH-Trunk + `端口类型=trunk` + 标签 `INTER_LINK`。
- **L3**：按资源表「互连地址段」顺序分配 `/30` 点对点地址 + 标签 `INTER_LINK`。

**不适用**：接入规划（服务器或接入交换机的接入端口规划，单端口而非 LEAF↔SPINE 互联）属另一套链路，不在本工具范围。

## 平面配置

```json
{ "<plan_name>": { "sheet_name": "...", "keyword": "...", "network_type": "...", "peer_keyword": "..." } }
```

- `plan_name`：用户输入的互联规划名称，也是 CLI `--plan` 的值。
- `sheet_name`：端口连线表中的页签；未填时兼容旧格式，使用 `plan_name` 作为 sheet 名。
- `keyword`：在该页签 leaf 列上做包含匹配。
- `peer_keyword`：在对端列上做包含匹配；缺省为 `spine`，`SPINE上行互联规划` 使用 `SP1-LQS`。
- `network_type`：资源表「网络平面」列取值；同时写入输出「网络平面」列。

可通过 CLI `--plane-config FILE` 或 Python `plane_config={...}` 覆盖默认。

## 输入契约

### 建模仿真输出文档007-端口连线表

- 默认文件名：`建模仿真输出文档007-端口连线表.xlsx`。
- 默认按用户输入规划名称选择 sheet，例如 `计算带外管理互联规划` 对应 `计算带外管理面端口互联`。
- 找首个含「设备命名」的单元格行作为表头。
- L2 取第 1/2/3 列与倒数 4/3/2/1 列；L3 取第 1/2 列与倒数 3/2/1 列。
- 筛选：本端列匹配 `keyword` 且对端列匹配 `peer_keyword`（缺省 `spine`），去重；为空时报错。
- 同表识别 MLAG 对（设备列含 `leaf|spine` 与「接入交换机」列两端同型）。

### 项目信息收集表

- 默认文件名：`项目信息收集表.xlsx`。
- 优先读取 sheet `资源表`；若不存在或不含 `网络平面` 列，则自动扫描首个包含 `网络平面` 列的 sheet。
- 列 `网络平面`、`VLAN`（或以 VLAN 开头）、`互连地址段` / `内部网络设备互连地址段`（格式 `起始IP-结束IP`；没有这些列时自动使用资源行中首个 IPv4 起止地址段，如 `地址池*`）、`网关位置`（或以 `网关位置` 开头，值为 `LEAF`/`SPINE`）。
- 行定位：`网络平面 == network_type`。

## 输出契约

输出工作簿 sheet 名固定为 `网络互联规划`。

固定列顺序：`网络平面, 本端设备, 本端接口, 本端接口IP地址, 本端接口掩码, 本端ETH-TRUNK, 本端VLAN, 对端设备, 对端接口, 对端接口IP地址, 对端接口掩码, 对端ETH-TRUNK, 对端VLAN, PVID, 端口类型, 标签`。

| 字段 | L2 | L3 |
|------|----|----|
| 端口类型 | `trunk` | 空 |
| 本/对端 VLAN | 资源表 VLAN | 空 |
| 本/对端 ETH-TRUNK | 分配（MLAG 对同号） | 空 |
| 本/对端 IP / 掩码 | 空 | `/30` 顺序推进；配置 `网关位置=LEAF/SPINE` 时只填对应侧，未配置时本端 +1、对端 +2 |
| PVID | 空 | 空 |
| 标签 | `INTER_LINK` | `INTER_LINK` |

## 规则与校验

- **L2 Trunk**：默认从 2 起递增；MLAG 配对两端共用；可读取「接入规划」和「历史互联」xlsx 把已占用编号纳入避让。是否与旧输出合并由 `--merge-existing` 单独控制。
- **L3 /30**：起始 IP 向上对齐到 4 的倍数；每行占用 4 个地址；总连线数超出可容纳的 /30 子网数 → 抛错不生成。

## 调用方式

CLI（详见 `README.md`）：

```bash
python scripts/run_oob_interconnect.py --layer {l2|l3} \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --plan 计算带外管理互联规划 \
  --out runs/A3网络互联规划.xlsx \
  [ --plane-config FILE ] [ --access-plan FILE ] [ --trunk-history FILE ] [ --merge-existing ]
```

Python：

```python
from oob_interconnect import run_l2, run_l3, run_l2_multi, run_l3_multi
```

## 故障排查

| 现象 | 处理 |
|------|------|
| 「未找到 '设备命名'」 | 选择正确 sheet；表头单元格须含字面量「设备命名」 |
| 「未找到包含 'X' 与 'spine' 的物理连线」 | 检查 `keyword` 与 spine 列命名 |
| 「资源表中未找到 X」/「VLAN 为空」 | 确认 `网络平面` 行存在与 VLAN 列名 |
| L3「仅可容纳 N 个 /30」 | 扩大 `互连地址段` 范围或减少连线 |
| L2 Trunk 编号冲突 | 通过 `--access-plan`/`--trunk-history` 提供历史占用 |

## 关键字面量

- 表头探测：`设备命名`
- 互联标签：`INTER_LINK`
- 端口类型（L2）：`trunk`
- L3 掩码：`30`

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
