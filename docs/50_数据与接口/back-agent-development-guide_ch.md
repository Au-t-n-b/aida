# Back-Agent 开发指南

本文档面向重构后的真实 `backagent` 开发人员，说明它在 GKCLAW 系统中的定位、与 `frontagent` 的关系、需要实现的能力、任务/结果包契约，以及联调验收要求。

本文档不是 `back-agent-mock` 的实现说明。`back-agent-mock` 只是本仓库内的联调工具，真实 `backagent` 应以本文档定义的业务边界和接口契约为准。

## 1. GKCLAW 是什么

GKCLAW 是面向工勘现场的智能协同系统。它把后台任务编排、现场移动端采集、视频/语音实时理解、LLM 结构化记录和结果回传串成一条闭环。

GKCLAW 不是单纯的移动端拍照工具，也不是传统后台表单系统。它的核心价值是：

- backagent 将项目、人员、任务、工勘项和业务依赖组织成正式任务。
- frontagent 在现场执行过程中连接 App、接收语音和视频帧、调用 LLM、维护任务运行态。
- App 让工勘人员通过任务卡片、视频画面、按住说话和 TTS 引导完成现场记录。
- 结果最终回到 backagent，由 backagent 进入正式业务库、审核流、报表或后续流程。

LLM 可以帮助现场会话引导、图像/语音理解、结构化记录和依赖项判断，但正式任务归属、人员分配、结果归档和业务闭环仍由 backagent 掌握。

## 2. 当前集成形态

当前网络条件下，backagent 位于内网，frontagent 位于公网服务器，现场 App 通过公网连接 frontagent。由于防火墙策略暂时无法让公网 frontagent 直接访问内网 backagent，正式跨网通信通过邮件 ZIP 包完成。

```text
backagent 内网
  -> 邮件 task.dispatch ZIP
  -> frontagent 公网服务器
  -> WebSocket
  -> Android App 现场工勘
  -> frontagent 结构化记录和任务运行态
  -> 邮件 task.result ZIP
  -> backagent 入库、审核、归档
```

邮件层是当前网络约束下的兼容传输层，不是业务核心模型。未来如果网络打通，可将邮件替换为 HTTP、消息队列或专线接口，但 backagent/frontagent/App 的职责边界仍应保持。

## 3. frontagent 与 backagent 的关系

backagent 是正式业务系统和数据归档系统，负责“任务从哪里来、属于哪个项目、派给谁、最终结果进入哪里”。

frontagent 是现场智能执行代理，负责“任务如何在现场被语音、视频、图片和 LLM 协同完成”。

App 是现场操作入口，负责“工勘人员如何看见任务、进入任务、采集视频帧、语音交互、触发回传”。

职责边界：

| 领域 | Owner | 说明 |
| --- | --- | --- |
| 项目、人员、正式任务 | backagent | 项目编码、人员工号、任务 ID、任务名称、任务归档均由 backagent 管理。 |
| `task_id` | backagent | 正式任务 ID 必须由 backagent 生成，frontagent 不得改写。 |
| 工勘项模板和分簇 | backagent | backagent 负责编排 `items` 和 `item_clusters`。 |
| 业务依赖规则 | backagent | backagent 负责编排 `dependency_rules`，frontagent 只执行边界校验和运行态落库。 |
| 现场会话运行态 | frontagent | 包括 WebSocket 会话、视频帧缓存、ASR/TTS 代理、LLM 输入输出、本地 task-record。 |
| 结构化记录 | frontagent | RecordLLM 输出本轮记录，frontagent 写入本地任务记录文件。 |
| 结果最终入库 | backagent | frontagent 只导出结果包，backagent 才是正式入库方。 |
| 移动端任务过滤可信执行 | frontagent | App 展示不可信，frontagent 必须按 `surveyor_code` 执行服务端过滤。 |

开发人员应牢记：

