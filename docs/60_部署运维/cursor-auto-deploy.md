# Cursor Auto 模式 · 服务器部署执行手册

> **给 Cursor 的说明**：本文档是一份自包含的操作手册。你需要通过 SSH 登录两台内网服务器完成部署。每一步都有验证命令——执行完必须验证通过才能进入下一步，验证失败时按「失败处理」指引操作。

---

## 0. 背景与目标

**你要完成的事**：把本地改好的代码同步到服务器，重建 Docker 镜像，让用户能通过浏览器访问完整的工勘 AI 系统（智慧工勘 zhgk skill + SDUI 界面）。

**两台服务器的分工**：
| 服务器 | IP | 运行什么 | 部署目录 |
|--------|-----|---------|---------|
| ServerA | `10.143.2.197` | ClawManager（鉴权+调度） | `/opt/aida/clawmanager` |
| ServerB | `10.143.2.198` | NodeAgent + Docker + 容器 + aida/agent | `/opt/aida/clawmanager` 和 `/opt/aida/aida` |

**本地代码位置**：
| 代码 | 本地路径 |
|------|---------|
| ClawManager（含本次修改的 resume 端点） | `D:\aida\0605-linux\merge_clawManager\197\clawmanager\` |
| xclaw nanobot 后端 | `D:\aida\0605-linux\backend\xclaw\` |
| aida/agent（LangGraph zhgk skill） | `D:\aida\` |
| aida/frontend（构建产物） | `D:\aida\frontend\dist\`（需先在本地 build） |

---

## 1. 前置检查

### 1.1 确认本地 SSH 连通性

```bash
# 测试能否 SSH 到两台服务器（替换 USER 为你的用户名）
ssh USER@10.143.2.197 "hostname && echo '197 OK'"
ssh USER@10.143.2.198 "hostname && echo '198 OK'"
```

✅ 两台都输出 `OK` → 继续  
❌ 连不上 → 检查 VPN/内网连接，或向用户确认 SSH 凭据

### 1.2 确认服务器现有服务状态

```bash
# 197 上的 manager
ssh USER@10.143.2.197 "curl -s http://127.0.0.1:8000/health | python3 -m json.tool"

# 198 上的 nodeagent
ssh USER@10.143.2.198 "curl -s http://127.0.0.1:8900/health | python3 -m json.tool"

# 198 上的 aida/agent
ssh USER@10.143.2.198 "curl -s http://127.0.0.1:7401/healthz | python3 -m json.tool"

# 198 上是否有 Docker
ssh USER@10.143.2.198 "docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'Docker not available'"
```

✅ 全部有响应 → 继续  
❌ 某个服务没响应 → 记录，继续（不是阻塞项）

---

## 2. 同步更新后的 ClawManager 代码

> 本次更新内容：resume 链路（5 个文件，新增 HITL 续跑端点）

### 2.1 同步 manager 到 ServerA（197）

```bash
# 只同步修改过的文件（不影响已有的 .env / runtime 数据）
rsync -avz --checksum \
    D:/aida/0605-linux/merge_clawManager/197/clawmanager/manager/app/ \
    USER@10.143.2.197:/opt/aida/clawmanager/manager/app/

# 验证关键文件已更新
ssh USER@10.143.2.197 "grep -n 'TaskResumeRequest\|def resume' \
    /opt/aida/clawmanager/manager/app/schemas/task.py \
    /opt/aida/clawmanager/manager/app/services/task_service.py \
    /opt/aida/clawmanager/manager/app/api/v1/tasks.py"
```

✅ grep 输出包含 `TaskResumeRequest` 和 `def resume` → 继续  
❌ 无输出 → rsync 可能失败，检查路径，重试

### 2.2 同步 nodeagent 到 ServerB（198）

```bash
rsync -avz --checksum \
    D:/aida/0605-linux/merge_clawManager/197/clawmanager/nodeagent/node_agent/ \
    USER@10.143.2.198:/opt/aida/clawmanager/nodeagent/node_agent/

# 验证
ssh USER@10.143.2.198 "grep -n 'resume_task\|async def resume' \
    /opt/aida/clawmanager/nodeagent/node_agent/api/tasks.py"
```

✅ grep 输出包含 `resume_task` → 继续

---

## 3. 重启 ClawManager 服务

### 3.1 重启 ServerA（197）上的 manager

```bash
ssh USER@10.143.2.197 << 'ENDSSH'
cd /opt/aida/clawmanager

# 找到并停止现有 manager 进程
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 2

