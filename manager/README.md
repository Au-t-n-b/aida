# AIDA Manager

UX 协调层：**鉴权**（代理数据中心）、会话管理；后续扩展容器调度。

## 启动

```bash
source agent/.venv/bin/activate
# agent/.env 配置 DATA_CENTER_BASE_URL
uvicorn manager.main:app --host 0.0.0.0 --port 8000
```

或与全栈一并启动：`python scripts/start_aida_nanobot.py`

## UX 对接

| 接口 | 说明 |
|------|------|
| `POST /api/v1/auth/login` | UX 登录；内部调数据中心 `POST /api/v1/users/login` + `GET /api/v1/users/me` |
| `POST /api/v1/auth/logout` | 注销会话 |
| `GET /api/v1/auth/me` | 当前用户（Bearer token） |
| `POST /api/v1/chat/access` | 登录后聊天票据（指向 AIDA Agent） |
| `GET /health` | 健康检查 |

前端 `VITE_CLAWMANAGER_BASE` 指向 Manager（默认 `http://127.0.0.1:8000`）。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `DATA_CENTER_BASE_URL` | `http://127.0.0.1:9000` | 数据中心 Base URL |
| `AIDA_AGENT_BASE_URL` | `http://127.0.0.1:7401` | AIDA Agent（chat/access 回传） |
| `MANAGER_PORT` | `8000` | 监听端口 |

鉴权契约见 `docs/50_数据与接口/接口/auth.md`。
