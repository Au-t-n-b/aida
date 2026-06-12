---
name: a3-subskills-orchestration
description: >
  A3 智能网络开局全流程编排：Step 0 意图识别（Claw MD，可选）→ 输入预检 → L1/L2 批次调度 或 L3 直执（互斥）
  → 可选 Conductor 一键 LLD / 融合 / ZTP。线上由 runtime subprocess 执行；Claw 只发 skill_runtime_start（sd_*）。
  关键词：地址规划 / 互联规划 / 接入规划 / 网管规划 / LLD设计 / 生成完整LLD / 融合完整LLD / ZTP / 命名替换
---

# A3 智能网络开局 · 全流程编排（subskills）

本文件是 A3 开局 Skill 体系的**唯一主编排文档**，负责流程编排、智能路由和状态管理。
所有路径均相对于 `a3-intelligent-network-opening` 根目录（`path_config.py` 所在位置）。

> **平台运行时**：Claw 发 `skill_runtime_start`（`sd_*` action + 标准命令 `text`），由 `runtime/driver.py` → `runtime/orchestrator.py` subprocess 执行；**不要**自行 shell 子脚本。  
> **Step 0**：仅当用户 NL 且无法直接映射 Section B 的 `sd_*` 时，Claw Read MD（见 `lld-intent-recognition.code1/SKILL.md` 的 Read 策略）；driver 仅校验标准命令。

**Step 2 与 Step 3 互斥**：L1/L2 走 dispatch 批次；三级叶子走 L3 直执；同一请求只走一条路径。

---

## Claw 契约（线上 runtime · 必读）

Claw **只做两件事**：

1. （可选）Step 0：用户 NL → 一行标准命令（RESOLVED / CLARIFYING / FAILED）
2. 发 `skill_runtime_start`：`action` = Section B 的 `sd_*`，`text` = 标准命令

Claw **禁止**：

- Read `subskills/{package}/SKILL.md` 后自行 shell subprocess
- Read `workflow_plan.json` / `steps.md` 后逐步执行 Conductor 步骤
- 对 L1/L2/L3/Conductor **重复 Read** 同一 MD
- 收到 driver 的 `chat.guidance` / `dashboard.patch` / `artifact.publish` 后再次编排（转述用户即可）

**快路径（跳过 Step 0，零 Read intent MD）**：

| 场景 | 动作 |
|---|---|
| 用户句与 `intent-taxonomy.md` 标准命令**精确一致**（大小写不敏感） | Section B 查表发对应 `sd_*` + `text` |
| `ProjectData/RunTime/pipeline_state.json` 有 `pending_command` | 按 HITL 卡片 `resumeAction` 续跑 |

**Claw 与 runtime 分工**：

| 用户意图 | Claw | runtime 负责 |
|---|---|---|
| 生成完整 LLD | 只发 `sd_lld_generate` | `conductor_runner` plan_run + 逐步 subprocess |
| 融合 LLD | 只发 `sd_lld_integrate` | integrate subprocess |
| 地址/互联 L1 批次 | 只发 `sd_step2_begin` 等 | `dispatch_runner` |
| 三级单命令 | 只发 `sd_step2_dw_*` 等 | L3 subprocess |
| 检查输入件 | 只发 `sd_query_inputs` | input check subprocess |

---

## A. 流程总览

| Step | 名称 | 触发关键词 / action | 核心入口 | 关键输入 → 输出 | 前置依赖 |
|---|---|---|---|---|---|
| 0 | 意图识别（可选） | 任意 NL（非快路径） | `subskills/lld-intent-recognition.code1/SKILL.md` | 用户口语 → 一行标准命令 | 无 |
| 1 | 输入预检 | 检查输入件 / `sd_query_inputs` | runtime → `a3-input-components-workflow.code1` | 007 + 资源表 → 输入件清单 | Input/ 上传 |
| 2 | L1/L2 调度 | 地址规划 / 互联规划 / `sd_step2_begin` 等 | runtime → `lld-dispatch-orchestrator.code1` | L1/L2 指令 → 各平面 A3*.xlsx | 007 + 资源表 |
| 3 | L3 直执 | 计算带外管理地址规划 / `sd_step2_dw_*` 等 | runtime → `subskills/{package}.code1/` | 单条三级命令 → 单平面产物 | 各子 Skill 自行定义 |
| 4 | Conductor/ZTP | 生成完整LLD / 融合 / ZTP / `sd_lld_*` | runtime → `a3_LLD_generate_code1/` 等 | 007 + 各平面表 → LLD / ZTP 衍生件 | 依步骤而定 |

### 执行约束

- **L3 单指令**：无全局执行顺序；用户指定任一三级命令即可 Step 3 直执。
- **L1/L2 批次**：Step 2 仅对**当前** L1/L2 按 `dispatch_tree.yaml` **批次内**串行。
- **完整 LLD**：仅「生成完整LLD设计」走 Section D；23 步由 runtime 内部完成，见 `subskills/a3_LLD_generate_code1/workflow.yaml`。

---

