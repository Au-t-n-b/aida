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
├── decisions/     架构决策记录（ADR）
├── docs/          团队 Agent 开发范式（架构梳理 / 工程范式 / 评测标准）
├── .cursorrules   Cursor/Claude Code 红线规则（编码时实时约束）
└── AGENTS.md      AI 工具完整规范（权威）
```

## 快速起手

### 0. 本地 Mock 数据中心（仅本地联调需要）

如果本机没有可用的远端数据中心，先启动本地 Mock Datacenter；生产、测试环境或已连接远端数据中心时不需要启动它。

```bash
# 在仓库根目录执行，使用 agent/.venv
python agent/.local/mock_datacenter.py
```

Mock 服务地址：`http://127.0.0.1:9000`  
默认账号：`liwen / 123456`

本地联调时，在 `agent/.env` 中配置：

```bash
DATA_CENTER_BASE_URL=http://127.0.0.1:9000
AIDA_AGENT_BASE_URL=http://127.0.0.1:7401
```

### 1. 后端（FastAPI · port 7401）

```bash
cd agent
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# 配置密钥（复制模板后填入智谱 key 和 Langfuse key）
cp .env.example .env

# 启动
uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload
```

### 2. 前端（Vite + React · port 5173）

```bash
cd frontend
npm install
npm run dev
```

### 3. 守门（提交前必跑，违规阻断）

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

- **前端**：`frontend/`（Vite+React，port 5173）
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
