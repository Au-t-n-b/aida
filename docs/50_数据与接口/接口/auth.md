# 数据中心接口 · 5.1 认证（auth）

> 摘自 [数据中心 API 调用规范](../数据中心API调用规范.md) §5。**通用约定 / 鉴权 / 数据定位 / 标准流程配方见主文件**，本文件只列本模块逐接口入参/出参/错误码。

#### POST /api/v1/users/register — 注册账号
- **功能**：创建一个平台用户账号，用于后续登录与被分配项目角色。
- **鉴权**：无。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| username | Body | string | 是 | 登录用户名，全局唯一 |
| password | Body | string | 是 | 登录口令（服务端加密存储） |
| email | Body | string | 否 | 邮箱 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| userId | int | 新建用户 ID |
| username | string | 用户名 |

- **错误**：1001 用户名已存在。

#### POST /api/v1/users/login — 登录获取令牌
- **功能**：校验用户名口令，成功后签发 JWT 令牌，供后续管理类接口鉴权使用。
- **鉴权**：无。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| username | Body | string | 是 | 登录用户名 |
| password | Body | string | 是 | 登录口令 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| token | string | JWT 令牌，用于请求头 `Authorization: Bearer <token>` |
| expiresIn | int | 令牌有效期（秒） |
| userId | int | 当前用户 ID |

- **错误**：1002 凭证错误、1003 账号禁用。

#### GET /api/v1/users/me — 获取当前登录用户
- **功能**：返回当前 token 对应的用户信息、角色与权限点集合，用于确认登录态与前端按权限渲染。
- **鉴权**：必填。
- **入参**：无（凭请求头 token 识别）。
- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| userId | int | 用户 ID |
| username | string | 用户名 |
| email | string | 邮箱 |
| isAdmin | bool | 是否管理员 |
| globalRoles | array | 全局角色列表，元素 `{ roleCode 角色码, roleName 角色名 }` |
| projectRoles | array | 项目角色列表，元素 `{ projectId 项目ID, roleCode, roleName }` |
| permissions | string[] | 该用户拥有的权限点编码集合（如 `file:contract:upload`） |

#### DELETE /api/v1/users/{userId} — 删除用户
- **功能**：按用户 ID 删除账号；不允许删除自己。
- **鉴权**：`user:delete`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| userId | Path | int | 是 | 待删除用户 ID |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| deleted | bool | 是否删除成功 |

- **错误**：1005 不能删除自己。