- `task_id` 是全链路主键。
- `assignees` 决定任务对哪些工勘人员可见。
- `item_clusters` 决定工勘项在现场如何组织和展示。
- `dependency_rules` 决定复杂业务依赖如何交给 RecordLLM 判断。
- `session.status` 决定回传结果是阶段性回传还是最终回传。
- 邮件主题和正文只用于筛选和排障，ZIP 内 `manifest.json` 与 payload JSON 才是权威数据。

## 4. Backagent 重构后的模块建议

真实 backagent 可以按自身技术栈实现，但至少应具备以下逻辑模块：

- 项目管理：维护 `project_id`、`project_code`、`project_name`。
- 人员管理：维护 `surveyor_code`、`surveyor_name` 和人员可用状态。
- 工勘项模板管理：维护任务模板、选项、示例图、前台备注和后台备注。
- 任务编排：生成正式 `task_id`、任务名称、工勘项列表、分簇、分配人员和依赖规则。
- 依赖规则生成：在任务编排阶段生成 `dependency_rules`。
- ZIP 包生成：生成 `manifest.json`、`task.json` 和资产文件。
- 邮件发件：发送 `task.dispatch` 到 frontagent 邮箱。
- 邮件收件：接收 `task.import_ack`、`task.result`、`task.error`。
- 包解析与校验：校验 manifest、checksum、payload schema 和附件路径。
- 幂等与对账：按 `message_id`、`package_id`、`task_id`、checksum 去重和对账。
- 结果入库：处理阶段性回传和最终回传。
- 运维诊断：展示任务发送、回执、web 链接、结果包、错误包和重试状态。

## 5. 任务生命周期

建议 backagent 内部维护如下状态机：

| 状态 | 含义 | 进入条件 |
| --- | --- | --- |
| `planned` | 任务已编排但未发送。 | 生成任务但尚未发出邮件包。 |
| `dispatched` | 任务包已发送。 | `task.dispatch` 邮件发送成功或进入可重试发件队列。 |
| `accepted` | frontagent 已导入任务。 | 收到 `task.import_ack`，保存 `web_access_url`。 |
| `in_progress` | 现场任务进行中。 | 可由首次阶段性结果、App 进入任务事件或人工状态同步触发。 |
| `staged_returned` | 已收到阶段性结果。 | 收到 `task.result` 且 `result.session.status !== "completed"`。 |
| `completed` | 已收到最终结果。 | 收到 `task.result` 且 `result.session.status === "completed"`。 |
| `failed` | 任务失败。 | 收到不可恢复错误或超过重试策略。 |
| `quarantined` | 需要人工处理。 | 包冲突、checksum 冲突、final 后收到不兼容结果等。 |

backagent 不应通过邮件主题、邮件顺序、App 文案或操作员口头表达判断任务是否最终完成。最终性只看 `result.json.session.status`。

## 6. 标识符约束

### `task_id`

`task_id` 是正式任务主键，由 backagent 在任务下发前生成。

要求：

- 在 backagent 管理域内全局唯一，包括跨项目唯一。
- 创建后不可变。
- 在下发、回执、App 会话、Web 访问、结果回传、错误回传中原样复用。
- 可安全作为文件名片段和 URL path/query 值。
- 不包含个人信息、手机号、身份证号、客户敏感信息。
- 不依赖任务名称或项目名称。

推荐正则：

```text
^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$
```

推荐示例：

```text
task-20260611-ZHGK-000001
task_01HWXYZ8M3Q2K7R9A5BCDEF123
```

### 其他标识符

- `package_id`：包级幂等键。每个 ZIP 包唯一；payload 变化时必须生成新 `package_id`。
- `project_id`：backagent 内部稳定项目 ID，项目改名时不变。
- `project_code`：展示和分组用项目编码，适合放入邮件主题。
- `surveyor_code`：工勘人员身份主键，移动端任务过滤和结果提交校验都应以它为准。
- `surveyor_name`：人员展示名，第一版 Web 访问会与工号一起做精确校验。
- `item_key` / `问题序号`：任务内工勘项唯一键。所有引用建议按字符串值比较。
- `asset_id`：任务包内资产唯一 ID。
- `path`：ZIP 内相对路径，不能是绝对路径，不能包含 `..`。

