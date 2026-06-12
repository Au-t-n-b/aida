> 模块 · **初始化与软件安装**（用户步骤 ⑨ / deploy_chain `step9_init_install_at`）。

# init_install — 初始化与软件安装

灵衢、RM211、服务器的初始化与软件安装类命令。命令骨架统一，差异见各命令 `config` 与本目录注册项。

## 命令清单

| 命令 | task_type | device_kind | 状态 |
|------|-----------|-------------|------|
| 服务器连线检查 | connection | server | ✅ |
| 灵衢连线检查 | lq_connection | switch | ✅ |
| 灵衢配置检查 | lq_config_check | switch | ✅ |
| 灵衢健康检查 | lq_health_check | switch | ✅ |
| 灵衢光链路检查 | hccs_weak_light | switch | ✅ |
| 服务器 OS 安装 | os_install | server | ✅ |
| 服务器昇腾软件安装 | ascend_install | server | ✅ |
| 服务器健康检查 | server_health_check | server | **留位** |
| 集群健康检查 | cluster_health_check | server | ✅ |
| 服务器弱光检查 | weak_light | server | ✅ |

## 共性前置

- 步骤 ⑦⑧ 完成；`gateway.json` 有效。
- 灵衢配置检查另需步骤 ⑥ ZTP；灵衢健康检查另需步骤 ⑥ 测试参数 xlsx。
- 设备范围统一见 `shared/device_scope/SKILL.md`。

进度：完成任一命令写 `deploy_chain.step9_init_install_at`。
