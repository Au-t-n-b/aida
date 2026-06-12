---
name: a3-storage-dw-manage-ip-workflow
description: Offline deterministic A3 存储带外管理地址规划. Use when generating 存储带外管理地址 Excel from 007 port-connection sheets plus 项目信息收集表; reads 网络平面=存储带外管理面 and chooses L2 when 网关位置*=SPINE or L3 when 网关位置*=LEAF. Strictly follows a3_storage_dw_manage_ip_address.py and a3_l3_storage_dw_manage_ip_address.py address allocation rules.
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_storage_dw_manage_pipeline.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## Purpose

离线生成 A3 **存储带外管理地址规划**，输入 `007 端口连线表 + 项目信息收集表/网络资源需求表`，输出一份 `A3存储带外管理地址规划.xlsx`。该流程为**确定性计算**，不依赖 LLM、EDM、数据库或前端展示 API。

## Entrypoint

`python scripts/offline_storage_dw_manage_pipeline.py [--mode auto|l2|l3] [--007 PATH] [--resource PATH] [--sheet NAME] [--resource-sheet SHEET] [--out-dir output]`

## Dependencies

`pip install pandas openpyxl`

## Parameters

- `--mode auto`：默认值。读取资源表 `网络平面 == 存储带外管理面` 行的 `网关位置*`，`SPINE` → L2，`LEAF` → L3。
- `--mode l2` / `--mode l3`：强制执行对应层。
- `--007 PATH`：007 端口连线表；省略时在 cwd 下按 `007` / `端口连线` / `端口互联` 自动探测。
- `--resource PATH`：项目信息收集表；省略时在 cwd 下按 `项目信息收集` / `信息收集表` / `资源` 自动探测。
- `--sheet NAME`：007 sheet，默认 `存储带外管理面端口互联`。
- `--resource-sheet SHEET`：资源表 sheet，默认 `网络资源需求表`。
- `--net-plane NAME`：资源表网络平面行名，默认 `存储带外管理面`。
- `--out-dir output`：输出目录，必须位于 cwd 树下。

## Inputs Contract

### 007 端口连线表

| 项 | 规则 |
|----|------|
| 表头定位 | 找包含 `设备命名` 的行 |
| 设备映射 | 首列为 `存储设备`，末列为 `接入交换机` |
| 接口统计 | 通过结构化列 `起始端信息-设备命名` 统计每台存储设备端口行数 |
| 交换机 IP 数量 | 过滤 `存储设备` 中含 `leaf`/`spine` 的行后按接入交换机汇总 |

### 项目信息收集表

必须读取 `网络平面 == 存储带外管理面` 的行：

| 字段 | 说明 |
|------|------|
| `地址池*` | `A.B.C.D-E.F.G.H` |
| `最小规划掩码*` | 整数掩码位（列名含 `最小规划掩码` 即可） |
| `网关位置*` | `SPINE`（L2）或 `LEAF`（L3） |
| `网关地址*` | `网段起始位` / `网段结束位` / 具体 IP |
| `VLAN*` | 单个数字或 `start-end` |

## Business Rules

### 存储设备 IP 数量

对齐两个原脚本的 `get_switch_info()` 与分配逻辑：

- 设备名包含 `9950`：固定展开为 **8 个 IP**。
- 其他存储设备：按 `起始端信息-设备命名` 在 007 中出现的端口行数展开。
- 输出中同一存储设备可出现多行，每行一个 `带外管理地址`。
- `接口名称` 使用 `起始端信息-接口信息` 的映射，按原脚本 `port_dict` 口径取值。

### L2（`网关位置*=SPINE`）

来源：`a3_storage_dw_manage_ip_address.py`

1. 按接入交换机统计 `IP数量`。
2. 用 `地址池* + 最小规划掩码*` 调用确定性 `split_ip_range`。
3. 从第一台交换机起顺序累加 `IP数量`：未超过当前网段可用 IP 则共用网段；超过则切到下一网段。
4. 网关规则：`网段起始位` → 网络地址+1；`网段结束位` → 广播地址-1；具体 IP 则直接使用。
5. VLAN 规则：单值全局共用；范围值按网段组递增，不足输出 `vlan不足`。

### L3（`网关位置*=LEAF`）

来源：`a3_l3_storage_dw_manage_ip_address.py`

1. 按接入交换机统计 `IP数量`。
2. 从地址池起始 IP 所属网段开始，按配置掩码连续生成网段。
3. 每台接入交换机独占一个网段。
4. 网关/VLAN 规则同 L2。

### 地址分配

对每个网段：

1. 收集该网段内所有接入交换机下挂的存储设备。
2. 按设备规则展开为待分配列表。
3. 可用 IP = 当前网段 host 地址 ∩ 地址池范围，排除网关。
4. 逐个顺序分配 IP。

## Outputs

目录：`output/run_YYYYMMDD_HHMMSS/`

只输出一份文件：

| 文件 | Sheet |
|------|-------|
| `A3存储带外管理地址规划.xlsx` | `存储带外管理地址` |

输出列：

- `设备名称`
- `带外管理地址`
- `带外管理掩码`
- `带外管理网关`
- `带外管理VLAN`
- `接口名称`

## Validation

`python scripts/validate_inputs.py --007 PATH --resource PATH [--sheet NAME] [--resource-sheet SHEET]`

## Errors

- `未找到包含 '设备命名' 的行`
- `未找到网络平面等于 '存储带外管理面' 的记录`
- `网关位置* must be SPINE or LEAF`
- `地址池格式错误，应为 起始IP-结束IP`
- `网段个数不足`
- `网段 ... 中可用 IP 不足，请检查！`

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