## 7. 邮件传输契约

双方各自持有一个邮箱：

- backagent 邮箱：发送任务包，接收回执、结果和错误包。
- frontagent 邮箱：接收任务包，发送回执、结果和错误包。

邮箱地址、IMAP/SMTP host、端口、TLS、用户名、授权码都必须是运行时可配置项，不能写死到代码或任务包中。

每封业务邮件应包含：

- 一个简短主题，用于自动筛选和人工排障。
- 一个简短正文，用于粗略说明。
- 一个 ZIP 附件，用于机器处理。

推荐主题：

```text
[GKCLAW][TASK_DISPATCH] {project_code}/{task_id}
[GKCLAW][TASK_IMPORT_ACK] {project_code}/{task_id}
[GKCLAW][TASK_RESULT] {project_code}/{task_id}
[GKCLAW][TASK_ERROR] {project_code}/{task_id}
```

规则：

- 邮件主题和正文不是权威业务数据。
- 接收方必须以 ZIP 内 `manifest.json` 和 payload JSON 为准。
- 没有合法 ZIP 附件的邮件不能创建、更新、完成或取消任务。
- 如果主题/正文与 ZIP metadata 不一致，应记录 warning，并以 ZIP metadata 为准。
- 正常流程不依赖人工转发、重命名或编辑邮件。

## 8. ZIP 包结构

任务下发包：

```text
task-{task_id}.zip
  manifest.json
  task.json
  assets/
    items/
      {item_key}/
        example-1.jpg
        example-2.png
```

导入回执包：

```text
ack-{task_id}.zip
  manifest.json
  ack.json
```

结果回传包：

```text
result-{task_id}.zip
  manifest.json
  result.json
  evidence/
    ...
```

错误回传包：

```text
error-{task_id}.zip
  manifest.json
  error.json
```

所有 JSON 文件必须使用 UTF-8 编码。ZIP 内路径必须使用相对路径。

## 9. Manifest 契约

每个包都必须包含 `manifest.json`。

```json
{
  "schema_version": "gkclaw.mail.v1",
  "package_id": "pkg-20260611-000001",
  "package_type": "task.dispatch",
  "created_at": "2026-06-11T03:00:00.000Z",
  "source": "back-agent",
  "target": "front-agent",
  "task_id": "task-20260611-ZHGK-000001",
  "project_id": "proj-zhgk-2026",
  "project_code": "ZHGK-2026",
  "checksum": {
    "task.json": "sha256:..."
  }
}
```

字段说明：

- `schema_version`：当前为 `gkclaw.mail.v1`。
- `package_id`：发送方生成的包级唯一 ID。
- `package_type`：`task.dispatch`、`task.import_ack`、`task.result`、`task.error`。
- `created_at`：包创建时间，ISO-8601 字符串。
- `source` / `target`：发送方和接收方系统标识。
- `task_id`：正式任务 ID。
- `project_id` / `project_code`：项目上下文。
- `checksum`：相对路径到 `sha256:{hex}` 的映射。

backagent 接收任何 ZIP 包时都应校验：

- manifest 是否存在且可解析。
- `schema_version` 是否支持。
- `package_type` 与实际 payload 文件是否匹配。
- checksum 是否匹配 ZIP entry 原始字节。
- 路径是否安全。
- `task_id`、`package_id` 是否符合幂等和冲突策略。

## 10. 任务下发 Payload

backagent 在 `task.dispatch` 包中发送 `task.json`。

