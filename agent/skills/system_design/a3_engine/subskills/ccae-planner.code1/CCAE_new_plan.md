# CCAE Planner 网络平面分配规则

本文总结 `ccae-planner` skill 中对 CCAE 各网络平面的 IP、网关、VLAN、目的网络、目的掩码、VIP 和 Bond 模式分配规则。

## 总体规则

- 网络平面包括：容器内部通信网络、北向网络、南向带外网络、南向带内网络。
- 各平面基于 `network_resources` 中对应平面的 `ip_pool` / `network_pool` 生成地址规划。
- 非容器内部平面必须提供 `ip_pool`、`vlan`、`gateway_position`，缺失会报错。
- 容器内部平面允许网关和 VLAN 为空。
- 节点 IP 按子网主机地址从小到大分配。
- VIP 是集群级浮动 IP，不绑定单个节点，分配后会从最终可用 IP 中排除。
- 当前脚本未单独输出“目的掩码”字段；项目 prompt 中仅北向网络目的网段和目的掩码要求输出 `0.0.0.0`。

## 容器内部通信网络

| 项目 | 规则 |
| --- | --- |
| 网络平面 | `ccae_container_internal`，显示名为容器内部通信网络 |
| IP 分配 | 每个 CCAE 节点分配 1 个 IP，从子网第一个主机地址开始顺序取 |
| 网关 | `gateway_position` 为空时认为不需要网关；若提供 `start_position` / `end_position`，分别取子网首个 / 最后一个可用主机地址 |
| VLAN | 允许为空；默认映射为 `400`，但当前实际优先读取 `network_resources.vlan` |
| VIP / 浮动 IP | 分配 2 个 VIP，紧跟节点 IP 后取；用途为高可用性虚拟 IP、故障转移备用 IP |
| Bond 模式 | `mode1` |
| 目的网络 | 节点数不超过 3：`Container-Internal (容器间通信 FULL-MESH)`；超过 3：`Container-Internal (容器间通信 SPINE-LEAF)` |
| 目的掩码 | 当前脚本未单独输出 |

## 北向网络

| 项目 | 规则 |
| --- | --- |
| 网络平面 | `ccae_northbound`，显示名为北向网络 |
| IP 分配 | 每个 CCAE 节点分配 1 个 IP，从小到大取，避开 `occupied_ip` 和网关 |
| 网关 | 必须提供 `gateway_position`；`start_position` 取子网首个可用主机地址，`end_position` 取最后一个可用主机地址 |
| VLAN | 必须从 `network_resources.vlan` 获取；默认映射为 `100`，但当前缺失会报错 |
| VIP / 浮动 IP | 分配 1 个 VIP，在节点 IP 后继续取下一个未占用地址；用途为北向网络高可用虚拟 IP |
| Bond 模式 | `mode1` |
| 目的网络 | `Northbound-Southbound (上联核心网)` |
| 目的掩码 | 当前脚本未单独输出；项目 prompt 中北向目的网段 / 目的掩码为 `0.0.0.0` |

## 南向带外网络

| 项目 | 规则 |
| --- | --- |
| 网络平面 | `ccae_southbound_oob`，显示名为南向带外网络 |
| IP 分配 | 每个 CCAE 节点分配 1 个 IP；所有形态下都规划，物理链路共享不影响 IP 规划 |
| 网关 | 必须提供 `gateway_position`；`start_position` 取子网首个可用主机地址，`end_position` 取最后一个可用主机地址 |
| VLAN | 必须从 `network_resources.vlan` 获取；默认映射为 `200`，但当前缺失会报错 |
| VIP / 浮动 IP | 分配 1 个 VIP；用途为带外网络高可用虚拟 IP |
| Bond 模式 | `mode1` |
| 目的网络 | `Southbound-OOB (带外管理网)` |
| 目的掩码 | 当前脚本未单独输出 |

注意：当前脚本把 `available_ips` 和 `reserved_ips` 都加入避让集合。也就是说，`available_ips` 会被当作“已占用”而不参与分配，这与“可用 IP 池”的语义不一致，后续需要修正。

## 南向带内网络

| 项目 | 规则 |
| --- | --- |
| 网络平面 | `ccae_southbound_ib`，显示名为南向带内网络 |
| IP 分配 | 每个 CCAE 节点分配 1 个 IP，从小到大取，只避开 `occupied_ip` 和网关 |
| 网关 | 必须提供 `gateway_position`；`start_position` 取子网首个可用主机地址，`end_position` 取最后一个可用主机地址 |
| VLAN | 必须从 `network_resources.vlan` 获取；默认映射为 `300`，但当前缺失会报错 |
| VIP / 浮动 IP | 分配 1 个 VIP；用途为带内网络高可用虚拟 IP |
| Bond 模式 | `mode4` |
| 目的网络 | `Southbound-IB (带内业务网)` |
| 目的掩码 | 当前脚本未单独输出 |

## VLAN 范围处理

- 当前实现只支持单个 VLAN 值，例如 `100` 或 `"100"`。
- 如果 `network_resources.vlan` 提供范围，例如 `"100-120"`，会在 `int(vlan)` 转换时报错。
- 除容器内部网络外，其他平面 VLAN 为空会报错。
- 当前未实现“VLAN 范围按平面、子网或设备顺序分配”的逻辑。

## VIP / 浮动 IP 汇总

| 平面 | VIP 数量 | 用途 |
| --- | ---: | --- |
| 容器内部通信网络 | 2 | 高可用性虚拟 IP、故障转移备用 IP |
| 北向网络 | 1 | 北向网络高可用虚拟 IP |
| 南向带外网络 | 1 | 带外网络高可用虚拟 IP |
| 南向带内网络 | 1 | 带内网络高可用虚拟 IP |

项目 prompt 中模块二对应名称为：

- `CaaS内部浮动IP(DIP)`
- `CaaS外部浮动IP(DIP)`
- `北向网络浮动IP`
- `南向带外网络浮动IP`
- `南向带内网络浮动IP`
