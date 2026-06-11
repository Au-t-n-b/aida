---
name: zhgk
description: 智慧工勘（Skill-First · v4 意图驱动）—— 数据中心机房工勘全流程编排。支持 4 种意图：全流程工勘（建表→勘测→评估→报告）、场景建议、补充勘测、报告生成。当用户说「开始工勘 / 全流程工勘 / 生成工勘报告 / 场景建议 / 补充勘测 / 工勘审批分发 / 代际制冷 / AI评估 / 机房满足度 / 入场评估标准表 / BOQ」等时调用。
---

# 智慧工勘（zhgk）· AIDA Agent Skill v4

## 何时使用本 skill

| 用户说 | 调用场景 |
|--------|---------|
| 开始工勘 / 全流程工勘 / 跑工勘 Agent | survey_work 意图 |
| 生成工勘报告 / 出报告 / 填报告模板 | report_gen 意图 |
| 场景推荐 / 勘测场景建议 | scene_suggest 意图 |
| 补充条目 / 追加勘测项 | supplement 意图 |
| 机房 / BOQ / 评估标准表 / AI评估 / 代际制冷 / 满足度 / 风险识别 / 问题清单 | 判断上下文选合适意图 |

---

## A. 业务流程（15 个步骤 · 意图驱动）

| 步骤 | 名称 | 输入 → 输出 | 意图 | 后端节点 |
|------|------|------------|------|---------|
| 1 | 意图选择 | 用户选择工作流 | 所有 | `intent_select` |
| 2 | 场景建议生成 | 代际-制冷 → 场景推荐 | scene_suggest | `scene_suggest_run` |
| 3 | 代际制冷识别 | BOQ.xlsx → 代际-制冷标签 | survey_work/supplement/report_gen | `determine_gen` |
| 4 | 底表过滤建表 | 入场评估标准表 + 代际制冷 → 全量勘测结果表 | survey_work | `filter_build` |
| 5 | 勘测方法分流 | 全量结果表 → 现场勘测/客户反馈分组 | survey_work | `method_split` |
| 6 | 数据条目追加 | 底表数据类 → 追加到结果表 | survey_work | `data_append` |
| 7 | 勘测表确认 | 结果表摘要 → 用户确认（HITL） | survey_work | `confirm_table` |
| 8 | 任务下发 | 确认后的勘测表 → GKCLAW 任务包邮件下发（HITL） | survey_work | `task_dispatch` |
| 9 | 等待现场上传 | 空白表 → 已填写的结果表（HITL） | survey_work | `wait_survey` |
| 10 | AI 五值评估 | 结果表检查内容+结果 → AI评估列 | survey_work/report_gen | `assess` |
| 11 | 问题清单生成 | 不满足+无法识别条目 → 问题清单.xlsx | survey_work/report_gen | `issue_list` |
| 12 | 复勘检查门控 | 评估结果 → 复勘决策（HITL） | survey_work | `resurvey_gate` |
| 13 | 补充勘测处理 | 已有结果表 → 追加数据/自定义条目 | supplement | `supplement_run` |
| 14 | 报告生成 | 三件套 + 报告模板 → 工勘报告.docx | report_gen | `report_gen_run` |
| 15 | 审批与分发 | 工勘报告 → 邮件通知干系人 | report_gen | `report_distribute` |

> **preflight（环境预检）** 为内部基础设施步骤（`internal=True`），豁免契约约束，先于所有业务步骤执行。

---

## B. 端点速查

| 方法 | 路径 | 用途 |
|------|------|------|
| GET  | `/healthz`                     | 健康检查 |
| POST | `/agent/zhgk/start`            | 启动 run（body: `{intent, project_code, project_name, room_name}`） |
| GET  | `/agent/zhgk/stream/{run_id}`  | SSE 实时事件流 |
| POST | `/agent/zhgk/resume`           | HITL 续跑（body: `{run_id, payload: {choice: "..."}}`） |
| GET  | `/agent/zhgk/ui/{run_id}`      | SDUI 快照 |
| GET  | `/agent/zhgk/artifact?path=...`| 下载产物 |
| GET  | `/agent/zhgk/runs`             | 历史 run 列表 |

---

## C. 数据目录结构

```
ProjectData/
  Template/   ← 入场评估标准表.xlsx  工勘常见高风险库.xlsx  新版项目工勘报告模板.docx
  Input/      ← BOQ.xlsx（用户上传）
  Output/     ← 全量勘测结果表.xlsx  问题清单表.xlsx  风险识别结果表.xlsx  工勘报告.docx
  RunTime/    ← project_info.json（中间数据）
  Images/     ← 现场照片
```

---

## D. 意图选项

| 意图 | 触发关键词 | 适用步骤 |
|------|-----------|---------|
| survey_work | 开始工勘/全流程/建表/代际制冷/入场评估 | 步骤 3-12 |
| report_gen | 生成报告/出报告/Word 报告 | 步骤 3, 10-11, 14-15 |
| scene_suggest | 场景建议/推荐场景 | 步骤 2 |
| supplement | 补充条目/追加条目 | 步骤 3, 13 |

---

## E. HITL 交互设计

| 步骤 | HITL 类型 | 触发条件 | 用户操作 |
|------|-----------|---------|---------|
| intent_select | ChoiceCard | intent 未设置 | 选择 4 个意图之一 |
| determine_gen | ChoiceCard | BOQ 解析失败 | 手动选择代际-制冷 |
| confirm_table | ChoiceCard | 表格生成完成 | 确认 / 重新生成 |
| task_dispatch | ChoiceCard | 勘测表确认完成后 | 下发到现场 App / 跳过（本地人工勘测） |
| wait_survey | FilePicker | 等待现场回传 | 上传填好的结果表 |
| resurvey_gate | ChoiceCard | 有不满足条目 | 复勘 / 跳过 |

---

## F. 五值评估体系

| 值 | 含义 |
|----|------|
| 满足 | 检查结果完全符合标准 |
| 不满足 | 检查结果明确不符合标准 |
| 不涉及 | 该项在当前场景不适用 |
| 未勘测 | 检查结果为空（系统自动标记）|
| 无法识别 | 信息不足，无法判断 |

---

## G. 故障排查

| 现象 | 处理 |
|------|------|
| `SS-TF-E-001` 底表文件不存在 | 提供 `ProjectData/Template/入场评估标准表.xlsx` |
| `SS-BP-E-003` 无法推断代际制冷 | HITL ChoiceCard 手动指定 |
| `SS-AE-E-001` LLM 评估超时 | 检查网络，重试 |
| `SS-RB-E-001` 报告模板不存在 | 提供 `ProjectData/Template/新版项目工勘报告模板.docx` |
