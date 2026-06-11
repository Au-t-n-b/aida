# GKCLAW 邮件链路（zhgk = backagent）实现说明与联调手册

> 契约真相源：[back-agent-development-guide_ch.md](back-agent-development-guide_ch.md)（gkclaw.mail.v1）。
> 本文只写 AIDA 侧实现与操作，契约字段不复制（单一真相）。

## 1. 链路与职责

```text
zhgk(backagent·内网) → mailgw POST /api/send → 邮件[task.dispatch ZIP] → frontagent(公网)
        ↑                                                                    ↓ App 现场工勘
  wait_survey 检查时拉取 ← mailgw GET /api/inbox ← 邮件[import_ack/result/error ZIP]
```

- 发送唯一出口：`agent/mailer.py`（`AIDA_MAIL_BACKEND=mailgw`）；收件唯一入口：`agent/mailbox.py`。
- 协议层：`agent/skills/zhgk/services/gkclaw/`（ids/schema/package/registry/mapping/dispatch/ingest）。
- 流水线接点：`confirm_table → task_dispatch(HITL·仅 survey_work) → wait_survey(双源)`。
- 任务状态真相：`ProjectData/RunTime/gkclaw/<task_id>/state.json`（packages.json=包账本，
  results/=回传版本，evidence/=证据，pending_results/=合并阻塞暂存，_quarantine/=隔离区）。

## 2. 状态机与处置规则（实现口径）

planned → dispatched → accepted → staged_returned → completed；failed / superseded。
无 in_progress（无 App 事件通道，staged 到达即 staged_returned）。

- final 唯一判据 = result.json `session.status=="completed"`；staged 只记录展示不推进。
- 幂等（§20）：同 package_id 同 checksum=幂等成功；同 id 异 checksum=冲突隔离；
  final 后 staged=隔离；final 后异内容 final=冲突隔离；未知 task_id=隔离不建任务。
- 重发：契约无撤销包类型 → 内容变更重发=新 task_id，旧任务 superseded（其回传仅留档）。
- final 合并三道闸（任一不过 → pending_results/ 暂存+告警）：submitted_by ∈ assignees；
  表指纹一致（下发后表未变更）；Input/ 无待合并人工表（先到先得）。
- `to_back_备注`（含规则自动"不涉及"原因）留档 result-notes.json（主表无对应列）。

## 3. 字段映射（下发）

仅下发 `勘测方法=="现场勘测"` 行。问题序号=str(序号)；勘测项=检查内容；选项列表=[]；
to_front_备注=【勘测要素/项目】+ 底表`视频勘测背景知识`（自然键回连底表取回，join 失败置空），
`语音助手背景知识`不同则附加；细分场景/是否支持视频勘测/底表序号进 item.metadata。
分簇=物理空间维度：v1 单兜底簇 cluster-all（cluster_name=机房名）；底表增设「物理位置」
列后经 `mapping.derive_clusters(cluster_values=…)` 零代码切换多簇。

## 4. 配置（agent/.env）

| 变量 | 说明 |
|---|---|
| `AIDA_SEND_EMAIL=1` | 真发开关（默认 dry-run：建包登记不发邮件） |
| `AIDA_MAIL_BACKEND=mailgw` | 发送走 mailgw 网关 |
| `MAILGW_BASE` / `MAILGW_TOKEN` | 网关地址与 Bearer token（密钥只进 .env） |
| `GKCLAW_FRONTAGENT_MAILBOX` | frontagent 收件邮箱（**域名须加入 mailgw 白名单**，否则下发卡审批队列） |

人员配置：start payload `assignees` 或 `ProjectData/RunTime/gkclaw/assignees.json`
（`[{"surveyor_name":"张三","surveyor_code":"S001"}]`）；缺失时 task_dispatch 文件型 HITL 阻断。

## 5. 联调流程（契约 §23 对应）

前置交换：对方 frontagent 收件邮箱→填 `GKCLAW_FRONTAGENT_MAILBOX` 并加 mailgw 白名单；
我方 mailgw 邮箱地址告知对方（回传目的地）；双方确认 schema_version=gkclaw.mail.v1、
附件大小上限（mailgw `max_attachment_mb`）。

1. zhgk 跑 survey_work 至 confirm_table 确认 → task_dispatch 选「下发」。
2. 对端导入后回 ACK → wait_survey 卡片出现「对端已导入 + 现场 Web 入口」。
3. App 按 assignees 姓名+工号登录可见任务；阶段回传 → 状态 staged_returned（不推进）。
4. 现场结束任务（final）→ 自动转写 `Input/已填写_全量勘测结果表.xlsx` → wait_survey
   合并 → assess 继续。提示：拉取发生在 wait_survey 检查时（run 启动/每次 resume），
   等邮件期间在页面上提交一次空 resume 即触发刷新。
5. 异常对账：`RunTime/gkclaw/` 下看 state.json/packages.json；隔离包看 `_quarantine/`；
   合并阻塞看任务 `merge_blocked_reason` 与 `pending_results/`。

## 6. 验收对照（契约 §24 → 实现/证据）

| 验收项 | 实现 | 证据 |
|---|---|---|
| 合法 dispatch ZIP（manifest+task.json） | package.build_package | eval: package_build_parse_roundtrip |
| task_id 全局唯一稳定 | ids.new_task_id（seq.txt） | eval: ids_task_id_format_and_uniqueness |
| 项目/人员/任务名下发 | mapping.build_task_payload | eval: mapping_builds_contract_task |
| 非空 item_clusters | derive_clusters 兜底簇 | eval: mapping_clusters_default_single |
| 依赖规则引用校验 | schema.validate_task | eval: schema_task_dependency_rules |
| 发送任务邮件 | mailer mailgw backend | eval: mailer_mailgw_backend_sends |
| 接收并保存 web_access_url | ingest._apply_ack | eval: ingest_ack_updates_state… |
| manifest/checksum 校验 | package.parse_package | eval: package_checksum_tamper_detected |
| staged/final 区分（session.status） | ingest._apply_result | eval: ingest_staged_records_final… |
| 按 task_id 关联、按 submitted_by 识别 | registry + 安全闸 1 | eval: ingest_submitted_by_guard |
| 规则"不涉及"作为正常结果入库+备注留档 | 合并通道 + result-notes.json | eval: final 用例断言 notes |
| 重复包/重复 ACK/重复结果幂等 | decide_inbound | eval: registry_decide_inbound… / ingest_idempotency… |
| 冲突隔离（同 id 异内容/final 后） | decide_inbound + _quarantine | 同上 |
| 对账诊断 | state.json/packages.json/mail_scan.json + SDUI 卡 | 人工巡检（自动对账=后续增强） |

## 7. 已知边界与后续增强

仅 survey_work 下发（supplement 下期）；复勘轮不自动重发（人工上传）；无后台轮询
（cron 自动拉取=后续）；evidence 不回填表内图片列；单 mailgw ↔ 单 AIDA 实例
（workers=1 单写者）；依赖规则编排器、示例图资产、对账页面=后续增强。