```json
{
  "task_id": "task-20260611-ZHGK-000001",
  "task_name": "液冷机房工勘联调任务 01",
  "project": {
    "project_id": "proj-zhgk-2026",
    "project_code": "ZHGK-2026",
    "project_name": "智慧工勘测试项目"
  },
  "assignees": [
    {
      "surveyor_name": "张三",
      "surveyor_code": "S001"
    }
  ],
  "items": [
    {
      "问题序号": "1",
      "勘测项": "机房门口标识是否清晰",
      "选项列表": ["清晰", "不清晰", "未见标识"],
      "勘测结果": "",
      "to_front_备注": "请让现场人员拍摄或描述门口标识。",
      "to_back_备注": "",
      "示例图": []
    }
  ],
  "item_clusters": [
    {
      "cluster_id": "cluster-basic",
      "cluster_name": "基础环境",
      "item_keys": ["1"]
    }
  ],
  "dependency_rules": [],
  "supplemental_context": null,
  "metadata": {
    "priority": "normal",
    "location_label": "A01 机房"
  }
}
```

必填要求：

- `task_id` 必填，由 backagent 生成。
- `task_name` 必填，用于 App/Web 任务卡片展示。
- `project.project_id`、`project.project_code`、`project.project_name` 必填。
- `assignees` 至少包含一个人员。
- `items` 至少包含一个工勘项。
- `item_clusters` 正式任务必须非空。
- 每个 `items[].问题序号` 必须至少出现在一个 cluster 中。

注意：

- 邮件任务包中的 `project` 和 `assignees` 位于顶层。
- HTTP 兼容接口中的人员过滤字段必须放入 `metadata.assignees`，见本文档“HTTP 兼容接口”。
- `勘测内容` 字段已废弃，不应再下发。

## 11. 工勘项字段

每个 `items[]` 表示一个工勘项。

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `问题序号` | 是 | 任务内唯一工勘项 key。 |
| `勘测项` | 是 | 现场需要核验或采集的内容。 |
| `选项列表` | 是 | 候选答案。自由文本项使用空数组。 |
| `勘测结果` | 否 | 下发时通常为空；结果回传时包含记录结果。 |
| `to_front_备注` | 否 | 给现场引导、frontagent 和 LLM 的提示。 |
| `to_back_备注` | 否 | 给 backagent 结果解释、审核或报表使用的备注。 |
| `示例图` | 否 | 示例图片引用，不内嵌 base64。 |
| `metadata` | 否 | 扩展字段。 |

示例图引用：

```json
{
  "asset_id": "asset-item-1-example-1",
  "path": "assets/items/1/example-1.jpg",
  "mime_type": "image/jpeg",
  "label": "标识示例",
  "description": "用于提示现场拍摄门口标识"
}
```

规则：

- 示例图文件必须真实存在于 ZIP 中。
- `path` 必须是 ZIP 相对路径，不能包含 `..`。
- manifest 中应为每个示例图写 checksum。

## 12. item_clusters 分簇

`item_clusters` 是正式任务必填字段，用于 App 右侧/抽屉工勘项列表分组展示。它不改变工勘项主键，权威工勘项身份仍是 `问题序号`。

```json
[
  {
    "cluster_id": "cluster-power",
    "cluster_name": "供配电",
    "item_keys": ["1", "2", "3"]
  },
  {
    "cluster_id": "cluster-cooling",
    "cluster_name": "制冷系统",
    "item_keys": ["4", "5", "6"]
  }
]
```

要求：

- `cluster_id` 在单任务内唯一。
- `cluster_name` 建议必填，用于展示。
- `item_keys` 只能引用已存在的 `items[].问题序号`。
- cluster 数组顺序就是展示顺序。
- `item_keys` 内顺序就是簇内展示顺序。
- 如果业务上没有分组，也必须生成一个兜底簇，例如 `cluster-all`。

## 13. dependency_rules 依赖规则

复杂工勘任务中，某个前置项结果可能让后续多项直接“不涉及”。这类业务依赖应由 backagent 在任务编排阶段写入 `dependency_rules`。

frontagent 不负责从工勘项名称里硬编码发现依赖，也不做“否/不需要/无需”等字符串硬匹配。frontagent 会把规则和最新运行态交给 RecordLLM，由 RecordLLM 进行语义判断；frontagent 再做边界校验和落库。

