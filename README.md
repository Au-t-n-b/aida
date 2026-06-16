# AIDA · 智能交付编排系统

AI 原生四层架构的算力交付系统——以企业知识为底座，以 DORA 本体为语义骨架，以 Agent Skill 为执行引擎，支撑 PD/TD 完成算力交付履约。

> 👋 **第一次来 / 找不到路？** 双击打开 [`docs/site/portal.html`](docs/site/portal.html) —— **团队协作门户**，按「新人 / 架构师 / 模块开发者」三道门带你逐层上手，每步配可复制的 AI 提示词。双击即开，无需起服务。

## 仓库结构

```
aida/
├── frontend/      Vite + React 前端（工作台、会话 ClawRail、评测 /evals）
├── agent/         FastAPI + LangGraph Python 后端
│   ├── skills/    Skill 实现（zhgk 智慧工勘 · 首个端到端样板）
│   ├── tools/     工具库（Tool 基类 + Registry）
│   ├── evals/     评测体系（SKILL 四维 + 工具自纠率）
│   ├── docs/      开发手册（START_HERE · SKILL-DEV · TOOL-DEV）
│   └── scripts/   守门 lint（no-naked-llm / no-naked-send / skill-contract / tools）
├── skills/        A 层 SKILL.md（Claude Code / Cursor 触发层）
│   └── zhgk/      智慧工勘 Skill 定义
├── manager/       UX 协调层（登录鉴权、会话票据，代理数据中心）
├── mailgw/        邮件网关（GKCLAW 任务包收发，可选）
├── decisions/     架构决策记录（ADR）
├── docs/          团队 Agent 开发范式（架构梳理 / 工程范式 / 评测标准）
├── .cursorrules   Cursor/Claude Code 红线规则（编码时实时约束）
└── AGENTS.md      AI 工具完整规范（权威）
```

## 快速起手

### 0. 本地 Mock 数据中心（仅本地联调需要）

如果本机没有可用的远端数据中心，先启动本地 Mock Datacenter；生产、测试环境或已连接远端数据中心时不需要启动它。

```bash
# 在仓库根目录执行。首次初始化时可先完成后端依赖安装，再启动本服务。
python agent/.local/mock_datacenter.py
```

Mock 服务地址：`http://127.0.0.1:9000`  
默认账号：`liwen / 123456`

本地联调时，在 `agent/.env` 中配置：

```bash
DATA_CENTER_BASE_URL=http://127.0.0.1:9000
AIDA_AGENT_BASE_URL=http://127.0.0.1:7401
MANAGER_PORT=8081
```

### 1. 后端（FastAPI · port 7401）

```bash
# 在仓库根目录执行
python -m venv agent/.venv

# Windows
agent\.venv\Scripts\activate
# macOS / Linux
source agent/.venv/bin/activate

# 使用镜像源安装依赖
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r agent/requirements.txt

# 配置密钥（复制模板后填入智谱 key 和 Langfuse key）
cp agent/.env.example agent/.env

# 公司内网下模型调用如需代理，可在 agent/.env 中追加：
# HTTP_PROXY=http://10.143.2.250:8088/
# HTTPS_PROXY=http://10.143.2.250:8088/

# 启动
uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload
```

> ⚠️ `HTTP_PROXY` / `HTTPS_PROXY` 仅在公司内网或能访问该代理时启用。若当前不在公司内网，保留
> `http://10.143.2.250:8088/` 会导致 LLM 请求先卡在代理连接上，界面常见表现为
> `LLM 摘要跳过（Request timed out.）`，且每一步等待明显变长。此时请注释掉这两行并重启 Agent。

改动 `agent/skills/*/sdui.py`、`agent/sdui/*` 或 step 执行逻辑后，需要重启 Agent；旧 run 保留的是旧内存态，建议重新启动一次流程验证。

### 2. Manager（鉴权代理 · port 8081，本地登录需要）

如果前端需要走登录流程，需要同时启动 Manager。生产、测试环境应指向真实数据中心；本地联调可配合上面的 Mock Datacenter。

```bash
# 在仓库根目录执行，复用 agent/.venv
uvicorn manager.main:app --host 127.0.0.1 --port 8081
```

### 3. 前端（Vite + React · port 8080）

```bash
cd frontend
npm install --registry=https://registry.npmmirror.com
npm run dev
```

本地登录最小组合：Mock Datacenter 9000（仅无远端数据中心时）+ Agent 7401 + Manager 8081 + Frontend 8080。

### 3.1 本地重置脚本（仅本地测试用）

#### 3.1a 只重置工勘工作区（推荐）

