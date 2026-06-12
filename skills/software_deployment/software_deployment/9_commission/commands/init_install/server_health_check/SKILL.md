> 命令 · **服务器健康检查**（CloudOps 图1：`AI推理-服务器` → 健康检查）。**当前留位，不可执行。**

# 服务器健康检查 server_health_check（留位）

## Agent 侧审计

路径：`CPCIA_AGENT/.../deploymentandtest`

| 项 | 结论 |
|----|------|
| `interface.py` handler 映射 | **无** `server_health_check` 条目 |
| `api_handler/` | **无** 独立 handler |
| `config/params/` | **无** 对应模板目录 |
| 易混淆项 | `ThirdActivity.HEALTH_CHECK` → `health_check_handler.execute_cluster_health_check` → **`cluster_health_check`**（非本命令） |
| `pipeline_constants` | 引用 `ThirdActivity.SERVER_HEALTH_CHECK`，但 `tasks.py` **未定义**该活动常量（遗留引用） |

**结论：Agent 未实现本命令，Skill 维持留位，不补 `config/`。**

## 为何留位

- CloudOps 执行机图1 有独立菜单（服务器管理侧「健康检查」），与 Agent/Toolkit 可下发任务 **不是同一 task_type**。
- 与以下可执行命令 **不可混用**：
  - **单机综合检测** → `single_comprehensive` / `singleComprehensiveDetection`
  - **集群健康检查** → `cluster_health_check` / `clusterHealthCheck`

## 替代方案（产品优先级）

| 优先级 | 用户意图 | 应用命令 | 说明 |
|--------|----------|----------|------|
| **P1** | 集群全量健康检查（含交换机） | `cluster_health_check` | Agent `HEALTH_CHECK` 实际走此命令；`scope=all` |
| **P2** | 单机验收 / 单台健康类检测 | `single_comprehensive` | subsystem_test；`scope=pod` 或 `include` |
| **P3** | 必须走 CloudOps 图1 菜单 | CloudOps 执行机手工 | 待 Toolkit 提供 `work_stage` + Agent handler 后再接入 Skill |

## 用户说法（识别后提示留位）

- 「服务器健康检查」「执行健康检查」「图1 健康检查」

## LLM 话术示例

> 图1「服务器健康检查」当前 Skill **未接入**（Agent 无 handler）。  
> - 若要做 **集群健康**：请用 `commission_run` + `command=cluster_health_check`  
> - 若要做 **单机综合检测**：请用 `command=single_comprehensive`  
> - 若必须走 CloudOps 图1 菜单，请在执行机侧手工操作。

## 接入前置（待 Toolkit / Agent 补齐）

1. 确认图1「健康检查」的 `X-WORKSTAGE` 与 `execute.json` 真值
2. Agent 增加 handler + `interface.py` 映射 + `config/params/server_health_check/`
3. 本目录补 `config/`，`task_catalog` 置 `implemented=True`
