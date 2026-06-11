# GKCLAW 部署与联调指南（zhgk = backagent）

> **读者**：负责服务器部署的工程师 + 与 frontagent 团队联调的对接人。
> 契约真相源：[back-agent-development-guide_ch.md](back-agent-development-guide_ch.md)；
> 实现与字段映射：[GKCLAW邮件链路.md](GKCLAW邮件链路.md)。本文只管「怎么部署、怎么联调、出问题怎么查」。

```text
zhgk(backagent·内网服务器) ──mailgw(同机:8025)──→ 邮件[task.dispatch ZIP] ──→ frontagent(公网)
        ↑                                                                        ↓ App 现场工勘
  wait_survey 检查时拉取 ←──mailgw 收件箱←── 邮件[import_ack / result / error ZIP]
```

---

## 1. 部署前提

| 前提 | 说明 |
|---|---|
| 代码版本 | GKCLAW 链路已合入 master；**mailgw 网关也已并入本仓 `mailgw/` 子目录**（含完整历史）。服务器 `git clone` 本仓即同时获得 AIDA 与 mailgw 两个服务的代码 |
| 同机部署 | mailgw 与 AIDA 后端必须部署在**同一台机器**（附件按本地绝对路径传递，是双方的接口约定） |
| 公司邮箱 | 一个专用邮箱账号（backagent 邮箱）：SMTP 发信 + POP3 收信凭据 |
| 对端信息 | frontagent 收件邮箱地址（联调前由对方提供，见 §6） |
| Python | 3.11+（两个服务各自 venv） |

## 2. mailgw 部署（邮件网关 · 端口 8025 · 代码在本仓 `mailgw/` 子目录）

详细步骤见 [mailgw/docs/部署与配置手册.md](../../mailgw/docs/部署与配置手册.md)（独立 venv 安装
`mailgw/requirements.txt`，与 AIDA 的 venv 分开），此处只列 GKCLAW 相关要点：

1. **凭据**（mailgw `.env`）：公司邮箱 SMTP/POP3 host、端口、账号、授权码；为 AIDA 签发调用 token：
   ```
   MAILGW_TOKEN_AIDA=<随机长串>     # 网关侧命名 MAILGW_TOKEN_<调用方>
   ```
2. **白名单**（mailgw `config.yaml`）：把 **frontagent 邮箱的域名**加入 `whitelist_domains`——
   否则每次任务下发都会卡在人工审批队列。
3. **附件上限**：`max_attachment_mb` 需 ≥ 任务包大小（当前任务包无示例图，几十 KB；
   将来启用示例图资产后按需调大，并与对方确认其邮箱附件上限）。
4. 启动：`python -m mailgw --host 127.0.0.1 --port 8025`（建议 systemd 托管，参考 AIDA 的单元写法）。

## 3. AIDA 后端部署（端口 7401）

完整方案（uvicorn/nginx/systemd/前端构建）见 **ROADMAP Step 3**，GKCLAW 不改变其中任何一条。关键约束复述：

- `uvicorn agent.main:app --host 127.0.0.1 --port 7401 --workers 1`——**workers=1 是硬约束**
  （SSE 要求；GKCLAW 的状态文件单写者假设也依赖它）。
- nginx 反代必须 `proxy_buffering off` + `proxy_http_version 1.1` + 300s 超时（SSE 踩坑表见 ROADMAP §3.4）。
- 工作区初始化：`ZHGK_ROOT` 下 `ProjectData/{Template,Input,Output,RunTime,Images}`，
  **三个模板文件人工放置**到 `Template/`（入场评估标准表.xlsx / 工勘常见高风险库.xlsx / 新版项目工勘报告模板.docx）。
- `agent/.env`：`ZHIPU_API_KEY` 必填（assess 等 LLM 步骤）。

## 4. GKCLAW 链路配置（agent/.env）

```bash
# 真发开关：不设或 ≠1 时全程 dry-run（建包登记但不发邮件）——回退开关就是它
AIDA_SEND_EMAIL=1
# 发送通道：经 mailgw 网关（白名单管控 + 审批 + 留痕）
AIDA_MAIL_BACKEND=mailgw
MAILGW_BASE=http://127.0.0.1:8025
MAILGW_TOKEN=<§2 第 1 步签发的 MAILGW_TOKEN_AIDA 的值>    # 注意：AIDA 侧变量名是 MAILGW_TOKEN
GKCLAW_FRONTAGENT_MAILBOX=<对方提供的 frontagent 收件邮箱>
```

人员配置（任务分配人，App/Web 按姓名+工号校验身份）：
- 方式 A：start 请求体带 `assignees`；
- 方式 B：`ProjectData/RunTime/gkclaw/assignees.json`，内容
  `[{"surveyor_name":"张三","surveyor_code":"S001"}]`。
- 两处都没有时，task_dispatch 会以文件型 HITL 阻断并提示上传。

## 5. 部署后自验（联调前，无需对方参与）

| # | 动作 | 通过标准 |
|---|---|---|
| 1 | 服务器跑离线回归：`agent/.venv/bin/python agent/evals/eval_gkclaw.py` | `[eval-gkclaw] OK · 42/42` |
| 2 | **暂不设** `AIDA_SEND_EMAIL`，跑一次 survey_work 到 task_dispatch 选「下发」 | SDUI 出现 GKCLAW 卡：`已下发 + dry-run 未真发`；`RunTime/gkclaw/<task_id>/outbox/` 有 task-\*.zip |
| 3 | 真实 LLM 全流程 smoke：survey_work 从建表到问题清单跑通一遍（task_dispatch 选「跳过」+ 人工上传通道） | 全流程无报错，AI 评估列有结果（这是 zhgk 本体的上线验收，GKCLAW 不替代它） |
| 4 | 设 `AIDA_SEND_EMAIL=1`，把 `GKCLAW_FRONTAGENT_MAILBOX` 临时指向**自己的测试邮箱**再下发一次 | 测试邮箱收到主题 `[GKCLAW][TASK_DISPATCH] {project_code}/{task_id}` 的邮件，ZIP 附件完整 |

