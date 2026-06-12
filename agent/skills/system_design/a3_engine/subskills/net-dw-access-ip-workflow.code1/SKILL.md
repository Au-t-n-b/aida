---
name: net-dw-access-ip-workflow
description: 网络带外管理地址规划离线工具。输入《建模仿真输出文档007-端口连线表.xlsx》+《项目信息收集表.xlsx》，复刻 a3_net_dw_manage_ip_address.py 的接入交换机网段规划、网络设备 MGMT 地址分配、LEAF vlanif 地址追加和网关中间表输出逻辑。
disable-model-invocation: true
metadata:
  package: net_dw_access_ip/
  cli: scripts/run_net_dw_access_ip.py
  access_cli: scripts/run_network_access_plan.py
  source_reference: ../a3_net_dw_manage_ip_address.py
  access_source_reference: ../a3_network_access_plan.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## 概述

- **输入**：《建模仿真输出文档007-端口连线表.xlsx》、《项目信息收集表.xlsx》、007 页签、资源表网络平面。
- **输出**：默认 `A3网络带外管理地址规划.xlsx`，sheet 固定为 `网络带外管理地址`。
- **中间输出**：默认 `A3带外管理网关地址规划.xlsx`，保存迁移到 SPINE 后的网关信息；文件已存在时按项目逻辑追加。
- **接入规划查询**：`scripts/run_network_access_plan.py` 复刻 `a3_network_access_plan.py`，读取已生成的 `A3网络设备接入规划.xlsx` 第一个 sheet，按项目 `WEB_NETWORK_TYPE_CONFIG` 解析出的网络平面过滤。
- **执行方式**：纯本地 Excel 读写，不依赖项目 DB、EDM、LLM、global_store、日志或上传服务。

## 适用范围

当前工具复刻 `a3_net_device_dw_manage_ip_address_generate` 的 **A3 网络带外管理地址规划**：

| 规划项 | 默认值 |
|------|------|
| 007 sheet | `网络带外管理面端口互联` |
| 资源表网络平面 | `网络带外管理面` |
| 输出 sheet | `网络带外管理地址` |
| 网络设备接口 | `MGMT` |
| LEAF 接口 | `vlanif<VLAN>` |

同时复刻 `a3_network_access_plan.network_access_plan` 的 **网络设备接入规划查询**。该逻辑不读取 007 重新生成接入规划，只读取各地址规划流程已合并出的 `A3网络设备接入规划.xlsx` 第一个 sheet，并按 `网络平面` 精确过滤：

| 接入规划名称 | main_flow sheet | 过滤网络平面 |
|------|------|------|
| `计算带外管理接入规划` / `计算带外管理面接入规划` | `计算带外管理面端口互联` | `计算带外管理面` |
| `存储带外管理接入规划` / `存储带外管理面接入规划` | `存储带外管理面端口互联` | `存储带外管理面` |
| `网络带外管理接入规划` / `网络带外管理面接入规划` | `网络带外管理面端口互联` | `网络带外管理面` |
| `灵衢带外管理接入规划` / `灵衢带外管理面接入规划` | `灵衢带外管理面端口互联` | `灵衢带外管理面` |
| `带外管理面接入规划` | `存储管理面端口互联` | `存储管理面` |
| `计算管理面接入规划` | `计算管理面端口互联` | `计算管理面` |
| `计算业务面接入规划` | `计算业务面端口互联` | `计算业务面` |
| `计算样本面接入规划` | `存储面端口互联 \| 样本面端口互联` | `计算样本面` |
| `计算参数面接入规划` | `参数面端口互联` | `计算参数面` |
| `计算管存面接入规划` | `计算管存面端口互联` | `计算管存面` |
| `存储管理面接入规划` | `存储管理面端口互联` | `存储管理面` |
| `存储业务面接入规划` | `存储业务面端口互联` | `存储业务面` |
| `存储样本面接入规划` | `样本面端口互联 \| 数据面端口互联` | `存储样本面` |

`--plan` 兼容带 `_L2` / `_L3` 后缀的 `main_flow.py` key。

## 输入契约

### 建模仿真输出文档007-端口连线表

- 找首个含「设备命名」的单元格行作为表头。
- 表头之后的数据行中，第 1 列按源逻辑视为「网络设备」，最后 1 列视为「接入交换机」。
- 「接入交换机」包含 `LEAF` 的记录参与交换机节点数量统计。
- 按「接入交换机」聚合第 1 列网络设备，作为待分配 `MGMT` 地址的设备列表。
- 同一 sheet 第 1 列含 `LEAF` 且最后 1 列为 SPINE/对端设备时，用于生成 `{leaf: [spine...]}` 映射，并把网关信息迁移到 SPINE 中间表。

### 项目信息收集表

- 按项目实现固定读取第一个 sheet。
- 行定位：默认 `网络平面 == 网络带外管理面`，离线 CLI 仍保留 `--plane` 用于显式覆盖。
- 必需列：`网络平面`、`地址池*`、包含 `最小规划掩码` 或 `掩码` 的列、`VLAN*`、`网关地址*`。
- 地址池格式：`起始IP-结束IP`。
- VLAN 支持单值（所有网段共用）或范围（每个网段顺序取一个 VLAN）。
- 网关支持 `网段起始位` / `网段结束位` / `SPINE` / `LEAF` 语义，也支持具体 IPv4 地址。

## 输出契约

输出工作簿 sheet 名固定为 `网络带外管理地址`。

固定列顺序：

