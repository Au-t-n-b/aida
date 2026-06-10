# AIDA 数据中心 API 调用规范

> **版本**：v2.3 · 2026-06-08
> **定位**：数据中心服务对外接口的调用说明，按功能模块逐接口给出功能、鉴权、入参、出参与调用约束。业务模块 / skill 对数据的一切操作均通过本文档接口完成。
> **目的**：让人和 AI（skill）**不看源码即可知道**——数据中心提供哪些能力、每个接口怎么调（方法/路径/参数及其含义/必填性）、**返回哪些字段及其含义**、需要什么权限、典型业务场景按什么顺序调。从而任何模块/skill 都能正确完成数据操作。
> **读者**：写 skill、做业务开发、对接数据中心的同学
> **配套**：数据本身的规则（存在哪、谁能读写）见《AIDA 业务数据规范》。
> **SSOT**：接口字段最终以运行时 OpenAPI 文档 `http://<服务地址>/docs`（及 `/openapi.json`）为准；本文档描述功能、含义、约束与典型流程，分歧以 OpenAPI 为准。

---

## 目录

- [第 1 章 通用约定](#第-1-章-通用约定)
- [第 2 章 功能模块总览](#第-2-章-功能模块总览)
- [第 3 章 数据定位与发现](#第-3-章-数据定位与发现)
- [第 4 章 标准数据流程配方](#第-4-章-标准数据流程配方)
- [第 5 章 接口详解](#第-5-章-接口详解)
  - [5.1 认证（auth）](接口/auth.md)
  - [5.2 项目（project）](接口/project.md)
  - [5.3 文件与目录（file / directory）](接口/file.md)
  - [5.4 组织资产（org-asset）](接口/org-asset.md)
  - [5.5 数据血缘（lineage）](接口/lineage.md)
  - [5.6 Skill 中心（skill）](接口/skill.md)
  - [5.7 配置中心-人员（user-mgmt）](接口/user-mgmt.md)
  - [5.8 配置中心-角色与权限（rbac）](接口/rbac.md)
  - [5.9 配置中心-模型（model-config）](接口/model-config.md)
  - [5.10 运维中心-审计（audit）](接口/audit.md)
- [第 6 章 Skill 与数据中心的边界](#第-6-章-skill-与数据中心的边界)
- [第 7 章 版本与演进](#第-7-章-版本与演进)

---

## 第 1 章 通用约定

### 1.1 基础

| 项 | 约定 |
| --- | --- |
| Base URL | `http://<服务地址>` |
| 版本前缀 | 所有接口以 `/api/v1` 开头 |
| 健康检查 | `GET /api/v1/health` |
| 内容类型 | JSON 接口 `application/json`；上传 `multipart/form-data` |
| 字段风格 | 请求/响应字段为 **camelCase**（如 `projectId`、`fileStage`） |

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
文件下载类接口直接返回二进制流（`Content-Disposition` 带文件名），不走上述封套。

### 1.3 入参 / 出参的表达约定

- **入参**表列：`参数 | 位置 | 类型 | 必填 | 说明`。
  - **位置**：`Path`（路径变量）/ `Query`（URL 查询参数）/ `Body`（JSON 请求体）/ `Form`（multipart 表单）。
  - **必填**：`是` / `否`（"否"即可选参数）。
- **出参**表列：`字段 | 类型 | 说明`，逐字段列出 `data` 的内容。
- 文中示例里以 `$VAR` 表示占位变量（如 `$PID`、`$UPSTREAM_MODULE`），调用时替换为实际值。

### 1.4 分页参数（列表类接口通用）

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| page | Query | int | 否 | 页码，默认 1，≥1 |
| pageSize | Query | int | 否 | 每页条数，默认 20，范围 1~200（人员接口上限 100） |

### 1.5 鉴权

| 接口类别 | 鉴权 | 说明 |
| --- | --- | --- |
| 管理类（内部） | 必须 JWT + RBAC | 缺 token 返回 401；权限不足返回 403。请求头 `Authorization: Bearer <token>` |
| 数据交换类（外部/机机） | 可选 | 带 token 走 RBAC；不带 token 本期放行 |

- Token 由 `POST /api/v1/users/login` 获取。
- 下文每个接口标注【鉴权】：`必填` / `可选` / 所需权限点（如 `skill:list`）。

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
| 1 | 认证 auth | `/api/v1/users` | 注册、登录、当前用户、删除用户 | 取 token |
| 2 | 项目 project | `/api/v1/projects` | 项目 CRUD、审批、成员、目录树 | 项目空间与目录树入口 |
| 3 | 文件 file | `/api/v1/files`、`/api/v1/directories`、`/api/v1/storage` | 业务文件增删查、目录增删、存储统计 | **业务数据面核心** |
| 4 | 组织资产 org-asset | `/api/v1/org-assets` | 公共/主数据只读、元数据维护 | 参考/主数据 |
| 5 | 数据血缘 lineage | `/api/v1/file-lineage` | 文件血缘查询 | 数据追溯 |
| 6 | Skill 中心 skill | `/api/v1/skills` | Skill 注册/发布/包文件/融合 | Skill 文件管理 |
| 7 | 配置中心-人员 user-mgmt | `/api/v1/user-mgmt` | 人员 CRUD | 独立业务数据 |
| 8 | 配置中心-角色权限 rbac | `/api/v1/roles`、`/api/v1/permissions` | 角色、权限点、映射 | 权限 |
| 9 | 配置中心-模型 model-config | `/api/v1/model-configs` | 模型配置 CRUD | 模型 |
| 10 | 运维中心-审计 audit | `/api/v1/audit-logs` | 审计日志查询 | 操作留痕 |

> 对 skill 业务开发最常用的是模块 3/4/5/6（文件、组织资产、血缘、Skill）。

---

## 第 3 章 数据定位与发现

任何读写前先定位目标对象，拿到 `nodeId`（目录/放文件用）或 `fileId`（下载/删除/血缘用）。

| 方式 | 接口 | 用途 |
| --- | --- | --- |
| 查项目目录树 | `GET /api/v1/projects/{uuid}/tree` | 拿到各级目录与文件节点（含 nodeId、fileId、moduleCode、fileStage） |
| 按条件筛文件 | `GET /api/v1/files` | 定位某模块某阶段的文件，拿 fileId |
| 查组织资产 | `GET /api/v1/org-assets`、`/tree` | 定位公共表 |

- `fileStage` 取值：`输入文件` / `解析结果` / `输出结果`。
- `moduleCode` 取值见数据规范第 3.4 节（以 `app/constants/modules.py` 为准）。

---

<a id="dc-recipes"></a>

## 第 4 章 标准数据流程配方

可复制的调用序列（curl 示意，省略 token）。**示例中的 `$VAR` 与具体取值均为占位/示例，请替换为实际值**。

### 4.1 读上游模块的「输出结果」作为输入

```bash
# 约定：$PID=项目ID(project_id)，$UPSTREAM_MODULE=上游模块代码（示例：合同则填 contract）
# 1) 定位上游输出文件
curl "$BASE/api/v1/files?projectId=$PID&moduleCode=$UPSTREAM_MODULE&fileStage=输出结果"
#    → data.list[].fileId

# 2) 下载
curl -OJ "$BASE/api/v1/files/$FILE_ID/download"
```

### 4.2 把中间态写入本模块「解析结果」

```bash
# 1) 从目录树取本模块「解析结果」目录的 nodeId（按 moduleCode + fileStage=解析结果 过滤）
curl "$BASE/api/v1/projects/$UUID/tree"

# 2) 上传到该目录（$PARSE_NODE_ID=解析结果目录节点ID）
curl -F "file=@<本地文件>" -F "targetNodeId=$PARSE_NODE_ID" \
     -F "fileLogicalName=<文件业务名>" "$BASE/api/v1/files/upload"
```

### 4.3 产出对外成品到「输出结果」并登记血缘

> 放 `解析结果` 还是 `输出结果` 由 skill 逻辑决定；个别模块若有发布动作（如交付预案 Release）按其自身规则执行。

```bash
# 1) 上传到本模块「输出结果」目录（$OUT_NODE_ID=输出结果目录节点ID）
curl -F "file=@<本地成品>" -F "targetNodeId=$OUT_NODE_ID" "$BASE/api/v1/files/upload"
#    → data.fileId（新成品）

# 2) 登记血缘：成品由某上游文件加工而来（接口能力见 §5.5）
```

### 4.4 引用组织资产（只读）

```bash
curl "$BASE/api/v1/org-assets?keyword=<公共表关键词>"   # 定位，拿 fileId
curl -OJ "$BASE/api/v1/files/$ASSET_FILE_ID/download"   # 下载（组织资产文件同样用文件下载接口）
```

### 4.5 Skill 包文件读写

```bash
curl "$BASE/api/v1/skills/$SKILL_PK/files"                              # 列包内文件
curl "$BASE/api/v1/skills/$SKILL_PK/files/content?relPath=<包内相对路径>" # 读单个文件
curl -X PUT "$BASE/api/v1/skills/$SKILL_PK/files" \
     -H 'Content-Type: application/json' \
     -d '{"relPath":"<包内相对路径>","content":"<文本内容>"}'             # 写单个文件
```

---

## 第 5 章 接口详解

> 每个接口给出【功能】【鉴权】【入参】【出参】，入参与出参均为独立表格。分页接口的出参为 `list[]` 元素字段，外层另含 `total`。无入参的接口会注明「无」。


> §5 已按模块拆分到 `接口/` 子目录（每次只读你要的那个，省 token）。通用约定见 §1、数据定位见 §3、标准流程配方见 §4。

| 模块 | 接口文件 | 行数 |
|---|---|---|
| 5.1 认证（auth） | [`接口/auth.md`](接口/auth.md) | 75 |
| 5.2 项目（project） | [`接口/project.md`](接口/project.md) | 303 |
| 5.3 文件与目录（file / directory） | [`接口/file.md`](接口/file.md) | 134 |
| 5.4 组织资产（org-asset） | [`接口/org-asset.md`](接口/org-asset.md) | 60 |
| 5.5 数据血缘（lineage） | [`接口/lineage.md`](接口/lineage.md) | 22 |
| 5.6 Skill 中心（skill） | [`接口/skill.md`](接口/skill.md) | 290 |
| 5.7 配置中心-人员（user-mgmt） | [`接口/user-mgmt.md`](接口/user-mgmt.md) | 117 |
| 5.8 配置中心-角色与权限（rbac） | [`接口/rbac.md`](接口/rbac.md) | 150 |
| 5.9 配置中心-模型（model-config） | [`接口/model-config.md`](接口/model-config.md) | 105 |
| 5.10 运维中心-审计（audit） | [`接口/audit.md`](接口/audit.md) | 32 |

## 第 6 章 Skill 与数据中心的边界

一条核心边界：**skill / 业务模块读写数据，全部通过本文档接口完成，不直接读写磁盘文件、不直连数据库。**

原因：文件本体与库内目录索引（`fs_nodes`）、血缘（`file_lineage`）是配套的，必须成对变更才能保持一致。绕过 API 直接动磁盘会造成「磁盘有文件但目录树查不到」或「目录树有记录但文件不存在」等不一致。详见《AIDA 业务数据规范》§6.3。

实践要点：

- 放文件先定位 `targetNodeId`，经 `POST /files/upload`；不要往磁盘目录直接写。
- 读文件经 `GET /files` 定位 + `GET /files/{id}/download`；不要直接读磁盘路径。
- Skill 包文件经 `/skills/{pk}/files*` 系列接口读写。
- 组织资产只读，不调用任何写接口去改它。

---

## 第 7 章 版本与演进

接口随业务演进，遵循「加法自由、破坏可控」。

### 7.1 分水岭

- 标注 `experimental` / 尚无稳定调用方的接口：可自由变更，仅记改动记录。
- 一旦被 skill / 模块稳定调用，即成契约，受 §7.2 约束。

### 7.2 兼容性约定（已有调用方时）

1. 不删除、不重命名已发布接口的路径与字段。
2. 新增请求参数为可选并带默认值。
3. 响应只增不减字段，不改已有字段类型与语义。
4. 客户端宽容读取响应中的未知字段（遇到不认识的字段忽略，不报错）。
5. 保持错误码语义稳定，可新增、不可改旧码含义。
6. 写操作尽量幂等（如上传重名加时间戳），便于安全重试。

### 7.3 版本策略：多版本并存

- 破坏性接口变更通过新增大版本前缀实现（`/api/v2`），不在 `/api/v1` 上做破坏性改动。
- 新旧版本并存一个迁移窗口期，老版本下线前公告。
- 新增接口、新增可选参数、修 bug 在当前版本内进行。

### 7.4 废弃流程

1. 接口标 `deprecated`，文档注明替代接口与预计移除版本。
2. 响应可附带 `Deprecation` / `Sunset` 头提示。
3. 通过审计日志确认无调用方后，随新版本下线。

### 7.5 SSOT 与变更可见性

- 接口字段 SSOT 为 OpenAPI（`/docs`、`/openapi.json`）；本文档描述功能/含义/约束，字段细节以 OpenAPI 为准。
- 建议在 CI 对 OpenAPI 做 diff，删字段/改类型等破坏性变更自动告警。

### 7.6 决策记录（ADR）

接口大版本升级、协议风格调整记录 ADR（背景/决定/理由/被取代的旧决策），与数据规范共用同一 ADR 索引。

---

## 改动记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| v2.0 | 2026-06-08 | 重写为专业版：按 10 个功能模块逐接口给出功能/鉴权/入参/出参 |
| v2.1 | 2026-06-08 | 新增「目的」声明；入参改表格 + 必填列；展开功能说明；§4 配方占位化 |
| v2.2 | 2026-06-08 | 所有接口拆为独立小节；出参逐字段列全并给含义（按 service 实际返回） |
| v2.3 | 2026-06-08 | **每个接口的入参与出参一律用独立表格**，取消行内紧凑写法与「对象引用」简写；入参逐一核对 schema、出参逐一核对 service 实际返回值 |