## B. 智能路由

收到用户指令后，按以下规则判断（NL 且非快路径时先 Step 0）：

| 用户意图 | 路由目标 | `action` | `text`（标准命令） |
|---|---|---|---|
| 冷启 / 开始开局 | Step 0 + 上传引导 | `sd_start` | — |
| 上传续跑 | 输入检查 | `sd_after_input_upload` | — |
| 查询 / 检查输入件 | Step 1 | `sd_query_inputs` | `检查输入件是否妥当` |
| L1「地址规划」 | Step 2 | `sd_step2_begin` | `地址规划` |
| L1「互联规划」 | Step 2 | `sd_step4_interconnect` | `互联规划` |
| L1「接入规划」 | Step 2 | `run_command` | `接入规划` |
| 三级叶子（带外/平面/ASN 等） | Step 3 | `sd_step2_dw_*` / `run_command` | 对应标准命令 |
| 生成完整 LLD | Section D | `sd_lld_generate` | `生成完整LLD设计` |
| 融合完整 LLD | Step 4 | `sd_lld_integrate` | `融合完整LLD设计` |
| ZTP / 灵衢 / 命名替换 | Step 4 / 3 | `sd_step6_*` 等 | 对应标准命令 |
| 防火墙互联 / 知识问答 | — | Step 0 → FAILED 固定话术 | — |
| 无法判断 | 追问 | Step 0 → CLARIFYING | choice |

### Claw 发送模板

```json
{
  "type": "chat_card_intent",
  "verb": "skill_runtime_start",
  "payload": {
    "type": "skill_runtime_start",
    "skillName": "a3-intelligent-network-opening",
    "requestId": "req-<唯一>",
    "action": "sd_step2_dw_compute",
    "text": "计算带外管理地址规划"
  }
}
```

HITL 续跑使用 `resumeAction`（如 `sd_after_input_upload`）。兼容旧 action：`start`、`run_command`、`resume_after_upload_inputs`。

---

## C. 各步骤执行模板

### Step 0：意图识别（Claw · 仅 MD · 可选）

**何时跳过**：见上文「Claw 契约 · 快路径」。

**前置检查**：无硬性文件依赖。

**执行**：按 [`lld-intent-recognition.code1/SKILL.md`](lld-intent-recognition.code1/SKILL.md) 的 **Read 策略** 读取 intent 资料，输出**一行标准命令**（RESOLVED / CLARIFYING / FAILED）。

**完成后**：发 `skill_runtime_start`，`action` 为 Section B 对应 `sd_*`（或 `run_command`），`text` = 标准命令。

---

### Step 1：输入预检

**前置检查**：
- `ProjectData/Input/` 下 007 端口连线表、项目信息收集表、001 设备信息表、004 设备位置表（均为必选）
- 缺失则 HITL 上传

**线上（Claw）**：发 `sd_query_inputs`，`text=检查输入件是否妥当`；等待 driver 返回 guidance + 大盘更新。

**离线调试（Claw 禁止照做）**：`subskills/a3-input-components-workflow.code1/scripts/offline_input_components_pipeline.py`

**完成标志**：输入件清单 status=ready；大盘 `input-slot-list` 更新。

**完成后**：引导用户发 L3 命令或 L1 批次（如「地址规划」「计算带外管理地址规划」）。

---

### Step 2：L1/L2 调度（与 Step 3 互斥）

**前置检查**：007 + 项目信息收集表就绪。

**线上（Claw）**：发 Section B 对应 action，例如 `sd_step2_begin` + `text=地址规划`；等待 `runtime/dispatch_runner.py` 返回。

**离线调试（Claw 禁止照做）**：

```bash
cd subskills/lld-dispatch-orchestrator.code1
python scripts/offline_dispatch_pipeline.py plan --intent "地址规划"
python scripts/offline_dispatch_pipeline.py run --intent "地址规划" --topology <007> --resource <资源表>
```

**完成标志**：各平面 `A3*.xlsx` 写入 `ProjectData/Output/`。

**完成后**：引导融合 LLD 或继续其他 L1/L3 命令。

---

### Step 3：L3 直执（与 Step 2 互斥）

**前置检查**：查 H 附录定位 package；各子 SKILL 自行定义输入件（runtime 侧校验）。

**线上（Claw）**：发 Section B 对应 `sd_step2_dw_*` 或 `run_command` + 标准命令 `text`；**禁止** Read `{package}/SKILL.md`。每次一条三级指令。

**离线调试（Claw 禁止照做）**：`subskills/{package}/scripts/offline_*_pipeline.py`

**完成标志**：对应平面规划表写入 Output/。

---

### Step 4：Conductor / ZTP / 融合

**融合 LLD（线上）**：`sd_lld_integrate`，`text=融合完整LLD设计`。

**生成完整 LLD（线上）**：见 Section D。