# 重新启动（从 manager/ 子目录启动，以便 app 包路径正确）
cd /opt/aida/clawmanager/manager
source /opt/aida/clawmanager/.venv/bin/activate 2>/dev/null || \
    source /opt/aida/clawmanager/manager/.venv/bin/activate 2>/dev/null || true

nohup uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 --workers 1 \
    >> /var/log/clawmanager.log 2>&1 &

echo "manager PID: $!"
sleep 3
curl -s http://127.0.0.1:8000/health
ENDSSH
```

✅ 最后一行返回 `{"status":"ok"}` → 继续  
❌ 连接拒绝 → 查日志：`ssh USER@10.143.2.197 "tail -30 /var/log/clawmanager.log"`

### 3.2 重启 ServerB（198）上的 nodeagent

```bash
ssh USER@10.143.2.198 << 'ENDSSH'
pkill -f "node_agent.server" 2>/dev/null || true
sleep 2

cd /opt/aida/clawmanager
source .venv/bin/activate 2>/dev/null || \
    source /opt/aida/clawmanager/nodeagent/.venv/bin/activate 2>/dev/null || true

cd /opt/aida/clawmanager/nodeagent
nohup python -m node_agent.server \
    >> /var/log/nodeagent.log 2>&1 &

echo "nodeagent PID: $!"
sleep 3
curl -s http://127.0.0.1:8900/health
ENDSSH
```

✅ 返回包含 `ok` 的 JSON → 继续

### 3.3 验证 resume 端点已注册

```bash
# 检查 manager API 路由是否包含 resume
ssh USER@10.143.2.197 "curl -s http://127.0.0.1:8000/openapi.json | python3 -c \
    \"import json,sys; routes=[r for r in json.load(sys.stdin)['paths'] if 'resume' in r]; print(routes)\""

# 检查 nodeagent
ssh USER@10.143.2.198 "curl -s http://127.0.0.1:8900/openapi.json | python3 -c \
    \"import json,sys; routes=[r for r in json.load(sys.stdin)['paths'] if 'resume' in r]; print(routes)\""
```

✅ 两台都输出包含 `resume` 的路径列表 → 继续

---

## 4. 准备工勘数据目录

```bash
ssh USER@10.143.2.198 << 'ENDSSH'
# 创建 ClawManager 挂载路径（v4：Template 替代 Start）
mkdir -p /srv/claw/projects/K1903/workspace/ProjectData/{Template,Input,Output,RunTime,Images}
mkdir -p /srv/claw/skills/{admin,pd,employee}
mkdir -p /srv/claw/sessions

