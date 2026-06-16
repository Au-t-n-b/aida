# skill 运行时热插拔 · 测试步骤（给同事）

> **测什么**：改完一个 skill 目录包放进 `agent/skills/<name>/`，**调一次接口、aida 进程不重启**就生效。
> **分支**：`feature_new`（含提交 `d34466a`）。先 `git pull` 到最新。

---

## 0. 前提（三件，缺一不可）

1. **拉最新代码** + 装依赖
   ```bash
   git checkout feature_new && git pull
   cd agent && python -m venv .venv && .venv\Scripts\activate   # 已建过则跳过
   pip install -r requirements.txt
   pip install tzdata          # ⚠ Windows/Py3.13 必装，否则后端起不来（ZoneInfoNotFoundError）
   ```

2. **在 `agent/.env` 里配 admin token**（不配则接口返回 503，这是故意的 fail-closed 安全设计）
   ```ini
   AIDA_ADMIN_TOKEN=dev-token-123
   ```

3. **启动后端 —— 务必不要加 `--reload`** ❗
   ```bash
   # 仓库根目录
   uvicorn agent.main:app --host 127.0.0.1 --port 7401
   ```
   > 为什么不加 `--reload`：加了的话 uvicorn 自己会在文件一改就**重启整个进程**，那是它在生效、不是我们的热插拔。要测"零重启生效"，必须关掉 `--reload`，让**只有 `/agent/admin/reload` 接口**去拾取改动。

下面命令里 token 用 `dev-token-123`，端口 `7401`，按你的实际改。Windows 自带 `curl.exe`，GET 也可直接浏览器打开。

---

## 1. 基线：先看现在有哪些 skill
```bash
curl http://127.0.0.1:7401/agent/skills
```
**预期**：列出 `zhgk / guihua / system_design / device_install / software_deployment / xtsj`。

---

## 2. 核心：改一个现有 skill → 零重启生效

1. 在**运行 agent 的机器**上，编辑 `agent/skills/zhgk/skill.py`，把 `ZhgkSkill` 的 `description = "..."` 末尾加几个字，比如 `…（热插拔测试XYZ）`，**存盘**。
2. 调热重载（**不重启服务**）：
   ```bash
   curl -X POST "http://127.0.0.1:7401/agent/admin/reload?skill=zhgk" \
        -H "Authorization: Bearer dev-token-123"
   ```
   **预期**：`{"ok": true, "skill": "zhgk", "action": "reloaded"}`
3. 确认新代码已活：
   ```bash
   curl http://127.0.0.1:7401/agent/skills/zhgk
   ```
   **预期**：返回里的 `description` 带上了你加的 `（热插拔测试XYZ）`，而**进程从没重启**。
4. 把 description 改回去，再 reload 一次复原。

> 进阶（可选）：改完后直接在前端/接口 `POST /agent/zhgk/start` 跑一遍，确认新逻辑真的在执行。

---

## 3. 全量重扫（一次刷新所有 skill）
```bash
curl -X POST "http://127.0.0.1:7401/agent/admin/reload" \
     -H "Authorization: Bearer dev-token-123"
```
**预期**：`{"ok": true, "results": [{"skill":"device_install","action":"reloaded"}, ...]}`，每个 skill 都 reloaded。

---

## 4. 事务化：改坏了不会污染、不会崩（重点验证）

1. 故意把 `agent/skills/zhgk/skill.py` 改出语法错（比如随便删个括号），**存盘**。
2. reload：
   ```bash
   curl -X POST "http://127.0.0.1:7401/agent/admin/reload?skill=zhgk" \
        -H "Authorization: Bearer dev-token-123"
   ```
   **预期**：`{"ok": false, "skill": "zhgk", "action": "error", "error": "SyntaxError: ..."}`
3. 关键：**服务没崩，zhgk 旧版还在**：
   ```bash
   curl http://127.0.0.1:7401/agent/skills/zhgk     # 仍正常返回（旧版本还活着）
   ```
4. 把语法错改回，再 reload → 恢复 `ok: true`。

> 对比：如果用 `uvicorn --reload`，这一步会**直接把整个服务搞崩**。我们的热插拔是单 skill 隔离的。

---

## 5. 安全：token 校验
```bash
# 不带 / 带错 token
curl -i -X POST "http://127.0.0.1:7401/agent/admin/reload?skill=zhgk" \
     -H "Authorization: Bearer WRONG"
```
**预期**：`401`（无效 token）。若你**没配** `AIDA_ADMIN_TOKEN`，则返回 `503`（端点禁用）。

---

## 6. （可选）新增一个 skill 目录 → 出现在列表

把一个**完整合法**的 skill 目录包放到 `agent/skills/<newname>/`（含 `skill.py` 暴露 `get_<newname>_skill` + 其 `SKILL.md`），然后：
```bash
curl -X POST "http://127.0.0.1:7401/agent/admin/reload?skill=<newname>" \
     -H "Authorization: Bearer dev-token-123"      # 预期 action: "added"
curl http://127.0.0.1:7401/agent/skills            # 列表里多出 <newname>
```
删掉目录后再 reload 该名 → `action: "removed"`，列表里消失。

---

## 故障排查

| 现象 | 原因 / 处理 |
|---|---|
| 启动报 `ZoneInfoNotFoundError: Asia/Shanghai` | 缺 tzdata → `pip install tzdata`（与本功能无关的环境问题） |
| reload 返回 **503** | 没配 `AIDA_ADMIN_TOKEN`（fail-closed），在 `agent/.env` 配上并重启一次 |
| reload 返回 **401** | token 不对，检查 `Authorization: Bearer <值>` 与 `.env` 一致 |
| 改了文件 reload 后没变化 | 八成是用了 `uvicorn --reload`（它抢先整进程重启）→ 去掉 `--reload` 重测 |
| reload 返回 `action: "error"` 但你没改错 | 看 `error` 字段（缺工厂 `get_<name>_skill`？import 报错？） |

## 测完请反馈
- 第 2、4 步是否如预期（零重启生效 + 改坏不崩）；
- 各步的实际返回 JSON；
- 环境（OS / Python 版本 / 是否需要 `pip install tzdata`）。
