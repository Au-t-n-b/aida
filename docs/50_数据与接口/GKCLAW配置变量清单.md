# GKCLAW 配置变量清单

> **用途**：联调前逐项核对；部署/换机时按本清单填配置。
> **关联文档**：[GKCLAW部署与联调指南.md](GKCLAW部署与联调指南.md) · [GKCLAW邮件链路.md](GKCLAW邮件链路.md) · [mailgw/docs/部署与配置手册.md](../../mailgw/docs/部署与配置手册.md)
> **当前部署机**：`10.143.2.198` · 代码根目录 `/opt/aida/aida`
> **本地开发机**：`D:\.cursor_workplace\aida\aida_6.15`（Windows 联调）

---

## 0. 架构与端口

```text
浏览器 :8080/:8081 → AIDA agent :7401 → mailgw :8025 → SMTP → frontagent 邮箱
                                                    ↑ agent_notify / POP3 轮询 ← frontagent 回传邮件
```

| 服务 | 地址 | 备注 |
|------|------|------|
| mailgw API | `http://127.0.0.1:8025` | 仅本机；AIDA 同机调用 |
| mailgw 审批页 | `http://127.0.0.1:8025/admin` | 用户 `admin`；白名单外邮件人工放行 |
| AIDA agent | `http://127.0.0.1:7401`（本地）/ `http://10.143.2.198:7401`（现场） | **`--workers 1` 硬约束** |
| 前端 | `http://127.0.0.1:8080`（本地）/ `http://10.143.2.198:8081`（现场） | 浏览器联调入口 |

---

## 1. mailgw — `config.yaml`

**路径**：
- 现场：`/opt/aida/aida/mailgw/config.yaml`
- 本地：`mailgw/config.yaml`（结构可参考 `mailgw/config.yaml.example`）

| 配置项 | 当前值 | 说明 |
|--------|--------|------|
| `smtp.host` | `smtp.huawei.com` | 发送邮件服务器 |
| `smtp.port` | `587` | 发送端口 |
| `smtp.ssl` | `false` | `false` = 连接后 **STARTTLS**（587 用这个） |
| `smtp.username` | `p_aidagkclaw` | 邮箱登录账号 |
| `smtp.from_addr` | `aidagkclaw@huawei.com` | 发件人地址（backagent） |
| `smtp.display_name` | `AIDA GKCLAW backagent` | 发件显示名 |
| `pop3.host` | `pop.huawei.com` | 接收邮件服务器 |
| `pop3.port` | `995` | 接收端口 |
| `pop3.ssl` | `true` | `true` = **SSL 加密连接**（995 用这个） |
| `pop3.username` | `p_aidagkclaw` | 与 SMTP 账号相同 |
| `pop3.poll_interval` | `10` | **建议值 10 秒**；后台定时拉取并触发 `agent_notify`；`0` = 仅 `wait_survey` 手动刷新时拉取 |
| `policy.whitelist_domains` | `["huawei.com", "qq.com"]` | to+cc **全部命中**才直发，否则进审批队列 |
| `policy.whitelist_addresses` | `["307576239@qq.com"]` | frontagent 精确白名单（建议保留） |
| `policy.hourly_limit` | `50` | 每小时发送上限 |
| `policy.daily_limit` | `200` | 每日发送上限 |
| `policy.max_attachment_mb` | `25` | 单封附件总大小上限（MB） |
| `policy.max_recipients` | `20` | 单封收件人数量上限 |
| `data_dir` | `./data` | SQLite 与附件落盘目录 |
| `agent_notify.enabled` | `true` | 收到 GKCLAW 回传邮件后 POST 通知 AIDA Agent |
| `agent_notify.base_url` | `http://127.0.0.1:7401` | 本地独立进程地址；Docker Compose 演示时由 `AGENT_NOTIFY_BASE=http://agent:7401` 覆盖 |
| `agent_notify.skill` | `zhgk` | 通知目标 skill |

**华为邮箱客户端对照**（运维口径）：