# 复制已有的底表文件（从之前部署的路径，v4 用 Template/）
if [ -d /srv/zhgk/ProjectData/Template ]; then
    cp -n /srv/zhgk/ProjectData/Template/* \
        /srv/claw/projects/K1903/workspace/ProjectData/Template/ 2>/dev/null || true
    echo "Template/ 文件数: $(ls /srv/claw/projects/K1903/workspace/ProjectData/Template/ | wc -l)"
fi

if [ -d /srv/zhgk/ProjectData/Input ]; then
    cp -n /srv/zhgk/ProjectData/Input/* \
        /srv/claw/projects/K1903/workspace/ProjectData/Input/ 2>/dev/null || true
    echo "Input/ 文件数: $(ls /srv/claw/projects/K1903/workspace/ProjectData/Input/ | wc -l)"
fi

# 给 pd 角色放 zhgk skill 定义（让 context API 返回 zhgk）
mkdir -p /srv/claw/skills/pd/zhgk
echo "# zhgk skill" > /srv/claw/skills/pd/zhgk/SKILL.md

# 验证
echo "=== 数据目录验证 ==="
ls /srv/claw/projects/K1903/workspace/ProjectData/Template/ 2>/dev/null | head -5
ls /srv/claw/projects/K1903/workspace/ProjectData/Input/ 2>/dev/null | head -5
ENDSSH
```

✅ Template/ 下有底表文件，Input/ 下有 BOQ.xlsx → 继续  
❌ Template/ 为空 → 需要手动上传底表文件（见下方说明）

**如果底表文件不在 /srv/zhgk（即需要从本地传）**：
```bash
scp D:/path/to/入场评估标准表.xlsx USER@10.143.2.198:/srv/claw/projects/K1903/workspace/ProjectData/Template/ 2>/dev/null || \
echo "⚠️ 底表文件需手动提供（入场评估标准表.xlsx + 工勘常见高风险库.xlsx），工勘会在 HITL 步骤暂停（正常行为）"
```

---

## 5. 构建 Docker 镜像 xclaw-agui:0.2

> 这是最耗时的步骤（5-20 分钟），主要是网络下载和 Python 包安装。

### 5.1 在 ServerB（198）上组织构建上下文

```bash
ssh USER@10.143.2.198 << 'ENDSSH'
echo "=== 准备构建上下文 ==="
mkdir -p /opt/aida/build

# 检查已有目录
echo "clawmanager 已有: $(ls /opt/aida/clawmanager 2>/dev/null | head -3)"
echo "aida 已有: $(ls /opt/aida/aida 2>/dev/null | head -3)"
ENDSSH
```

### 5.2 从本地同步构建所需代码到 ServerB

```bash
# clawmanager（含修改后的 Dockerfile.claw + claw-entrypoint.sh）
rsync -avz --checksum \
    --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
    D:/aida/0605-linux/merge_clawManager/197/clawmanager/ \
    USER@10.143.2.198:/opt/aida/build/clawmanager/

# xclaw nanobot 后端（Dockerfile.claw 需要 backend/xclaw/claw/）
rsync -avz --checksum \
    --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' --exclude='node_modules' \
    D:/aida/0605-linux/backend/xclaw/ \
    USER@10.143.2.198:/opt/aida/build/backend/xclaw/

# aida/agent（LangGraph zhgk skill，这是新增的）
rsync -avz --checksum \
    --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
    --exclude='runtime' --exclude='evals/results' --exclude='frontend' \
    D:/aida/ \
    USER@10.143.2.198:/opt/aida/build/aida/

# 验证三个目录都在
ssh USER@10.143.2.198 "ls /opt/aida/build/"
```

✅ 输出包含 `clawmanager  backend  aida` → 继续

### 5.3 验证 Dockerfile 正确（包含 aida/agent COPY 指令）

```bash
ssh USER@10.143.2.198 "grep -n 'COPY aida\|AIDA_AGENT\|aida/agent' \
    /opt/aida/build/clawmanager/deploy/Dockerfile.claw"
```

✅ 能看到 `COPY aida/agent/ agent/` 之类的行 → 继续  
❌ 无输出 → Dockerfile 是旧版，执行：
```bash
rsync -avz D:/aida/0605-linux/merge_clawManager/197/clawmanager/deploy/ \
    USER@10.143.2.198:/opt/aida/build/clawmanager/deploy/
```

### 5.4 执行 Docker 构建

```bash
ssh USER@10.143.2.198 << 'ENDSSH'
cd /opt/aida/build

echo "=== 开始构建 xclaw-agui:0.2（预计 5-20 分钟）==="
docker build \
    -f clawmanager/deploy/Dockerfile.claw \
    -t xclaw-agui:0.2 \
    --build-arg http_proxy=http://10.143.2.250:8088/ \
    --build-arg https_proxy=http://10.143.2.250:8088/ \
    . 2>&1 | tee /tmp/docker-build.log

BUILD_EXIT=$?
echo "=== 构建退出码: $BUILD_EXIT ==="
if [ $BUILD_EXIT -eq 0 ]; then
    docker images | grep xclaw-agui
    echo "✅ 构建成功"
else
    echo "❌ 构建失败，查看最后 50 行日志："
    tail -50 /tmp/docker-build.log
fi
ENDSSH
```

✅ 输出 `✅ 构建成功` 且 `docker images` 包含 `xclaw-agui:0.2` → 继续  
❌ 构建失败 → 查看 `/tmp/docker-build.log`，常见问题及处理见附录

---

## 6. 更新 ClawManager 使用新镜像

```bash
ssh USER@10.143.2.197 << 'ENDSSH'
# 找到 manager 的 .env 文件
ENV_FILE=""
for f in /opt/aida/clawmanager/.env \
          /opt/aida/clawmanager/manager/.env \
          /opt/aida/clawmanager/deploy/.env; do
    if [ -f "$f" ]; then
        ENV_FILE="$f"
        break
    fi
done

if [ -z "$ENV_FILE" ]; then
    echo "❌ 找不到 .env 文件，手动检查 /opt/aida/clawmanager/ 下的 .env"
    exit 1
fi

echo "找到 .env: $ENV_FILE"
echo "当前镜像配置: $(grep DEFAULT_IMAGE $ENV_FILE)"

# 更新镜像版本
sed -i 's/DEFAULT_IMAGE=xclaw-agui:0\.[0-9]*/DEFAULT_IMAGE=xclaw-agui:0.2/g' "$ENV_FILE"
echo "更新后: $(grep DEFAULT_IMAGE $ENV_FILE)"

