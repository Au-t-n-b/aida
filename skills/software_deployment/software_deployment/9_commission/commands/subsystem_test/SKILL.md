> 模块 · **子系统测试**（用户步骤 ⑩ / deploy_chain ⑩）。

# subsystem_test — 子系统测试

计算子系统测试类命令（灵衢 PRBS、服务器压测/单机测试/打流、单 Pod 集群通信与集成等）。

## 命令清单

| 命令 | task_type | device_kind | device_field | poll_mode | 状态 |
|------|-----------|-------------|--------------|-----------|------|
| 单机综合检测 | single_comprehensive | server | deviceIds | — | ✅ |
| 灵衢 PRBS 测试 | lq_prbs_test | switch | deviceIds | prbs_multi_step | ✅ |
| 计算硬件压测 | burn_test | server | nodeList | — | ✅ |
| 单机模型测试 | single_model_test | server | nodeList | — | ✅ |
| 打流测试 / 灵衢总线打流 | traffic_test | server | deviceIds | traffic_array | ✅ |
| 集群通信配置测试-单 POD | hccl_test_single_pod | server | nodeList | hccl_count | ✅ |
| 集群训练测试-单 POD | cluster_train_single_pod | server | nodeList | cluster_train | ✅ |
| 集群推理测试-单 POD | cluster_infer_single_pod | server | nodeList | cluster_train | ✅ |
| 存储子系统测试 | storage_subsystem_test | storage | deviceIds | — | **留位** · Agent 无 handler；CloudOps 手工 |
| 网络子系统测试 | network_subsystem_test | switch | switchesDeviceIds | — | **留位** · Agent 无 handler；CloudOps 手工 |

**留位策略（Agent 审计 2026-06-08）：**

| 命令 | Agent handler | Agent params | Skill 动作 |
|------|---------------|--------------|------------|
| `storage_subsystem_test` | 无 | 无 | **维持留位** · P1 替代：CloudOps 手工 |
| `network_subsystem_test` | 无 | 无 | **维持留位** · P1 替代：CloudOps 手工；P2/P3 见 SKILL（lq_connection/traffic_test，语义不同） |

**说明：**

- ✅ 命令：`implemented=True`，含 `config/{execute,query}.json` + 薄 `SKILL.md`，走 `commission_run` → `task_runner`。
- 留位命令：Agent 无 Toolkit handler + 无 params 模板 → **不补 config/**；替代方案见各命令 `SKILL.md`。
- 灵衢 PRBS 使用三步 query（`selectNodes` → `prbsStressTest` → `recoverDevice`），完成后光模块恢复约 1.5h。
- 训练场景命令（`single_model_test`、`cluster_train_single_pod`）在 `scene.json` 为推理场景时不可执行。

## 共性前置

- 步骤 7/8 完成；通常依赖 init_install 已完成。
- 业务参数（压测时长、阈值、打流配置等）来自 CloudOps **参数模板 xlsx** 对应页签；首期 `execute.json` 保持 Agent 默认常量，空值可能导致下发失败。
- 设备范围统一见 `shared/device_scope/SKILL.md`（8 种文法）。

进度：完成任一命令写 `deploy_chain.step10_subsystem_test_at`。
