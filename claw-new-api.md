# AIDA 数据中心 · CLaw Manager 新增接口文档

> 版本：v1.0 | 日期：2026-06-11

本文档描述数据中心为 CLaw Manager MVP 新增的 3 个接口。所有接口沿用数据中心现有规范：统一 `/api/v1` 前缀、统一响应包络 `{code, message, data}`、camelCase 字段名。

---

## 目录

| 序号 | 接口 | 用途 | 鉴权 |
|---|---|---|---|
| 1 | `POST /api/v1/auth/login` | CLaw 登录，返回 token + 用户完整档案 | 无 |
| 2 | `GET /api/v1/projects/my` | 当前用户参与的项目列表 | Bearer token |
| 3 | `POST /api/v1/projects/runtime-context` | 用户在指定项目下的运行上下文 | Bearer token |

---

## 通用约定

### 鉴权方式

除登录接口外，其余接口均携带：

```http
Authorization: Bearer {accessToken}
```

### 统一响应包络

成功：

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

失败：

```json
{
  "code": <错误码>,
  "message": "<错误描述>",
  "data": null
}
```

### 项目 ID

项目标识 `projectId` 使用 `projects.project_id`（UUID32 去横线字符串），示例：`4f8a7f2e4b9141de9fd2c6d8f0a1b2c3`。

---

## 接口一：CLaw 登录

### `POST /api/v1/auth/login`

#### 1.1 用途

CLaw Manager 调用数据中心登录接口，完成用户认证，获取后续请求所需的 accessToken，同时返回用户的全局角色和权限列表。

> 注意：原有 `POST /api/v1/users/login` 保留不动（向后兼容），本接口为 CLaw 专用，响应格式不同。

#### 1.2 请求

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{
  "username": "pd_user",
  "password": "pd123"
}
```

#### 1.3 请求字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `username` | string | 是 | 登录用户名 |
| `password` | string | 是 | 登录密码 |

#### 1.4 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "accessToken": "eyJhbGciOi...",
    "tokenType": "Bearer",
    "user": {
      "userId": "1",
      "username": "pd_user",
      "displayName": "pd_user",
      "email": "pd_user@example.com",
      "status": 1,
      "globalRoles": [
        {
          "roleCode": "PD",
          "roleName": "项目总监"
        }
      ],
      "permissions": [
        "project:list",
        "project:read",
        "skill:list",
        "skill:read"
      ]
    }
  }
}
```

#### 1.5 响应字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `accessToken` | string | 是 | 后续请求的 Bearer token |
| `tokenType` | string | 是 | 固定 `"Bearer"` |
| `user.userId` | string | 是 | 用户 ID（数据库主键，字符串形式） |
| `user.username` | string | 是 | 用户名 |
| `user.displayName` | string | 是 | 展示名；当前版本回退为 username |
| `user.email` | string | 否 | 邮箱 |
| `user.status` | int | 是 | 用户状态（1=正常） |
| `user.globalRoles` | array | 是 | 全局角色列表 `[{roleCode, roleName}]` |
| `user.permissions` | array | 是 | 全局权限码列表（已排序） |

#### 1.6 错误响应

| 场景 | code | HTTP 状态 | message |
|---|---|---|---|
| 用户名或密码错误 | 1002 | 400 | `invalid username or password` |
| 用户被禁用 | 1003 | 403 | `user disabled` |

---

## 接口二：当前用户参与的项目列表

### `GET /api/v1/projects/my`

#### 2.1 用途

登录成功后，CLaw Manager 使用 token 获取当前用户参与的所有项目，用于前端 landing 页面展示。

**"参与"的口径**：`user_project_roles` 表中有该用户的记录（项目级角色）∪ 该用户是项目的 creator / TD / PD / PCM（取并集）。

#### 2.2 请求

```http
GET /api/v1/projects/my?page=1&pageSize=100
Authorization: Bearer {accessToken}
```

#### 2.3 Query 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` | int | 否 | 1 | 页码 |
| `pageSize` | int | 否 | 20 | 每页数量（最大 200） |
| `status` | string | 否 | - | 项目状态筛选；不传则返回所有参与项目 |
| `keyword` | string | 否 | - | 项目名 / 项目编码模糊搜索 |

