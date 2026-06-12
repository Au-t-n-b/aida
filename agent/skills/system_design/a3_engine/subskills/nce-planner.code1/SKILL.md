---
name: nce-planner
description: 离线 NCE 部署规划。输入 007 端口表 + 项目信息收集表 [+ MLAG 设备列表]，按现有 nce_deployment_plan.py 规则确定性生成 A3NCE部署规划.xlsx，不依赖 LLM/EDM/DB。
disable-model-invocation: true
metadata:
  package: NCE-skill/
  entrypoint: scripts/run_nce_planner.py
  rules: NCE_new_plan.md
  source_reference: ../network_management/nce_deployment_plan.py
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令，由 [subskills/SKILL.md](../SKILL.md) 编排调用。

# NCE Planner

## 概述

- **输入**：007 端口互联表、项目信息收集表/网络资源表、可选 MLAG 对端设备名列表。
- **输出**：`A3NCE部署规划.xlsx`，sheet `NCE部署方案`。
- **执行**：纯本地 Python，一键跑到底；失败直接报错退出。
- **平台交互**：第一版无 HITL、无 Dashboard/EmbeddedWeb、无 artifact.publish。

## 依赖

```bash
pip install -r requirements.txt
```

## 入口

```bash
cd NCE-skill
python scripts/run_nce_planner.py \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --mlag-list mlag_devices.txt \
  --out A3NCE部署规划.xlsx
```

省略 `--topology` / `--resource` 时，在当前工作目录下按文件名关键字自动探测（含 `007`/`端口连线`、`项目信息收集`/`资源`）。

可选校验：

```bash
python scripts/validate_inputs.py --topology ... --resource ...
```

## 输入契约

### 007 端口表

- 默认 sheet：`计算带外管理面端口互联`
- 首列设备名包含 `NCEFB` 或 `NCEFI` 的行参与规划；按出现顺序去重。

### 资源表

默认第一个 sheet，必需列：`网络平面`、`地址池*`、`最小规划掩码*`。非内部通信网络还需要 `VLAN*`、`网关位置*` 或 `网关地址*`。

匹配的网络平面：

- `NCEFB内部通信网络`
- `NCEFB北向网络`
- `NCEFB南向网络`
- `NCEFB BGP南向网络`
- `NCEFI北向网络`
- `NCEFI南向网络`

### MLAG 列表（可选）

- 文本文件，每行一个对端/相关设备名。
- 命中任一 NCE 设备时输出 Bond 模式 `mode4(lacp)`，否则为 `mode1`。

## 输出契约

列：`设备名称 | 网络平面 | 接口名称 | IP地址 | 掩码 | 网关 | VLAN | Bond模式 | 目的网段 | 目的掩码`

- NCEFB 节点段：内部、北向、南向、BGP 南向按存在顺序输出。
- NCEFB 浮动 IP 段：北向、南向、BGP 南向按存在顺序输出。
- NCEFI 节点段：北向、南向按存在顺序输出。
- NCEFI 浮动 IP 段：北向、南向按存在顺序输出。

## 分配规则摘要

见 [NCE_new_plan.md](./NCE_new_plan.md)。

- 节点 IP：各平面按地址池主机地址升序分配，避让网关。
- 浮动 IP：紧跟节点 IP 后顺序取 1 个。
- 内部通信网络：网关、VLAN 输出为空。
- 北向网络：目的网段/目的掩码输出 `0.0.0.0`。

## 实现结构

| 文件 | 职责 |
|------|------|
| `scripts/nce_ip_rules.py` | 网关、可用 IP 枚举、VLAN 和行分配 |
| `scripts/nce_resource_parser.py` | 资源表行解析 |
| `scripts/nce_topology_parser.py` | 007 NCE 设备列表 |
| `scripts/nce_planner.py` | 主流程与 Excel 写出 |
| `scripts/run_nce_planner.py` | CLI |
| `scripts/validate_inputs.py` | 输入校验 |

## 测试

```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