## 6. 联调前信息交换清单（与 frontagent 团队）

| 方向 | 内容 |
|---|---|
| 对方 → 我方 | frontagent 收件邮箱（填 `GKCLAW_FRONTAGENT_MAILBOX` + 加 mailgw 白名单）；对方回传所用发件地址；对方邮箱附件大小上限 |
| 我方 → 对方 | backagent（mailgw）邮箱地址——对方 ACK/结果/错误包的目的地 |
| 双方确认 | `schema_version = gkclaw.mail.v1`；source/target 标识（back-agent / front-agent，契约默认）；任务包内无示例图资产（v1） |

## 7. 联调十步（契约 §23 对照 · 每步验证点）

> 我方的"刷新"动作 = 在 wait_survey 等待页提交一次 resume（拉取发生在 wait_survey 检查时，**无后台轮询**）。

| # | 步骤 | 操作方 | 我方验证点 |
|---|---|---|---|
| 1 | 生成 task.dispatch ZIP | 我方（task_dispatch 选「下发」） | `RunTime/gkclaw/<task_id>/outbox/task-*.zip`；state.json `state=dispatched` |
| 2 | 邮件发出 | 自动 | SDUI 卡 `mailgw: sent`；若 `pending_approval` → 白名单漏配，见 §8 |
| 3 | frontagent 导入任务 | 对方 | — |
| 4 | 收 task.import_ack | 我方刷新 | SDUI 卡变「对端已导入」+ 现场 Web 入口 URL；state=accepted |
| 5 | App 用 assignees 姓名+工号登录 | 现场 | 对方确认任务过滤按 surveyor_code 生效 |
| 6 | 任务卡片可见（项目名/编码/任务名/任务 ID/状态） | 现场 | — |
| 7 | 现场完成若干工勘项 | 现场 | — |
| 8 | 触发「回传结果」（阶段性） | 现场 → 我方刷新 | state=staged_returned；`results/result-001.json` 落档；**流程不推进、任务不关闭** |
| 9 | 触发「结束任务」（final） | 现场 → 我方刷新 | `Input/已填写_全量勘测结果表.xlsx` 自动生成 → wait_survey 放行 → assess 继续；state=completed |
| 10 | 归档对账 | 我方 | `packages.json` 各包 disposition 正确；`to_back_备注`（规则自动"不涉及"原因）在 `result-notes.json` 留档 |

补充联调用例（建议至少各做一次）：重复发送同一 final 包 → duplicate 幂等；final 后再发 staged → 隔离；
用非 assignees 工号提交 → 整包隔离（§22 安全闸）。

## 8. 排障速查

状态真相位置：`ProjectData/RunTime/gkclaw/<task_id>/`（state.json / packages.json / results/ /
evidence/ / pending_results/）；隔离区 `RunTime/gkclaw/_quarantine/`；扫描账本 `RunTime/gkclaw/mail_scan.json`。

| 现象 | 原因 | 处置 |
|---|---|---|
| 下发后 SDUI 显示 `pending_approval` | frontagent 域不在 mailgw 白名单 | mailgw `config.yaml` 补白名单；本单去 `/admin` 人工放行 |
| task_dispatch 报 `MAILGW_TOKEN 未配置` / `GKCLAW_FRONTAGENT_MAILBOX 未配置` | agent/.env 漏配 | 按 §4 补配，task_dispatch 支持单步重试 |
| state=failed，`last_error` 有连接错误 | mailgw 服务未起 / 端口不通 | 起服务后单步重试 task_dispatch |
| 一直等不到 ACK | 对方未收到或未导入 | 查 mailgw 发送记录与 `/admin`；和对方核对其收件箱；必要时重发（**新 task_id**，旧任务自动 superseded） |
| 回传"不生效" | 没有刷新（拉取只在 wait_survey 检查时发生）/ MAILGW_TOKEN 漏配 | 在等待页提交一次 resume；查 `mail_scan.json` 的 verdict |
| 包进 `_quarantine/` | checksum 篡改 / 路径逃逸 / 未知 task_id / payload 不合契约 / 冲突 | 看 packages.json 对应 disposition 与 note，按契约 §19-20 处置 |
| state.json 出现 `merge_blocked=true` | 表指纹不一致（下发后表被改）或双源冲突（Input/ 已有人工表） | 看 `merge_blocked_reason`；转写结果在 `pending_results/`，人工裁决后手动放入 Input/ |
| 邮件发了但显示 dry-run | `AIDA_SEND_EMAIL≠1` | 按 §4 设置后重发（新 task_id） |

## 9. 回退方案

GKCLAW 是增量能力，回退不影响 zhgk 存量流程：

1. **软回退**：`AIDA_SEND_EMAIL` 置 0（或删掉）→ 全程 dry-run，不再外发；
2. **流程内回退**：task_dispatch HITL 选「跳过下发」→ 完全走原有人工上传通道；
3. 已发出的任务无法撤回（契约无撤销包类型）：旧任务的后续回传只落档不合并（superseded 语义），无需处理。

## 10. 后续增强（已在 ROADMAP 技术债登记）

supplement 意图开放下发 · 复勘轮自动重发 · cron 自动拉取（替代手动刷新）· 对账页面 ·
mailbox 守门 lint · 示例图资产 · 依赖规则编排器。