#### 2.4 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "id": 123,
        "projectId": "4f8a7f2e4b9141de9fd2c6d8f0a1b2c3",
        "projectName": "京东三期智算中心",
        "projectCode": "K1903",
        "bidCode": "BID-2026-001",
        "customerName": "京东",
        "status": "APPROVED",
        "stage": "delivery",
        "progress": 30,
        "risk": "low",
        "description": "三期智算中心交付项目",
        "creatorId": 1,
        "creatorName": "admin",
        "tdUserId": 2,
        "tdName": "td_user",
        "pdUserId": 3,
        "pdName": "pd_user",
        "pcmUserId": 4,
        "pcmName": "pcm_user",
        "rootPath": "/opt/aida/aida-data/business/projects/4f8a7f2e4b9141de9fd2c6d8f0a1b2c3",
        "createdAt": "2026-06-08T10:00:00",
        "updatedAt": "2026-06-08T10:00:00",
        "myRoles": [
          {
            "roleCode": "PD",
            "roleName": "项目总监"
          }
        ],
        "canEnter": true
      },
      {
        "id": 124,
        "projectId": "7a8b9c0d1e2f34567890abcdef123456",
        "projectName": "A1 智算集群一期",
        "projectCode": "A1",
        "bidCode": "BID-2026-002",
        "customerName": "某客户",
        "status": "PENDING_APPROVAL",
        "stage": null,
        "progress": 0,
        "risk": "low",
        "description": null,
        "creatorId": 1,
        "creatorName": "admin",
        "tdUserId": null,
        "tdName": null,
        "pdUserId": 3,
        "pdName": "pd_user",
        "pcmUserId": null,
        "pcmName": null,
        "rootPath": "/opt/aida/aida-data/business/projects/7a8b9c0d1e2f34567890abcdef123456",
        "createdAt": "2026-06-09T14:00:00",
        "updatedAt": "2026-06-09T14:00:00",
        "myRoles": [
          {
            "roleCode": "TD",
            "roleName": "技术交付"
          }
        ],
        "canEnter": false,
        "disabledReason": "project status is PENDING_APPROVAL"
      }
    ],
    "total": 2
  }
}
```

#### 2.5 响应字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | number | 是 | 数据库内部主键 |
| `projectId` | string | 是 | 项目 UUID32 |
| `projectName` | string | 是 | 项目名称 |
| `projectCode` | string | 否 | 业务项目编号 |
| `bidCode` | string | 否 | 投标 / 商务编码 |
| `customerName` | string | 否 | 客户名称 |
| `status` | string | 是 | 项目状态（`PENDING_APPROVAL` / `APPROVED` / `REJECTED` / `ARCHIVED`） |
| `stage` | string | 否 | 项目阶段 |
| `progress` | int | 是 | 进度百分比 |
| `risk` | string | 是 | 风险等级 |
| `description` | string | 否 | 项目描述 |
| `creatorId` | number | 是 | 创建人 ID |
| `creatorName` | string | 否 | 创建人用户名 |
| `tdUserId` | number | 否 | 技术交付负责人 ID |
| `tdName` | string | 否 | 技术交付负责人用户名 |
| `pdUserId` | number | 否 | 项目总监 ID |
| `pdName` | string | 否 | 项目总监用户名 |
| `pcmUserId` | number | 否 | PCM ID |
| `pcmName` | string | 否 | PCM 用户名 |
| `rootPath` | string | 否 | 项目物理根目录 |
| `createdAt` | string | 否 | 创建时间（ISO 8601） |
| `updatedAt` | string | 否 | 更新时间（ISO 8601） |
| `myRoles` | array | 是 | 当前用户在该项目下的角色列表 `[{roleCode, roleName}]` |
| `canEnter` | bool | 是 | 是否允许进入该项目（`status == "APPROVED"` 时为 true） |
| `disabledReason` | string | 否 | 不可进入原因（仅 `canEnter=false` 时出现） |

#### 2.6 业务规则

1. 必须登录（Bearer token 有效）。
2. 只返回当前 token 用户参与的项目。
3. `canEnter` 用于前端判断是否允许点击进入。
4. 即使 `canEnter=false`，也返回该项目用于展示。
5. `myRoles` 来自 `user_project_roles` 表中该用户在该项目下的角色分配；未分配角色时为空数组。

#### 2.7 错误响应

| 场景 | code | HTTP 状态 | message |
|---|---|---|---|
| 未登录 / token 无效 | 401 | 401 | `缺少 Token` 或 `无效或过期的 Token` |

---

## 接口三：项目运行上下文

### `POST /api/v1/projects/runtime-context`

#### 3.1 用途

用户在前端选择项目后，CLaw Manager 调用该接口，获取当前用户在该项目下的完整运行上下文。该接口是 MVP 最核心接口，返回：

1. 项目基础信息
2. 用户信息
3. 用户在该项目下的角色（数组）
4. 权限（MVP 返回 `{}`，语义为全放开）
5. 组织资产根目录（orgRoot）
6. 项目数据根目录（projRoot）
7. 可加载的 Skill 路径列表（skillPaths）
8. 注入容器的环境变量（env）

#### 3.2 请求

token 走 `Authorization: Bearer {accessToken}` 标识调用方身份，body 的 `user` + `project` 定位「哪个用户在哪个项目下」。

```http
POST /api/v1/projects/runtime-context
Content-Type: application/json
Authorization: Bearer {accessToken}
```

```json
{
  "user": "pd_user",
  "project": "4f8a7f2e4b9141de9fd2c6d8f0a1b2c3"
}
```

#### 3.3 请求字段

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `user` | string | 是 | 用户名（登录响应的 `user.username`） |
| `project` | string | 是 | 项目 `project_id`（UUID32 去横线） |

请求头：

| Header | 必填 | 说明 |
|---|---|---|
| `Authorization` | 是 | `Bearer {accessToken}` |
| `Content-Type` | 是 | `application/json` |

#### 3.4 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "project": {
      "id": 123,
      "projectId": "4f8a7f2e4b9141de9fd2c6d8f0a1b2c3",
      "projectName": "京东三期智算中心",
      "projectCode": "K1903",
      "status": "APPROVED"
    },
    "user": {
      "userId": "3",
      "username": "pd_user",
      "displayName": "pd_user"
    },
    "projectRoles": [
      {
        "roleCode": "PD",
        "roleName": "项目总监"
      }
    ],
    "permissions": {},
    "orgRoot": "/opt/aida/aida-data/business/org-assets",
    "projRoot": "/opt/aida/aida-data/business/projects/4f8a7f2e4b9141de9fd2c6d8f0a1b2c3",
    "skillPaths": [
      "/opt/aida/aida-data/skill/org/zhgk/zhgk-skill",
      "/opt/aida/aida-data/skill/org/guihua/guihua-skill"
    ],
    "env": {
      "AIDA_PROJECT_ID": "4f8a7f2e4b9141de9fd2c6d8f0a1b2c3",
      "AIDA_PROJECT_CODE": "K1903",
      "AIDA_PROJECT_NAME": "京东三期智算中心",
      "AIDA_USER_ID": "3",
      "AIDA_USERNAME": "pd_user",
      "AIDA_PROJECT_ROLE": "PD",
      "ORG_ROOT": "/opt/aida/aida-data/business/org-assets",
      "PROJ_ROOT": "/opt/aida/aida-data/business/projects/4f8a7f2e4b9141de9fd2c6d8f0a1b2c3"
    }
  }
}
```

