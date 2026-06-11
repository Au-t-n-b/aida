# mailgw —— AIDA 邮件网关

给自研 agent（AIDA，LangGraph + GLM-4.5）用的独立邮件网关服务：SMTP 发送 + POP3 收件，白名单分级管控（命中直发 / 未命中转人工审批），全程审计，邮箱凭据与 LLM 上下文完全隔离。

```
AIDA Agent (LangGraph 节点)
   │  HTTP + Bearer Token（5 个 LangGraph tool）
   ▼
邮件网关服务 mailgw（FastAPI 单进程）
   ├─ 发送通道：SMTP 公司邮箱（每次新建连接，1/4/16s 退避重试）
   ├─ 收件通道：POP3 拉取，UIDL 去重，MIME 解析后缓存进 SQLite
   ├─ 管控引擎：白名单判定 → 直发 / 入待审批队列；限流
   ├─ 审批入口：极简 Web 页 /admin（待审列表 + 通过/驳回）
   └─ 存储：SQLite（发件队列、收件缓存、审计日志）+ 附件落盘
```

## 快速开始

```bash
pip install -r requirements.txt
copy config.yaml.example config.yaml   # 填 SMTP/POP3 地址与白名单
copy .env.example .env                 # 填授权码、审批口令、API token
python -m mailgw --port 8025
# 审批页：http://127.0.0.1:8025/admin（用户名 admin）
```

## 文档（docs/）

| 文档 | 读者 |
|---|---|
| [部署与配置手册](docs/部署与配置手册.md) | 部署/运维 |
| [API 接口文档](docs/API接口文档.md)（含 LangGraph 接入示例） | agent 接入开发者 |
| [审批操作手册](docs/审批操作手册.md) | 审批人 |
| [设计文档](docs/superpowers/specs/2026-06-10-mail-gateway-design.md) | 开发/评审 |

## 测试

```bash
pytest        # 47 个用例：单元 + API + e2e（本地 aiosmtpd 假 SMTP + POP3 stub，不碰真邮箱）
```
