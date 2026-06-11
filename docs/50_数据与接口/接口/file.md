# 数据中心接口 · 5.3 文件与目录（file / directory）

> 摘自 [数据中心 API 调用规范](../数据中心API调用规范.md) §5。**通用约定 / 鉴权 / 数据定位 / 标准流程配方见主文件**，本文件只列本模块逐接口入参/出参/错误码。

#### GET /api/v1/files — 文件列表
- **功能**：按项目、模块、阶段、关键词分页查询业务文件，用于定位目标文件并取得 `fileId`。
- **鉴权**：可选（带 token 校验 `file:{moduleCode}:list`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| projectId | Query | string | 否 | 项目 ID（UUID32）；不传则跨项目（按权限） |
| moduleCode | Query | string | 否 | 模块代码，取值见数据规范 §3.4 |
| fileStage | Query | string | 否 | 文件阶段：`输入文件`/`解析结果`/`输出结果` |
| keyword | Query | string | 否 | 文件逻辑名关键词 |
| page | Query | int | 否 | 页码 |
| pageSize | Query | int | 否 | 每页条数 |

- **出参**（`list[]` 元素，外层含 `total`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| fileId | int | 文件 ID |
| fileLogicalName | string | 文件业务逻辑名 |
| fileName | string | 实际文件名（含扩展名） |
| logicalPath | string | 逻辑路径 |
| ext | string | 扩展名 |
| sizeBytes | int | 文件大小（字节） |
| version | string | 版本 |
| source | string | 来源：`manual` 人工 / `auto_parse` 自动解析 |
| uploaderId | int | 上传人用户 ID |
| createdAt | string | 创建时间 |

#### POST /api/v1/files/upload — 上传文件
- **功能**：上传一个文件到指定目录节点；若同目录已有同名文件，则复用其节点并更新内容（不产生重复节点）。
- **鉴权**：可选（校验 `file:{moduleCode}:upload`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| file | Form | file | 是 | 待上传的文件二进制 |
| targetNodeId | Form | int | 是 | 目标**目录**节点 ID（来自目录树） |
| fileLogicalName | Form | string | 否 | 文件业务逻辑名；缺省取文件名去扩展名 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| fileId | int | 文件 ID |
| nodeId | int | 文件对应的目录树节点 ID |
| fileName | string | 实际文件名 |
| logicalPath | string | 逻辑路径 |
| moduleCode | string | 所属模块代码 |
| fileStage | string | 所属阶段 |
| sizeBytes | int | 文件大小 |
| checksum | string | 文件 SHA256 校验值 |

- **约束**：目标须为目录节点；「暂不」模块目录拒绝（400）。

#### GET /api/v1/files/{fileId}/download — 下载文件
- **功能**：按文件 ID 流式下载文件本体。
- **鉴权**：可选（带 token 校验 `file:{moduleCode}:download`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| fileId | Path | int | 是 | 文件 ID |

- **出参**：二进制文件流（响应头 `Content-Disposition` 带文件名），不走统一封套。
- **错误**：3001 文件不存在。

#### DELETE /api/v1/files/{fileId} — 删除文件
- **功能**：删除指定文件（同时删除库内文件行、目录节点与磁盘物理文件）。
- **鉴权**：可选（校验 `file:{moduleCode}:delete`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| fileId | Path | int | 是 | 文件 ID |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| deleted | bool | 是否删除成功 |

#### POST /api/v1/directories — 新建目录
- **功能**：在指定父目录下新建一个子目录（同步写库行并创建物理目录）。
- **鉴权**：可选（校验 `file:{moduleCode}:upload`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| parentNodeId | Body | int | 是 | 父目录节点 ID |
| name | Body | string | 是 | 新目录名称 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| nodeId | int | 新目录节点 ID |
| logicalPath | string | 新目录逻辑路径 |

- **约束**：父须存在且为目录；同级不可重名；「暂不」模块拒绝。

#### DELETE /api/v1/directories/{nodeId} — 删除目录
- **功能**：级联删除一个目录及其全部子目录、文件（含库节点、文件行与磁盘内容）。
- **鉴权**：可选（校验 `file:{moduleCode}:delete`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| nodeId | Path | int | 是 | 目录节点 ID |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| deleted | bool | 是否删除成功 |

- **约束**：系统模板目录（isSystem=true）禁止删除（403）。

#### GET /api/v1/storage — 存储统计
- **功能**：返回存储用量统计（总量、文件数、目录数，并按项目及组织资产拆分）。
- **鉴权**：可选。
- **入参**：无。
- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| bytes | int | 业务文件总字节数 |
| files | int | 文件总数 |
| dirs | int | 目录总数 |
| projects | array | 按项目拆分，元素 `{ projectId 项目ID, files 文件数, bytes 字节数 }` |
| org | object | 组织资产统计 `{ bytes 字节数, files 文件数 }` |