#### 3.5 响应字段

**`project`**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | number | 否 | 数据库内部主键 |
| `projectId` | string | 是 | 项目 UUID32 |
| `projectName` | string | 是 | 项目名称 |
| `projectCode` | string | 否 | 业务项目编号 |
| `status` | string | 是 | 项目状态 |

**`user`**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `userId` | string | 是 | 用户 ID |
| `username` | string | 是 | 用户名（后台系统标识） |
| `displayName` | string | 是 | 前台展示名；当前版本回退为 username |

**`projectRoles`**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `projectRoles` | array | 是 | 用户在该项目下的角色列表 `[{roleCode, roleName}]` |

说明：同一用户在同一项目可拥有多个角色，全部返回，由 CLaw 侧自行选取。

**`permissions`**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `permissions` | object | 是 | MVP 返回 `{}`，语义为全放开 |

归一化规则（CLaw Manager 侧）：

```text
permissions 为空对象 {} → 所有 canXxx 视为 true
```

**`orgRoot` / `projRoot`**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `orgRoot` | string | 是 | 组织级数据根（NodeAgent 可达的宿主路径） |
| `projRoot` | string | 是 | 当前项目数据根（NodeAgent 可达的宿主路径） |

路径派生规则：

```text
orgRoot  = {BUSINESS_ROOT}/org-assets        → /opt/aida/aida-data/business/org-assets
projRoot = {BUSINESS_ROOT}/projects/{projectId} → /opt/aida/aida-data/business/projects/{projectId}
```

**`skillPaths`**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `skillPaths` | string[] | 是 | 可加载的 Skill 源路径列表（逐个 Skill 子目录） |

说明：

```text
1. 枚举来源：扫描 {SKILL_ROOT}/org/{模块}/{skill_id} 两级目录结构，返回所有叶子 Skill 目录。
2. 数据中心不校验 SKILL.md / skill.manifest.json / is_langgraph，校验由 NodeAgent 负责。
3. skillPaths 可以为空数组（无已部署 Skill 时），但字段必须存在。
```