- 接收：`pop.huawei.com`，端口 995，要求加密连接（SSL）
- 发送：`smtp.huawei.com`，端口 587，加密类型 STARTTLS → mailgw 侧 `smtp.ssl: false`

---

## 2. mailgw — `.env`（敏感）

**路径**：
- 现场：`/opt/aida/aida/mailgw/.env`
- 本地：`mailgw/.env`（**禁止提交 Git**）

| 变量 | 当前值 | 说明 |
|------|--------|------|
| `MAILGW_SMTP_PASSWORD` | `94Gd!*8_` | SMTP 授权码/密码 |
| `MAILGW_POP3_PASSWORD` | `94Gd!*8_` | POP3 授权码（通常与 SMTP 相同） |
| `MAILGW_ADMIN_PASSWORD` | `UaSbif0VtXPaHrZ0rhjSgQ` | 审批页 `/admin` 登录口令 |
| `MAILGW_TOKEN_AIDA` | `f6O6V-Z5GihiJVMUGy3DO4Hn53w1zvRZHEZBwTlkWTc` | AIDA 调用 mailgw 的 Bearer Token |

Token 重新生成：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 3. AIDA agent — `.env`（GKCLAW 段）

**路径**：
- 现场：`/opt/aida/aida/agent/.env`
- 本地：`agent/.env`

| 变量 | 当前值 | 说明 |
|------|--------|------|
| `AIDA_SEND_EMAIL` | `1` | 真发开关；不设或 `≠1` 则全程 **dry-run**（只建包不发信） |
| `AIDA_MAIL_BACKEND` | `mailgw` | 发送走 mailgw 网关 |
| `MAILGW_BASE` | `http://127.0.0.1:8025` | mailgw 地址（与 agent 同机） |
| `MAILGW_TOKEN` | `f6O6V-Z5GihiJVMUGy3DO4Hn53w1zvRZHEZBwTlkWTc` | **必须与 `MAILGW_TOKEN_AIDA` 相同**（变量名不同） |
| `GKCLAW_FRONTAGENT_MAILBOX` | `307576239@qq.com` | 任务包收件方（frontagent） |

### zhgk 本体（非 GKCLAW 专用，但联调必填）

| 变量 | 当前值 | 说明 |
|------|--------|------|
| `ZHIPU_API_KEY` | （现场填写） | 智谱 API，assess 等 LLM 步骤 |
| `ZHGK_ROOT` | `/srv/zhgk`（现场）/ 默认 `~/.nanobot/workspace/skills/zhgk`（本地） | 工勘工作区根目录 |
| `HTTP_PROXY` | `http://10.143.2.250:8088/` | 内网代理（智谱 API） |

模板参考：`agent/.env.example`

---

## 4. 人员配置 — assignees

任务下发后，frontagent App 按 **姓名 + 工号** 过滤可见任务。

**方式 A**：`POST /agent/zhgk/start` 请求体带 `assignees`
**方式 B**：文件（联调推荐）

**路径**：`{ZHGK_ROOT}/ProjectData/RunTime/gkclaw/assignees.json`

```json
[
  {"surveyor_name": "测试员", "surveyor_code": "S001"}
]
```

> `surveyor_name` / `surveyor_code` 须与 frontagent 团队事先约定一致。

---

## 5. 服务器 DNS — `/etc/hosts`

**路径**：`/etc/hosts`（198 内网 DNS 无法解析华为邮箱域名时需添加）

```text
7.221.188.53 smtp.huawei.com
7.221.188.53 pop.huawei.com
```

换机或 IP 变更后重新 `nslookup smtp.huawei.com` 核对。

Windows 本地若 DNS 解析失败，可在 `C:\Windows\System32\drivers\etc\hosts` 追加相同条目。

---

## 6. 双方信息交换（联调前）

| 方向 | 内容 |
|------|------|
| 我方 → 对方 | backagent 邮箱：`aidagkclaw@huawei.com`（对方 ACK/结果/错误包的目的地） |
| 对方 → 我方 | frontagent 收件：`307576239@qq.com`（已写入 `GKCLAW_FRONTAGENT_MAILBOX` + mailgw 白名单） |
| 双方确认 | `schema_version = gkclaw.mail.v1`；source/target：`back-agent` / `front-agent` |
| 双方确认 | assignees 列表（姓名 + 工号）；对方邮箱附件大小上限 |

