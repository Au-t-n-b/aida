# AIDA 评测标准 v2 ·（SKILL + 工具）

> 上承 [03 团队范式 §6](../20_架构与范式/03_团队Agent开发范式.md)（可观测 → 评测闭环）+ [METRICS.md](METRICS.md)（**测什么** · 指标定义）。
> 本文定义 **怎么算合格** —— 反「假绿」的硬原则 + 断言矩阵 + 守门。
>
> **动机**：zhgk 审视（2026-06-03）暴露 `quality=1.0` 是**假绿**。v1 四维 + 自纠率方向对，但有三个结构性漏洞，v2 用 5 条硬原则堵住。

## 0. 为什么要 v2（三个真实漏洞）

| 漏洞 | 现象 | 后果 |
|------|------|------|
| **覆盖半截** | golden 只到 step2，report_gen/distribute 永远 `pending` | 评测对后半段全盲 |
| **只量不质** | `completion_rate` 测"填了多少格"，不测"评估结论对不对" | 内容错了照样绿 |
| **阉割无感** | report_gen `MAX_LLM_CALLS=5` 砍掉 84/89 评估项 | 核心智能步骤是 stub，评测仍 1.0 |

---

## 1. 五条硬原则（每条配守门）

| # | 原则 | 规则 | 守门（怎么强制） |
|---|------|------|-----------------|
| **1** | **覆盖完整性** | 每个非 `internal` 业务 step，断言集 ≥1 条覆盖 | eval 启动校验 `断言覆盖 ⊇ skill 业务 step`，缺失 → **直接判失败**（非跳过） |
| **2** | **Step 自证** | 每个 step 把 `status` + 关键产物指标写进 `skill_result` | eval 检测"流程 done 但有业务 step ≠ completed" → 判失败 |
| **3** | **量/质分层** | L1 存在性 + L2 完整度 + L3 正确性；产 LLM 判断的 step 必须有 L3 | 断言矩阵按层标注，缺层告警 |
| **4** | **防 demo-stub** | 核心 LLM step 断言"实际处理量 == 应处理量" | 有结论数 == 评估项数；`unrecognized` 占比 ≤ 阈值 |
| **5** | **阈值区间 + 样本门槛** | 区间非等值；`min_calls=3` 不下结论（v1 保留） | 已落地 |

> 一句话：**原则 1 防漏测、原则 2 防瞒报、原则 3 防虚测、原则 4 防阉割、原则 5 防误报。**

---

## 2. SKILL 评测：断言矩阵（每个 skill 必填这张表）

以 zhgk 为样板：

| step | L1 存在性 | L2 完整度 | L3 正确性 | 防 stub |
|------|----------|----------|----------|---------|
| scene_filter | 4 过滤表 ready | `filter_summary` 行数 > 0 | 制冷/场景识别合法 | — |
| survey_build | 全量表 + 3 待办 ready | `completion_rate ≥ 45` | 抽样归类合法 | — |
| **report_gen** | 评估表 + 风险表 + 报告.docx ready | `assessment.total > 0` | 结论枚举合法 + 缺陷非空 | **有结论数 == 评估项数；`unrecognized` 占比 ≤ 0.2** |
| **report_distribute** | — | `recipients > 0` | — | `status == completed`（非 skipped） |

**端到端**：所有业务 step `completed` + 产物齐全 + golden 全段非空。

### L3 正确性落地路线（决策：规则校验先行 + 渐进 golden）

| 层 | 手段 | 何时 | zhgk 示例 |
|----|------|------|----------|
| **L3-a 规则校验** | 字段合法性：枚举值合法、必填非空、类型对、量匹配 | **立即** | 结论 ∈ {满足/不满足/无法识别/不涉及}；不满足项必有缺陷记录 |
| **L3-b golden 抽样** | 少量人工标准答案比对命中率 | 渐进（核心 step） | 10 个评估项的正确满足度，比对命中率 ≥ 阈值 |
| **L3-c LLM-as-judge** | 另一模型评判结论质量 | 远期（judge 自身要先被评测） | 暂不采用 |

---

## 3. 工具评测标准（v1 → v2）

| 维度 | v1 现状 | v2 深化 |
|------|---------|---------|
| 自纠率 ⭐ | `ok=False` 比例（`eval_tools.aggregate`） | 修正定义：真正追踪「validate 失败 → 同工具连续重试」序列，而非仅 ok=False |
| 成功率 / p50 / p95 / 热度 | ✓ | 保留 |
| **参数契约** | 无 | 新增：每工具完整 JSON Schema + `required` 准确（补 `lint_tools.py` 守门） |
| **输出契约** | 无 | 新增：`execute` 返回结构稳定、含 `ok`/`error`，可断言 |
| **副作用 dry-run** | 无 | 新增：有副作用工具默认 dry-run，评测验证「不真发」 |

基线（v1 保留）：自纠率 ≤ 0.30 · 成功率 ≥ 0.70 · p95 ≤ 5000ms · `min_calls_to_judge=3`。

---

## 4. 评测产物治理（呼应 results 堆积 300+）

- **results/ 保留策略**：每类（`zhgk-*` / `tools-*` / `deviations-*` / `cursor-*`）最近 **50** 个 + 按天滚动；超出归档或删。
- **golden 标准**：fixture 必须是「全 step `completed` + 全业务段齐全」的**真实理想态**，不得把半截固化为基线。

---

## 5. 命名契约

`execution.steps[].name` 必须 == B 层 `step.key`。
- ⚠️ 历史遗留：工作区 `skill_result_writer` 的 step4 写 `name="distribute"`，但 `step.key="report_distribute"`。eval 暂做兼容映射；**待 writer 统一**后移除映射。

---

## 6. 落地状态（本次补洞 2026-06-03）

| 项 | 状态 |
|----|------|
| report_gen 接 writer（assessment/risk/report 段 + step3 completed） | ✅ |
| report_distribute 接 writer（write_distribute + step4） | ✅ |
| eval_zhgk 扩断言（覆盖+自证+L1/L2+防stub+L3-a 规则） | ✅ |
| golden 补全为全 step completed + 全段 | ✅ |
| 命名兼容映射（distribute ↔ report_distribute） | ✅ |
| 工具自纠率修正（retry 序列检测 + retry_rate 断言） | ✅ |
| lint_tools.py（name/desc/schema 契约 + 孤儿检测 + 挂 prebuild） | ✅ |
| results 保留策略 | ⬜ 待做 |
| 工具输出契约断言 + 副作用 dry-run 验证 | ⬜ 待做 |
| L3-b golden 抽样 | ⬜ 渐进 |
