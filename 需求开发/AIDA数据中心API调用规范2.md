# AIDA 数据中心 API 调用规范 v2

> **版本**：v3.0 · 2026-06-12
> **定位**：数据中心服务对外接口的调用说明，按功能模块逐接口给出功能、鉴权、入参、出参与调用约束。业务模块 / skill / 外部系统（CLaw 等）对数据的一切操作均通过本文档接口完成。
> **目的**：让人和机器**不看源码即可知道**——数据中心提供哪些能力、每个接口怎么调（方法/路径/参数及其含义/必填性）、**返回哪些字段及其含义**、需要什么权限、典型业务场景按什么顺序调。
> **与 v1 的关键差异**：文件 / 目录 / 组织资产写操作全面改为**语义寻址**（用「项目 + 模块 + 阶段 + 子目录 + 文件名」等业务参数定位，**入参不再出现内部主键 fileId / nodeId**）；下载改为 `GET` 查询参数；新增文件 / 目录**重命名**接口；项目列表按用户隔离（`GET /projects` 收紧为管理员专用，新增 `/projects/my`、`/users/{username}/projects`）；新增外部服务登录与项目运行上下文接口。详见各模块与「附录 A 相对 v1 的变更对照」。
> **读者**：写 skill、做业务开发、对接数据中心的同学，以及外部系统（CLaw）集成方。
> **SSOT**：接口字段最终以运行时 OpenAPI 文档 `http://<服务地址>/docs`（及 `/openapi.json`）为准；本文档描述功能、含义、约束与典型流程，分歧以 OpenAPI 为准。

---

## 目录