# 重启 manager 使配置生效
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 2
cd /opt/aida/clawmanager/manager
source /opt/aida/clawmanager/.venv/bin/activate 2>/dev/null || true
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 \
    >> /var/log/clawmanager.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:8000/health
ENDSSH
```

✅ health 返回正常，grep 显示 `xclaw-agui:0.2` → 继续

---

## 7. 构建前端并部署

### 7.1 本地构建（在 Windows 本地执行）

```bash
# 确认 .env 已配置
cat D:/aida/frontend/.env

# 如果 .env 不存在或配置不对，先创建
# 期望内容：
# VITE_AGENT_BASE=http://10.143.2.198:7401
# VITE_CLAWMANAGER_BASE=http://10.143.2.197:8000
```

如果 `.env` 配置不对，修复后执行：
```bash
# 写入正确的 .env（替换已有内容）
cat > D:/aida/frontend/.env << 'EOF'
VITE_AGENT_BASE=http://10.143.2.198:7401
VITE_CLAWMANAGER_BASE=http://10.143.2.197:8000
EOF

# 构建
cd D:/aida/frontend && npm run build
```

✅ 构建完成，`D:\aida\frontend\dist\` 下有 `index.html` → 继续

### 7.2 上传前端产物到 ServerA（197）

```bash
# 上传到 197（xclaw 前端目录）
rsync -avz --delete \
    D:/aida/frontend/dist/ \
    USER@10.143.2.197:/opt/aida/xclaw/dist/

# 验证
ssh USER@10.143.2.197 "curl -s http://127.0.0.1:50962 | grep -o '<title>.*</title>' | head -1 || echo '前端服务未在 50962 监听'"

# 如果前端是 python 静态服务，重启它（端口以实际为准）
ssh USER@10.143.2.197 << 'ENDSSH2'
# 查找现有前端服务进程
echo "现有前端进程:"
ps aux | grep -E "http.server|vite preview" | grep -v grep

# 如果用 python http.server
pkill -f "http.server" 2>/dev/null || true
sleep 1
cd /opt/aida/xclaw/dist
nohup python3 -m http.server 50962 >> /var/log/xclaw-frontend.log 2>&1 &
echo "前端 PID: $!"
sleep 2
curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:50962
ENDSSH2
```

✅ HTTP 200 → 继续

---

## 8. 端到端验证

### 8.1 基础连通性

```bash
# 197 manager
curl -s http://10.143.2.197:8000/health

# 198 nodeagent  
curl -s http://10.143.2.198:8900/health

# 198 aida/agent
curl -s http://10.143.2.198:7401/healthz | python3 -m json.tool

