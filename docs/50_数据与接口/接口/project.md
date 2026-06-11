# 数据中心接口 · 5.2 项目（project）

> 摘自 [数据中心 API 调用规范](../数据中心API调用规范.md) §5。**通用约定 / 鉴权 / 数据定位 / 标准流程配方见主文件**，本文件只列本模块逐接口入参/出参/错误码。

> 项目状态枚举：`PENDING_APPROVAL`(待审批) / `APPROVED`(已审批/进行中) / `REJECTED`(已驳回) / `ARCHIVED`(已归档)。

#### POST /api/v1/projects — 创建项目
- **功能**：创建一个新项目，初始状态为「待审批」；同时按目录骨架模板生成该项目目录树（本期模块同步建物理目录，暂不模块仅建库行）。可在创建时一并指定关键角色与初始成员。
- **鉴权**：必填（`project:create`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| projectName | Body | string | 是 | 项目名称 |
| bidCode | Body | string | 否 | 投标编码 |
| customerName | Body | string | 否 | 客户名称 |
| projectCode | Body | string | 否 | 项目编码 |
| tdUsername | Body | string | 否 | TD（技术交付）账号用户名 |
| pdUsername | Body | string | 否 | PD（项目总监）账号用户名 |
| pcmUsername | Body | string | 否 | PCM 账号用户名 |
| stage | Body | string | 否 | 项目阶段 |
| progress | Body | int | 否 | 项目进度百分比（0~100） |
| risk | Body | string | 否 | 风险等级/描述（默认 low） |
| description | Body | string | 否 | 项目描述 |
| deliveryTraits | Body | array | 否 | 项目交付特点信息（产品代际/制冷方式/训推类型/Pod形态等） |
| members | Body | array | 否 | 初始成员，元素 `{ userId:int 用户ID, roleId:int 角色ID }` |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 项目数据库主键（内部 ID） |
| projectId | string | 项目 ID（UUID32），后续接口路径 `{uuid}` 与 `projectId` 取值 |
| status | string | 项目状态（创建后为 PENDING_APPROVAL） |
| rootPath | string | 项目根物理路径 |

- **错误**：2002 项目名已存在。

#### GET /api/v1/projects — 项目列表
- **功能**：分页查询项目列表，支持按状态与关键词过滤。
- **鉴权**：可选（`project:list`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| status | Query | string | 否 | 按项目状态过滤 |
| keyword | Query | string | 否 | 项目名称关键词模糊匹配 |
| page | Query | int | 否 | 页码，默认 1 |
| pageSize | Query | int | 否 | 每页条数，默认 20 |

- **出参**（`list[]` 元素，外层含 `total`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 项目数据库主键 |
| projectId | string | 项目 ID（UUID32） |
| projectName | string | 项目名称 |
| bidCode | string | 投标编码 |
| customerName | string | 客户名称 |
| projectCode | string | 项目编码 |
| status | string | 项目状态 |
| stage | string | 项目阶段 |
| progress | int | 进度百分比 |
| risk | string | 风险等级 |
| description | string | 项目描述 |
| deliveryTraits | array | 项目交付特点信息 |
| creatorId | int | 创建人 ID |
| creatorName | string | 创建人用户名 |
| tdUserId | int | TD 用户 ID |
| tdName | string | TD 用户名 |
| pdUserId | int | PD 用户 ID |
| pdName | string | PD 用户名 |
| pcmUserId | int | PCM 用户 ID |
| pcmName | string | PCM 用户名 |
| rootPath | string | 项目根物理路径 |
| createdAt | string | 创建时间（ISO8601） |
| updatedAt | string | 更新时间（ISO8601） |

#### GET /api/v1/projects/{uuid} — 项目详情
- **功能**：按项目 ID 返回项目完整信息及其成员列表。
- **鉴权**：可选（`project:read`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID（UUID32） |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 项目数据库主键 |
| projectId | string | 项目 ID（UUID32） |
| projectName | string | 项目名称 |
| bidCode | string | 投标编码 |
| customerName | string | 客户名称 |
| projectCode | string | 项目编码 |
| status | string | 项目状态 |
| stage | string | 项目阶段 |
| progress | int | 进度百分比 |
| risk | string | 风险等级 |
| description | string | 项目描述 |
| deliveryTraits | array | 项目交付特点信息 |
| creatorId / creatorName | int / string | 创建人 ID / 用户名 |
| tdUserId / tdName | int / string | TD 用户 ID / 用户名 |
| pdUserId / pdName | int / string | PD 用户 ID / 用户名 |
| pcmUserId / pcmName | int / string | PCM 用户 ID / 用户名 |
| rootPath | string | 项目根物理路径 |
| createdAt / updatedAt | string | 创建 / 更新时间 |
| members | array | 成员列表，元素 `{ userProjectRoleId 成员绑定ID, userId, username, roleCode, roleName }` |

#### PUT /api/v1/projects/{uuid} — 更新项目
- **功能**：更新项目的可变字段（名称、关键角色、阶段、进度、风险、描述、交付特点）。
- **鉴权**：可选（`project:update`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |
| projectName | Body | string | 否 | 项目名称 |
| tdUsername | Body | string | 否 | TD 账号用户名 |
| pdUsername | Body | string | 否 | PD 账号用户名 |
| pcmUsername | Body | string | 否 | PCM 账号用户名 |
| stage | Body | string | 否 | 项目阶段 |
| progress | Body | int | 否 | 进度百分比 |
| risk | Body | string | 否 | 风险等级/描述 |
| description | Body | string | 否 | 项目描述 |
| deliveryTraits | Body | array | 否 | 项目交付特点信息 |

