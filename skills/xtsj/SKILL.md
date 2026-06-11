---
name: xtsj
description: 系统设计（a3 智能网络开局）—— 命令分发式编排器。当用户说「系统设计 / 网络开局 / 地址规划 / 互联规划 / LLD 生成 / 检查输入件 / ZTP 配置 / 设备命名」，或者描述中包含「CSM / CC-GLM / CC-YBM / CPM-LQ / DW 管理 / GCM / L2/L3 互联 / 开局 LLD / ZTP cfg / ZTP lld / IP 规划 / ASN 分配 / 网络平面 / 计算面 / 存储面」等术语时调用本 skill。与 zhgk/guihua 线性流水线不同，本 skill 是命令分发模式（dispatch_mode=True）：用户按需触发任一命令（如 input_check / address_plan），每条命令对应一个 step handler，多条命令可任意顺序多次执行。基础命令 PoC 实装 input_check；后续 10+ 子能力按 A3-MIGRATION-PLAN §3 逐步追加。
---

# 系统设计（xtsj）· AIDA Agent Skill

本 skill 是 **AIDA 项目** `a3-intelligent-network-opening` 业务逻辑的 Claude Code 表层。
真正的执行由 `D:\aida\agent\` 下的 LangGraph + FastAPI 后端完成。

> **架构模式**：dispatch（菜单式），区别于 zhgk / guihua 的线性 DAG。
> 每次 start 请求携带 `command` 字段，后端按命令 key 路由到对应 step handler。

---

## 何时使用本 skill

1. **直接触发关键词**：系统设计 / 网络开局 / 地址规划 / LLD 生成 / 检查输入件 / ZTP 配置 / 设备命名
2. **平面 / 子系统名称**：CSM / CC-GLM / CC-YBM / CPM-LQ / GCM / DW 管理 / L2 互联 / L3 互联
3. **输入件状态查询**：「输入件是否齐备」/ 「检查建模仿真产物」/ 「001/004/007 文件在哪」
4. **LLD 场景**：「生成完整 LLD」/ 「dispatch LLD」/ 「骨架 LLD 合并」

---

## A. 已实装命令（后端节点）

| 命令 key | 中文 | 后端节点 |
|---|---|---|
| `input_check` | 检查输入件 | `input_check` |
| `address_plan` | 地址批规划（CSM/CC-GLM/CC-YBM/CPM-LQ） | `address_plan` |

## A-2. 路线图（待追加命令）

| 命令 key | 中文 | 对应 a3 子能力 |
|---|---|---|
| `address_plan` | 地址批规划 | CSM / CC-GLM / CC-YBM / CPM-LQ |
| `interconnect` | 互联规划 | L2/L3/OOB 互联 |
| `lld_generate` | LLD 生成 | 骨架 + 融合 |
| `device_naming` | 设备命名 | a3-device-naming-workflow |
| `switch_asn` | 交换机 ASN 分配 | a3-switch-asn-workflow |
| `ztp_cfg` | ZTP 配置文件生成 | a3-generate-ztp-cfg-workflow |
| `ztp_lld` | ZTP LLD 生成 | a3-generate-ztp-lld-workflow |

---

## B. HTTP 端点表

| 方法 | 路径 | 用途 |
|---|---|---|
| GET  | `/healthz`                          | 健康检查 + LLM 配置 |
| POST | `/agent/xtsj/start`                 | 启动命令（body: `{command, project_name}`） |
| GET  | `/agent/xtsj/stream/{run_id}`       | SSE 事件流（`sdui` / `done` / `error`） |
| POST | `/agent/xtsj/resume`                | HITL 续跑（body: `{run_id, payload}`） |
| GET  | `/agent/xtsj/ui/{run_id}`           | 已完成 run 的最终 SDUI 快照 |
| GET  | `/agent/xtsj/status/{run_id}`       | 状态快照 |
| GET  | `/agent/xtsj/artifact?path=...`     | 下载产物 |

---

## C. 执行规范

### C-1. 触发方式

```python
POST /agent/xtsj/start
{
  "command": "input_check",          # 命令 key（见 A 表）
  "project_name": "系统设计 · 智能网络开局"
}
```

若不带 `command`，默认执行 `input_check`。

### C-2. 命令别名（自然语言 → 命令 key）

| 用户说 | 路由到 |
|---|---|
| 检查输入件是否妥当 / sd_query_inputs | `input_check` |
| 地址规划 / 地址批规划 / IP规划 / sd_batch_ip | `address_plan` |
| 生成完整 LLD / 一键 LLD | `lld_generate` |
| 设备命名 / 命名规则 | `device_naming` |

归一化逻辑在 `XtsjSkill.initial_project()`（`SD_TO_COMMAND` 映射表）。

### C-3. 多命令工作流

系统设计通常需要按顺序执行多条命令（先检查输入件→再地址规划→再LLD生成）。
每条命令是独立的 run（独立 run_id）；前端展示每个 run 的结果，用户逐步推进。

---

## D. SDUI 组件表（前后端三方契约）

| 组件 type | 用途 | 所属命令 |
|---|---|---|
| `Header` | 标题 + CTA 按钮 | 全命令通用 |
| `PlaneMatrix` | 网络平面状态矩阵（行 = 平面，列 = 状态） | input_check / address_plan |
| `Card(tone=warning)` | 缺件提示 | input_check |
| `Card(tone=success)` | 齐备提示 | input_check |
| `ArtifactGrid` | 产物文件下载 | 全命令通用 |
| `Text` | 说明文本 | 全命令通用 |

---

## E. 工作区路径

| 内容 | 路径 |
|---|---|
| 本 skill | `~/.claude/skills/xtsj/SKILL.md` |
| 后端 skill 包 | `D:\aida\agent\skills\xtsj\` |
| 工作区（可通过 XTSJ_ROOT 覆盖） | `~/.nanobot/workspace/skills/a3-intelligent-network-opening` |
| 输入件目录 | `{work_root}/ProjectData/Input/` |
| 移植方案 | `docs/archive/migration/A3-MIGRATION-PLAN.md`（已归档） |