```json
{
  "rule_id": "mobile_lift_skip",
  "description": "不需要评估移动升降搬运车时，后续移动升降搬运车相关项不涉及。",
  "trigger_item_keys": ["5"],
  "trigger_semantics": "第5项结果表达不需要评估移动升降搬运车，包括否、不需要、无需、不计划采用、不涉及移动升降搬运车等语义。",
  "target_item_keys": ["6", "7", "8", "9"],
  "action": {
    "type": "mark_not_applicable",
    "result": "不涉及"
  },
  "overwrite": "not_completed_only",
  "confidence_threshold": 0.8
}
```

要求：

- `rule_id` 在单任务内唯一。
- `trigger_item_keys` 和 `target_item_keys` 只能引用已存在工勘项。
- `trigger_semantics` 要写自然语言语义，不要只写固定字符串。
- 当前只支持 `action.type = "mark_not_applicable"`。
- 默认结果是 `不涉及`。
- 默认覆盖策略建议使用 `not_completed_only`。
- 复杂依赖应拆成多条小规则，明确每条规则影响哪些目标项。

规则自动处理后的目标项会像普通结果一样回传。frontagent 会把规则原因追加到 `to_back_备注`，例如：

```text
[规则自动处理: mobile_lift_skip] 第5项结果表达“不需要”，语义等价于无需评估移动升降搬运车。
```

更详细的字段和编排建议见 `docs/back-agent-dependency-rules-guide_ch.md`。

## 14. 导入回执 Payload

frontagent 成功导入任务后，会返回 `task.import_ack` 包，其中 `ack.json` 形如：

```json
{
  "status": "accepted",
  "task_id": "task-20260611-ZHGK-000001",
  "task_name": "液冷机房工勘联调任务 01",
  "project": {
    "project_id": "proj-zhgk-2026",
    "project_code": "ZHGK-2026",
    "project_name": "智慧工勘测试项目"
  },
  "assignees": [
    {
      "surveyor_name": "张三",
      "surveyor_code": "S001"
    }
  ],
  "web_access_url": "https://front-agent.example.com/tasks/web/wa_7b4f...",
  "accepted_at": "2026-06-11T03:01:00.000Z"
}
```

backagent 必须：

- 按 `task_id` 关联任务。
- 保存 `web_access_url`，并把它视为 opaque URL。
- 将任务状态推进到 `accepted`。
- 对重复 ACK 做幂等处理。
- 若 ACK 中项目、任务或人员信息与原任务不一致，应进入告警或隔离流程。

## 15. Web 访问契约

每个正式任务成功导入后，frontagent 会生成唯一 `web_access_url`。

用户打开链接后：

1. 页面要求输入姓名和工号。
2. frontagent 校验该姓名和工号是否匹配任务 `assignees` 中任意一人。
3. 匹配成功后进入该任务的 Web 会话界面。
4. 匹配失败则拒绝访问。

第一版身份验证使用 `surveyor_name` 和 `surveyor_code` 精确匹配。因此 backagent 应保持人员姓名和工号规范稳定。

## 16. App 任务可见性

App 登录只采集：

- `surveyor_name`
- `surveyor_code`

App 查询任务时，frontagent 根据 `surveyor_code` 执行服务端过滤。App 本地过滤只能作为展示优化，不能作为权限边界。

任务卡片需要展示：

- 项目名称
- 项目编码
- 任务名称
- 任务 ID 或任务编码
- 任务状态

如果 frontagent 收到某个当前 App 缓存中不存在的人员任务，仍应导入任务。该任务会在用户切换到匹配的姓名/工号后可见。

## 17. 结果回传 Payload

frontagent 回传 `task.result` 包时，`result.json` 应包含完整上下文。

