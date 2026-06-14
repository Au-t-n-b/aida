# AIDA · Vite 前端

Vite + React 前端工程，取代原 Next.js 静态导出版本，**是当前唯一前端真相**。

## 技术栈

- Vite 8 + React 19 + TypeScript
- react-router-dom 7（BrowserRouter）
- Tailwind CSS 3（`preflight: false`，与 `globals.css` 共存）

## 开发

```bash
npm install --registry=https://registry.npmmirror.com
npm run dev          # http://localhost:5173
```

Python Agent 需单独启动，请在仓库根目录执行：

```bash
agent\.venv\Scripts\activate   # Windows；macOS/Linux 使用 source agent/.venv/bin/activate
uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload
```

登录流程还需要 Manager（默认 `http://127.0.0.1:8000`）；本地没有远端数据中心时，先按根 README 启动 Mock Datacenter。

## 构建

```bash
npm run build        # dist/
npm run preview      # 本地预览（含 SPA fallback）
npm run build:desktop  # 构建并复制到桌面目录
```

## 从 Next 项目同步 UI 改动

Vite 版是当前唯一前端真相。该脚本仅用于遗留迁移场景，运行前务必确认不会覆盖当前 Vite 改动。

仅同步框架无关目录（`components`、`data`、`lib`、`types`、`globals.css`）：

```bash
npm run sync:from-next
```

同步后若覆盖了 `app-shell` / `claw-rail`，请把 `next/link`、`next/navigation` 改回 `@/compat/*`。

## 路由对照

| 路径 | 页面 |
|------|------|
| `/` | 未登录 → `/login`；已登录 → `/landing` |
| `/login` | 登录 |
| `/landing` | 项目列表 |
| `/cockpit` | 项目孪生看板 |
| `/proposal` | 交付预案 |
| `/preview` | 合同 / BOQ |
| `/module/:key` | 交付模块（如 `/module/survey`） |
| `/twin/survey` | 实景孪生 3D 场景 |
| … | 见 `src/router.tsx` |

## 离线 file://

BrowserRouter 在纯 `file://` 下深链需每路由一份 `index.html`。构建后运行：

```bash
node scripts/gen-offline-html.mjs
```

或 `npm run build:desktop`（会自动尝试生成）。
