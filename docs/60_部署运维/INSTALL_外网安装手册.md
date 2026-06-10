# AIDA 外网安装手册

> 适用场景：公司内网无法访问 PyPI / npm，需在家或外网机器完成依赖安装，再带回内网运行。  
> 仓库地址：<https://github.com/Au-t-n-b/aida.git>

---

## 一、环境要求

| 组件 | 版本 |
|------|------|
| Python | **3.10+**（推荐 3.10.x，与 win_amd64 wheel 兼容最好） |
| Node.js | **18+**（你当前 22.x 可用） |
| Git | 任意较新版本 |

可选账号（运行工勘 Skill 时需要）：

- **智谱 BigModel API Key**（必填，否则 `/healthz` 显示 `configured: false`）
- Langfuse（可选，用于 trace / 评测可视化）

---

## 二、外网：获取代码

```bash
git clone https://github.com/Au-t-n-b/aida.git
cd aida
```

若已在内网 clone 过，也可直接把整个 `D:\aida` 文件夹用 U 盘/网盘拷到外网，跳过 clone。

---

## 三、外网：安装 Python 后端依赖

### 3.1 关键约定（易错）

1. **虚拟环境路径**：`agent/.venv`（在仓库根下创建，不要 `cd agent` 后再建）
2. **启动 uvicorn**：必须在**仓库根目录** `aida/` 执行，不能在 `agent/` 里执行  
   否则报错：`ModuleNotFoundError: No module named 'agent'`

### 3.2 Windows（PowerShell）

```powershell
cd D:\aida          # 换成你的实际路径

python -m venv agent\.venv
.\agent\.venv\Scripts\Activate.ps1

# 若 pip 报 GBK 解码 requirements.txt 失败，先设 UTF-8：
$env:PYTHONUTF8 = "1"

pip install -U pip
pip install -r agent\requirements.txt
```

### 3.3 macOS / Linux

```bash
cd ~/aida

python3 -m venv agent/.venv
source agent/.venv/bin/activate

pip install -U pip
pip install -r agent/requirements.txt
```

### 3.4 验证 Python 依赖

```powershell
.\agent\.venv\Scripts\python.exe -c "import fastapi, langgraph, openai; print('OK')"
```

应输出 `OK`。

---

## 四、外网：配置后端密钥

```powershell
# Windows
Copy-Item agent\.env.example agent\.env

# macOS / Linux
cp agent/.env.example agent/.env
```

编辑 `agent/.env`，**至少**填写：

```ini
ZHIPU_API_KEY=你的智谱key
```

可选：

```ini
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## 五、外网：安装前端依赖

```bash
cd frontend
npm install
cd ..
```

验证：

```bash
cd frontend
npm run build    # 可选，确认能编译
```

---

## 六、外网：本地试跑（确认无误再打包）

开**两个终端**，都在仓库根 `aida/`：

**终端 1 — 后端（7401）**

```powershell
cd D:\aida
.\agent\.venv\Scripts\Activate.ps1
uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload
```

**终端 2 — 前端（5173）**

```powershell
cd D:\aida\frontend
npm run dev
```

浏览器打开：<http://localhost:5173>

健康检查：

```powershell
curl http://127.0.0.1:7401/healthz
```

期望 JSON 含 `"ok": true`，且填好 key 后 `"configured": true`。

---

## 七、带回内网：三种方式

### 方式 A（推荐）：整包拷贝

在外网把整个项目目录打包（含已安装的依赖）：

**必须包含：**

```
aida/
├── agent/.venv/          ← Python 依赖（体积大，但必须）
├── frontend/node_modules/ ← 前端依赖
├── agent/.env            ← 你的密钥（勿提交 git）
└── 其余源码目录
```

**可不拷：**

- `.git/`（内网已有仓库可不要）
- `frontend/dist/`（可内网再 build）

压缩示例（PowerShell，在外网执行）：

```powershell
cd D:\
Compress-Archive -Path D:\aida -DestinationPath D:\aida-offline-ready.zip
```

拷到内网后解压到例如 `D:\aida`，直接按「第六节」启动即可，**无需再 pip/npm install**。

> 注意：`.venv` 是在**同一操作系统 + 同一大版本 Python** 下打的包才最稳。  
> 外网是 Windows + Python 3.10，内网也应是 Windows + Python 3.10。

---

### 方式 B：只拷 wheel / node_modules 压缩包

外网单独打包依赖，内网解压到对应位置：

```powershell
# Python wheels 清单（外网）
pip download -r agent\requirements.txt -d agent\wheels