- [第 1 章 通用约定](#第-1-章-通用约定)
- [第 2 章 功能模块总览](#第-2-章-功能模块总览)
- [第 3 章 语义定位与数据发现](#第-3-章-语义定位与数据发现)
- [第 4 章 标准数据流程配方](#第-4-章-标准数据流程配方)
- [第 5 章 接口详解](#第-5-章-接口详解)
  - [5.1 认证（auth）](#51-认证auth)
  - [5.2 项目（project）](#52-项目project)
  - [5.3 文件与目录（file / directory）](#53-文件与目录file--directory)
  - [5.4 组织资产（org-asset）](#54-组织资产org-asset)
  - [5.5 数据血缘（lineage）](#55-数据血缘lineage)
  - [5.6 Skill 中心（skill）](#56-skill-中心skill)
  - [5.7 配置中心-人员（user-mgmt）](#57-配置中心-人员user-mgmt)
  - [5.8 配置中心-角色与权限（rbac）](#58-配置中心-角色与权限rbac)
  - [5.9 配置中心-模型（model-config）](#59-配置中心-模型model-config)
  - [5.10 运维中心-审计（audit）](#510-运维中心-审计audit)
- [第 6 章 Skill 与数据中心的边界](#第-6-章-skill-与数据中心的边界)
- [第 7 章 版本与演进](#第-7-章-版本与演进)
- [附录 A 相对 v1 的变更对照](#附录-a-相对-v1-的变更对照)

---

## 第 1 章 通用约定

### 1.1 基础

| 项 | 约定 |
| --- | --- |
| Base URL | `http://<服务地址>` |
| 版本前缀 | 所有接口以 `/api/v1` 开头 |
| 健康检查 | `GET /api/v1/health`（返回 `{ "status": "ok" }`，无需鉴权） |
| 内容类型 | JSON 接口 `application/json`；上传 `multipart/form-data` |
| 字段风格 | 请求/响应字段为 **camelCase**（如 `projectId`、`fileStage`、`folderSubPath`） |

### 1.2 统一响应封套

所有 JSON 接口返回统一结构：

```json
{ "code": 0, "message": "success", "data": { } }
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| code | int | 0 表示成功；非 0 为错误码（见 §1.6） |
| message | string | 提示信息 |
| data | object/array/null | 业务数据；下文「出参」即指 `data` 的内容 |

**分页响应**：`data` 形如 `{ "list": [ ... ], "total": <int> }`；下文分页接口的「出参」描述的是 `list[]` 的元素字段，外层另含 `total`（总条数）。
**文件下载类接口**直接返回二进制流（`Content-Disposition` 带文件名），不走上述封套。

### 1.3 入参 / 出参的表达约定

- **入参**表列：`参数 | 位置 | 类型 | 必填 | 说明`。
  - **位置**：`Path`（路径变量）/ `Query`（URL 查询参数）/ `Body`（JSON 请求体）/ `Form`（multipart 表单）。
  - **必填**：`是` / `否`（"否"即可选参数）。
- **出参**表列：`字段 | 类型 | 说明`，逐字段列出 `data` 的内容。
- 文中示例里以 `$VAR` 表示占位变量，调用时替换为实际值。

### 1.4 分页参数（列表类接口通用）

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| page | Query/Body | int | 否 | 页码，默认 1，≥1 |
| pageSize | Query/Body | int | 否 | 每页条数，默认 20，范围 1~200（人员接口上限 100） |

### 1.5 鉴权

| 接口类别 | 鉴权 | 说明 |
| --- | --- | --- |
| 管理类（内部） | 必须 JWT + RBAC | 缺 token 返回 401；权限不足返回 403。请求头 `Authorization: Bearer <token>` |
| 数据交换类（外部/机机） | 可选 | 带 token 走 RBAC；不带 token 本期放行（可信内网机机调用） |

- 平台账号 Token 由 `POST /api/v1/users/login` 获取（返回 `token`）。
- 外部系统获取「带完整授权上下文」的令牌用 `POST /api/v1/auth/login`（返回 `accessToken` + 角色/权限）。
- 下文每个接口标注【鉴权】：`无` / `可选` / `必填` / 所需权限点（如 `skill:list`）/ `仅管理员`。
- **管理员**：拥有全局 `ADMIN` 角色的用户，RBAC 判定中对所有权限点直接放行。

### 1.6 错误码

| code | 含义 | HTTP |
| --- | --- | --- |
| 0 | 成功 | 200 |
| 400 / 401 / 403 / 404 / 500 | 请求错误 / 未认证 / 无权限 / 不存在 / 服务器错误 | 同名 |
| 1001~1005 | 用户名已存在 / 凭证错误 / 账号禁用 / 用户不存在 / 不能删除自己 | 400/403/404 |
| 2001~2002 | 项目状态非法 / 项目名已存在 | 400 |
| 3001~3002 | 文件不存在 / 文件上传失败 | 404/400 |
| 4001~4002 | Skill 槽位冲突 / Skill 状态非法 | 400 |

### 1.7 幂等与重试

- 文件上传同名 → 自动复用文件节点并更新内容（不新增重复节点），上传可安全重试。
- 删除类接口幂等（重复删除不报错）。

---

## 第 2 章 功能模块总览

| # | 功能模块 | 路由前缀 | 主要职责 | 与业务数据的关系 |
| --- | --- | --- | --- | --- |
| 1 | 认证 auth | `/api/v1/users`、`/api/v1/auth` | 注册、登录（平台/外部）、当前用户、删除用户 | 取 token |
| 2 | 项目 project | `/api/v1/projects`、`/api/v1/users/{username}/projects` | 项目 CRUD、审批、成员、目录树、按用户查项目、运行上下文 | 项目空间与目录树入口 |
| 3 | 文件 file | `/api/v1/files`、`/api/v1/directories`、`/api/v1/storage` | 业务文件增删改查、目录增删改、存储统计（**全语义寻址**） | **业务数据面核心** |
| 4 | 组织资产 org-asset | `/api/v1/org-assets` | 公共/主数据只读、元数据维护 | 参考/主数据 |
| 5 | 数据血缘 lineage | `/api/v1/file-lineage` | 文件血缘查询 | 数据追溯 |
| 6 | Skill 中心 skill | `/api/v1/skills` | Skill 注册/发布/包文件/融合 | Skill 文件管理 |
| 7 | 配置中心-人员 user-mgmt | `/api/v1/user-mgmt` | 人员 CRUD | 独立业务数据 |
| 8 | 配置中心-角色权限 rbac | `/api/v1/roles`、`/api/v1/permissions` | 角色、权限点、映射 | 权限 |
| 9 | 配置中心-模型 model-config | `/api/v1/model-configs` | 模型配置 CRUD | 模型 |
| 10 | 运维中心-审计 audit | `/api/v1/audit-logs` | 审计日志查询 | 操作留痕 |

> 对 skill / 业务开发最常用的是模块 3/4/5/6（文件、组织资产、血缘、Skill）。

---

## 第 3 章 语义定位与数据发现

> **v2 核心变化**：文件/目录的读写**不再需要先取 `nodeId`/`fileId` 再操作**，而是直接用业务语义参数定位。目录树接口仍保留，但仅用于**浏览展示**，不再是操作的前置必需步骤。

### 3.1 语义定位键（文件/目录接口通用）

下列参数在多个文件/目录接口中重复出现，统一解释：

| 参数 | 类型 | 含义 | 取值说明 |
| --- | --- | --- | --- |
| `projectId` | string | 项目标识（UUID32） | 由登录 / 查项目得到。**操作组织资产时不传**（组织资产跨项目） |
| `moduleCode` | string | 业务模块代号（英文） | 19 个固定值之一，如 `contract`(合同)、`proposal`(交付预案)、`ops-survey`(智慧工勘)；组织资产固定为 `org-assets`。取值见数据规范 §1.3 / `app/constants/modules.py` |
| `fileStage` | string | IPO 数据阶段 | 仅 3 个合法值：`输入文件` / `解析结果` / `输出结果`。**普通模块必填；flat 模块（pm-basic 基本信息、program-docs 项目文档）与组织资产不传**（无三层结构） |
| `folderSubPath` | string | 阶段目录下的子目录相对路径 | 多层用 `/` 分隔，如 `合同文件` 或 `合同文件/2024`；不传表示直接指向阶段根目录。承载于 JSON body / form / query，多层路径在 query 中需 URL 编码 |
| `fileName` | string | 文件名（含扩展名） | 如 `设备清单.xlsx`，用于定位某个具体文件 |

> **定位逻辑**：`projectId + moduleCode + fileStage + folderSubPath` 共同锁定**一个目录**；再加 `fileName` 锁定**目录中的一个文件**。等价于"D盘/某项目/合同/输入文件/合同文件 这个文件夹里的 设备清单.xlsx"。
> **域无歧义**：`moduleCode` 全局唯一，已隐含其所属一级域（如 `contract` 必在「早期介入/合同」），无需另传域。

### 3.2 数据发现接口

| 方式 | 接口 | 用途 |
| --- | --- | --- |
| 查项目目录树 | `GET /api/v1/projects/{uuid}/tree` | 浏览项目各级目录与文件（含 moduleCode、fileStage、logicalPath） |
| 查组织资产 | `GET /api/v1/org-assets`、`/api/v1/org-assets/tree` | 浏览/定位公共表 |
| 按语义筛文件 | `POST /api/v1/files/list` | 列某模块某阶段某子目录下的文件 |

---

## 第 4 章 标准数据流程配方

可复制的调用序列（curl 示意，省略 token）。`$VAR` 为占位，请替换为实际值。

### 4.1 读上游模块的「输出结果」作为输入

```bash
# $PID=项目ID(UUID32)，$UP=上游模块代码（合同填 contract）
# 1) 列上游输出文件，确认文件名
curl -X POST "$BASE/api/v1/files/list" -H 'Content-Type: application/json' \
     -d "{\"projectId\":\"$PID\",\"moduleCode\":\"$UP\",\"fileStage\":\"输出结果\"}"
#    → data.list[].fileName

# 2) 下载（语义定位，GET 查询参数）
curl -OJ "$BASE/api/v1/files/download?projectId=$PID&moduleCode=$UP&fileStage=输出结果&fileName=<文件名>"
```

### 4.2 把中间态写入本模块「解析结果」

```bash
# 直接语义上传，folderSubPath 不存在会自动建目录
curl -F "file=@<本地文件>" \
     -F "projectId=$PID" -F "moduleCode=<本模块代码>" -F "fileStage=解析结果" \
     "$BASE/api/v1/files/upload"
```

### 4.3 产出成品到「输出结果」

```bash
curl -F "file=@<本地成品>" \
     -F "projectId=$PID" -F "moduleCode=<本模块代码>" -F "fileStage=输出结果" \
     -F "fileDisplayName=<业务显示名>" \
     "$BASE/api/v1/files/upload"
#    → data.fileId（新成品，返回信息）
```

### 4.4 引用组织资产（只读）

```bash
curl "$BASE/api/v1/org-assets?keyword=<公共表关键词>"     # 定位资产名
curl -OJ "$BASE/api/v1/files/download?moduleCode=org-assets&fileName=<资产文件名>"  # 下载
```

### 4.5 Skill 包文件读写

```bash
curl "$BASE/api/v1/skills/$SKILL_PK/files"                               # 列包内文件
curl "$BASE/api/v1/skills/$SKILL_PK/files/content?relPath=<包内相对路径>"  # 读单个文件
curl -X PUT "$BASE/api/v1/skills/$SKILL_PK/files" -H 'Content-Type: application/json' \
     -d '{"relPath":"<包内相对路径>","content":"<文本内容>"}'              # 写单个文件
```

---

## 第 5 章 接口详解

> 每个接口给出【功能】【鉴权】【入参】【出参】，入参与出参均为独立表格。分页接口的出参为 `list[]` 元素字段，外层另含 `total`。无入参的接口会注明「无」。

### 5.1 认证（auth）

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

#### POST /api/v1/users/login — 平台登录获取令牌
- **功能**：校验用户名口令，成功后签发 JWT 令牌，供后续管理类接口鉴权使用。数据中心前端使用此接口。
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

#### POST /api/v1/auth/login — 外部服务登录（含授权上下文）
- **功能**：供外部服务（如 CLaw）登录，返回 `accessToken` 及用户**完整授权上下文**（全局角色、权限点集合），一次拿齐身份与权限。
- **鉴权**：无。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| username | Body | string | 是 | 登录用户名 |
| password | Body | string | 是 | 登录口令 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| accessToken | string | JWT 令牌 |
| tokenType | string | 令牌类型，固定 `Bearer` |
| user | object | 用户身份与授权上下文，结构见下 |

`user` 对象字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| userId | string | 用户 ID（字符串形式） |
| username | string | 用户名 |
| displayName | string | 显示名（当前等于 username） |
| email | string | 邮箱 |
| status | int | 状态：1 启用 / 0 禁用 |
| globalRoles | array | 全局角色列表，元素 `{ roleCode, roleName }` |
| permissions | string[] | 权限点编码集合（如 `file:contract:upload`） |

- **错误**：1002 凭证错误（`invalid username or password`）、1003 账号禁用。

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
| globalRoles | array | 全局角色列表，元素 `{ roleCode, roleName }` |
| projectRoles | array | 项目角色列表，元素 `{ projectId, roleCode, roleName }` |
| permissions | string[] | 权限点编码集合 |

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

### 5.2 项目（project）

> 项目状态枚举：`PENDING_APPROVAL`(待审批) / `APPROVED`(已审批/进行中) / `REJECTED`(已驳回) / `ARCHIVED`(已归档)。
> **项目可见性（v2 新规则）**：普通用户只能看到自己参与的项目（creator/td/pd/pcm 或在 `user_project_roles` 中有该项目角色）；列全部项目（`GET /projects`）已收紧为**仅管理员**。

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
| members | Body | array | 否 | 初始成员，元素 `{ userId:int, roleId:int }` |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | 项目数据库主键（内部 ID） |
| projectId | string | 项目 ID（UUID32），后续接口路径 `{uuid}` 与 `projectId` 取值 |
| status | string | 项目状态（创建后为 PENDING_APPROVAL） |
| rootPath | string | 项目根物理路径 |

- **错误**：2002 项目名已存在。

#### GET /api/v1/projects — 项目列表（仅管理员）
- **功能**：分页查询**全部**项目，支持按状态与关键词过滤。**仅管理员可调用**；普通用户请用 `GET /api/v1/projects/my`。
- **鉴权**：仅管理员（非管理员 403）。
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

#### GET /api/v1/projects/my — 我参与的项目
- **功能**：返回**当前登录用户**参与的项目（creator/td/pd/pcm 或在该项目有角色）。未参与任何项目则返回空列表。数据中心前端的主项目列表使用此接口。
- **鉴权**：必填（凭 token 识别当前用户）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| status | Query | string | 否 | 按项目状态过滤 |
| keyword | Query | string | 否 | 项目名称 / 项目编码关键词模糊匹配 |
| page | Query | int | 否 | 页码，默认 1 |
| pageSize | Query | int | 否 | 每页条数，默认 20 |

- **出参**（`list[]` 元素，外层含 `total`）：在「GET /projects」列表元素全部字段基础上，额外包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| myRoles | array | 当前用户在该项目的角色，元素 `{ roleCode, roleName }` |
| canEnter | bool | 是否可进入（项目状态为 APPROVED 时为 true） |
| disabledReason | string | 不可进入原因（canEnter 为 false 时出现，如 `project status is PENDING_APPROVAL`） |

#### GET /api/v1/users/{username}/projects — 按用户名查其参与的项目
- **功能**：按指定用户名返回其参与的项目。供外部系统（如 CLaw）显式指定查询对象。
- **鉴权**：必填 + **本人或管理员**（调用方只能查自己，或调用方为管理员/服务账号才能查他人，否则 403）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| username | Path | string | 是 | 目标用户名（全局唯一） |
| status | Query | string | 否 | 按项目状态过滤 |
| keyword | Query | string | 否 | 项目名称 / 项目编码关键词 |
| page | Query | int | 否 | 页码，默认 1 |
| pageSize | Query | int | 否 | 每页条数，默认 20 |

- **出参**（`list[]` 元素，外层含 `total`）：同「GET /projects/my」（含 myRoles/canEnter/disabledReason，此处指目标用户在各项目的角色）。
- **错误**：1004 用户不存在；403 无权查看他人项目。

#### GET /api/v1/projects/{uuid} — 项目详情
- **功能**：按项目 ID 返回项目完整信息及其成员列表。
- **鉴权**：可选（`project:read`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID（UUID32） |

- **出参**：在「GET /projects」列表元素全部字段基础上，额外包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| members | array | 成员列表，元素 `{ userProjectRoleId, userId, username, roleCode, roleName }` |

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

- **出参**：更新后的项目对象，字段同「GET /projects」列表元素。
- **错误**：2002 项目名已存在。

#### GET /api/v1/projects/{uuid}/tree — 项目目录树
- **功能**：返回该项目的完整目录树（查数据库 `fs_nodes` 拼装，不扫磁盘）。用于浏览展示目录结构。
- **鉴权**：必填。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |
| includeFileCount | Query | bool | 否 | 是否返回每个目录的文件计数 |

- **出参**：`{ tree: [ 节点 ... ] }`，每个节点字段如下（目录节点 `children` 递归嵌套子节点）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| nodeId | int | 节点 ID（内部标识） |
| name | string | 节点名称（目录名/文件名） |
| logicalPath | string | 逻辑路径 |
| type | string | 节点类型：`dir` 目录 / `file` 文件 |
| moduleCode | string | 所属模块代码（可为空） |
| fileStage | string | 阶段：输入文件/解析结果/输出结果（可为空） |
| phase | string | 本期/暂不 |
| isSystem | bool | 是否系统模板节点（true 不可删/不可重命名） |
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

#### POST /api/v1/projects/runtime-context — 项目运行上下文
- **功能**：供外部系统（CLaw）激活某用户在某项目下的运行环境时调用，返回该用户在该项目的角色、组织资产根/项目根/Skill 路径及环境变量集合，用于拉起运行态。要求项目状态为 `APPROVED` 且该用户参与该项目。
- **鉴权**：必填（凭 token 识别调用方）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| user | Body | string | 是 | 目标用户名 |
| project | Body | string | 是 | 项目 ID（UUID32） |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| project | object | 项目信息 `{ id, projectId, projectName, projectCode, status }` |
| user | object | 用户信息 `{ userId(字符串), username, displayName }` |
| projectRoles | array | 该用户在该项目的角色，元素 `{ roleCode, roleName }` |
| permissions | object | 权限上下文（本期为空对象占位） |
| orgRoot | string | 组织资产根物理路径 |
| projRoot | string | 项目根物理路径 |
| skillPaths | string[] | 组织级 Skill 目录路径列表 |
| env | object | 环境变量集合（见下） |

`env` 对象字段：`AIDA_PROJECT_ID`、`AIDA_PROJECT_CODE`、`AIDA_PROJECT_NAME`、`AIDA_USER_ID`、`AIDA_USERNAME`、`AIDA_PROJECT_ROLE`(逗号分隔角色码)、`ORG_ROOT`、`PROJ_ROOT`。

- **错误**：1004 用户不存在；404 项目不存在；403 用户未参与该项目；2001 项目状态不允许激活运行态。

#### POST /api/v1/projects/{uuid}/approve — 项目审批通过
- **功能**：审批人对「待审批」项目作出**通过**决定，状态由 `PENDING_APPROVAL` 流转为 `APPROVED`。
- **鉴权**：必填（`project:approve`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |
| approverId | Body | int | 是 | 审批人用户 ID |
| comment | Body | string | 否 | 审批意见 |

- **出参**：`{ status: "APPROVED" }`。
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

- **出参**：`{ status: "REJECTED" }`。
- **错误**：2001 仅待审批项目可驳回。

#### POST /api/v1/projects/{uuid}/resubmit — 重新提交审批
- **功能**：项目创建者对被驳回的项目修改后**重新发起审批**，状态由 `REJECTED` 回到 `PENDING_APPROVAL`。
- **鉴权**：必填。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |

- **出参**：`{ status: "PENDING_APPROVAL" }`。
- **错误**：2001 仅已驳回项目可重新提交。

#### POST /api/v1/projects/{uuid}/archive — 项目归档
- **功能**：将已审批/已完成的项目**归档**，状态由 `APPROVED` 变为 `ARCHIVED`。
- **鉴权**：必填（`project:archive`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |
| operatorId | Body | int | 是 | 操作人用户 ID |
| comment | Body | string | 否 | 归档说明 |

- **出参**：`{ status: "ARCHIVED" }`。
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

- **出参**：`{ userProjectRoleId: int }`（新建成员绑定 ID）。

#### DELETE /api/v1/projects/{uuid}/members/{userProjectRoleId} — 移除项目成员
- **功能**：解除一条「人员-角色」绑定。
- **鉴权**：必填（`member:delete`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| uuid | Path | string | 是 | 项目 ID |
| userProjectRoleId | Path | int | 是 | 成员绑定 ID |

- **出参**：`{ deleted: bool }`。

### 5.3 文件与目录（file / directory）

> **全语义寻址**：入参用「项目 + 模块 + 阶段 + 子目录 + 文件名」定位，**不出现 fileId / nodeId**。语义定位键含义见 §3.1。
> 组织资产文件用本组接口操作：`moduleCode=org-assets`、不传 `projectId`、不传 `fileStage`。

#### POST /api/v1/files/list — 文件列表
- **功能**：按项目、模块、阶段、子目录、关键词分页查询业务文件。
- **鉴权**：可选（带 token 校验 `file:{moduleCode}:list`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| projectId | Body | string | 否 | 项目 ID；不传则查组织资产 |
| moduleCode | Body | string | 否 | 模块代码 |
| fileStage | Body | string | 否 | 文件阶段：`输入文件`/`解析结果`/`输出结果` |
| folderSubPath | Body | string | 否 | 阶段下子目录相对路径，仅列该子目录下的文件 |
| fileKeyword | Body | string | 否 | 文件显示名关键词模糊匹配 |
| page | Body | int | 否 | 页码，默认 1 |
| pageSize | Body | int | 否 | 每页条数，默认 20 |

- **出参**（`list[]` 元素，外层含 `total`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| fileId | int | 文件 ID（返回信息，后续操作无需回传） |
| fileDisplayName | string | 文件业务显示名 |
| fileName | string | 实际文件名（含扩展名） |
| logicalPath | string | 逻辑路径 |
| ext | string | 扩展名 |
| sizeBytes | int | 文件大小（字节） |
| version | string | 版本 |
| source | string | 来源：`manual` 人工 / `auto_parse` 自动解析 |
| uploaderId | int | 上传人用户 ID |
| createdAt | string | 创建时间 |

#### POST /api/v1/files/upload — 上传文件
- **功能**：把文件上传到「指定模块+阶段+子目录」对应目录。`folderSubPath` 指向的子目录不存在时**自动逐级创建**；同目录已有同名文件则复用其节点并更新内容（可安全重试）。
- **鉴权**：可选（校验 `file:{moduleCode}:upload`）。
- **请求类型**：`multipart/form-data`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| file | Form | file | 是 | 待上传的文件二进制 |
| projectId | Form | string | 否 | 目标项目 ID；不传则上传到组织资产 |
| moduleCode | Form | string | 是 | 目标模块代码 |
| fileStage | Form | string | 普通模块必填 | 目标阶段；flat 模块/组织资产不传 |
| folderSubPath | Form | string | 否 | 目标子目录；不存在自动创建 |
| fileDisplayName | Form | string | 否 | 文件业务显示名；缺省取文件名去扩展名 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| fileId | int | 文件 ID |
| nodeId | int | 文件对应目录树节点 ID（返回信息） |
| fileName | string | 实际文件名 |
| logicalPath | string | 逻辑路径 |
| moduleCode | string | 所属模块代码 |
| fileStage | string | 所属阶段 |
| sizeBytes | int | 文件大小 |
| checksum | string | 文件 SHA256 校验值 |

- **约束**：目标模块为「暂不」模块时拒绝（400）；目标目录定位失败 404；超过大小上限 3002。

#### GET /api/v1/files/download — 下载文件
- **功能**：按语义定位某个文件，以二进制流返回文件内容。
- **鉴权**：可选（带 token 校验 `file:{moduleCode}:download`）。
- **入参**（查询参数；含 `/` 的 `folderSubPath` 需 URL 编码）：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| moduleCode | Query | string | 是 | 模块代码 |
| fileName | Query | string | 是 | 要下载的文件名（含扩展名） |
| projectId | Query | string | 否 | 项目 ID；不传则组织资产 |
| fileStage | Query | string | 普通模块必填 | 文件阶段 |
| folderSubPath | Query | string | 否 | 子目录相对路径 |

- **出参**：二进制文件流（响应头 `Content-Disposition` 带文件名，支持中文），不走统一封套。
- **错误**：3001 文件不存在。

#### POST /api/v1/files/delete — 删除文件
- **功能**：按语义定位并删除文件（同时删库内文件行、目录节点、磁盘物理文件）。幂等。
- **鉴权**：可选（校验 `file:{moduleCode}:delete`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| projectId | Body | string | 否 | 项目 ID；不传则组织资产 |
| moduleCode | Body | string | 是 | 模块代码 |
| fileStage | Body | string | 普通模块必填 | 文件阶段 |
| folderSubPath | Body | string | 否 | 子目录相对路径 |
| fileName | Body | string | 是 | 要删除的文件名 |

- **出参**：`{ deleted: bool }`。
- **错误**：3001 文件不存在。

#### POST /api/v1/files/rename — 重命名文件
- **功能**：按语义定位文件并重命名（同步更新库内文件名/逻辑路径/物理文件名）。
- **鉴权**：可选（校验 `file:{moduleCode}:upload`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| projectId | Body | string | 否 | 项目 ID；不传则组织资产 |
| moduleCode | Body | string | 是 | 模块代码 |
| fileStage | Body | string | 普通模块必填 | 文件阶段 |
| folderSubPath | Body | string | 否 | 子目录相对路径 |
| fileName | Body | string | 是 | 原文件名 |
| newName | Body | string | 是 | 新文件名（含扩展名） |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| fileId | int | 文件 ID |
| fileName | string | 新文件名 |
| logicalPath | string | 新逻辑路径 |
| moduleCode | string | 所属模块代码 |
| fileStage | string | 所属阶段 |

- **错误**：3001 文件不存在；400 同级已存在同名文件或目录。

#### POST /api/v1/directories/create — 新建目录
- **功能**：在「指定模块+阶段+父子目录」下新建一个子目录（同步写库行并创建物理目录）。
- **鉴权**：可选（校验 `file:{moduleCode}:upload`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| projectId | Body | string | 否 | 项目 ID；不传则组织资产 |
| moduleCode | Body | string | 是 | 模块代码 |
| fileStage | Body | string | 普通模块必填 | 阶段 |
| folderSubPath | Body | string | 否 | 在阶段下哪个已有子目录里建（父）；不传=阶段根 |
| directoryName | Body | string | 是 | 新目录名称 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| nodeId | int | 新目录节点 ID（返回信息） |
| logicalPath | string | 新目录逻辑路径 |

- **约束**：「暂不」模块拒绝（400）；同级不可重名（400）。

#### POST /api/v1/directories/delete — 删除目录
- **功能**：按语义定位并级联删除一个目录及其全部子目录、文件（含库节点、文件行与磁盘内容）。
- **鉴权**：可选（校验 `file:{moduleCode}:delete`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| projectId | Body | string | 否 | 项目 ID；不传则组织资产 |
| moduleCode | Body | string | 是 | 模块代码 |
| fileStage | Body | string | 普通模块必填 | 阶段 |
| folderSubPath | Body | string | 是 | 要删除的目录（相对阶段根，如 `BOQ` 或 `合同文件/2024`） |

- **出参**：`{ deleted: bool }`。
- **约束**：系统模板目录（isSystem=true）禁止删除（403）；目录不存在 404。

#### POST /api/v1/directories/rename — 重命名目录
- **功能**：按语义定位并重命名目录。重命名后**级联更新所有子孙节点的逻辑路径**及子孙文件行的存储路径，物理目录整体移动。
- **鉴权**：可选（校验 `file:{moduleCode}:upload`）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| projectId | Body | string | 否 | 项目 ID；不传则组织资产 |
| moduleCode | Body | string | 是 | 模块代码 |
| fileStage | Body | string | 普通模块必填 | 阶段 |
| folderSubPath | Body | string | 是 | 要重命名的目录（相对阶段根） |
| newName | Body | string | 是 | 新目录名称 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| nodeId | int | 目录节点 ID |
| logicalPath | string | 重命名后逻辑路径 |

- **约束**：系统模板目录禁止重命名（403）；根目录禁止重命名（403）；同级不可重名（400）。

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
| projects | array | 按项目拆分，元素 `{ projectId, files, bytes }` |
| org | object | 组织资产统计 `{ bytes, files }` |

### 5.4 组织资产（org-asset）

> 组织资产为跨项目公共/主数据，业务模块**只读**引用；文件读写（列表/下载/上传/删除/重命名）统一走 §5.3 文件接口（`moduleCode=org-assets`，不传 projectId/fileStage）。本组仅含组织资产专属的浏览与元数据维护接口。

#### GET /api/v1/org-assets/tree — 组织资产目录树
- **功能**：返回组织资产目录树，供只读浏览与定位。
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

> 下载组织资产文件：`GET /api/v1/files/download?moduleCode=org-assets&fileName=<资产文件名>`。

#### POST /api/v1/org-assets/update — 维护组织资产元数据
- **功能**：按资产名更新某组织资产文件的维护人与描述（管理类；业务模块对组织资产只读）。维护人用**用户名**指定。
- **鉴权**：可选（建议管理员）。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| assetName | Body | string | 是 | 资产名称（组织资产逻辑名），如 `AI平台白名单` |
| maintainerUsername | Body | string | 否 | 维护人用户名（后端解析为用户 ID） |
| description | Body | string | 否 | 资产描述 |

- **出参**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| fileId | int | 文件 ID |
| assetName | string | 资产名称 |
| maintainerUsername | string | 维护人用户名 |
| description | string | 资产描述 |
| updatedAt | string | 更新时间 |

- **错误**：3001 资产不存在或不属于组织资产；1004 维护人用户不存在。

### 5.5 数据血缘（lineage）

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
| nodes | array | 血缘节点，元素 `{ fileId, fileLogicalName }` |
| edges | array | 血缘边，元素 `{ upstreamId, downstreamId, relation }` |

> `relation` 取值：`derived_from`（下游由上游加工而来）/ `referenced_by`（被引用）。

### 5.6 Skill 中心（skill）

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
| versions | array | 版本历史，元素 `{ version, changeLog, publishedBy, createdAt }` |

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

- **出参**：`{ status: "published", currentVersion: string }`。
- **错误**：4002 已废弃的 Skill 不可发布。

#### POST /api/v1/skills/{skillPk}/deprecate — 废弃 Skill
- **功能**：将已发布的 Skill 标记为废弃（不再推荐使用）。
- **鉴权**：`skill:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |

- **出参**：`{ status: "deprecated" }`。
- **错误**：4002 仅已发布的 Skill 可废弃。

#### DELETE /api/v1/skills/{skillPk} — 删除 Skill
- **功能**：删除指定 Skill 及其版本记录与包目录。
- **鉴权**：`skill:delete`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |

- **出参**：`{ deleted: bool }`。

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

- **出参**：`{ relPath: string, content: string }`。
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

- **出参**：`{ relPath: string, sizeBytes: int }`。

#### DELETE /api/v1/skills/{skillPk}/files — 删除单个包文件
- **功能**：按相对路径删除包内文件。
- **鉴权**：`skill:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |
| relPath | Query | string | 是 | 包内相对路径 |

- **出参**：`{ deleted: bool }`。

#### POST /api/v1/skills/{skillPk}/upload-folder — 批量上传文件夹
- **功能**：按相对路径列表，把一组文件批量写入 Skill 包目录。
- **鉴权**：`skill:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |
| files | Form | file[] | 是 | 文件列表 |
| paths | Form | string[] | 是 | 与 files 一一对应的包内相对路径 |

- **出参**：`{ skillPk, packagePath, fileCount, totalBytes }`。

#### POST /api/v1/skills/{skillPk}/upload — 上传 Skill 包(zip)
- **功能**：上传整包 zip，解压写入 Skill 包目录。
- **鉴权**：`skill:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| skillPk | Path | int | 是 | Skill 主键 |
| file | Form | file | 是 | zip 包文件 |

- **出参**：`{ skillPk, packagePath, fileCount }`。
- **错误**：400 无效的 zip / zip 内含非法路径；3002 超过大小上限。

#### GET /api/v1/skills/{skillPk}/download — 下载 Skill 包(zip)
- **功能**：将 Skill 包目录打包为 zip 下载。
- **鉴权**：`skill:read`（强制鉴权，需带 Bearer）。
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

- **出参**：`{ fusionId, resultVersion(本期 null), mergedDiff(本期 null) }`。

### 5.7 配置中心-人员（user-mgmt）

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
| projectRoles | array | 项目角色，元素 `{ projectId, projectName, roleCode, roleName }` |

#### GET /api/v1/user-mgmt/{userId} — 人员详情
- **功能**：按 ID 返回用户信息及其项目角色。
- **鉴权**：`user:read`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| userId | Path | int | 是 | 用户 ID |

- **出参**：同人员列表元素字段（userId、username、email、status、lastLoginAt、createdAt、updatedAt、projectRoles）。

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

- **出参**：同人员详情字段（projectRoles 新建为空数组）。
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

- **出参**：同人员详情字段。

#### DELETE /api/v1/user-mgmt/{userId} — 删除人员
- **功能**：删除指定用户（不可删自己）。
- **鉴权**：`user:delete`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| userId | Path | int | 是 | 用户 ID |

- **出参**：`{ deleted: bool }`。
- **错误**：1004 用户不存在、1005 不能删除自己。

### 5.8 配置中心-角色与权限（rbac）

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

- **出参**：`{ id, roleCode, roleName, description, userCount(新建0), permissions(新建空) }`。
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

- **出参**：`{ id, roleCode, roleName, description, userCount, permissions }`。

#### PUT /api/v1/roles/{roleId}/permissions — 设置角色权限
- **功能**：以**全量覆盖**方式为角色绑定权限点集合（传入即为最终集合）。
- **鉴权**：`role:update`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| roleId | Path | int | 是 | 角色 ID |
| permissionIds | Body | int[] | 是 | 权限点 ID 列表（全量覆盖） |

- **出参**：`{ roleId, permissionIds }`。

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
| permissionCode | Body | string | 是 | 权限点编码 |
| permissionName | Body | string | 是 | 权限点名称 |
| resourceDomain | Body | string | 否 | 资源域 |
| actionType | Body | string | 否 | 动作类型 |

- **出参**：`{ id, permissionCode, permissionName, resourceDomain, actionType }`。
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

- **出参**：`{ id, permissionCode, permissionName, resourceDomain, actionType }`。

### 5.9 配置中心-模型（model-config）

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
| provider | Body | string | 否 | 提供方 |
| modelId | Body | string | 否 | 厂商侧模型标识 |
| baseUrl | Body | string | 否 | 接口地址 |
| apiKey | Body | string | 否 | 访问密钥 |
| params | Body | object | 否 | 额外参数 |
| enabled | Body | bool | 否 | 是否启用，默认 true |

- **出参**：同模型列表元素字段（apiKey 脱敏）。
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

- **出参**：同模型列表元素字段（apiKey 脱敏）。

#### DELETE /api/v1/model-configs/{id} — 删除模型配置
- **功能**：删除一个模型配置。
- **鉴权**：`model:delete`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | Path | int | 是 | 模型配置 ID |

- **出参**：`{ deleted: bool }`。

### 5.10 运维中心-审计（audit）

#### GET /api/v1/audit-logs — 审计日志查询
- **功能**：分页查询系统操作审计记录（谁、在哪个项目、做了什么、何时），用于追溯与合规。
- **鉴权**：`audit:read`。
- **入参**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| userId | Query | int | 否 | 按操作人用户 ID 过滤 |
| projectId | Query | int | 否 | 按项目过滤 |
| action | Query | string | 否 | 按动作过滤（如 upload_file、rename_directory） |
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
| action | string | 动作（如 upload_file、rename_file、rename_directory、approve_project） |
| targetType | string | 操作对象类型（如 file、fs_node、project、skill） |
| targetId | string | 操作对象 ID |
| detail | object | 操作明细（JSON） |
| createdAt | string | 操作时间 |

---

## 第 6 章 Skill 与数据中心的边界

一条核心边界：**skill / 业务模块 / 外部系统读写数据，全部通过本文档接口完成，不直接读写磁盘文件、不直连数据库。**

原因：文件本体与库内目录索引（`fs_nodes`）、血缘（`file_lineage`）是配套的，必须成对变更才能保持一致。绕过 API 直接动磁盘会造成「磁盘有文件但目录树查不到」或「目录树有记录但文件不存在」等不一致。

实践要点（v2）：

- 文件读写用**语义参数**直接调用（`projectId + moduleCode + fileStage + folderSubPath + fileName`），无需先取内部 ID。
- 写文件经 `POST /files/upload`；读文件经 `POST /files/list` 定位 + `GET /files/download`；不要直接动磁盘。
- Skill 包文件经 `/skills/{pk}/files*` 系列接口读写。
- 组织资产只读引用（`moduleCode=org-assets`），不调用写接口去改它（元数据维护除外，且建议管理员）。

---

## 第 7 章 版本与演进

接口随业务演进，遵循「加法自由、破坏可控」。

### 7.1 分水岭
- 标注 `experimental` / 尚无稳定调用方的接口：可自由变更，仅记改动记录。
- 一旦被 skill / 模块 / 外部系统稳定调用，即成契约，受 §7.2 约束。

### 7.2 兼容性约定（已有调用方时）
1. 不删除、不重命名已发布接口的路径与字段。
2. 新增请求参数为可选并带默认值。
3. 响应只增不减字段，不改已有字段类型与语义。
4. 客户端宽容读取响应中的未知字段。
5. 保持错误码语义稳定，可新增、不可改旧码含义。
6. 写操作尽量幂等，便于安全重试。

### 7.3 版本策略：多版本并存
- 破坏性接口变更通过新增大版本前缀实现（`/api/v2`），不在 `/api/v1` 上做破坏性改动。
- 新旧版本并存一个迁移窗口期，老版本下线前公告。

### 7.4 SSOT
- 接口字段 SSOT 为 OpenAPI（`/docs`、`/openapi.json`）；本文档描述功能/含义/约束，字段细节以 OpenAPI 为准。

---

## 附录 A 相对 v1 的变更对照

> 本表汇总 v2 相对 v1（《AIDA 数据中心 API 调用规范》v2.3）的接口变更，便于存量调用方迁移。

### A.1 文件 / 目录：旧 ID 寻址 → 新语义寻址

| 旧接口（v1，已下线） | 新接口（v2） | 说明 |
| --- | --- | --- |
| `GET /files`（query） | `POST /files/list`（body） | 入参增 folderSubPath；keyword→fileKeyword；出参 fileLogicalName→fileDisplayName |
| `POST /files/upload`（targetNodeId） | `POST /files/upload`（语义 form） | 删 targetNodeId，改 projectId+moduleCode+fileStage+folderSubPath；fileLogicalName→fileDisplayName |
| `GET /files/{fileId}/download` | `GET /files/download`（query 语义） | 不再用 fileId，改语义查询参数 |
| `DELETE /files/{fileId}` | `POST /files/delete`（body 语义） | 不再用 fileId |
| （无） | `POST /files/rename` | **新增**：重命名文件 |
| `POST /directories`（parentNodeId） | `POST /directories/create`（语义 body） | 删 parentNodeId；name→directoryName |
| `DELETE /directories/{nodeId}` | `POST /directories/delete`（body 语义） | 不再用 nodeId |
| （无） | `POST /directories/rename` | **新增**：重命名目录（级联更新子孙路径） |

### A.2 组织资产

| 旧接口（v1） | 新接口（v2） | 说明 |
| --- | --- | --- |
| `PUT /org-assets/{fileId}`（maintainerId） | `POST /org-assets/update`（assetName + maintainerUsername） | 不再用 fileId；维护人改用 username |
| 下载经 `GET /files/{fileId}/download` | `GET /files/download?moduleCode=org-assets&fileName=...` | 走统一语义下载 |

### A.3 认证 / 项目

| 变更 | 说明 |
| --- | --- |
| **新增** `POST /api/v1/auth/login` | 外部服务登录，返回 accessToken + 角色/权限上下文 |
| **新增** `GET /api/v1/projects/my` | 当前用户参与的项目（前端主列表用） |
| **新增** `GET /api/v1/users/{username}/projects` | 按用户名查其项目（本人或管理员） |
| **新增** `POST /api/v1/projects/runtime-context` | 项目运行上下文（CLaw 拉起运行态） |
| **变更** `GET /api/v1/projects` | 由「可选鉴权列全部」收紧为**仅管理员** |

---

## 改动记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| v3.0 | 2026-06-12 | 文件/目录/组织资产全面语义寻址（去 fileId/nodeId 入参）；下载改 GET 查询参数；新增文件/目录重命名；项目列表按用户隔离（GET /projects 仅管理员 + /projects/my + /users/{username}/projects）；新增外部登录与运行上下文接口；附录 A 给出 v1→v2 迁移对照 |