**ZTP / 灵衢 / 命名（线上）**：Section B 查表发 `sd_step6_*` 等；**禁止** Read ZTP 子 SKILL。  
**ZTP 自动补齐**：`生成ZTP*` / `生成灵衢*` 由子 pipeline `prerequisite_runner` 链式补规划表与 ZTP_LLD；`ZTP名称替换*` 由 runtime `ztp_prereq.ensure_ztp_lld` 先补 ZTP_LLD（仅需 007 + 收集表 + 004 等扫描件，见 `runtime/ztp_prereq.py`）。

---

## D. 一键生成完整 LLD

**触发**：`sd_lld_generate` / 「生成完整LLD设计」

**线上（Claw）**：

1. （可选）确认 007 + 资源表已上传：`sd_after_input_upload`
2. **直接发** `skill_runtime_start`：`action=sd_lld_generate`，`text=生成完整LLD设计`
3. 等待 driver 返回 guidance + artifact；**禁止** Read `a3_LLD_generate_code1/SKILL.md`；**禁止**读 `workflow_plan.json` 逐步执行
4. （可选）融合：`sd_lld_integrate`，`text=融合完整LLD设计`

**runtime 内部（Claw 不可见）**：`execute_conductor(mode=plan_run)` → `run_conductor_steps` 循环 subprocess → 产物写入 `ProjectData/Output/` 与 `ProjectData/Work/*/conductor/`。

**不走 Step 2 dispatch**。

```mermaid
flowchart LR
  Upload[sd_after_input_upload] --> Gen[sd_lld_generate]
  Gen --> Int[sd_lld_integrate]
```

---

## E. 状态恢复（断点续跑）

每次执行前可读 `ProjectData/RunTime/pipeline_state.json`、`ProjectData/RunTime/session_rid.json`：

| 场景 | 行为 |
|---|---|
| 缺输入件 | HITL 上传 → `sd_after_input_upload` |
| 已有 pending_command | 按 HITL 卡片 `resumeAction` 续跑 |
| 用户明确指定命令 | 以用户指令为准 |

---

## F. 环境预检

```bash
python scripts/preflight_check.py
python scripts/driver_smoke_test.py
```

检查 skill 根文件、`subskills/` 索引、command_registry 与 intent 资料是否齐全。

---

## G. 路径配置

| 常量 / 用途 | 路径 |
|---|---|
| Skill 根 | `a3-intelligent-network-opening/` |
| 输入 | `ProjectData/Input/` |
| 中间态 | `ProjectData/RunTime/` |
| 输出 | `ProjectData/Output/` |
| 业务能力库 | `subskills/*.code1/` |
| L3 索引 | `subskills/lld-dispatch-orchestrator.code1/l3_skill_index.yaml` |
| L1/L2 树 | `subskills/lld-dispatch-orchestrator.code1/dispatch_tree.yaml` |

**必需输入**：

| 文件 | autodetect 关键词 |
|---|---|
| 建模仿真输出文档007-端口连线表.xlsx | 007 / 端口连线 |
| 项目信息收集表.xlsx | 项目信息收集 / 资源 |
| 001 / 004 设备表 | 必选 |

---

## H. 附录 · L3 索引（按 L1 分组）

权威源：`subskills/lld-dispatch-orchestrator.code1/l3_skill_index.yaml`。

**地址规划** — `a3-*-dw-manage-ip-workflow.code1`、`a3-l2-l3-ip-workflow.code1`、`a3-cc-glm-ip-workflow.code1`、`a3-ywm-ip-workflow.code1`、`a3-csm-ip-workflow.code1` 等。各流水线在生成平面地址表的同时，按项目 `merge_and_save_data` 口径合并写入 `output/run_*/A3网络设备接入规划.xlsx`（sheet `网络设备接入规划`），供接入规划查询使用。

**互联规划** — `oob-interconnect-workflow.code1`。

**接入规划** — `net-dw-access-ip-workflow.code1`（读取上一步合并的 `A3网络设备接入规划.xlsx`，按 `网络平面` 过滤导出）。

**网管 / 路由** — `ccae-planner.code1`、`dme-planning.code1`、`nce-planner.code1`、`switch-mlag-planning-workflow.code1`、`a3-switch-asn-workflow.code1`。

**LLD / ZTP / 检查** — `a3_LLD_generate_code1`、`a3-generate-ztp-*`、`a3-input-components-workflow.code1`。

**命名替换** — `a3-device-naming-workflow.code1`。

**不支持 offline**：防火墙互联规划、网络地址规划知识。

---

## I. 运行时文件索引

| 文件 | 作用 |
|---|---|
| `runtime/driver.py` | 平台子进程入口 |
| `runtime/orchestrator.py` | HITL、输入检查、执行状态机 |
| `runtime/sd_actions.py` | `sd_*` → 标准命令 |
| `runtime/command_registry.py` | 命令注册 |
| `runtime/intent_router.py` | 校验 Step 0 标准命令 |
| `data/dashboard.json` | 中栏 SDUI |

**大盘节点**：`task-timeline`、`sd-art-panel`、`stepper-main`、`plane-matrix`、`input-slot-list`、`output-file-list`。

同步 subskills：`python scripts/copy_subskills.py`
