---
name: switch-mlag-planning-workflow
description: 交换机 MLAG 规划离线工具。输入《建模仿真输出文档007-端口连线表.xlsx》+《项目信息收集表.xlsx》，对齐 a3_switch_mlag.py 的 leaf/spine 同型 MLAG 连线筛选、DAD/PEER-LINK 分配、MLAG 地址填充、带外 LEAF 过滤和 Excel 合并区域输出逻辑；项目 DB/EDM/展示链路由本地文件读写替代。
disable-model-invocation: true
metadata:
  package: switch_mlag_planning/
  cli: scripts/run_switch_mlag.py
  source_reference: ../a3_switch_mlag.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## 概述

- **输入**：《建模仿真输出文档007-端口连线表.xlsx》、《项目信息收集表.xlsx》。
- **输出**：传入 `user_id/project_id` 时默认 `{user_id}_{project_id}_A3交换机MLAG规划.xlsx`，sheet 固定为 `交换机MLAG规划`。
- **中间输出**：传入 `user_id` 时默认 `{user_id}_交换机MLAG规划.xlsx`，保存未合并区域的数据表。
- **执行方式**：纯本地 Excel 读写，不依赖项目 DB、EDM、LLM、日志、上传服务或 dialogue 展示。

## 适用范围

当前工具对齐项目 `a3_switch_mlag.a3_switch_connect` 的核心生成逻辑。`main_flow.py` 中“交换机MLAG规划”只负责路由到该函数，MLAG 的读取、分配、保存逻辑集中在 `a3_switch_mlag.py`。离线工具默认按项目入口扫描 007 工作簿中与 `WEB_NETWORK_TYPE_CONFIG` 完全同名的 sheet，并跳过 `超平面`。

| 007 sheet | 输出网络平面 |
|------|------|
| `存储面端口互联 \| 样本面端口互联` | `计算样本面` |
| `计算管理面端口互联` | `计算管理面` |
| `计算业务面端口互联` | `计算业务面` |
| `计算管存面端口互联` | `计算管存面` |
| `参数面端口互联` | `计算参数面` |
| `样本面端口互联 \| 数据面端口互联` | `存储样本面` |
| `存储业务面端口互联` | `存储业务面` |
| `存储管理面端口互联` | `存储管理面` |
| `计算带外管理面端口互联` | `计算带外管理面` |
| `网络带外管理面端口互联` | `网络带外管理面` |
| `灵衢带外管理面端口互联` | `灵衢带外管理面` |
| `存储带外管理面端口互联` | `存储带外管理面` |
| `带外管理面端口互联` | `带外管理面` |
| `网络业务地址规划` | `其它` |

## 输入契约

### 建模仿真输出文档007-端口连线表

- 找首个含「设备命名」的单元格行作为表头。
- 从表头之后读取数据，按位置映射列：第 1/2/3 列为本端交换机、本端端口、本端接口带宽；倒数第 4/3/2/1 列为对端带宽、对端接口类型、对端端口、对端交换机。
- 只保留本端交换机包含 `leaf|spine`，且两端同为 leaf 或同为 spine 的连线。
- 带外网络平面按项目逻辑过滤掉本端设备包含 `LEAF` 的记录。

### 项目信息收集表

- 优先读取 sheet `网络资源需求表`；若不存在或不含 `网络平面` 列，则自动扫描 `资源表` 和其他 sheet。
- 行定位：`网络平面 == MLAG`。
- 读取 `地址池*` / `地址池` 与 `最小规划掩码` / `掩码`。
- 在地址池内寻找第一对连续 IP，要求两者在同一子网内且都不是 network/broadcast 地址；找不到时按项目逻辑输出空 IP。

## 输出契约

输出工作簿 sheet 名固定为 `交换机MLAG规划`。

固定列顺序：

`网络平面, 本端设备, 本端接口, 本端接口IP地址, 本端接口掩码, 本端ETH-TRUNK, 本端VLAN, 对端设备, 对端接口, 对端接口IP地址, 对端接口掩码, 对端ETH-TRUNK, 对端VLAN, PVID, 端口类型, 标签`