换底表、清旧结果表、清 GKCLAW 登记，但**不重启服务**、**不删 Template 底表**：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/reset_zhgk.ps1
```

或：

```bash
python agent/scripts/reset_zhgk_workspace.py
```

| 参数 | 作用 |
|------|------|
| （默认） | 清 `Output` / `RunTime` / `Images`；保留 `Template`（含风险库）与 `Input` |
| `-ClearInput` / `--clear-input` | 同时清 `Input`，并 seed 演示 `本地工勘报告.pdf` |
| `-ClearTemplate` / `--clear-template` | 同时清底表，下次须重新 HITL 上传 |
| `-Full` / `--full` | 清 Template + Input + checkpoint |
| `-DryRun` / `--dry-run` | 仅预览将删除的路径 |

#### 3.1b 全套本地联调重置（停服 + 清数据 + 拉起）

当本地 run 状态、GKCLAW task、mailgw 缓存或前端页面状态出现串扰时，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/reset_local_dev.ps1
```

脚本会停止并重启本地联调服务：Mock Datacenter `9000`、Agent `7401`、Manager `8081`、mailgw `8025`（存在 `mailgw/config.yaml` 时）和 Frontend `8080`。

它会清理本地运行态数据（通过 `reset_zhgk_workspace.py --clear-input`）：

- `ZHGK_ROOT/ProjectData/Input`（随后重新 seed 演示报告）
- `ZHGK_ROOT/ProjectData/Output`
- `ZHGK_ROOT/ProjectData/RunTime`
- `ZHGK_ROOT/ProjectData/Images`
- `mailgw/data`（可用 `-KeepMailgwData` 保留）

不会清理源码、依赖、`agent/.env`、`mailgw/config.yaml`、`ProjectData/Template` 和 `ProjectData/Start`。该脚本仅用于本机重新测试，不用于生产或共享环境。

常用参数：

```powershell
# 只清理运行数据，不重新拉服务
powershell -ExecutionPolicy Bypass -File scripts/reset_local_dev.ps1 -NoStart

# 保留 mailgw 本地数据库/附件缓存
powershell -ExecutionPolicy Bypass -File scripts/reset_local_dev.ps1 -KeepMailgwData

# 不启动前端或 mailgw
powershell -ExecutionPolicy Bypass -File scripts/reset_local_dev.ps1 -NoFrontend -NoMailgw
```

### 3.2 演示服务器 Docker Compose（非生产）

演示服务器推荐用仓库根目录的 `docker-compose.yml` 一次拉起 Agent、Manager、Frontend、mailgw。它面向演示联调，不是生产高可用部署方案：

```bash
# docker-compose.yml 默认读取已提交的 example 配置，便于演示环境直接校验/拉起。
# 若要覆盖为本地私有配置，可复制后按实际环境填写：
#   cp agent/.env.example agent/.env
#   cp mailgw/.env.example mailgw/.env
#   cp mailgw/config.yaml.example mailgw/config.yaml
#   export MAILGW_CONFIG_FILE=./mailgw/config.yaml
docker compose up -d --build
```

访问入口：`http://<演示服务器IP>:5401`。前端默认走同源反代，不需要在浏览器侧配置 `127.0.0.1`；nginx 会把 `/agent`、`/api/v1`、`/api/sog`、`/data/sog-assets` 转到容器内 Agent，把登录和项目接口转到 Manager。

演示服务器必须确认：

- 如需私有覆盖，`agent/.env` 中 `DATA_CENTER_BASE_URL` 指向容器可访问的数据中心地址；如果使用 Mock Datacenter，不能写宿主机视角的 `127.0.0.1`，应改为容器可达的 IP/域名。
- `agent/.env.example` 或私有 `agent/.env` 中 `AIDA_SEND_EMAIL=1`、`AIDA_MAIL_BACKEND=mailgw`、`MAILGW_TOKEN` 已配置。
- `mailgw/.env.example` 或私有 `mailgw/.env` 中 `MAILGW_TOKEN_AIDA` 与 Agent 侧 `MAILGW_TOKEN` 完全一致。
- `mailgw/config.yaml.example` 或私有 `mailgw/config.yaml` 中 `pop3.poll_interval` 建议设为 `30~60`，并保持 `agent_notify.enabled: true`，这样收到 GKCLAW 回传邮件后会自动通知 Agent 继续检查。
- `data/sog-assets/` 和 `data/sog-scenes.json` 已准备好；它们会挂载进容器，重启后保留。

演示服务器重置运行态时使用（底层均为 `agent/scripts/reset_zhgk_workspace.py`）：

