# AIDA Claw 容器（P0）

每 `(user, project)` 一个 Claw 实例：**agent :7401** + **nanobot :8900**（同容器内 supervisord 管理）。  
ontology / 数据中心 / mailgw / manager / frontend **不打进镜像**，经宿主机 URL 访问。

## 宿主机 vs 容器（`AIDA_CLAW_ORCHESTRATION=1`）

| 组件 | 宿主机 | `aida/claw_liwen` 容器 |
|------|--------|-------------------------|
| Manager | ✅ :8001（或 MANAGER_PORT） | — |
| Frontend | ✅ :8080 | — |
| ontology / mailgw / DC | ✅ 共享单例 | 经 host-gateway 访问 |
| agent + nanobot | ❌ **不启** :7401/:8900 | ✅ 每项目一个容器 |

启动：`AIDA_CLAW_ORCHESTRATION=1 python scripts/start_aida_nanobot.py`  
进项目：前端 `enter-project` → Manager `docker run` 拉起 `claw-u{uid}-p{pid}`。

## 构建

```bash
# 仓库根目录
docker build -f deploy/claw/Dockerfile -t aida/claw_liwen:dev .
```

内网基像：`harbor.aie.rnd.huawei.com/library/python:3.12.13-slim`。无外网 Harbor 时可临时改 Dockerfile 第一行为 `FROM python:3.12-slim`。

## 运行

```bash
mkdir -p /opt/aida/aida-data/business /opt/aida/aida-data/runtime/checkpoints

docker run --rm -d --name claw-smoke \
  -p 17401:7401 \
  -v /opt/aida/aida-data:/opt/aida/aida-data:rw \
  --env-file agent/.env \
  -e AIDA_BUSINESS_ROOT=/opt/aida/aida-data/business \
  -e AIDA_CHECKPOINT_DB=/opt/aida/aida-data/runtime/checkpoints/claw-smoke.db \
  --add-host=host.docker.internal:host-gateway \
  aida/claw_liwen:dev

curl -sf http://127.0.0.1:17401/healthz | head
curl -sf http://127.0.0.1:17401/agent/skills | head
docker stop claw-smoke
```

Windows（PowerShell）把 `/opt/aida/aida-data` 换成本机路径，例如 `D:/aida-data`。

## 目录挂载契约

| 宿主机 | 容器内 | 说明 |
|--------|--------|------|
| `/opt/aida/aida-data` | `/opt/aida/aida-data` | **同路径** bind-mount |
| — | `.../business` | `AIDA_BUSINESS_ROOT` |
| — | `.../runtime/checkpoints/u{uid}-p{pid}.db` | 每用户+项目独立 checkpoint（P1 编排写入） |

## 进程模型

```
claw_entrypoint.sh
  → claw_bootstrap.py（sync skills + nanobot config.json）
  → supervisord -n
       ├─ nanobot serve :8900
       └─ wait_nanobot_then_agent.sh → uvicorn agent.main :7401
```

## Smoke

```bash
python scripts/claw_container_smoke.py --build
```

## P0 验收清单

- [ ] `docker build` 成功
- [ ] `GET /healthz` 200（冷启动 ≤120s）
- [ ] `GET /agent/skills` 非空
- [ ] 容器内 nanobot `GET :8900/health` 200（`docker exec` 验证）
- [ ] SSE：`curl -N http://127.0.0.1:17401/agent/<skill>/stream?...` 能收事件

## 联调

P1 完成后 Manager 将通过 nginx `location /claw/{routing_key}/` 反代到动态 host port，浏览器不直连 `:7401`。
