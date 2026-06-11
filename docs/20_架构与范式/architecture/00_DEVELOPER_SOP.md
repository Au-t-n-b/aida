# 开发者 SOP（Domain Developer）

> **角色**：在一张 TASK 的「修改范围」护栏内，用对话生成精准实现一个模块。**越界要走 RFC，不自己拓宽边界。**
> **铁律**：只做 TASK 列出的事；缺跨模块接口 → Mock + RFC，不伪造、不跨界、不空等。
> **四条工作流**：D1 领 TASK 开发 · D2 阻碍 RFC · D3 pull 同步 · D4 PR 自检。
> **单模块工程做法**（A+B 双层 / BaseStep / HITL / SDUI / 评测）以 [`START_HERE.md`](../../10_快速开始/START_HERE.md) 为准——本 SOP 只管「在团队护栏内怎么协同」。

---

## Workflow D1 · 领 TASK 并开发

1. **读 TASK**（手工通读，别让 AI 代读）：理解 [修改范围 / 红线 / 验收 / 依赖]。不清楚就找架构师，别猜。
2. **标准起手式** —— 让 AI 进入护栏（@ 引用两张地图 + TASK）：

   ```text
   先读以下三份了解全局与边界：
   - @docs/architecture/01_system_architecture.md
   - @docs/architecture/02_module_boundaries.md
   - @docs/architecture/tasks/TASK_<名>.md

   据 TASK 子任务 [3.x] 实现 <功能>。严格限制：
   - 只新建/修改 TASK §1 列出的文件；高冲突文件（注册表/module.tsx/modules-data.ts）只在分配行追加
   - 不碰 02 §5 红线区（main.py/graph.py/base.py/前端通用件）；需要碰就停下告诉我走 RFC
   - LLM 走 ctx.invoke_llm，工具走 ctx.call_tool，外发走 mailer/notifier（不裸调）
   - 不 import 其它业务场景 Skill（zhgk/guihua/xtsj）
   ```

3. **迭代**：每轮重新 `@TASK`，防止多轮对话里 AI 逐渐突破边界。
4. **建骨架照清单**：复制 `agent/skills/_template/` → `<id>/`，按 [START_HERE §4](../../10_快速开始/START_HERE.md) 填。
5. **自测**：逐条对 TASK §3 验收；`git diff --name-only` 确认只动了允许的文件。

---

## Workflow D2 · 阻碍处理（缺跨模块接口 → RFC）

**触发**：开发中需要一个**别的模块 / 底座**没提供的接口或能力。

1. **确认确实没有**：在 [02 §2/§3](02_module_boundaries.md) + `base.py` 钩子全集里搜一遍。
2. **不伪造、不跨界**：用 Mock 占位保持自己的模块可跑——

   ```python
   # TODO [Wait for RFC]: <接口名> 尚未批准，暂用 Mock
   result = {"status": "mock", "items": []}   # RFC_<日期>_<接口>.md
   ```

3. **写 RFC**：`rfc/RFC_<日期>_<接口>.md`，提交并通知架构师（见模板）。
4. **继续干别的**：不要空等——用 Mock 完成本模块其余部分。

### RFC 模板（`rfc/RFC_<日期>_<接口>.md`）

```markdown
# RFC_<YYYY-MM-DD>_<接口名>
> 开发者：<名>　模块：<id>　阻塞子任务：TASK_<名> §3.x

## 背景
做 <子任务> 时需要 <能力>，现有 02 §2/§3 与 base 钩子都没有。

## 申请的接口契约
- 名称 / 签名：<fn(args) -> ret>
- 归属：<通用底座 base/tools（高频复用） | 模块内（一次性）>
- 入参 / 出参 / 错误模式：<...>

## 占位实现
当前用 Mock：<片段>，待批准后替换。
```

> **RFC vs 直接改底座**：你**不能**自己改 `base.py`/`main.py`（§5 红线）。RFC 是把「我需要动底座」的决定权交回架构师；批准后由架构师改底座并落 ADR。

---

## Workflow D3 · 代码同步（git pull 后的影响评估）

**触发**：`git pull` 之后。**问题**：别人合入的改动会不会影响我当前 TASK？

1. **看合了什么**：`git log --oneline -N`；`git diff HEAD~N..HEAD --stat`。
2. **对照边界**：变更文件落在哪个模块 / 是否动了 [02 §4 高冲突文件](02_module_boundaries.md) / 是否改了我依赖的接口 / 是否改了两张地图。
3. **决策**：

   | 情况 | 动作 |
   |------|------|
   | 变更与我模块无关 | 继续 |
   | 我依赖的接口签名变了 | 更新我的调用 |
   | 两张地图被更新 | 重读相关段，对齐新边界 |
   | 高冲突文件被别人改了我也要改的行 | 找架构师统一合并，别硬覆盖 |
   | 出现不属于任何模块的新文件 | 通知架构师（可能要登记/跑 Workflow C） |

---

## Workflow D4 · 提交 PR 与修复

**触发**：所有验收通过，或 PR 被打回。

1. **本地跑全套守门**（与架构师 Workflow B 同一套 —— 本地绿才提）：

   ```bash
   cd D:/aida
   agent/.venv/Scripts/python agent/scripts/lint_no_naked_llm.py
   agent/.venv/Scripts/python agent/scripts/lint_no_naked_send.py
   agent/.venv/Scripts/python agent/scripts/lint_skill_contract.py
   agent/.venv/Scripts/python agent/scripts/lint_sdui_contract.py
   agent/.venv/Scripts/python agent/scripts/lint_runtime_contract.py
   agent/.venv/Scripts/python agent/scripts/lint_tools.py
   agent/.venv/Scripts/python agent/scripts/lint_module_boundaries.py
   cd frontend && npm run typecheck   # 碰了前端就跑
   ```

2. **自查清单**：
   - [ ] `git diff --name-only` ⊆ TASK §1 修改范围
   - [ ] 高冲突文件只在分配行改动
   - [ ] 没有残留 `# TODO [Wait for RFC]`（除非对应 RFC 仍未批）
   - [ ] 没有 `console.log` / 调试打印 / 裸 LLM / 裸外发
   - [ ] TASK §3 每条 AC 已逐条验证
   - [ ] 碰了挂 `@ts-nocheck` 的旧前端文件 → 优先去掉 nocheck 补类型（AGENTS.md 前端规范）
3. **提交**：commit message `[<id>] 动词 + 内容`。
4. **被打回**：从审查报告逐条提取违规 → 修 → 重跑守门 → 再提。

---

## 制止话术（AI 越界时立即打断）

多轮对话里 AI 容易逐渐突破边界。发现越界**立刻**用以下话术，不要接受：

| 现象 | 话术 |
|------|------|
| 改了 TASK 范围外的文件 | 「停下。你修改了 `<文件>`，它不在 TASK §1 修改范围内。撤回，只改 [3.x] 列出的文件。」 |
| 改了红线底座 | 「停下。`<文件>` 是 02 §5 红线区。不要改它——告诉我缺什么能力，我走 RFC。」 |
| 横向 import 别的模块 | 「停下。不要 import `agent.skills.<其它模块>`。模块间零依赖，共享走 base/数据中心目录。」 |
| 裸调 LLM / 外发 | 「停下。LLM 走 `ctx.invoke_llm`，外发走 `mailer`。不要裸 import。」 |
| 伪造不存在的接口 | 「停下。那个接口不存在。用 Mock 占位并生成 RFC，别假装它能用。」 |

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-07 | 初版：D1–D4 + RFC 模板 + 制止话术 |