```bash
# 清 Output/RunTime/Images，保留 Template 底表与风险库、Input
bash scripts/reset_demo.sh

# 清理后顺手重启容器服务
bash scripts/reset_demo.sh --restart

# 连 Input 也清理，适合从头演示一轮
bash scripts/reset_demo.sh --clear-input --restart

# 彻底重置（含底表与 LangGraph checkpoint）
bash scripts/reset_demo.sh --full --restart
```

该脚本不会清理源码、依赖、`agent/.env`、`mailgw/.env`、`mailgw/config.yaml`；**默认保留** `ProjectData/Template`（含风险库）；`--full` 时才会清空 Template。`data/sog-assets` 和 `data/sog-scenes.json` 始终保留。

### 4. 实景孪生 3D 场景（可选演示）

`孪生世界 → 实景孪生` 页面依赖后端 `agent` 提供 SOG/3D 场景资源。历史场景默认读取：

```text
data/sog-assets/channel1/scene.sog
data/sog-scenes.json
```

本地演示时需要预先放好 `scene.sog`（大文件不入库）。页面会展示场景列表、视频上传时间、场景状态；新上传的视频当前登记为“训练中”，训练/转码服务后续接入前先走 mock 状态。

初始视角在 `data/sog-scenes.json` 的场景 `camera` 字段中配置：

```json
"camera": {
  "position": [0, 1.6, -8],
  "target": [0, 1, 0],
  "fov": 60
}
```

`position` 是进入场景时相机所在位置，`target` 是看向的位置。调试时只需修改对应场景的 `camera`，重启/刷新后端 settings 即可生效。

验证接口：

```bash
curl http://127.0.0.1:7401/api/sog/scenes
```

### 5. 邮件网关（可选，仅 GKCLAW 真发/回传需要）

默认邮件链路为 dry-run，不会真实发送。若要通过 mailgw 收发 GKCLAW 任务包，先启动 `mailgw/`，再在 `agent/.env` 中配置：

```bash
AIDA_SEND_EMAIL=1
AIDA_MAIL_BACKEND=mailgw
MAILGW_BASE=http://127.0.0.1:8025
MAILGW_TOKEN=<mailgw 签发的 Bearer token>
GKCLAW_FRONTAGENT_MAILBOX=front-agent@example.com
```

本地独立启动 mailgw 时，`MAILGW_BASE` 通常是 `http://127.0.0.1:8025`；Docker Compose 演示服务器中由编排覆盖为 `http://mailgw:8025`。若需要回传后自动继续流程，`mailgw/config.yaml` 的 `pop3.poll_interval` 不能为 `0`，且 `agent_notify.enabled` 应保持开启。

配置细节见 [`docs/50_数据与接口/GKCLAW配置变量清单.md`](docs/50_数据与接口/GKCLAW配置变量清单.md)、[`mailgw/README.md`](mailgw/README.md) 和 [`docs/50_数据与接口/GKCLAW部署与联调指南.md`](docs/50_数据与接口/GKCLAW部署与联调指南.md)。

### 6. 守门（提交前必跑，违规阻断）

```bash
# 激活 Python venv 后在仓库根执行
python agent/scripts/lint_no_naked_llm.py    # 禁裸 LLM 调用
python agent/scripts/lint_no_naked_send.py   # 禁裸外发
python agent/scripts/lint_skill_contract.py  # SKILL.md ↔ step.key 契约
python agent/scripts/lint_tools.py           # 工具契约（name/desc/schema）
```

新建业务场景 Skill → 阅读 [`START_HERE.md`](docs/10_快速开始/START_HERE.md)

## 架构概览

```
Wiki 大脑 → DORA 本体 → 交付 Claw/Agent → 交付编排应用
```

- **前端**：`frontend/`（Vite+React，port 8080）
- **后端**：`agent/`（FastAPI，port 7401）
- **样板 Skill**：`agent/skills/zhgk/`（智慧工勘，首个端到端跑通）
- **评测体系**：代码 `agent/evals/` · 标准与指标 [`docs/40_评测/`](docs/40_评测/EVAL-STANDARDS.md)（EVAL-STANDARDS v2，防假绿五原则）

## 开发规范

规范条文 → [`docs/03_团队Agent开发范式.md`](docs/20_架构与范式/03_团队Agent开发范式.md)  
AI 工具规则 → [`.cursorrules`](.cursorrules) / [`AGENTS.md`](AGENTS.md)  
守门命令：

```bash
python agent/scripts/lint_no_naked_llm.py
python agent/scripts/lint_no_naked_send.py
python agent/scripts/lint_skill_contract.py
python agent/scripts/lint_tools.py
```