```json
{
  "task_id": "task-20260611-ZHGK-000001",
  "task_name": "液冷机房工勘联调任务 01",
  "project": {
    "project_id": "proj-zhgk-2026",
    "project_code": "ZHGK-2026",
    "project_name": "智慧工勘测试项目"
  },
  "assignees": [
    {
      "surveyor_name": "张三",
      "surveyor_code": "S001"
    }
  ],
  "submitted_by": {
    "surveyor_name": "张三",
    "surveyor_code": "S001"
  },
  "session": {
    "task_id": "task-20260611-ZHGK-000001",
    "status": "completed",
    "started_at": "2026-06-11T03:10:00.000Z",
    "ended_at": "2026-06-11T03:30:00.000Z",
    "last_activity_at": "2026-06-11T03:30:00.000Z"
  },
  "items": [],
  "evidence": [],
  "updates": [],
  "observations": [],
  "exported_at": "2026-06-11T03:31:00.000Z"
}
```

backagent 必须使用 `task_id` 作为结果关联主键，并使用 `submitted_by.surveyor_code` 识别提交人。

## 18. 阶段性回传与最终回传

`result.json.session.status` 是判断结果是否最终的唯一权威字段。

阶段性回传：

```json
{
  "session": {
    "status": "active"
  }
}
```

backagent 行为：

- 保存为当前任务的最新阶段性结果。
- 不关闭任务。
- 不锁定任务。
- 继续接受后续阶段性或最终结果。
- 保留审计记录。

最终回传：

```json
{
  "session": {
    "status": "completed"
  }
}
```

backagent 行为：

- 保存为最终结果。
- 将任务置为 `completed`。
- 可触发归档、审核、报表或后续流转。
- 对重复 final 包做幂等处理。
- 对 final 后到达的不兼容结果包应拒绝或隔离，除非 backagent 明确实现了 reopen/revision 流程。

不要通过以下信息判断最终性：

- 邮件主题。
- 邮件正文。
- 包到达顺序。
- 操作员说了“结束任务”。
- App 当前页面状态。

## 19. 错误 Payload

frontagent 无法导入或处理任务包时，会返回 `task.error` 包。

```json
{
  "task_id": "task-20260611-ZHGK-000001",
  "package_id": "pkg-20260611-000001",
  "phase": "task_import",
  "code": "invalid_task_payload",
  "message": "Missing project.project_name",
  "recoverable": true,
  "reported_at": "2026-06-11T03:02:00.000Z"
}
```

backagent 应记录错误，并根据 `recoverable` 和 `code` 决定：

- 修复后重发。
- 人工介入。
- 取消任务。
- 隔离包并保留审计。

## 20. 幂等、重试与冲突处理

建议幂等键：

- 邮件 `message_id`
- `manifest.package_id`
- `manifest.task_id`
- ZIP 包 checksum
- payload 文件 checksum

推荐策略：

| 场景 | 行为 |
| --- | --- |
| 相同 `package_id` + 相同 checksum | 幂等成功。 |
| 相同 `package_id` + 不同 checksum | 包冲突，拒绝或隔离。 |
| 相同 `task_id` + 相同任务内容重复下发 | 幂等成功。 |
| 相同 `task_id` + 不同任务内容重复下发 | 任务冲突，拒绝或隔离。 |
| 新阶段性结果到达 | 接受并保存新版本。 |
| final 到达 | 接受并关闭任务。 |
| final 后重复 final 且内容一致 | 幂等成功。 |
| final 后收到 staged 或不兼容 final | 拒绝或隔离，除非有显式修订流程。 |

backagent 应提供定时对账能力，至少能回答：

- 哪些任务已发出但没有 ACK？
- 哪些任务收到 ACK 但没有结果？
- 哪些任务已有阶段性结果但未最终完成？
- 哪些包被判定为重复？
- 哪些包进入隔离？
- 哪个包关闭了任务？

## 21. HTTP 兼容接口

正式跨网链路使用邮件包。HTTP 发布接口仍保留给本地 `back-agent-mock`、临时调试和兼容测试：

```http
POST /api/front-agent/tasks
```

HTTP 请求必须使用 frontagent 的 `TaskPublishRequest` 形状。人员和项目需要放到 `metadata` 中：

