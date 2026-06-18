---
name: xxx
version: 0.1.0                 # 语义化版本（manifest，热加载/兼容用；每次发布递增）
enabled: true                  # 软开关：false 则前端不挂入口（无需删目录即可下线）
ui:                            # 导航元数据（驱动前端，前端不再硬编码；lint_skill_manifest 校验）
  label: <模块中文名>          # 导航显示名
  group: ops                   # 分组：ops=交付作业 · design=规划设计 · early=早期介入
  order: 50                    # 同组内排序（小在前）
  icon: <icon_key>             # 前端 ICON_MAP 键；未知则用 fallback 通用图标
  route_key: xxx               # 前端 /module/<route_key> 入口键；须全局唯一（缺省=name）
runtime:
  workspace_env: XXX_ROOT      # 工作区根环境变量（与 skill.py 的解析逻辑一致）
description: <模块一句话定位 + 触发关键词（决定召回，照 zhgk 写法堆全业务关键词）>。本 skill 通过 AIDA Agent 后端（LangGraph）顺序执行 N 个 step：① … ② …。支持从任意步骤切入、HITL 文件补齐、增量重跑、全流程一键执行。
---

# <模块中文名>（xxx）· AIDA Agent Skill

> A 层门面：何时调用 + 触发词 + HTTP 约定。真正执行由 `agent/skills/xxx/` 的 LangGraph 后端完成。
> 复制自 `_template`；改造见 [START_HERE](../../docs/10_快速开始/START_HERE.md)。

## 何时使用本 skill

- **触发关键词**：<…>
- **业务场景描述**：<…>
- **不要调用**：<纯讨论无执行需求 / 仅查看历史产物>

---

## A. 流程总览（N 个 step）

| Step | 名称 | 关键输入 → 输出 | 后端节点 |
|---|---|---|---|
| 1 | 示例步骤 | <输入> → <输出> | `example_step` |

> ⚠️「后端节点」列必须与 `agent/skills/xxx/steps` 的 `step.key` **逐一一致**（`lint_skill_contract` 校验）。
> 每个 step 的细则可放 `references/<step>.md`。

---

## B. 调用 AIDA Agent 后端（HTTP / SSE）

本 skill **不直接执行 Python**。所有调用走 `http://127.0.0.1:7401`：

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/agent/xxx/start` | 启动 run（body: `{project_code, ...}`），返回 `run_id` |
| GET  | `/agent/xxx/stream/{run_id}` | SSE 实时事件流 |
| POST | `/agent/xxx/resume` | HITL 续跑（补料后） |
| POST | `/agent/xxx/upload` | 上传补料文件 |
| GET  | `/agent/xxx/artifact?path=...` | 下载产物 |

> ✅ 端点前缀 `/agent/xxx/` 在注册 skill 后**自动可用**（`main.py` 已泛化为 `/agent/{skill}/*`，`graph.py` 按 `skill_id` 构图）—— 无需改后端 HTTP 层。

---

## C. 产物清单与验收

| Step | 完成标志（文件应在 `ProjectData/Output/` 或 `RunTime/`） |
|---|---|
| 1 | `ProjectData/Output/<…>` |
