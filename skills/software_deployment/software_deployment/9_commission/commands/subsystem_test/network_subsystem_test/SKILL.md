> 命令 · **网络子系统测试**。**当前留位，不可执行。**

# 网络子系统测试 network_subsystem_test（留位）

## Agent 侧审计

路径：`CPCIA_AGENT/.../deploymentandtest`

| 项 | 结论 |
|----|------|
| `tasks.py` 计划活动 | 有 `ThirdActivity.NETWORK_SUBSYSTEM_TEST`（「网络子系统验证」） |
| `interface.py` handler 映射 | **无** |
| `api_handler/` | **无** 对应 handler |
| `config/params/` | **无** `network_subsystem_test/` 目录 |
| `TaskType` | **无** 枚举项 |

**结论：Agent 仅有思维导图/计划活动名，未实现 Toolkit 下发，Skill 维持留位，不补 `config/`。**

## 为何留位

- 无 Agent handler、无 execute/query 模板真值，无法声明式接入 `task_runner`。
- 当前需在 CloudOps 执行机侧 **人工执行**「网络子系统验证」。

## 替代方案（产品优先级）

| 优先级 | 用户意图 | 应用命令 / 做法 | 说明 |
|--------|----------|-----------------|------|
| **P1** | 网络子系统验证（标准流程） | CloudOps 执行机 **手工** | 思维导图 10 网络子系统测试节点 |
| **P2** | 交换机 / 灵衢链路连通 | `lq_connection` | init_install；**不等价**于网络子系统验证 |
| **P3** | 灵衢总线 / 打流类 | `traffic_test` | subsystem_test；覆盖打流场景，**不能替代**网络子系统验证 |
| **P4** | 服务器侧连线 | `connection` | init_install；服务器底表，非网络子系统 scope |

## 用户说法（识别后提示留位）

- 「网络子系统测试」「网络子系统验证」

## LLM 话术示例

> 「网络子系统验证」当前 Skill **未接入**（Agent 无 handler、无 params 模板）。  
> 请在 CloudOps 执行机按网络子系统测试流程 **手工执行**。  
> 若仅需 **灵衢连线** 或 **打流**，可分别用 `lq_connection`、`traffic_test`（语义不同，勿当作替代验收）。

## 设备范围（注册表预留）

- `device_kind=switch`，`device_field=switchesDeviceIds`；设备来自完整配置《交换机信息》。

## 接入前置（待 Toolkit / Agent 补齐）

1. Agent 增加 handler + `interface.py` 映射 + `TaskType`
2. 提供 `config/params/network_subsystem_test/{execute,query}.json` 真值
3. 本目录补 `config/`，`task_catalog` 置 `implemented=True`
