> 本文件是 software_deployment 主 Skill 的辅助子指令，由 `upstream_check` action 调用；不写入 plan 状态。

# 材料巡检（upstream-check）

## 概述

按**当前运行步骤**扫描 `data/upstream_manifest.json` 中相关槽位，列出 `ProjectData/input/*` 已解析文件与缺失项，供用户补齐材料。**不执行**拆分、下发或 CloudOps 写盘。

## 触发条件

- 用户说「检查材料」「本步说明」「缺什么文件」
- Host `action` = `upstream_check` 或 `sd_start` 后选择「当前步骤说明」
- 工作台「本步说明」按钮

## 前置要求

无；任意进度均可调用。

## 执行逻辑

运行时：`runtime/subskills/upstream/runtime/driver.py`

1. 读取 `deploy_chain` ①～③ 字段推导 `step`（`paths.load_plan_runtime_step`）
2. `plan_action_for_step(step)` 得到子动作（`receive` / `split` / `dispatch` / `regenerate`）
3. `check_prerequisites(for_actions=[plan_receive|plan_split|...])` — **仅**返回该 action 在 manifest 中 `requiredFor` 匹配的槽位
4. 输出引导卡：本步标题、input 目录路径、材料清单（✓/缺）、推荐 `plan_*` 或 `cloudops_*` 按钮

## 槽位速查（全文见 manifest）

| 槽位 id | 典型目录 | 用于 action |
|---------|----------|-------------|
| `second_level_tasks` | `input/plan_receive` | `plan_receive`, `plan_split` |
| `testcase` | `input/plan_split` | `plan_split` |
| `pod_map`, `scene_info` | `input/plan_split` | `plan_split`（pod 多 Pod 时必填） |
| `lld_design` | `input/plan_dispatch` | `plan_dispatch`, `cloudops_init` |
| `cloudops_manual` | `input/cloudops` | `cloudops_full` |
| `check_list` | `input/cloudops` | `cloudops_full` |
| `cloudops_params`, `ztp_bundle` | `input/cloudops` | `cloudops_import`（可选） |

解析实现：`runtime/paths.resolve_slot`。

## 输出

- 仅 `chat.guidance` 事件，无持久化产物

## 注意

- **不扫描** `ProjectData/_legacy/`（历史 ZTP 样例已迁出主路径）
- 与 Step 1～6 的 `*_invoke` 区别：本动作无 `hitl.confirm_request` 后的写盘

---

巡检完毕；若用户确认材料齐全，返回主编排按 **B. 智能路由** 启动对应步骤。