# 内网离线安装
.\agent\.venv\Scripts\pip.exe install --no-index --find-links agent\wheels -r agent\requirements.txt
```

```powershell
# 前端：外网打包 node_modules
cd frontend
tar -a -c -f ..\frontend-node_modules.zip node_modules
# 内网解压到 frontend\node_modules
```

---

### 方式 C：内网仅有源码，依赖已在另一台外网机装好

只同步这两个目录到内网相同路径：

| 外网路径 | 内网目标 |
|----------|----------|
| `agent/.venv` | `D:\aida\agent\.venv` |
| `frontend/node_modules` | `D:\aida\frontend\node_modules` |
| `agent/.env` | `D:\aida\agent\.env` |

---

## 八、内网：启动（无需再装依赖时）

```powershell
cd D:\aida
.\agent\.venv\Scripts\Activate.ps1
uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload
```

```powershell
cd D:\aida\frontend
npm run dev
```

若内网 `npm run dev` 仍尝试联网，可加：

```powershell
$env:npm_config_offline = "true"
npm run dev
```

---

## 九、智慧工勘（zhgk）数据准备（可选）

要跑通工勘 Skill，还需底表与工作区：

```powershell
cd D:\aida
.\agent\.venv\Scripts\Activate.ps1
python agent\scripts\init_zhgk_workspace.py --dest "$env:USERPROFILE\Desktop\zhgk-desktop"
```

将底表放入 `Desktop\zhgk-desktop\ProjectData\Template\`（v4 目录）：

- 入场评估标准表.xlsx（必须）
- 工勘常见高风险库.xlsx（必须）
- 新版项目工勘报告模板.docx（可选）

在 `agent/.env` 增加：

```ini
ZHGK_ROOT=C:/Users/你的用户名/Desktop/zhgk-desktop
```

每次跑工勘前，在 `ProjectData/Input/` 放入 `BOQ.xlsx`（文件名须含 BOQ）。

---

## 十、工勘孪生（SOG 通道1）数据准备（可选）

孪生世界 → **工勘孪生**（`/twin/survey`）需要预置 SOG 场景文件（约 80MB，**不入 git**）。

### 10.1 复制通道1.sog

```powershell
cd D:\aida
$dst = "data\sog-assets\channel1"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item -Force "C:\Users\你的用户名\Desktop\通道\通道1.sog" "$dst\scene.sog"
```

或使用一键脚本（可指定源路径）：

```powershell
.\agent\scripts\init_sog_channel1.ps1
# 或
.\agent\scripts\init_sog_channel1.ps1 -Source "D:\path\to\通道1.sog"
```

目录结构：

```text
data/sog-assets/channel1/
  scene.sog
  hotspots.json   # 初始 []，可由页面编辑热点后更新
  meta.json
```

### 10.2 验证

Agent（7401）启动后：

```powershell
Invoke-WebRequest http://127.0.0.1:7401/api/sog/assets/channel1/hotspots -UseBasicParsing
# 预期 StatusCode 200，Content: []
```

浏览器打开：<http://localhost:5173/twin/survey>，应自动加载通道1 三维场景。

---

## 十一、常见问题

| 现象 | 处理 |
|------|------|
| `No module named 'agent'` | 在**仓库根**启动 uvicorn，不要 `cd agent` |
| pip `UnicodeDecodeError`（GBK） | Windows 设 `$env:PYTHONUTF8="1"` 后重装 |
| `/healthz` 的 `configured: false` | 检查 `agent/.env` 中 `ZHIPU_API_KEY` |
| 内网 pip 超时 / WinError 10013 | 内网不要 pip；用外网打好 `.venv` 再拷贝 |
| 代理仅 git 可用 | clone 用代理；**pip/npm 建议外网直连**，不要走公司 HTTPS 代理 |
| 前端连不上后端 | 确认 7401 已起；前端写死 `127.0.0.1:7401` |
| 端口占用 | 改 `agent/.env` 的 `AIDA_AGENT_PORT`，或结束占用 7401 的进程 |

---

## 十二、内网 clone 若失败（仅 git 需要时代理）

```bash
git config --global http.proxy "http://用户:密码@proxy.huawei.com:8080/"
git config --global https.proxy "http://用户:密码@proxy.huawei.com:8080/"
git config --global http.sslverify false
```

密码含 `!` 等特殊字符需 URL 编码（如 `!` → `%21`）。  
**pip/npm 不建议用 https:// 形式的 HTTPS_PROXY**，易 SSL 握手超时；外网直连安装更省事。

---

## 十三、检查清单

- [ ] 外网 `pip install -r agent/requirements.txt` 成功
- [ ] 外网 `frontend/npm install` 成功
- [ ] `agent/.env` 已填 `ZHIPU_API_KEY`
- [ ] 外网 `/healthz` 返回 `configured: true`
- [ ] 已打包 `agent/.venv` + `frontend/node_modules` 带回内网
- [ ] 内网从仓库根启动 uvicorn + `npm run dev`
- [ ] 浏览器可打开 http://localhost:5173

---

## 参考

- 仓库 README：<https://github.com/Au-t-n-b/aida>
- 详细上手：`SETUP.md`
- 新 Skill 开发：`docs/10_快速开始/START_HERE.md`