- **出参**：更新后的项目对象，字段同「GET /projects」列表元素（id、projectId、projectName、bidCode、customerName、projectCode、status、stage、progress、risk、description、deliveryTraits、creatorId/creatorName、tdUserId/tdName、pdUserId/pdName、pcmUserId/pcmName、rootPath、createdAt、updatedAt）。

#### GET /api/v1/projects/{uuid}/tree — 项目目录树
- **功能**：返回该项目的完整目录树（查数据库 `fs_nodes` 拼装，不扫磁盘）。用于在读写文件前定位目录/文件节点。
- **鉴权**：必填。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |
| includeFileCount | Query | bool | 否 | 是否返回每个目录的文件计数 |

- **出参**：`{ tree: [ 节点 ... ] }`，每个节点字段如下（目录节点 `children` 递归嵌套子节点）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| nodeId | int | 节点 ID（上传文件时作 targetNodeId） |
| name | string | 节点名称（目录名/文件名） |
| logicalPath | string | 逻辑路径 |
| type | string | 节点类型：`dir` 目录 / `file` 文件 |
| moduleCode | string | 所属模块代码（可为空） |
| fileStage | string | 阶段：输入文件/解析结果/输出结果（可为空） |
| phase | string | 本期/暂不 |
| isSystem | bool | 是否系统模板节点（true 不可删） |
| fileId | int | 文件节点对应文件 ID（目录为 null） |
| children | array | 子节点数组（目录才有） |
| sizeBytes | int | 文件大小（文件节点才有） |
| modified | string | 文件最后修改时间（文件节点才有） |

#### GET /api/v1/projects/pending-approval — 待审批项目列表
- **功能**：查询当前处于「待审批」状态、等待审批人处理的项目。
- **鉴权**：必填（`project:approve`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| page | Query | int | 否 | 页码，默认 1 |
| pageSize | Query | int | 否 | 每页条数，默认 20 |

- **出参**（`list[]` 元素，外层含 `total`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 项目主键 |
| projectId | string | 项目 ID |
| projectName | string | 项目名称 |
| creatorId | int | 创建人 ID |
| creatorName | string | 创建人用户名 |
| createdAt | string | 创建时间 |

#### POST /api/v1/projects/{uuid}/approve — 项目审批通过
- **功能**：审批人对处于「待审批」的项目作出**通过**决定，项目状态由 `PENDING_APPROVAL` 流转为 `APPROVED`。
- **鉴权**：必填（`project:approve`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |
| approverId | Body | int | 是 | 审批人用户 ID |
| comment | Body | string | 否 | 审批意见 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| status | string | 流转后状态（APPROVED） |

- **错误**：2001 仅待审批项目可审批。

#### POST /api/v1/projects/{uuid}/reject — 项目审批驳回
- **功能**：审批人**驳回**待审批项目，必须填写驳回意见，状态由 `PENDING_APPROVAL` 变为 `REJECTED`。
- **鉴权**：必填（`project:approve`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |
| approverId | Body | int | 是 | 审批人用户 ID |
| comment | Body | string | 是 | 驳回原因（必填） |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| status | string | 流转后状态（REJECTED） |

- **错误**：2001 仅待审批项目可驳回。

#### POST /api/v1/projects/{uuid}/resubmit — 重新提交审批
- **功能**：项目创建者对被驳回的项目修改后**重新发起审批**，状态由 `REJECTED` 回到 `PENDING_APPROVAL`。
- **鉴权**：必填。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| status | string | 流转后状态（PENDING_APPROVAL） |

- **错误**：2001 仅已驳回项目可重新提交。

#### POST /api/v1/projects/{uuid}/archive — 项目归档
- **功能**：将已审批/已完成的项目**归档**，状态由 `APPROVED` 变为 `ARCHIVED`，归档后通常只读、不再参与日常流转。
- **鉴权**：必填（`project:archive`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |
| operatorId | Body | int | 是 | 操作人用户 ID |
| comment | Body | string | 否 | 归档说明 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| status | string | 流转后状态（ARCHIVED） |

- **错误**：2001 仅已审批项目可归档。

#### GET /api/v1/projects/{uuid}/members — 查询项目成员
- **功能**：列出该项目下「人员-角色」绑定关系。
- **鉴权**：必填（`member:list`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |

- **出参**（`list[]` 元素）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| userProjectRoleId | int | 成员绑定 ID（移除成员时使用） |
| userId | int | 用户 ID |
| username | string | 用户名 |
| roleCode | string | 角色编码 |
| roleName | string | 角色名称 |

#### POST /api/v1/projects/{uuid}/members — 新增项目成员
- **功能**：在该项目中为某用户分配某角色（建立成员绑定）。
- **鉴权**：必填（`member:create`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |
| userId | Body | int | 是 | 用户 ID |
| roleId | Body | int | 是 | 角色 ID |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| userProjectRoleId | int | 新建成员绑定 ID |

#### DELETE /api/v1/projects/{uuid}/members/{userProjectRoleId} — 移除项目成员
- **功能**：解除一条「人员-角色」绑定。
- **鉴权**：必填（`member:delete`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |
| userProjectRoleId | Path | int | 是 | 成员绑定 ID |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| deleted | bool | 是否移除成功 |
