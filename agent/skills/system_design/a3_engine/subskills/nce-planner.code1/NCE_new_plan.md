# NCE Planner 分配规则

本文总结离线 `nce-planner` 对 NCEFB / NCEFI 部署规划的确定性规则，来源为 `../network_management/nce_deployment_plan.py`。

## 输入

- 007 端口互联表默认 sheet：`计算带外管理面端口互联`
- 设备名来自首列，筛选包含 `NCEFB` / `NCEFI` 的设备，按出现顺序保留首条
- 资源表默认第一个 sheet，按 `网络平面` 精确匹配：
  - `NCEFB内部通信网络`
  - `NCEFB北向网络`
  - `NCEFB南向网络`
  - `NCEFB BGP南向网络`
  - `NCEFI北向网络`
  - `NCEFI南向网络`

## 输出

- 文件：`A3NCE部署规划.xlsx`
- sheet：`NCE部署方案`
- 列：`设备名称 | 网络平面 | 接口名称 | IP地址 | 掩码 | 网关 | VLAN | Bond模式 | 目的网段 | 目的掩码`

输出分段：

1. NCEFB 节点行
2. 标题行 `网络用途_NCEFB`
3. NCEFB 浮动 IP 行
4. 标题行 `设备名称`
5. NCEFI 节点行
6. 标题行 `网络用途_NCEFI`
7. NCEFI 浮动 IP 行

## 节点规划

- 各网络平面按地址池主机地址升序分配。
- 每个设备在每个存在的网络平面分配 1 个 IP。
- `NCEFB内部通信网络` 不规划网关和 VLAN。
- 非内部网络按 `网关地址*` 或 `网关位置*` 解析网关，网关地址不参与分配。
- 北向网络输出 `目的网段 = 0.0.0.0`、`目的掩码 = 0.0.0.0`。

## 浮动 IP

- NCEFB 北向：`北向浮动IP`，网络平面显示为 `北向通信网络`
- NCEFB 南向：`南向浮动IP`，网络平面显示为 `南向通信网络`
- NCEFB BGP 南向：`BGP服务南向浮动IP`，网络平面显示为 `BGP服务南向网络`
- NCEFI 北向：`北向浮动IP`，网络平面显示为 `北向通信网络`
- NCEFI 南向：`南向浮动IP`，网络平面显示为 `南向通信网络`

浮动 IP 从对应平面节点 IP 之后继续取 1 个可用 IP。

## VLAN 和 Bond

- `VLAN*` 支持单值或范围，按设备行递增；浮动 IP 使用起始 VLAN。
- 可选 MLAG 列表中命中任一 NCE 设备时，Bond 模式为 `mode4(lacp)`；否则为 `mode1`。
- 节点段 bond 名称按存在的平面顺序从 `bond0` 递增。
- 浮动 IP 段按 NCEFB / NCEFI 各自存在的浮动网络从 `bond0` 递增。