---

## 7. 关键对应关系（易错）

```text
mailgw/.env   MAILGW_TOKEN_AIDA  ═══  agent/.env   MAILGW_TOKEN
                    （同一个值，两侧变量名不同）

smtp.ssl=false + port 587  →  STARTTLS（华为发送服务器默认）
pop3.ssl=true  + port 995  →  SSL（华为接收服务器默认）
pop3.poll_interval=10      →  每 10 秒拉取 + agent_notify 自动唤醒 wait_survey

AIDA_SEND_EMAIL=0  →  回退：全程 dry-run，不再外发
task_dispatch 选「跳过」 →  回退：走原有人工上传通道
```

---

## 8. 启停命令

### 8.1 现场（198 · Linux）

```bash
# mailgw
cd /opt/aida/aida/mailgw
nohup .venv/bin/python -m mailgw --host 127.0.0.1 --port 8025 >> /var/log/mailgw.log 2>&1 &

# agent（workers 必须 = 1）
cd /opt/aida/aida && source agent/.venv/bin/activate
pkill -f 'uvicorn agent.main:app' || true
nohup uvicorn agent.main:app --host 0.0.0.0 --port 7401 --workers 1 >> /var/log/aida-agent.log 2>&1 &
```

### 8.2 本地（Windows）

```powershell
# mailgw
Set-Location D:\.cursor_workplace\aida\aida_6.15\mailgw
..\agent\.venv\Scripts\python.exe -m mailgw --config config.yaml --env .env --host 127.0.0.1 --port 8025

# agent
Set-Location D:\.cursor_workplace\aida\aida_6.15
agent\.venv\Scripts\python.exe -m uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload
```

或使用一键脚本：`powershell -ExecutionPolicy Bypass -File scripts/reset_local_dev.ps1`

### 8.3 部署后自检

```bash
# 离线契约（无需 mailgw）
agent/.venv/bin/python agent/evals/eval_gkclaw.py
# 期望：[eval-gkclaw] OK

TOKEN=<MAILGW_TOKEN_AIDA>
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8025/api/inbox?refresh=true"
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"to":["307576239@qq.com"],"subject":"mailgw自检","body":"ok"}' \
  http://127.0.0.1:8025/api/send
```

PowerShell 等价：

```powershell
$token = "<MAILGW_TOKEN_AIDA>"
Invoke-RestMethod -Uri "http://127.0.0.1:8025/api/inbox?refresh=true" -Headers @{ Authorization = "Bearer $token" }
```

---

## 9. 状态与排障路径

| 内容 | 路径 |
|------|------|
| 任务状态真相 | `{ZHGK_ROOT}/ProjectData/RunTime/gkclaw/<task_id>/state.json` |
| 下发 ZIP | `.../outbox/task-*.zip` |
| 包账本 | `.../packages.json` |
| 回传结果 | `.../results/` |
| 隔离区 | `{ZHGK_ROOT}/ProjectData/RunTime/gkclaw/_quarantine/` |
| 收件扫描账本 | `{ZHGK_ROOT}/ProjectData/RunTime/gkclaw/mail_scan.json` |
| mailgw 日志 | 现场 `/var/log/mailgw.log`；本地 `.codex-start-logs/mailgw.out.log` |
| agent 日志 | 现场 `/var/log/aida-agent.log`；本地终端输出 |

详细十步联调与排障表见 [GKCLAW部署与联调指南.md](GKCLAW部署与联调指南.md) §7–§8。

---

## 10. 安全提醒

- 本文含**现场生产凭据**，勿提交公开仓库；换密码/Token 后同步更新 **mailgw `.env`** 与 **agent `.env`** 两处。
- `MAILGW_TOKEN_*` 只进 `.env`，禁止写入任务包、代码或对外文档。
- 修改 `poll_interval` 或 SMTP/POP3 后需**重启 mailgw**；修改 agent `.env` 后需**重启 agent**。