路径示例：

```text
/opt/aida/aida-data/skill/org/{模块}/{skill_id}

如：
/opt/aida/aida-data/skill/org/zhgk/zhgk-skill
/opt/aida/aida-data/skill/org/guihua/guihua-skill
/opt/aida/aida-data/skill/org/_base/common-skill
```

**`env`**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `env` | object | 是 | 注入容器的环境变量 |

| 变量名 | 说明 |
|---|---|
| `AIDA_PROJECT_ID` | 项目 UUID32 |
| `AIDA_PROJECT_CODE` | 业务项目编号 |
| `AIDA_PROJECT_NAME` | 项目名称 |
| `AIDA_USER_ID` | 用户 ID |
| `AIDA_USERNAME` | 用户名 |
| `AIDA_PROJECT_ROLE` | 用户在该项目下的角色编码（多个时逗号分隔） |
| `ORG_ROOT` | 组织资产根路径（= orgRoot 值） |
| `PROJ_ROOT` | 项目数据根路径（= projRoot 值） |

#### 3.6 业务规则

1. 必须登录（Authorization: Bearer 有效）。
2. `body.project` 对应的项目必须存在，否则返回 404。
3. `body.user` 指定的用户必须参与该项目（`user_project_roles` 有记录 ∪ creator/td/pd/pcm ∪ 全局角色），否则返回 403。
4. 项目状态必须为 `APPROVED`，否则返回 2001 错误。
5. `permissions` MVP 阶段统一返回 `{}`（全放开），后续版本再按需收窄。
6. 所有路径保证是 NodeAgent 可访问的合法宿主路径（由 `.env` 的 `BUSINESS_ROOT` / `SKILL_ROOT` 配置决定）。

#### 3.7 错误响应

| 场景 | code | HTTP 状态 | message |
|---|---|---|---|
| 请求体缺字段 / 格式错误 | 400 | 400 | `参数错误` |
| 未登录 / token 无效 | 401 | 401 | `缺少 Token` 或 `无效或过期的 Token` |
| 用户不属于该项目 | 403 | 403 | `user is not a member of this project` |
| 项目不存在 | 404 | 404 | `project not found` |
| 用户不存在 | 1004 | 404 | `用户 '{username}' 不存在` |
| 项目状态不允许进入 | 2001 | 400 | `project status does not allow runtime activation` |

---

## 端到端调用流程

```text
CLaw Manager 打开登录页
  ↓
POST /api/v1/auth/login  →  拿到 accessToken + user（含 globalRoles/permissions）
  ↓
CLaw Manager 保存 accessToken
  ↓
GET /api/v1/projects/my?page=1&pageSize=100  →  展示用户参与的项目列表
  ↓
用户选择某个 projectId（canEnter=true 的项目）
  ↓
POST /api/v1/projects/runtime-context  →  拿到 projectRoles / orgRoot / projRoot / skillPaths / env
  ↓
CLaw Manager 校验 status==APPROVED（permissions 为空则全放开）
  ↓
NodeAgent:
  · 挂载 orgRoot / projRoot 到容器
  · 逐个校验 skillPaths（SKILL.md + skill.manifest.json）→ 按 is_langgraph 分流 copy
  · 注入 env（含 ORG_ROOT / PROJ_ROOT）
  ↓
拉起容器 → 前端进入 cockpit
```

---

## 配置依赖

数据中心 `.env` 中以下两个配置决定所有路径的前缀：

```env
BUSINESS_ROOT=/opt/aida/aida-data/business
SKILL_ROOT=/opt/aida/aida-data/skill
```

路径派生关系：

| 用途 | 派生规则 | 示例值 |
|---|---|---|
| orgRoot | `{BUSINESS_ROOT}/org-assets` | `/opt/aida/aida-data/business/org-assets` |
| projRoot | `{BUSINESS_ROOT}/projects/{projectId}` | `/opt/aida/aida-data/business/projects/4f8a...b2c3` |
| skillPaths | `{SKILL_ROOT}/org/{模块}/{skill_id}` | `/opt/aida/aida-data/skill/org/zhgk/zhgk-skill` |

---

## 与现有接口的关系

| 新增接口 | 现有接口 | 说明 |
|---|---|---|
| `POST /api/v1/auth/login` | `POST /api/v1/users/login` | 新接口返回完整用户档案；旧接口保留不动 |
| `GET /api/v1/projects/my` | `GET /api/v1/projects` | 新接口按用户过滤 + 带 myRoles/canEnter；旧接口列全部项目 |
| `POST /api/v1/projects/runtime-context` | 无 | 全新接口 |
