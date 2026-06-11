# 数据中心接口 · 5.5 数据血缘（lineage）

> 摘自 [数据中心 API 调用规范](../数据中心API调用规范.md) §5。**通用约定 / 鉴权 / 数据定位 / 标准流程配方见主文件**，本文件只列本模块逐接口入参/出参/错误码。

#### GET /api/v1/file-lineage — 查询文件血缘
- **功能**：以某文件为起点，按方向与深度查询其上下游加工/引用关系，返回血缘图（节点 + 边），用于追溯来源与影响分析。
- **鉴权**：`lineage:read`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| fileId | Query | int | 是 | 起点文件 ID |
| direction | Query | string | 否 | 方向：`up`(上游)/`down`(下游)/`both`(双向)，默认 both |
| depth | Query | int | 否 | 追溯深度，1~10，默认 1 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| nodes | array | 血缘节点，元素 `{ fileId 文件ID, fileLogicalName 文件逻辑名 }` |
| edges | array | 血缘边，元素 `{ upstreamId 上游文件ID, downstreamId 下游文件ID, relation 关系 }` |

> `relation` 取值：`derived_from`（下游由上游加工而来）/ `referenced_by`（被引用）。