```json
{
  "task_id": "task-20260611-ZHGK-000001",
  "items": [],
  "item_clusters": [],
  "dependency_rules": [],
  "supplemental_context": null,
  "metadata": {
    "title": "液冷机房工勘联调任务 01",
    "task_name": "液冷机房工勘联调任务 01",
    "project": {
      "project_id": "proj-zhgk-2026",
      "project_code": "ZHGK-2026",
      "project_name": "智慧工勘测试项目"
    },
    "assignees": [
      {
        "surveyor_name": "张三",
        "surveyor_code": "S001"
      }
    ]
  }
}
```

重要：移动端任务可见性读取 `metadata.assignees`。如果 HTTP payload 只在顶层放 `assignees`，frontagent 会把任务视为未绑定人员，可能导致所有工勘员都能看到该任务。

## 22. 安全基线

第一版要求：

- 邮箱授权码、API Key、服务器密码不能写入任务包、源码或文档。
- 邮箱配置必须来自环境变量或安全配置中心。
- ZIP 包必须做路径安全校验。
- `manifest.json` 应声明 checksum。
- `web_access_url` 必须不可猜测，并作为 bearer-style 链接谨慎保存。
- Web 访问必须校验姓名和工号。
- 任务过滤必须由 frontagent 服务端执行。
- backagent 入库前必须校验 `submitted_by.surveyor_code` 属于任务 `assignees`。

后续可增强：

- 包签名。
- ZIP 加密或内容加密。
- 链接过期。
- 一次性访问码。
- SSO 或企业身份源。
- 邮件传输替换为专线 HTTP/MQ。

## 23. 联调流程

最小联调路径：

1. backagent 生成 `task.dispatch` ZIP。
2. backagent 发送邮件到 frontagent 邮箱。
3. frontagent 导入任务。
4. backagent 收到 `task.import_ack` 并保存 `web_access_url`。
5. App 使用任务分配人员的姓名和工号登录。
6. App 任务列表出现对应项目和任务。
7. 现场进入任务并完成若干工勘项。
8. 用户触发“回传结果”，backagent 收到阶段性 `task.result`，任务不关闭。
9. 用户触发“结束任务”，backagent 收到 `session.status=completed` 的最终 `task.result`。
10. backagent 归档结果并关闭任务。

## 24. 验收清单

backagent 达到以下条件即可进入正式联调：

- 能生成合法 `task.dispatch` ZIP，包含 `manifest.json` 和 `task.json`。
- 能生成全局唯一且稳定的 `task_id`。
- 能下发项目名称、项目编码、任务名称和分配人员。
- 能下发非空 `item_clusters`。
- 能在需要时生成 `dependency_rules`，且引用的 item key 全部存在。
- 能发送任务邮件到 frontagent 邮箱。
- 能接收并保存 `task.import_ack.web_access_url`。
- 能接收 `task.result` 并校验 manifest/checksum。
- 能根据 `session.status` 区分阶段性回传和最终回传。
- 能按 `task_id` 关联结果。
- 能按 `submitted_by` 识别提交人。
- 能将规则自动“不涉及”项作为正常结果入库，并保留 `to_back_备注` 中的规则原因。
- 能处理重复任务包、重复 ACK、重复结果包。
- 能隔离相同 `task_id` 不同内容、相同 `package_id` 不同 checksum、final 后不兼容结果等冲突。
- 能提供对账页面或诊断日志，定位未 ACK、未回传、重复、冲突和失败包。

## 25. 常见错误

- 把 `task_name` 或 `project_name` 当主键。
- HTTP 发布时把 `assignees` 放在顶层，导致任务对所有人员可见。
- 正式任务不提供 `item_clusters`。
- 只在邮件正文写业务数据，ZIP 内缺少权威 payload。
- 根据邮件主题判断任务类型或最终性。
- 依赖规则只写“否”这种固定字符串，而不是完整语义。
- final 后静默覆盖已有结果。
- 不校验 ZIP 路径，导致路径逃逸风险。
- 把邮箱授权码或 API Key 写入任务包或仓库。
