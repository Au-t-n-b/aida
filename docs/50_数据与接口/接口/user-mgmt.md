# 数据中心接口 · 5.7 配置中心-人员（user-mgmt）

> 摘自 [数据中心 API 调用规范](../数据中心API调用规范.md) §5。**通用约定 / 鉴权 / 数据定位 / 标准流程配方见主文件**，本文件只列本模块逐接口入参/出参/错误码。

#### GET /api/v1/user-mgmt — 人员列表
- **功能**：分页查询平台用户，支持关键词与状态过滤；每条含该用户的项目角色。
- **鉴权**：`user:list`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| keyword | Query | string | 否 | 用户名/邮箱关键词 |
| status | Query | int | 否 | 状态：1 启用 / 0 禁用 |
| page | Query | int | 否 | 页码，默认 1 |
| pageSize | Query | int | 否 | 每页条数，默认 20，上限 100 |

- **出参**（`list[]` 元素，外层含 `total`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| userId | int | 用户 ID |
| username | string | 用户名 |
| email | string | 邮箱 |
| status | int | 状态：1 启用 / 0 禁用 |
| lastLoginAt | string | 最后登录时间 |
| createdAt | string | 创建时间 |
| updatedAt | string | 更新时间 |
| projectRoles | array | 项目角色，元素 `{ projectId 项目ID, projectName 项目名, roleCode 角色码, roleName 角色名 }` |

#### GET /api/v1/user-mgmt/{userId} — 人员详情
- **功能**：按 ID 返回用户信息及其项目角色。
- **鉴权**：`user:read`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| userId | Path | int | 是 | 用户 ID |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| userId | int | 用户 ID |
| username | string | 用户名 |
| email | string | 邮箱 |
| status | int | 状态：1 启用 / 0 禁用 |
| lastLoginAt | string | 最后登录时间 |
| createdAt | string | 创建时间 |
| updatedAt | string | 更新时间 |
| projectRoles | array | 项目角色，元素 `{ projectId, projectName, roleCode, roleName }` |

#### POST /api/v1/user-mgmt — 新建人员
- **功能**：创建平台用户账号。
- **鉴权**：`user:create`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| username | Body | string | 是 | 登录用户名，全局唯一 |
| password | Body | string | 是 | 登录口令 |
| email | Body | string | 否 | 邮箱 |
| status | Body | int | 否 | 状态：1 启用 / 0 禁用，默认 1 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| userId | int | 新建用户 ID |
| username | string | 用户名 |
| email | string | 邮箱 |
| status | int | 状态 |
| lastLoginAt | string | 最后登录时间（新建为 null） |
| createdAt | string | 创建时间 |
| updatedAt | string | 更新时间 |
| projectRoles | array | 项目角色（新建为空数组） |

- **错误**：1001 用户名已存在。

#### PUT /api/v1/user-mgmt/{userId} — 更新人员
- **功能**：修改用户邮箱 / 启用状态。
- **鉴权**：`user:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| userId | Path | int | 是 | 用户 ID |
| email | Body | string | 否 | 邮箱 |
| status | Body | int | 否 | 状态：1 启用 / 0 禁用 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| userId | int | 用户 ID |
| username | string | 用户名 |
| email | string | 邮箱 |
| status | int | 状态 |
| lastLoginAt | string | 最后登录时间 |
| createdAt | string | 创建时间 |
| updatedAt | string | 更新时间 |
| projectRoles | array | 项目角色 |

#### DELETE /api/v1/user-mgmt/{userId} — 删除人员
- **功能**：删除指定用户（不可删自己）。
- **鉴权**：`user:delete`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| userId | Path | int | 是 | 用户 ID |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| deleted | bool | 是否删除成功 |

- **错误**：1004 用户不存在、1005 不能删除自己。
