# 12_输出文件 · 交付计划表导出说明

## 生成物边界

- `交付计划表.xlsx` 是系统生成物，由 `GET /api/v1/schedule/export-plan` 按正式 `PlanResult` 版本覆盖生成，请勿手改。
- 当前导出只消费已入库正式版本：可传 `plan_id + version` 指定版本；不传时导出最近一次正式计划版本。
- 导出逻辑不写项目实例常量；项目编号、场景、活动、日期、管理单元、队伍等均来自已保存的 `/contracts` 快照。

## 字段映射表

| Excel变量 | md字段 | 当前来源 | 留空/待定说明 |
|---|---|---|---|
| ID | 记录ID | `PlanResult.plan_id + version + ScheduledActivity.instance_id` | - |
| TODO_ID | 待办ID | - | 待业务定义待办系统关联规则 |
| SERIAL_NUMBER | 序号 | 导出时按 `PlanResult.activities` 顺序编号 | - |
| ACTIVITY_ID | 活动ID | `ScheduledActivity.activity_id` | - |
| ACTIVITY_NAME | 活动名称 | `ScheduledActivity.activity_name` | - |
| TASK_RANK | 任务层级 | `ScheduledActivity.scope_ref.scope` | - |
| PARENT_ID | 父任务ID | - | 当前契约无父子任务层级 |
| PROJECT_ID | 项目编号 | `InputBundle.project.project_id` | - |
| INSTRUCTION | 指令 | - | 待业务定义执行指令生成规则 |
| FORMAT_INSTRUCTION | 格式化指令 | - | 待业务定义格式化指令规则 |
| SRC_AGENT | 源角色 | - | 待业务定义 agent/角色口径 |
| TARGET_AGENT | 目标角色 | - | 待业务定义 agent/角色口径 |
| START_DATE | 计划开始时间 | `ScheduledActivity.start_date` | - |
| END_DATE | 计划结束时间 | `ScheduledActivity.end_date` | - |
| ACTUAL_START_DATE | 实际开始时间 | - | 排期结果不含实际执行回填 |
| ACTUAL_END_DATE | 实际结束时间 | - | 排期结果不含实际执行回填 |
| STATUS | 状态 | 固定派生：出现在正式 `PlanResult` 中即 `已排期` | - |
| PROCESS | 进度 | - | 当前契约无执行进度 |
| PRINCIPAL | 责任人 | 活动模板 `Activity.responsibility`，无则用 `ScheduledActivity.team_id` | - |
| PRINCIPAL_COMPANY | 责任人公司 | - | 当前契约无公司字段 |
| SCENARIO | 场景 | `InputBundle.project.scene` | 无场景时留空 |
| CREATED_BY | 创建人 | - | 当前契约无创建人 |
| CREATION_DATE | 创建时间 | - | 当前契约无创建时间 |
| LAST_UPDATE_BY | 最后更新人 | - | 当前契约无最后更新人 |
| LAST_UPDATE_DATE | 最后更新时间 | - | 当前契约无最后更新时间 |
| group_id | 分组ID | `ScheduledActivity.scope_ref.ref_id`，项目级用 `project_id` | - |
| RAW_EQUIPMENT_LIST | 原始设备列表 | - | 当前契约未把设备清单挂到活动实例 |
| TASK_COMMENT | 任务备注 | 活动模板 `Activity.note` | 无备注时留空 |
| MANAGEMENT_UNIT | 管理单元 | `ScheduledActivity.scope_ref.ref_id`，项目级用 `project_id` | - |
| OWNER | 所有人 | `ScheduledActivity.team_id`，无则同 `PRINCIPAL` | - |
| MANUAL_PROCESS | 人工进度 | - | 当前契约无人工进度 |
| REAL_MANAGEMENT_UNIT | 实际管理单元 | - | 排期结果不含实际执行管理单元回填 |

## 留空清单

当前留空列为：`TODO_ID`、`PARENT_ID`、`INSTRUCTION`、`FORMAT_INSTRUCTION`、`SRC_AGENT`、`TARGET_AGENT`、`ACTUAL_START_DATE`、`ACTUAL_END_DATE`、`PROCESS`、`PRINCIPAL_COMPANY`、`CREATED_BY`、`CREATION_DATE`、`LAST_UPDATE_BY`、`LAST_UPDATE_DATE`、`RAW_EQUIPMENT_LIST`、`MANUAL_PROCESS`、`REAL_MANAGEMENT_UNIT`。

这些列的业务口径已同步到仓根 `待业务确认.md`，拿到答案后再补映射，不在导出器里猜。
