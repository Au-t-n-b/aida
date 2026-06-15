# AIDA · 同事上手指南（SKILL 测试）

> 前提：Python 3.10+，Node.js 18+，已拿到 zhgk 底表数据压缩包（单独发送）。
> 如需体验实景孪生 3D 场景，还需准备 `通道1.sog` 文件（大文件，不入库）。

---

## 第一步：clone + Python 环境

```bash
git clone https://github.com/Au-t-n-b/aida.git
cd aida
```

**⚠️ venv 建在仓库根，不要 `cd agent/` 再建**（uvicorn 必须从仓库根运行）：

```bash
python -m venv agent/.venv

# Windows（PowerShell）
agent\.venv\Scripts\activate

# macOS / Linux
source agent/.venv/bin/activate

python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r agent/requirements.txt
```

---

## 第二步：配置密钥

```bash
cp agent/.env.example agent/.env
```

用编辑器打开 `agent/.env`，**至少填这一项**：

```ini
ZHIPU_API_KEY=你的智谱key      # 必填，没有 key 后端起来也会报错
```

可选但推荐（评测数据可视化需要）：

```ini
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## 第三步：准备 zhgk 工作区数据

### 3a. 初始化目录骨架

```bash
# Windows
python agent/scripts/init_zhgk_workspace.py --dest %USERPROFILE%\Desktop\zhgk-desktop

# macOS / Linux
python agent/scripts/init_zhgk_workspace.py --dest ~/Desktop/zhgk-desktop
```

会在桌面建好目录结构：

```
zhgk-desktop/
└── ProjectData/
    ├── Template/ ← 放底表/模板文件（下一步）
    ├── Input/    ← 每次跑工勘前放 BOQ + 人员信息
    ├── RunTime/  （自动生成）
    ├── Output/   （自动生成）
    └── Images/   （可放现场照片）
```

### 3b. 解压底表数据包

将收到的压缩包解压，把里面的文件放入 `zhgk-desktop/ProjectData/Template/`：

```
Template/
├── 入场评估标准表.xlsx           ← filter_build 读底表（必须）
├── 工勘常见高风险库.xlsx         ← 风险识别（必须）
└── 新版项目工勘报告模板.docx     ← 报告模板（可选，缺失时用内置模板）
```

### 3c. 在 .env 里指定工作区路径

```ini
# Windows 示例（路径里反斜杠要双写，或用正斜杠）
ZHGK_ROOT=C:/Users/你的用户名/Desktop/zhgk-desktop

# macOS / Linux
ZHGK_ROOT=/Users/你的用户名/Desktop/zhgk-desktop
```

---

## 第四步：启动后端

**⚠️ 在仓库根（aida/）目录下运行，不是在 agent/ 里**：

```bash
uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload
```

验证是否正常：

```bash
curl http://127.0.0.1:7401/healthz
```

正常输出应包含 `"ok": true` + `"configured": true`（LLM 配置好了）。

---

## 第五步：启动前端

```bash
cd frontend
npm install --registry=https://registry.npmmirror.com
npm run dev
```

访问 `http://localhost:8080`。默认前端走同源代理：本地 Vite dev server 代理到 `127.0.0.1:7401`，演示服务器由 nginx 反代到容器内 Agent。只有在需要绕过代理直连某台后端时，才在 `frontend/.env` 中填写 `VITE_AGENT_BASE`。

---

## 第六步：测试 SKILL

### 方式 A：API 直测（验证后端最快）

```bash
# 查 skill 列表
curl http://127.0.0.1:7401/agent/skills

# 启动工勘（先在 Template/ 放好底表，Input/ 放好 BOQ.xlsx）
curl -X POST http://127.0.0.1:7401/agent/zhgk/start \
  -H "Content-Type: application/json" \
  -d '{"project_code":"K1903","project_name":"测试项目","scenario_run":"训推一体"}'

# 拿到 run_id 后订阅实时进度（SSE）
curl http://127.0.0.1:7401/agent/zhgk/stream/<run_id>
```

### 方式 B：前端会话触发

前端页面 → 左侧会话输入「帮我跑工勘 K1903」→ 自动触发并显示进度卡。

---

## 常见问题

| 现象 | 原因 & 解决 |
|------|------------|
| `ModuleNotFoundError: No module named 'agent'` | uvicorn 在错误目录执行。**确保在仓库根 `aida/` 下运行**，不是 `cd agent/` 后运行 |
| `/healthz` 返回 `"configured": false` | `agent/.env` 里 `ZHIPU_API_KEY` 未填或填错 |
| 工勘卡在 0%，状态显示 `hitl` | `Template/` 目录里缺底表文件（入场评估标准表.xlsx / 工勘常见高风险库.xlsx）。上传后点「继续」 |
| 工勘卡在 20%，`Input/` 文件检查失败 | 缺 BOQ.xlsx，放入 `Input/`（文件名须含 BOQ）后 resume |
| 前端白屏 / 请求后端失败 | 后端没起、端口被占，或 `VITE_AGENT_BASE` 配错。默认可不填 `VITE_AGENT_BASE`，让前端走同源代理 |

---

## 第七步：实景孪生 3D 场景（可选）

> 如果你需要使用 `孪生世界 → 实景孪生` 页面，需要额外部署 3D 场景文件。

### 7a. 获取通道文件

准备 `.sog` 文件（3DGS/高斯建模结果，大文件不入库）。当前本地演示默认使用通道1历史场景。

### 7b. 部署到本地（Windows PowerShell）

```powershell
# 默认从 %USERPROFILE%\Desktop\通道\通道1.sog 读取
powershell -File agent/scripts/init_sog_channel1.ps1

# 或手动指定 .sog 文件路径
powershell -File agent/scripts/init_sog_channel1.ps1 -Source "D:\你的路径\通道1.sog"
```

脚本会把 `scene.sog` 复制到 `data/sog-assets/channel1/`，并生成 `meta.json` 和空 `hotspots.json`。

场景列表由 `data/sog-scenes.json` 管理；默认历史场景指向 `channel1`。页面支持修改场景名、查看上传时间。新上传视频当前登记为“训练中”，训练/转码服务接入前先按本地 mock 状态展示。

初始视角也配置在 `data/sog-scenes.json` 的场景 `camera` 字段中：

```json
"camera": {
  "position": [0, 1.6, -8],
  "target": [0, 1, 0],
  "fov": 60
}
```

如果进入后视角仍不合适，优先调整 `position`：第三个值更负通常表示向后退，第二个值表示高度；`target` 表示看向的中心点。

### 7c. 验证

后端启动后访问：`http://127.0.0.1:7401/api/sog/scenes`

应返回：

```json
[{ "id": "channel1", "status": "ready", "sceneExists": true, ... }]
```

前端访问 `http://localhost:8080/twin/survey` 即可看到实景孪生 3D 场景。

---

## 守门（提交代码前必跑）

```bash
# 激活 venv 后在仓库根执行
python agent/scripts/lint_no_naked_llm.py
python agent/scripts/lint_no_naked_send.py
python agent/scripts/lint_skill_contract.py
python agent/scripts/lint_tools.py
```

---

## 新增业务场景 Skill

阅读 [`START_HERE.md`](START_HERE.md) — 照 zhgk 打样 30 分钟搭起新 Skill 骨架。
