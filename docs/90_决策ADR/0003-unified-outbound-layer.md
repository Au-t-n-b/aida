# 0003. 统一外发出口：mailer.py（邮件）+ notifier.py（IM），lint 守门

- **状态**: Accepted
- **日期**: 2026-06-03
- **相关**: nanobot `agent/tools/email.py` & `welink.py`（参考来源）；`agent/mailer.py`；`agent/notifier.py`；`agent/tools/send_mail.py`；`agent/tools/send_welink.py`；`agent/scripts/lint_no_naked_send.py`

## 背景（Context）

工勘流程（zhgk）Step4 需要通过邮件分发审批、通过小鲁班 IM 通知干系人。内网 nanobot 项目已有成熟的
`send_email` / `send_welink` 工具实现，含限流、dry-run、鉴权、安全约束。

迁移时的核心约束：
- 当前项目已有 `mailer.py`（SMTP）和 `notifier.py`（WeLink），**两者均已完备**，不需重写。
- 工具层（`tools/send_mail.py`）已存在邮件工具；缺 IM 工具。
- nanobot 的两套 HITL 基础设施（ApprovalRegistry / PendingHitlStore）与本项目的软中断 HITL 机制
  不兼容，**不迁**。

## 考虑的选项（Options）

**A. 直接在 skill step / chat_engine 里调 httpx.post + smtplib**
- 优：无额外抽象
- 劣：无 dry-run 保护、无限流、无域名白名单；重复代码；难以统一测试；发散后难追溯。

**B. mailer.py + notifier.py 作唯一出口，工具层薄包装，lint 守门（选定）**
- 优：dry-run 防误发；限流（20/min, 200/day）；域名/路径约束；统一可观测；prebuild 守门阻断裸调。
- 劣：多一个间接层，对简单调用略显繁琐。

## 决策（Decision）

选 B。具体落地：

| 层级 | 文件 | 职责 |
|------|------|------|
| 出口层 | `agent/mailer.py` | 邮件唯一出口（SMTP_SSL + dry-run + 附件） |
| 出口层 | `agent/notifier.py` | IM 唯一出口（httpx + 限流 + 富文本表格 + dry-run） |
| 工具层 | `agent/tools/send_mail.py` | Agent 工具，薄包装 mailer.py |
| 工具层 | `agent/tools/send_welink.py` | Agent 工具，薄包装 notifier.py |
| 守门 | `agent/scripts/lint_no_naked_send.py` | 禁止 agent/ 其他文件裸用 smtplib/win32com/httpx.post |
| 钩子 | `package.json` prebuild | lint:no-naked-send 阻断构建 |

HITL 确认（「发信前确认」）单独决策：推荐走 `present_choices` → 下一轮 ReAct 调 send_mail/send_welink，
不引入 ApprovalRegistry/Future 机制（架构不兼容）。

## 后果（Consequences）

- 正面：发邮件/IM 的 skill step 只需 `from agent.mailer import send_mail` / `from agent.notifier import send_welink`，
  干净；prebuild 守门让裸调无法上线。
- 正面：nanobot 积累的安全经验（域名白名单思路、进程内限流）已在 notifier.py 落地，零额外工作量。
- 负面：httpx.post 守门范围粗（整个 agent/ 外的 POST 都被拦），若未来需要调其他 HTTP API，
  需在 `lint_no_naked_send.py` 的 `ALLOWED_IM` 里加白名单或新建对应的出口模块。
- 后续：若同时需要 Outlook COM（pywin32）发信，在 mailer.py 里加 `OutlookSender` 分支，工具层无感知。
  若要真正的「发信前预览卡」，走 ConfirmCard SDUI（Phase C）或 present_choices，不走 ApprovalRegistry。
