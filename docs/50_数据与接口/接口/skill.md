# 数据中心接口 · 5.6 Skill 中心（skill）

> 摘自 [数据中心 API 调用规范](../数据中心API调用规范.md) §5。**通用约定 / 鉴权 / 数据定位 / 标准流程配方见主文件**，本文件只列本模块逐接口入参/出参/错误码。

> Skill 状态枚举：`draft`(草稿) / `published`(已发布) / `deprecated`(已废弃)。`skillPk` 为数据库主键（路径用），`skillId` 为业务标识。

#### GET /api/v1/skills — Skill 列表
- **功能**：分页查询已注册的 Skill，支持按作用域、项目、绑定模块、状态过滤。
- **鉴权**：`skill:list`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| scope | Query | string | 否 | 作用域：`org`/`project`/`personal` |
| projectId | Query | int | 否 | 所属项目（project 作用域时） |
| moduleCode | Query | string | 否 | 绑定的业务模块代码 |
| status | Query | string | 否 | 状态 draft/published/deprecated |
| page | Query | int | 否 | 页码 |
| pageSize | Query | int | 否 | 每页条数 |

- **出参**（`list[]` 元素，外层含 `total`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| skillPk | int | Skill 数据库主键 |
| skillId | string | Skill 业务标识 |
| skillScope | string | 作用域 |
| skillName | string | Skill 名称 |
| bindsModuleCode | string | 绑定的业务模块代码 |
| currentVersion | string | 当前版本号 |
| status | string | 状态 |
| extendsSkillId | string | 继承自的 skillId |
| ownerName | string | 负责人用户名 |
| description | string | 描述 |
| updatedAt | string | 更新时间 |

#### GET /api/v1/skills/{skillPk} — Skill 详情
- **功能**：返回单个 Skill 的完整信息及其历史版本列表。
- **鉴权**：`skill:read`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| skillPk | int | Skill 主键 |
| skillId | string | 业务标识 |
| skillScope | string | 作用域 |
| skillName | string | 名称 |
| bindsModuleCode | string | 绑定模块代码 |
| projectId | int | 所属项目 |
| ownerId | int | 负责人用户 ID |
| extendsSkillId | string | 继承自的 skillId |
| currentVersion | string | 当前版本 |
| status | string | 状态 |
| packagePath | string | 包物理路径 |
| description | string | 描述 |
| ownerName | string | 负责人用户名 |
| updatedAt | string | 更新时间 |
| versions | array | 版本历史，元素 `{ version 版本号, changeLog 变更说明, publishedBy 发布人ID, createdAt 发布时间 }` |

#### POST /api/v1/skills — 创建 Skill
- **功能**：注册一个新的 Skill（创建空的包目录，初始状态 draft）。
- **鉴权**：`skill:create`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillId | Body | string | 是 | Skill 业务标识（同 scope/项目/owner 下唯一） |
| skillScope | Body | string | 是 | 作用域：`org`/`project`/`personal` |
| skillName | Body | string | 是 | Skill 显示名称 |
| description | Body | string | 否 | 描述 |
| bindsModuleCode | Body | string | 否 | 绑定的业务模块代码 |
| projectId | Body | int | 否 | 所属项目（project 作用域时） |
| ownerId | Body | int | 否 | 负责人用户 ID；缺省取操作人 |
| extendsSkillId | Body | string | 否 | 继承/扩展自的 skillId |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| skillPk | int | 新建 Skill 主键 |
| skillId | string | 业务标识 |
| skillScope | string | 作用域 |
| skillName | string | 名称 |
| bindsModuleCode | string | 绑定模块代码 |
| projectId | int | 所属项目 |
| ownerId | int | 负责人 ID |
| extendsSkillId | string | 继承自的 skillId |
| currentVersion | string | 当前版本（新建为 null） |
| status | string | 状态（新建为 draft） |
| packagePath | string | 包物理路径 |

- **错误**：4001 槽位冲突（skillId + scope + projectId + ownerId 已存在）。

#### POST /api/v1/skills/{skillPk}/publish — 发布 Skill 版本
- **功能**：为指定 Skill 发布一个新版本，更新其 `currentVersion`、状态置为 published，并记录版本历史。
- **鉴权**：`skill:publish`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |
| version | Body | string | 是 | 新版本号 |
| changeLog | Body | string | 否 | 本次版本变更说明 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| status | string | 发布后状态（published） |
| currentVersion | string | 更新后的当前版本号 |