| 字段 | 说明 |
|------|------|
| `设备名称` | 网络设备名或 LEAF 交换机名 |
| `带外管理地址` | 从对应网段可用 IP 顺序分配，排除网关且限制在地址池范围内 |
| `带外管理掩码` | 资源表最小规划掩码 |
| `带外管理网关` | 该网段网关 |
| `带外管理VLAN` | 单 VLAN 或 VLAN 范围分配结果 |
| `接口名称` | LEAF 为 `vlanif<VLAN>`，其他设备为 `MGMT` |

网关中间表列顺序固定为 `name, network_segment, gateway, vlan, mask`。

接入规划查询输入工作簿默认为 `A3网络设备接入规划.xlsx`，读取方式与项目文件一致：固定读取第一个 sheet，要求包含 `网络平面`、`vlan`、`pvid` 列；`vlan`、`pvid` 会转为整数可空类型并把空值展示为空字符串。离线 CLI 的 `--out` 只是辅助导出过滤结果；项目函数本身展示原接入规划文件并返回过滤后的 DataFrame。

## 规则与校验

- **网段划分**：以地址池起始 IP 和资源表掩码形成首个 CIDR 网段，后续网段按广播地址 + 1 连续推进。
- **交换机合并**：按 LEAF 顺序累加节点数量；未超过本网段可用 IP 数时共用同一网段，一旦超限则从当前交换机开始新网段。
- **地址分配**：按网段聚合交换机下挂网络设备；若本网段无下挂网络设备则跳过，若存在则再追加 LEAF 设备并顺序分配 IP；默认 `--leaf-scope global` 复刻源文件的全局 LEAF 追加行为。
- **网关迁移**：若能从 007 表识别 LEAF 到 SPINE 的连接，则把 LEAF 网关配置迁移到对应 SPINE；若识别不到，则按源逻辑保留空设备名的网关记录；同一 SPINE/VLAN 出现冲突时保留首次配置。
- **资源不足**：地址池格式非法、VLAN 数量不足、单网段可用 IP 不足、地址池无法继续分配网段时直接报错，不生成不完整结果。

## 调用方式

CLI：

```bash
python scripts/run_net_dw_access_ip.py \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --sheet 网络带外管理面端口互联 \
  --plane 网络带外管理面 \
  --out runs/A3网络带外管理地址规划.xlsx \
  --intermediate runs/A3带外管理网关地址规划.xlsx
```

Python：

```python
from net_dw_access_ip import run_from_files

result = run_from_files(
    topology_file="建模仿真输出文档007-端口连线表.xlsx",
    resource_file="项目信息收集表.xlsx",
)
```

接入规划查询 CLI：

```bash
python scripts/run_network_access_plan.py \
  --access-plan A3网络设备接入规划.xlsx \
  --plan 计算业务面接入规划 \
  --out runs/计算业务面接入规划.xlsx
```

接入规划查询 Python：

```python
from net_dw_access_ip import query_access_plan

result = query_access_plan(
    access_plan_file="A3网络设备接入规划.xlsx",
    plan_name="计算业务面接入规划",
)
```

项目对齐入口：

```python
from net_dw_access_ip import network_access_plan

df = network_access_plan(
    access_plan_file="A3网络设备接入规划.xlsx",
    sheet_name="计算业务面端口互联",
)
```

## 故障排查

| 现象 | 处理 |
|------|------|
| 「未找到包含'设备命名'的行」 | 检查 007 sheet 是否正确、表头是否包含字面量「设备命名」 |
| 「资源表中未找到网络平面」 | 检查 `--plane` 与资源表 `网络平面` 值是否一致 |
| 「无效的IP地址范围格式」 | 地址池需为 `起始IP-结束IP` |
| 「VLAN 数量不足」 | 扩大 VLAN 范围或改为单 VLAN |
| 「网段中可用 IP 不足」 | 扩大地址池、调整掩码或减少待分配设备 |
| 接入规划查询为空 | 先执行对应网络平面的地址规划（各 `a3-*-ip-workflow` 会在 `run_*` 目录生成/合并 `A3网络设备接入规划.xlsx`），确保其中已有该 `网络平面` |

## 地址规划侧已生成接入数据的平面

与项目 `merge_and_save_data` 一致，下列平面在**地址规划 skill** 执行后会写入 `A3网络设备接入规划.xlsx`：

| 网络平面 | 地址规划 skill |
|---|---|
| 计算带外管理面 | `a3-dw-manage-ip-workflow.code1` |
| 存储带外管理面 | `a3-storage-dw-manage-ip-workflow.code1` |
| 灵衢带外管理面 | `a3-lq-dw-manage-ip-workflow.code1` |
| 计算管理面 | `a3-l2-l3-ip-workflow.code1` |
| 存储管理面 | `a3-cc-glm-ip-workflow.code1` |
| 计算业务面 | `a3-ywm-ip-workflow.code1` |
| 存储业务面 | `a3-cc-ywm-ip-workflow.code1` |
| 计算参数面 | `a3-csm-ip-workflow.code1` |
| 计算样本面 | `a3-ybm-ip-workflow.code1` |
| 存储样本面 | `a3-cc-ybm-ip-workflow.code1` |

未列入上表、且项目亦未在地址规划中写入接入表的平面（如 **网络带外管理面**、**计算管存面** / GCM、**计算超平面**）不在本合并文件范围内。

## 关键字面量

- 表头探测：`设备命名`
- 默认资源平面：`网络带外管理面`
- 默认输出 sheet：`网络带外管理地址`
- 网络设备接口：`MGMT`
- LEAF 接口前缀：`vlanif`

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
