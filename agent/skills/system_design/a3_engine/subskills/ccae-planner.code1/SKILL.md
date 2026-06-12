---
name: ccae-planner
description: 离线 CCAE 四平面地址规划。输入 007 端口表 + 项目信息收集表 [+ MLAG 设备列表]，按 CCAE_new_plan.md 规则确定性生成 A3CCAE部署规划.xlsx，不依赖 LLM/EDM/DB。
disable-model-invocation: true
metadata:
  package: CCAE-skill/
  entrypoint: scripts/run_ccae_planner.py
  rules: CCAE_new_plan.md
  source_reference: ../network_management/ccae_deployment_plan.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

## 概述

- **输入（3 类）**：007 端口互联表（筛 CCAE 设备）、网络资源/项目信息收集表、可选 MLAG 对端设备名列表。
- **输出**：`A3CCAE部署规划.xlsx`，sheet `CCAE部署方案`（模块一节点 + 模块二 VIP）。
- **执行**：纯本地 Python，一键跑到底；失败直接报错退出。

## 依赖

```bash
pip install -r requirements.txt
```

## 入口

```bash
cd CCAE-skill
python scripts/run_ccae_planner.py \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --mlag-list mlag_devices.txt \
  --out A3CCAE部署规划.xlsx
```

省略 `--topology` / `--resource` 时，在当前工作目录下按文件名关键字自动探测（含 `007`/`端口连线`、`项目信息收集`/`资源`）。

可选校验：

```bash
python scripts/validate_inputs.py --topology ... --resource ...
```

## 输入契约

### 007 端口表

- 默认 sheet：`计算带外管理面端口互联`
- 首列设备名包含 `CCAE` 的行参与规划；按出现顺序去重

### 资源表（默认第一个 sheet）

| 平面匹配（网络平面列） | 内部 key |
|------------------------|----------|
| 容器内部 / 内部通信 | `ccae_container_internal` |
| 北向（排除带外/带内/南向） | `ccae_northbound` |
| 南向带外 / 带外 | `ccae_southbound_oob` |
| 南向带内 / 带内 | `ccae_southbound_ib` |

行名建议含 `CCAE`；必填列：`地址池*`、`最小规划掩码*`；非容器平面另需 `VLAN*`、`网关位置*`。

可选列：`occupied_ip`/`占用IP`、`reserved_ips`/`保留IP`、`网关地址*`。  
**不把 `available_ips` 当作已占用**（修正南向带外语义）。

### MLAG 列表（可选）

- 文本文件，每行一个对端/相关设备名
- 仅用于输出 `switch_mlag_flag` 日志；**Bond 模式以 CCAE_new_plan.md 为准**（容器/北向/带外 `mode1`，带内 `mode4(lacp)`）

## 输出契约

### 模块一（节点）

列：`设备名称 | 网络平面 | 接口名称 | IP地址 | 掩码 | 网关 | VLAN | Bond模式 | 目的网段 | 目的掩码`

- 接口：`bond0`～`bond3` 对应四平面
- 北向：`目的网段`/`目的掩码` = `0.0.0.0`；其余平面为空
- 容器内部：网关、VLAN 输出为空

### 模块二（VIP）

列：`网络用途 | 网络平面 | 接口名称 | IP地址 | 子网掩码 | 网关 | VLAN | Bond模式 | 目的网段 | 目的掩码`

| 网络用途 | VIP 数 |
|----------|--------|
| CaaS内部浮动IP(DIP) / CaaS外部浮动IP(DIP) | 容器内部 2 |
| 北向网络浮动IP | 1 |
| 南向带外网络浮动IP | 1 |
| 南向带内网络浮动IP | 1 |

资源表不存在的平面整平面跳过。

## 分配规则摘要

见 [CCAE_new_plan.md](./CCAE_new_plan.md)。

- 节点 IP：各平面按地址池主机地址升序分配，避让网关、`occupied_ip`、`reserved_ips`
- VIP：紧跟节点 IP 后顺序取值，并从可用池排除
- VLAN：仅支持单值；范围如 `100-120` 会报错

## 实现结构

| 文件 | 职责 |
|------|------|
| `scripts/ccae_ip_rules.py` | 网关、可用 IP 枚举、平面分配 |
| `scripts/ccae_resource_parser.py` | 资源表行解析 |
| `scripts/ccae_topology_parser.py` | 007 CCAE 设备列表 |
| `scripts/ccae_planner.py` | 主流程与 Excel 写出 |
| `scripts/run_ccae_planner.py` | CLI |
| `scripts/validate_inputs.py` | 输入校验 |

## 测试

```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
