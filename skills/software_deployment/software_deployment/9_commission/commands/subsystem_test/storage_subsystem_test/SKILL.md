> 命令 · **存储子系统测试**。**当前留位，不可执行。**

# 存储子系统测试 storage_subsystem_test（留位）

## Agent 侧审计

路径：`CPCIA_AGENT/.../deploymentandtest`

| 项 | 结论 |
|----|------|
| `tasks.py` 计划活动 | 有 `ThirdActivity.STORAGE_SUBSYSTEM_TEST`（「存储子系统验证」） |
| `interface.py` handler 映射 | **无** |
| `api_handler/` | **无** 对应 handler |
| `config/params/` | **无** `storage_subsystem_test/` 目录 |
| `TaskType` | **无** 枚举项 |

**结论：Agent 仅有思维导图/计划活动名，未实现 Toolkit 下发，Skill 维持留位，不补 `config/`。**

## 为何留位

- 无 Agent handler、无 execute/query 模板真值，无法声明式接入 `task_runner`。
- 当前需在 CloudOps 执行机侧 **人工执行**「存储子系统验证」。

## 替代方案（产品优先级）

| 优先级 | 用户意图 | 做法 | 说明 |
|--------|----------|------|------|
| **P1** | 存储子系统验证（标准流程） | CloudOps 执行机 **手工** | 思维导图 10 存储子系统测试节点；无 Skill 等价命令 |
| **P2** | 存储软件安装类 | 待独立 Spec | Agent 有 `st_software_install`（昇腾存储软件安装），**非**本子系统验证命令 |
| — | 计算/训练存储路径验证 | `single_model_test` / `cluster_train_single_pod` | 仅覆盖训练镜像路径，**不能替代**存储子系统验证 |

## 用户说法（识别后提示留位）

- 「存储子系统测试」「存储子系统验证」

## LLM 话术示例

> 「存储子系统验证」当前 Skill **未接入**（Agent 无 handler、无 params 模板）。  
> 请在 CloudOps 执行机按存储子系统测试流程 **手工执行**。  
> Toolkit 提供 API 后，将补 `config/` 并置 `implemented=True`。

## 设备范围（注册表预留）

- `device_kind=storage`，`device_field=deviceIds`；接入后可用 `scope=include` 指定存储节点 IP。

## 接入前置（待 Toolkit / Agent 补齐）

1. Agent 增加 handler + `interface.py` 映射 + `TaskType`
2. 提供 `config/params/storage_subsystem_test/{execute,query}.json` 真值
3. 本目录补 `config/`，`task_catalog` 置 `implemented=True`
