# 数据中心接口 · 5.9 配置中心-模型（model-config）

> 摘自 [数据中心 API 调用规范](../数据中心API调用规范.md) §5。**通用约定 / 鉴权 / 数据定位 / 标准流程配方见主文件**，本文件只列本模块逐接口入参/出参/错误码。

> 安全说明：列表与所有写操作返回的 `apiKey` 均做脱敏（仅前 3 位 + `****`）。

#### GET /api/v1/model-configs — 模型列表
- **功能**：查询已配置的模型，支持按启用状态/关键词过滤。
- **鉴权**：`model:list`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| enabled | Query | bool | 否 | 按启用状态过滤 |
| keyword | Query | string | 否 | 模型编码/名称关键词 |

- **出参**（`list[]` 元素）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 模型配置 ID |
| modelCode | string | 模型编码 |
| modelName | string | 模型名称 |
| provider | string | 提供方 |
| modelId | string | 厂商侧模型标识 |
| baseUrl | string | 接口地址 |
| apiKey | string | 密钥（脱敏） |
| params | object | 额外参数 |
| enabled | bool | 是否启用 |

#### POST /api/v1/model-configs — 新建模型配置
- **功能**：登记一个可调用的模型及其访问参数。
- **鉴权**：`model:create`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| modelCode | Body | string | 是 | 模型编码，全局唯一 |
| modelName | Body | string | 是 | 模型名称 |
| provider | Body | string | 否 | 提供方（如 openai/anthropic 等） |
| modelId | Body | string | 否 | 厂商侧模型标识 |
| baseUrl | Body | string | 否 | 接口地址 |
| apiKey | Body | string | 否 | 访问密钥 |
| params | Body | object | 否 | 额外参数（温度、最大 token 等） |
| enabled | Body | bool | 否 | 是否启用，默认 true |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 新建模型配置 ID |
| modelCode | string | 模型编码 |
| modelName | string | 模型名称 |
| provider | string | 提供方 |
| modelId | string | 厂商侧模型标识 |
| baseUrl | string | 接口地址 |
| apiKey | string | 密钥（脱敏） |
| params | object | 额外参数 |
| enabled | bool | 是否启用 |

- **错误**：400 模型编码已存在。

#### PUT /api/v1/model-configs/{id} — 更新模型配置
- **功能**：修改模型的名称 / 访问参数 / 启用状态。
- **鉴权**：`model:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | Path | int | 是 | 模型配置 ID |
| modelName | Body | string | 否 | 模型名称 |
| provider | Body | string | 否 | 提供方 |
| modelId | Body | string | 否 | 厂商侧模型标识 |
| baseUrl | Body | string | 否 | 接口地址 |
| apiKey | Body | string | 否 | 访问密钥 |
| params | Body | object | 否 | 额外参数 |
| enabled | Body | bool | 否 | 是否启用 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 模型配置 ID |
| modelCode | string | 模型编码 |
| modelName | string | 模型名称 |
| provider | string | 提供方 |
| modelId | string | 厂商侧模型标识 |
| baseUrl | string | 接口地址 |
| apiKey | string | 密钥（脱敏） |
| params | object | 额外参数 |
| enabled | bool | 是否启用 |

#### DELETE /api/v1/model-configs/{id} — 删除模型配置
- **功能**：删除一个模型配置。
- **鉴权**：`model:delete`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | Path | int | 是 | 模型配置 ID |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| deleted | bool | 是否删除成功 |
