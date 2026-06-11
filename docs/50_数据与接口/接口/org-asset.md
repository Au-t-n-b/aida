# 数据中心接口 · 5.4 组织资产（org-asset）

> 摘自 [数据中心 API 调用规范](../数据中心API调用规范.md) §5。**通用约定 / 鉴权 / 数据定位 / 标准流程配方见主文件**，本文件只列本模块逐接口入参/出参/错误码。

#### GET /api/v1/org-assets/tree — 组织资产目录树
- **功能**：返回组织资产（跨项目公共/主数据）的目录树，供只读浏览与定位。
- **鉴权**：可选。
- **入参**：无。
- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| tree | array | 组织资产目录树节点（结构同项目目录树节点，见 §5.2 树接口） |
| rootPath | string | 组织资产根物理路径 |

#### GET /api/v1/org-assets — 组织资产列表
- **功能**：列出组织资产文件，支持按逻辑名关键词过滤。
- **鉴权**：可选。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| keyword | Query | string | 否 | 组织资产逻辑名关键词 |

- **出参**（`list[]` 元素，外层含 `total`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| fileId | int | 文件 ID |
| fileLogicalName | string | 资产逻辑名 |
| ext | string | 扩展名 |
| mimeType | string | MIME 类型 |
| sizeBytes | int | 文件大小 |
| uploaderName | string | 上传人用户名 |
| maintainerName | string | 维护人用户名 |
| description | string | 资产描述 |
| createdAt | string | 创建时间 |
| updatedAt | string | 更新时间 |

> 下载组织资产文件：使用 `GET /api/v1/files/{fileId}/download`。

#### PUT /api/v1/org-assets/{fileId} — 维护组织资产元数据
- **功能**：更新某组织资产文件的维护人与描述（管理类；业务模块对组织资产只读）。
- **鉴权**：建议管理员。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| fileId | Path | int | 是 | 组织资产文件 ID |
| maintainerId | Body | int | 否 | 维护人用户 ID |
| description | Body | string | 否 | 资产描述 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| fileId | int | 文件 ID |
| description | string | 更新后描述 |
| maintainerId | int | 更新后维护人 ID |

- **错误**：404 文件不存在或不属于组织资产。