# 前端可访问
curl -s -o /dev/null -w "HTTP %{http_code}" http://10.143.2.197:50962
```

### 8.2 模拟登录拿 token

```bash
TOKEN=$(curl -s -X POST http://10.143.2.197:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"pd_user","password":"pd123","project_code":"K1903"}' \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('access_token','ERROR'))")

echo "Token: ${TOKEN:0:20}..."

SESSION_ID=$(curl -s -X POST http://10.143.2.197:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"pd_user","password":"pd123","project_code":"K1903"}' \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('session_id','ERROR'))")

echo "Session: $SESSION_ID"
```

✅ token 和 session_id 都不是 `ERROR` → 继续

### 8.3 启动工勘任务验证

```bash
# 启动 zhgk 任务
TASK_RESP=$(curl -s -X POST http://10.143.2.197:8000/api/v1/tasks \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"session_id\":\"$SESSION_ID\",\"kind\":\"zhgk\",\"params\":{}}")

echo "Task 响应: $TASK_RESP"
TASK_ID=$(echo $TASK_RESP | python3 -c "import json,sys; print(json.load(sys.stdin).get('task_id','ERROR'))")
echo "Task ID: $TASK_ID"
```

✅ TASK_ID 不是 `ERROR` → 继续

### 8.4 订阅任务事件（检查 SDUI 是否到来）

```bash
# 订阅 5 秒，看是否有 sdui 事件
timeout 15 curl -s \
    "http://10.143.2.197:8000/api/v1/tasks/${TASK_ID}/events?access_token=${TOKEN}" | \
    head -50
```

✅ 看到 `event: running` 且 data 里有 `sdui` 字段 → **全部完成！**  
⚠️ 看到 `event: running` 但没有 sdui → aida_runner.py 的 SSE 转发可能有问题，查日志  
❌ 连接立即断开 → 检查容器是否成功拉起：`ssh USER@10.143.2.198 "docker ps --filter name=claw-"`

---

## 9. 失败排查快速指引

### Docker 构建失败

```bash
# 查最后 100 行构建日志
ssh USER@10.143.2.198 "tail -100 /tmp/docker-build.log"

# 常见问题 1：pip 超时
# 处理：在 Dockerfile 里的 pip install 命令加 --index-url https://mirrors.aliyun.com/pypi/simple/
# 或在构建时加 --network host

# 常见问题 2：aida/ 目录不存在
ssh USER@10.143.2.198 "ls /opt/aida/build/aida/agent/ | head -5"
# 为空则重新 rsync aida/ 目录

# 常见问题 3：Node 下载失败（WebUI 编译）
# 处理：跳过 WebUI 构建（临时方案）
ssh USER@10.143.2.198 "grep -n 'NANOBOT_FORCE_WEBUI_BUILD' /opt/aida/build/clawmanager/deploy/Dockerfile.claw"
# 如果能找到这行，修改为 NANOBOT_FORCE_WEBUI_BUILD=0
```

### 容器拉起失败（登录后没有容器）

```bash
ssh USER@10.143.2.198 << 'ENDSSH'
# 查当前运行的容器
docker ps -a | grep claw

# 尝试手动拉起测试容器验证镜像正确
docker run --rm -e AUTHGATE_SESSION_ID=test \
    -e GRANT_SIGNING_SECRET=dummy \
    -e NANOBOT_CONFIG_JSON='{"agents":{"defaults":{"model":"glm-4.7"}}}' \
    xclaw-agui:0.2 \
    sh -c "echo 镜像可以启动; exit 0"
ENDSSH
```

### aida/agent 在容器内没有启动

```bash
# 进入容器检查
ssh USER@10.143.2.198 << 'ENDSSH'
CONTAINER=$(docker ps --filter name=claw- --format "{{.ID}}" | head -1)
if [ -n "$CONTAINER" ]; then
    echo "容器 ID: $CONTAINER"
    docker exec $CONTAINER ps aux | grep -E "uvicorn|aida"
    docker exec $CONTAINER curl -s http://127.0.0.1:7401/healthz || echo "aida/agent 未启动"
    docker logs $CONTAINER 2>&1 | tail -30
else
    echo "没有运行中的容器"
fi
ENDSSH
```

### manager 启动失败

```bash
ssh USER@10.143.2.197 << 'ENDSSH'
tail -50 /var/log/clawmanager.log
# 最常见原因：.env 里的 GRANT_SIGNING_SECRET / INTERNAL_SIGNING_SECRET 为空
grep "SIGNING_SECRET" /opt/aida/clawmanager/.env 2>/dev/null || \
grep "SIGNING_SECRET" /opt/aida/clawmanager/manager/.env 2>/dev/null
ENDSSH
```

---

## 10. 完成标准

以下全部满足则视为部署完成：

- [ ] `curl http://10.143.2.197:8000/health` → `{"status":"ok"}`
- [ ] `curl http://10.143.2.198:8900/health` → 有响应
- [ ] `curl http://10.143.2.198:7401/healthz` → `"ok":true`
- [ ] `docker images | grep xclaw-agui` 显示 `0.2`
- [ ] `docker ps | grep claw-` 登录后有用户容器
- [ ] 任务事件流中能看到含 `sdui` 的 payload
- [ ] 浏览器访问 `http://10.143.2.197:50962` 能看到 AIDA 界面

---

## 附录：关键路径速查

```
ServerA (197) 关键路径：
  manager 代码：/opt/aida/clawmanager/manager/
  manager .env：/opt/aida/clawmanager/.env（或 manager/.env）
  manager 日志：/var/log/clawmanager.log
  venv 激活：source /opt/aida/clawmanager/.venv/bin/activate

ServerB (198) 关键路径：
  nodeagent 代码：/opt/aida/clawmanager/nodeagent/
  nodeagent 日志：/var/log/nodeagent.log
  aida/agent 代码：/opt/aida/aida/
  aida/agent 日志：/var/log/aida-agent.log
  构建上下文：/opt/aida/build/{clawmanager,backend/xclaw,aida}
  数据目录：/srv/claw/projects/K1903/workspace/
  Docker 镜像：xclaw-agui:0.2
```
