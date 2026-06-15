# contracts · CHANGELOG（契约变更记录的唯一的家）

> 每次动 `/contracts` 在此记一行：日期 + 性质（新增/破坏性升版本）+ 内容 + 影响面。

- **2026-06-14 · 纯新增（指挥人预批）**：新增 `GapSummary`，`AdjustResponse.gap` 带出未压缩基线预计完成日、主目标日与基线缺口；`PlanKpis.gap_days` 带出每个方案预计完成日相对目标日的缺口。影响面：前端 TS 类型新增可选字段，既有响应字段保持不变。
- **2026-06-13 · 纯新增（预批轻流程）**：`REPORT_SUMMARY_PATH`（`POST /api/v1/schedule/report-summary`）+ `ReportSummaryRequest/Response`——风险报告页手动生成 AI 总结；请求只包含确定性报告抬头、统计与四清单条目快照，响应只返回解释层文本和 `is_ai_generated` 标识，不参与排期计算。影响面：前端 TS 类型新增路径常量与报告总结模型。
- **2026-06-13 · 纯新增（预批轻流程）**：`EXPORT_PLAN_PATH`（`GET /api/v1/schedule/export-plan`）——正式计划版本导出为 `交付计划表.xlsx` 文件流；只新增路径常量，不新增模型形状。
- **2026-06-11 · 纯新增（预批轻流程）**：`PARSE_CHANGES_PATH`（`POST /api/v1/schedule/parse-changes`）+ `ParseChangesResponse(changes: ChangeSet, warnings: list[str])`——固定模板变更表上传后确定性解析为 `ChangeSet`，非致命问题逐条 warnings 返回；影响面：前端 TS 类型新增路径常量与响应类型，既有 `generate / adjust / commit` 不变。
- **2026-06-12 · 纯新增（预批轻流程）**：`PROJECT_DATA_PATH`（`GET /api/v1/schedule/project-data`）——服务端经导入器读取 `02_项目数据` 并返回既有 `InputBundle`；只新增路径常量，不新增模型形状。
- **2026-06-11 · 纯新增（预批轻流程）**：`CommitRequest.duration_overrides`（可选，`instance_id → 工期天数`）——选定方案后允许前端把甘特工期微调随 `/commit` 提交；后端仍只采信工期并由引擎重算日期。影响面：前端 TS 类型新增可选字段，未传时保持 T-011 行为。
- **2026-06-11 · 纯描述（轻流程）**：T-010 目录重编号后，字段来源描述的数据目录编号从 06 改为 02；无字段形状、枚举或接口语义变更，前端 TS 仅注释同步再生成。
- **2026-06-10 · v1 冻结**：初版 38 个模型（输入 14 / 输出 10 / API 与错误 14）+ 三端点 `generate / adjust / commit`。从 `01蓝图/01_业务语义` + `02_项目数据` 表头长出，字段级来源映射内嵌 description；TS 生成链就位（`generate_ts.py` + 前端 `schedule.gen.ts`，`--check` 进完成定义与同步仪式）。指挥人审定冻结。
- **2026-06-10 · 纯新增（轻流程）**：`Project.total_card_count`（可选）——规模分档改由**卡数**驱动（<1000/1000~10000/>10000），《项目规模》标签降为回退（T-009 实现；背景：真实数据标签"标准项目"对不上档名，靠映射不可泛化）。
- **2026-06-10 · 纯新增（轻流程）**：`RiskType` 增加枚举值 **「依赖未纳入」**——T-002 实证真实基线含 21 条非 FS 依赖（17 FF + 4 SS），指挥人拍板 v1 降级策略=跳过计算+逐条风险提示（T-008 实现）。`ErrorResponse.code` 描述同步更新。影响面：纯增枚举值，前端 TS 联合类型加宽，无破坏。
