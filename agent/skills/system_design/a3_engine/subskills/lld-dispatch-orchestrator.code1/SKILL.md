---
name: lld-dispatch-orchestrator
description: LLD 一二级指令离线调度：按 dispatch_tree 展开 L1/L2，串行 subprocess 各三级 skill。
disable-model-invocation: true
metadata:
  entrypoint: scripts/offline_dispatch_pipeline.py
  dispatch_tree: dispatch_tree.yaml
  skill_registry: skill_registry.yaml
  l3_skill_index: l3_skill_index.yaml
---
> 本文件是 a3-intelligent-network-opening 主 Skill 的子指令（Step 2/5），由 [subskills/SKILL.md](../SKILL.md) 在 **L1/L2 路由命中** 时调用。
> 与 Step 3（三级直执）**互斥**：三级叶子命令不经过本 Skill；本 Skill 的 `run` 阶段内部 subprocess 各 L3 skill，主 Skill 无需再进入 Step 3。

# LLD 一二级指令调度 · Step 2

## 概述

基于 `dispatch_tree.yaml` 将 L1/L2 标准指令展开为可执行的 subprocess 任务序列：读 tree 做 L1→L2→下级指令映射，按 `l3_skill_index.yaml` 拼装 CLI，按 `skill_registry.yaml` 处理串行与 `pass_prior` 前置产物传递。

调度层**只负责指令展开与 subprocess 编排**；输入件探测、sheet 选择、层位判定、业务逻辑等均由各三级 skill 自行实现。

**本 Skill 替代主 Skill 直调 Step 3**：L1/L2 请求的全部 L3 执行均在 `run` 阶段内部完成。

## 触发条件

- subskills/SKILL.md Section B 路由命中 **L1** 指令（如「地址规划」「互联规划」「接入规划」）
- 或 **L2** 指令（如「业务面地址规划」「网络互联规划」「ZTP开局」「命名替换」）
- **禁止入口**：三级叶子命令（如「计算业务面地址规划」）→ 应走主 Skill Step 3

## 前置要求

- 本 skill 根目录下配置文件齐全：`dispatch_tree.yaml`、`skill_registry.yaml`、`l3_skill_index.yaml`、`intent-taxonomy.md`
- Step 0 已产出 L1 或 L2 标准命令
- 工作目录在 skill 根或 cwd 下
- `--topology` / `--resource` 为**可选**透传；不传时子 skill 自行探测（CLI 中不含路径参数）

## 执行

```bash
pip install -r requirements.txt

# 查看 L1/L2 树（可选）
python scripts/offline_dispatch_pipeline.py list

# 预览调度计划（stdout JSON，不落盘）
python scripts/offline_dispatch_pipeline.py plan \
  --intent "<L1或L2标准命令>" \
  [--topology PATH] [--resource PATH] [--out-dir output]

# 执行批次（内存展开 + subprocess 各 L3 skill）
python scripts/offline_dispatch_pipeline.py run \
  --intent "<L1或L2标准命令>" \
  [--topology PATH] [--resource PATH] [--out-dir output] [--dry-run] [--keep-going]

# 校验配置（可选）
python scripts/validate_dispatch_tree.py
python scripts/validate_dispatch_config.py
```

**run 内存展开**：`run --intent` 在内存中展开 task 元数据，并在执行每个 task 前**动态拼装 CLI**（含 `pass_prior`、`access-plan` 等）；`plan` 输出的 `cli` 仅为静态预览。subprocess 使用绝对路径调用脚本与 `--out-dir`。

## 输出

| 文件 | 位置 | 说明 |
|---|---|---|
| `A3*.xlsx` | `output/` 或各子 skill out-dir | 各 L3 task 产物 |

## pass_prior 与特殊策略

| 策略 / 规则 | 行为 |
|---|---|
| `pass_prior: [connect, access]` | 互联规划 L2：run 时扫描 out-dir 已有互联/接入产物并注入 CLI |
| `requires_access_plan: true` | 接入规划 L3：run 时扫描 `A3网络设备接入规划.xlsx` 注入 `--access-plan` |
| `nested_workflow` | 生成/融合 LLD 走 conductor（`a3_LLD_generate_code1`），**不使用** tree 下级节点名；主 Skill 应直接路由 Step 4 |
| `unsupported` | plan 时跳过并记录 note（如防火墙互联） |
| `l2_without_offline` | L1 展开时跳过（查询类、知识问答等） |
| 命名替换 L1/L2 | 五条 L2 各映射 `a3-device-naming-workflow.code1` 子命令 |

**当前限制**：

- 不做 007 sheet 门控、不做层位/网关推断（互联 `--layer` 见 `l3_skill_index.default_layer`）
- `pass_prior` / 接入 `--access-plan` 在 **run 时**按 `out-dir` 扫描注入；若对应文件尚不存在则不带 flag
- 输入文件请放在本 skill cwd 或依赖子 skill autodetect

## 配置参考

### 配置文件职责

| 文件 | 职责 |
|------|------|
| `dispatch_tree.yaml` | L1→L2→下级指令（仅标准指令名） |
| `skill_registry.yaml` | L2 策略：children / direct / nested_workflow / unsupported；pass_prior |
| `l3_skill_index.yaml` | 三级指令 → package / entrypoint / args_style |
| `intent-taxonomy.md` | 指令词汇表（validate 参照） |

### L2 策略说明

| strategy | 行为 |
|----------|------|
| `children` | 读 tree 下级列表，按序 subprocess 各三级 skill |
| `direct` | tree 为空或无 children 时，直接调用指定 skill |
| `nested_workflow` | 调用 conductor（如 LLD 生成/融合）；忽略 tree 子节点 |
| `unsupported` | plan 时跳过并记录 note |

### 调度全链路

```
L1/L2 指令
    ↓ run --intent（内存展开 task 元数据）
    ↓ 每 task 前动态 resolve_run_cli，内部 subprocess L3 skill
各三级 workflow skill 产物（A3*.xlsx）
```

### plan 参数

| 参数 | 说明 |
|------|------|
| `--intent` | L1 或 L2 标准指令名（必填） |
| `--topology` | 可选，透传至子 skill CLI |
| `--resource` | 可选，透传至子 skill CLI |
| `--out-dir` | 调度输出目录，默认 `output/` |

## 依赖

- `PyYAML>=6.0`（见 `requirements.txt`）

## 完成后

返回主 Skill [subskills/SKILL.md](../SKILL.md)：

1. 展示调度摘要（task 数、成功/跳过/失败、产物路径）
2. 引导用户下一步（如 L2 地址规划完成后提示「是否继续互联规划？」）
3. **主 Skill 不进入 Step 3**（L3 已在本 Skill run 阶段完成）

---

本步骤执行完毕，返回主编排 [subskills/SKILL.md](../SKILL.md) 继续后续流程。
