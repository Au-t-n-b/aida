# Architecture Decision Records (ADR)

> **团队范式规范 2「能力资产化·定制回流」的载体**（见 `docs/03_团队Agent开发范式.md`）。
> 记录**非显然**的架构/技术决策，供复盘、跨项目复用、把高频定制回流成底座能力。

## 何时写 ADR

**要写**：
- 改了通用底座（`llm.py` / `BaseSkill` / `Tool` / checkpointer / `mailer` …）且做法非显然；
- 选型决策（框架 / 库 / 架构形态）；
- 推翻了之前的做法（含修 bug 时改变了机制）；
- 任何"为什么这么做"未来会被反复追问的决策。

**不写**：显然的、能直接从代码读出的、纯实现细节。

## 编号与命名

`NNNN-kebab-title.md`，4 位递增（`0001-…`）。一个决策一个文件，不回头改已 Accepted 的正文——要变就开新 ADR 并把旧的标 `Superseded by NNNN`。

## 模板

```markdown
# NNNN. <决策标题>

- **状态**: Proposed | Accepted | Superseded by NNNN | Deprecated
- **日期**: YYYY-MM-DD
- **相关**: <锚点文件 / PR / 上游 ADR>

## 背景（Context）
是什么问题、什么约束逼出这个决策。

## 考虑的选项（Options）
A. … （优劣）
B. … （优劣）

## 决策（Decision）
选了哪个、为什么。

## 后果（Consequences）
- 正面：
- 负面 / 代价：
- 后续 / 触发回流：什么条件下应重新评估或回流底座。
```

## 状态流转

`Proposed`（提议讨论）→ `Accepted`（已采纳并落地）→ `Superseded by NNNN`（被新决策取代）/ `Deprecated`（不再适用）。

## 复盘节奏

定期审视本目录：**高频出现的同类定制 → 回流成底座能力**（缺能力→加 Tool/Step，呼应 `01_AI智能化系统架构梳理` §7.3 Agent 闭环）。每个 Skill 交付后回填一次。

## 索引

| # | 决策 | 状态 | 日期 |
|---|---|---|---|
| [0001](0001-resume-soft-interrupt-rerun.md) | HITL resume 用「软中断重跑（新 thread_id）」 | Accepted | 2026-06-03 |
| [0002](0002-frontend-vite-over-sync-from-next.md) | 前端以 vite 版为唯一真相，弃用 sync:from-next | Accepted | 2026-06-03 |
| [0003](0003-unified-outbound-layer.md) | 统一外发出口：mailer + notifier，lint 守门 | Accepted | 2026-06-03 |
| [0004](0004-skill-contract-lint.md) | SKILL.md ↔ steps 契约守门（lint_skill_contract） | Accepted | 2026-06-03 |
