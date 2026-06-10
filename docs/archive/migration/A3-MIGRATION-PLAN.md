# a3 系统设计 → aida 移植方案（架构 + PoC）

> 背景：作业模块「规划设计」= **建模仿真 jmfz**（已落为 `guihua`，线性 5 段）+ **系统设计 a3**（`a3-intelligent-network-opening`，命令分发器 + ~20 子流水线）。
> a3 的控制流与 aida 现有 `BaseSkill.steps[]`（固定线性 DAG）根本不同，本文给出移植方案与一条命令的 PoC（`xtsj` skill）。

## 1 · 两半的形态差异

| | jmfz（建模仿真） | a3（系统设计） |
|---|---|---|
| 控制流 | 线性 5 段 DAG | **命令分发器**（菜单式，用户任意顺序触发） |
| 调度 | `steps[]` 串行 | `command_registry` → adapter（l3 / dispatch / conductor）→ ~20 子能力 |
| 子能力 | 无 | ~20 个 `offline_*_pipeline.py`（**确定性计算**：IP 分配 / 网段规则） |
| 意图 | 无（直接 start） | Step 0 NL 意图识别 → 标准命令归一化（由会话侧完成） |
| 大盘 | 七段式 | 额外有 `plane-matrix`（10+ 平面 × 状态矩阵） |

## 2 · 三堵墙与解法

| 墙 | 问题 | 解法 |
|---|---|---|
| **① 控制流** | `BaseSkill` 只能线性串边，表达不了"按命令分发、任意顺序" | **扩展 `BaseSkill` 支持 `dispatch_mode`**：`build_graph()` 生成 `START → _dispatch → (按 project["command"] 选中的 handler) → END`；每个 handler 即一个 step（`key`=命令 id）。向后兼容（默认 `dispatch_mode=False`，zhgk/guihua 零影响） |
| **② 禁 subprocess** | a3 全是 subprocess 调 offline pipeline | **照 zhgk 范式**：把 pipeline 改写为**进程内 Python 模块**（`skills/xtsj/pipelines/*.py`），由 step.run() 直接调用 —— 不 subprocess、不污染 `DEFAULT_TOOLS`、在 step 粒度被 Langfuse trace。a3 pipeline 多为纯计算，无 LLM，天然适配 |
| **③ SDUI 词汇** | `plane-matrix` 不在 25 个节点内 | **新增 `PlaneMatrix` 节点**，走三方契约（builder.py ↔ sdui.ts ↔ SduiNodeView.tsx，过 `lint_sdui_contract`） |

## 3 · 命令 ↔ step 映射（dispatch 模型）

a3 的 `sd_*` action（`sd_actions.py`）→ aida dispatch skill 的 step.key：

| a3 action | 标准命令 | aida step.key | PoC |
|---|---|---|---|
| `sd_query_inputs` | 检查输入件是否妥当 | `input_check` | ✅ 已实装 |
| `sd_step2_begin` | 地址规划（L1 批次） | `address_batch` | ⬜ 后续 |
| `sd_step2_dw_compute` | 计算带外管理地址规划 | `plane_dw_compute` | ⬜ 后续 |
| `sd_step4_interconnect` | 互联规划 | `interconnect` | ⬜ 后续 |
| `sd_lld_generate` | 生成完整 LLD | `lld_generate`（conductor 长流程 → 可做 skill-as-tool） | ⬜ 后续 |

**每条命令 = 一次 run**（共享 `work_root`，磁盘态跨 run 累积）；大盘 `PlaneMatrix` 读磁盘产物反映累积进度，与 a3 一致。会话侧菜单（SDUI Button）`post_user_message` 触发各命令。

## 4 · PoC 落地清单（`xtsj` skill）

**后端**
- `agent/skills/base.py` — `dispatch_mode` / `default_command` + `build_graph()` 分支 + `_dispatch_router()`（框架增量，向后兼容）
- `agent/skills/xtsj/` — `skill.py`（`dispatch_mode=True`）+ `steps/input_check.py` + `pipelines/input_check.py`（移植自 a3 `input_checker.py`）+ `pipelines/planes.py`（10 平面定义 + 磁盘态）+ `sdui.py`
- `agent/skills/__init__.py` — `registry.register("xtsj", ...)`（一行）
- `agent/sdui/builder.py` — `SduiPlaneMatrixNode` + `SduiPlaneCell`

**前端**
- `frontend/src/lib/sdui.ts` — `SduiPlaneMatrixNode` 类型 + 并入 union
- `frontend/src/components/sdui/SduiNodeView.tsx` — `case 'PlaneMatrix'`
- `frontend/src/routes/module.tsx` — `MODULE_TO_SKILL` 加 `design: 'xtsj'`

**A 层**
- `skills/xtsj/SKILL.md`（仓库）+ `~/.claude/skills/xtsj/SKILL.md`（部署，lint 读这份）

## 5 · 守门

- `lint_sdui_contract`：PlaneMatrix 三方一致
- `lint_skill_contract`：SKILL.md「后端节点」列 ↔ `xtsj` 业务 step.key
- 其余（`lint_tools` / `lint_runtime_contract`）**不触碰**（pipeline 走进程内模块，不进 `DEFAULT_TOOLS`）

## 6 · 分阶段（PoC 之后）

1. **PoC（本次）**：dispatch 框架 + `input_check` 一条命令 + `PlaneMatrix` 打通端到端。
2. **批量平面**：把 ~10 个平面 IP 规划 pipeline 逐个移植为 `pipelines/*.py` + 对应 step；`PlaneMatrix` 自然点亮。
3. **L1 批次**：`address_batch` 一步内按 `dispatch_tree` 顺跑多平面（一个 step 内循环调多 pipeline）。
4. **完整 LLD**：conductor 长流程做成**独立 skill** 经 skill-as-tool 唤起（符合范式「长流程走 skill-as-tool」）。
5. **意图识别**：Step 0 NL→命令 归一化放到会话侧（chat_engine / skill-as-tool），driver 侧只认标准命令。