- **错误**：4002 已废弃的 Skill 不可发布。

#### POST /api/v1/skills/{skillPk}/deprecate — 废弃 Skill
- **功能**：将已发布的 Skill 标记为废弃（不再推荐使用）。
- **鉴权**：`skill:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| status | string | 废弃后状态（deprecated） |

- **错误**：4002 仅已发布的 Skill 可废弃。

#### DELETE /api/v1/skills/{skillPk} — 删除 Skill
- **功能**：删除指定 Skill 及其版本记录与包目录。
- **鉴权**：`skill:delete`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| deleted | bool | 是否删除成功 |

#### GET /api/v1/skills/{skillPk}/files — 列出包内文件
- **功能**：返回 Skill 包目录下的全部文件清单（递归）。
- **鉴权**：`skill:read`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |

- **出参**（`list[]` 元素）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| relPath | string | 包内相对路径（正斜杠分隔） |
| sizeBytes | int | 文件大小 |
| updatedAt | int | 最后修改时间（Unix 秒） |

#### GET /api/v1/skills/{skillPk}/files/content — 读取单个包文件
- **功能**：按相对路径返回包内文件的文本内容。
- **鉴权**：`skill:read`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |
| relPath | Query | string | 是 | 包内相对路径 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| relPath | string | 包内相对路径 |
| content | string | 文件文本内容 |

- **错误**：404 包内文件不存在。

#### PUT /api/v1/skills/{skillPk}/files — 写入单个包文件
- **功能**：按相对路径写入/覆盖包内文件内容（父目录不存在则自动创建）。
- **鉴权**：`skill:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |
| relPath | Body | string | 是 | 包内相对路径 |
| content | Body | string | 否 | 文件文本内容（缺省写空文件） |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| relPath | string | 包内相对路径 |
| sizeBytes | int | 写入字节数 |

#### DELETE /api/v1/skills/{skillPk}/files — 删除单个包文件
- **功能**：按相对路径删除包内文件。
- **鉴权**：`skill:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |
| relPath | Query | string | 是 | 包内相对路径 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| deleted | bool | 是否删除成功 |

#### POST /api/v1/skills/{skillPk}/upload-folder — 批量上传文件夹
- **功能**：按相对路径列表，把一组文件批量写入 Skill 包目录。
- **鉴权**：`skill:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |
| files | Form | file[] | 是 | 文件列表 |
| paths | Form | string[] | 是 | 与 files 一一对应的包内相对路径 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| skillPk | int | Skill 主键 |
| packagePath | string | 包物理路径 |
| fileCount | int | 成功写入文件数 |
| totalBytes | int | 写入总字节数 |

#### POST /api/v1/skills/{skillPk}/upload — 上传 Skill 包(zip)
- **功能**：上传整包 zip，解压写入 Skill 包目录。
- **鉴权**：`skill:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |
| file | Form | file | 是 | zip 包文件 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| skillPk | int | Skill 主键 |
| packagePath | string | 包物理路径 |
| fileCount | int | 解压写入文件数 |

- **错误**：400 无效的 zip / zip 内含非法路径；3002 超过大小上限。

#### GET /api/v1/skills/{skillPk}/download — 下载 Skill 包(zip)
- **功能**：将 Skill 包目录打包为 zip 下载。
- **鉴权**：`skill:read`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |

- **出参**：`application/zip` 二进制流（文件名 `{skillId}.zip`），不走统一封套。

#### POST /api/v1/skills/fusion — Skill 融合
- **功能**：登记一次 Skill 融合操作，将多个来源 Skill 合并产出到目标作用域（本期记录融合操作，自动 diff 留占位）。
- **鉴权**：`skill:publish`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillId | Body | string | 是 | 目标 Skill 业务标识 |
| sourceSkillPks | Body | int[] | 是 | 参与融合的源 Skill 主键列表 |
| targetScope | Body | string | 是 | 目标作用域 |
| approverId | Body | int | 是 | 审批人用户 ID |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| fusionId | int | 融合记录 ID |
| resultVersion | string | 结果版本（本期为 null） |
| mergedDiff | object | 合并差异（本期为 null，占位） |
