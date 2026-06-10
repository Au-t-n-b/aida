# 数据中心接口 · 5.10 运维中心-审计（audit）

> 摘自 [数据中心 API 调用规范](../数据中心API调用规范.md) §5。**通用约定 / 鉴权 / 数据定位 / 标准流程配方见主文件**，本文件只列本模块逐接口入参/出参/错误码。

#### GET /api/v1/audit-logs — 审计日志查询
- **功能**：分页查询系统操作审计记录（谁、在哪个项目、做了什么、何时），用于追溯与合规。
- **鉴权**：`audit:read`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| userId | Query | int | 否 | 按操作人用户 ID 过滤 |
| projectId | Query | int | 否 | 按项目过滤 |
| action | Query | string | 否 | 按动作过滤（如 upload_file、create_skill） |
| startTime | Query | string | 否 | 起始时间（ISO8601，含） |
| endTime | Query | string | 否 | 截止时间（ISO8601，含） |
| page | Query | int | 否 | 页码 |
| pageSize | Query | int | 否 | 每页条数 |

- **出参**（`list[]` 元素，外层含 `total`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 日志 ID |
| userId | int | 操作人用户 ID |
| projectId | int | 关联项目 ID |
| action | string | 动作（如 upload_file、approve_project） |
| targetType | string | 操作对象类型（如 file、project、skill） |
| targetId | string | 操作对象 ID |
| detail | object | 操作明细（JSON） |
| createdAt | string | 操作时间 |

---