## 分配规则

- **两种端口带宽**：数值更高的带宽作为 `PEER-LINK`，`ETH-TRUNK=1`；另一种作为 `DAD`，`ETH-TRUNK=0`。
- **一种端口带宽**：按本端交换机统计端口数量。端口数为奇数时第 1 条为 `DAD`；端口数为偶数时前 2 条为 `DAD`；其余为 `PEER-LINK`。
- **DAD 地址**：所有 `DAD` 行填充 MLAG 地址池找到的同一对本端/对端 IP 和掩码。
- **固定空值**：`本端VLAN`、`对端VLAN`、`PVID`、`端口类型` 输出 `NA`。
- **输出流程**：逐 sheet 更新未合并临时文件，替换同网络平面历史行后追加本次结果；全部 sheet 处理完成后，再读取临时文件生成最终合并版。
- **Excel 合并**：最终按 `网络平面, 本端设备, 本端ETH-TRUNK, 标签` 稳定排序，并对连续同组的本端/对端 IP、掩码、ETH-TRUNK 列合并单元格。

## 与项目实现对齐情况

已对齐的业务逻辑：

- `get_switch_data`：表头探测、列位置映射、leaf/leaf 与 spine/spine 同型 MLAG 连线筛选、去重逻辑保持一致。
- `get_net_ni_resource_info`：使用资源表 `MLAG` 行，从地址池和最小规划掩码中寻找第一对可用连续 IP；找不到时输出空 IP。
- `allocate_connection`：两种带宽时高带宽为 `PEER-LINK`；一种带宽时按本端交换机端口数量和端口序号划分 `DAD`/`PEER-LINK`。
- `switch_connect`：按 `WEB_NETWORK_TYPE_CONFIG` 映射网络平面，跳过 `超平面`，带外网络平面过滤本端设备包含 `LEAF` 的记录。
- `standard_merge_df` / `merge_excel_regions`：输出列、空值规范化、排序字段和合并单元格列与项目保持一致。

离线运行差异：

- 项目从 DB/EDM 读取 Excel，并上传中间文件和最终文件；本工具只读写本地文件。
- 项目输出文件名带 `user_id`、`project_id`：`{user_id}_交换机MLAG规划.xlsx` 和 `{user_id}_{project_id}_A3交换机MLAG规划.xlsx`；本工具传入 `user_id/project_id` 时默认使用同款文件名，也可通过 CLI 参数覆盖。
- 项目逐 sheet 写入未合并临时文件并删除同网络平面历史数据；本工具已按该方式输出，并在最终阶段读取未合并临时文件生成合并版。
- 项目只固定读取 `网络资源需求表`；本工具优先读取该 sheet，找不到时会兼容扫描包含 `网络平面` 列的其他 sheet，便于脱离项目运行。
- 项目 MLAG 入口默认只处理工作簿中与 `WEB_NETWORK_TYPE_CONFIG` 完全同名的 sheet；本工具默认保持一致。需要离线兼容 `|` 拆分候选 sheet 时，可加 `--compat-composite-sheets` 或直接用 `--sheet` 指定。
- `a3_switch_mlag.py` 中 `_get_all_switch_mlag_data` 当前未被本规划入口调用，本工具未迁移这段未使用逻辑。

## 调用方式

CLI：

```bash
python scripts/run_switch_mlag.py \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --user-id x00612310 \
  --project-id 00ffa4183d76bfed42996718460816e9 \
  --output-dir runs
```

Python：

```python
from switch_mlag_planning import generate_switch_mlag

result = generate_switch_mlag(
    topology_file="建模仿真输出文档007-端口连线表.xlsx",
    resource_file="项目信息收集表.xlsx",
    user_id="x00612310",
    project_id="00ffa4183d76bfed42996718460816e9",
    output_dir="runs",
)
```

更多参数见 `README.md`。

## 关键字面量

- 表头探测：`设备命名`
- 资源表网络平面：`MLAG`
- 标签：`DAD`、`PEER-LINK`
- 输出 sheet：`交换机MLAG规划`

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
