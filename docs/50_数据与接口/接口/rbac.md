# 数据中心接口 · 5.8 配置中心-角色与权限（rbac）

> 摘自 [数据中心 API 调用规范](../数据中心API调用规范.md) §5。**通用约定 / 鉴权 / 数据定位 / 标准流程配方见主文件**，本文件只列本模块逐接口入参/出参/错误码。

#### GET /api/v1/roles — 角色列表
- **功能**：查询全部角色及其用户数与权限点，支持关键词过滤。
- **鉴权**：`role:list`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| keyword | Query | string | 否 | 角色名/编码关键词 |

- **出参**（`list[]` 元素）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 角色 ID |
| roleCode | string | 角色编码（稳定码） |
| roleName | string | 角色名称 |
| description | string | 描述 |
| userCount | int | 该角色下的用户数 |
| permissions | array | 该角色拥有的权限点列表（元素含 permissionCode 等） |

#### POST /api/v1/roles — 新建角色
- **功能**：创建一个角色定义。
- **鉴权**：`role:create`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| roleCode | Body | string | 是 | 角色编码（稳定码） |
| roleName | Body | string | 是 | 角色名称 |
| description | Body | string | 否 | 描述 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 新建角色 ID |
| roleCode | string | 角色编码 |
| roleName | string | 角色名称 |
| description | string | 描述 |
| userCount | int | 用户数（新建为 0） |
| permissions | array | 权限点列表（新建为空） |

- **错误**：400 角色编码已存在。

#### PUT /api/v1/roles/{roleId} — 更新角色
- **功能**：修改角色名称 / 描述。
- **鉴权**：`role:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| roleId | Path | int | 是 | 角色 ID |
| roleName | Body | string | 否 | 角色名称 |
| description | Body | string | 否 | 描述 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 角色 ID |
| roleCode | string | 角色编码 |
| roleName | string | 角色名称 |
| description | string | 描述 |
| userCount | int | 用户数 |
| permissions | array | 权限点列表 |

#### PUT /api/v1/roles/{roleId}/permissions — 设置角色权限
- **功能**：以**全量覆盖**方式为角色绑定权限点集合（传入即为最终集合）。
- **鉴权**：`role:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| roleId | Path | int | 是 | 角色 ID |
| permissionIds | Body | int[] | 是 | 权限点 ID 列表（全量覆盖） |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| roleId | int | 角色 ID |
| permissionIds | int[] | 设置后的权限点 ID 列表 |

#### GET /api/v1/permissions — 权限点列表
- **功能**：查询权限点，支持按资源域过滤。
- **鉴权**：`permission:list`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| resourceDomain | Query | string | 否 | 资源域，如 file / skill / project / user 等 |

- **出参**（`list[]` 元素）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 权限点 ID |
| permissionCode | string | 权限点编码（如 `file:contract:upload`） |
| permissionName | string | 权限点名称 |
| resourceDomain | string | 资源域 |
| actionType | string | 动作类型（read/upload/delete 等） |

#### POST /api/v1/permissions — 新建权限点
- **功能**：登记一个权限点定义。
- **鉴权**：`permission:create`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| permissionCode | Body | string | 是 | 权限点编码（如 `file:contract:upload`） |
| permissionName | Body | string | 是 | 权限点名称 |
| resourceDomain | Body | string | 否 | 资源域（file/skill/project 等） |
| actionType | Body | string | 否 | 动作类型（read/upload/delete 等） |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 新建权限点 ID |
| permissionCode | string | 权限点编码 |
| permissionName | string | 权限点名称 |
| resourceDomain | string | 资源域 |
| actionType | string | 动作类型 |

- **错误**：400 权限编码已存在。

#### PUT /api/v1/permissions/{permissionId} — 更新权限点
- **功能**：修改权限点名称 / 资源域 / 动作类型。
- **鉴权**：`permission:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| permissionId | Path | int | 是 | 权限点 ID |
| permissionName | Body | string | 否 | 权限点名称 |
| resourceDomain | Body | string | 否 | 资源域 |
| actionType | Body | string | 否 | 动作类型 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 权限点 ID |
| permissionCode | string | 权限点编码 |
| permissionName | string | 权限点名称 |
| resourceDomain | string | 资源域 |
| actionType | string | 动作类型 |
