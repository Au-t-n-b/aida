---
name: software_deployment
version: 1.0.0
enabled: true
ui:
  label: 部署调测
  group: ops
  order: 40
  icon: deploy
  route_key: deploy
runtime:
  workspace_env: SOFTWARE_DEPLOYMENT_ROOT
description: 软件部署与调测全流程——计划 1～3、CloudOps 4～6、Toolkit 7～8、init_install 四条检查命令、调测报告汇总。关键词：部署调测 / CloudOps / Toolkit / 连线检查 / 弱光检查 / 调测报告。
---

# 软件部署与调测（software_deployment）· AIDA Agent Skill

## 何时使用

- 开始部署 / 接收二级任务 / 拆分计划 / CloudOps / Toolkit 导入 / init_install 检查 / 调测报告

## 后端节点（与 B 层 step.key 一致）

| Step | 名称 | 后端节点 |
|------|------|----------|
| 1 | 接收二级任务 | plan_receive |
| 2 | 拆分调测计划 | plan_split |
| 3 | 下发设备底表 | plan_dispatch |
| 4 | CloudOps 初配 | cloudops_init |
| 5 | CloudOps 补充 | cloudops_supplement |
| 6 | CloudOps 完整配置 | cloudops_full |
| 7 | 配置调测设备 | toolkit_executor |
| 8 | 导入 Toolkit | toolkit_import |
| 9 | 服务器连线检查 | connection |
| 10 | 灵衢连线检查 | lq_connection |
| 11 | 服务器弱光检查 | weak_light |
| 12 | 灵衢光链路检查 | hccs_weak_light |
| 13 | 调测报告汇总 | commission_report |

## HTTP 端点

| 方法 | 路径 |
|------|------|
| POST | `/agent/software_deployment/start` |
| GET | `/agent/software_deployment/stream/{run_id}` |
| POST | `/agent/software_deployment/resume` |
| GET | `/agent/software_deployment/status/{run_id}` |

工作区根：`SOFTWARE_DEPLOYMENT_ROOT`（默认仓库内 `skills/software_deployment/`，含 `runtime/`、`data/`、`ProjectData/`）

## init_install 命令范围

当前 LangGraph 仅接入以下四条 init_install 命令（`9_commission/commands/init_install/`）：

- `connection` — 服务器连线检查
- `lq_connection` — 灵衢连线检查
- `weak_light` — 服务器弱光检查
- `hccs_weak_light` — 灵衢光链路检查

子系统测试、集群测试等其他 commission 命令暂未接入。
