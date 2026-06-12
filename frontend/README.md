# AIDA · Vite 前端

Vite + React 前端工程，取代原 Next.js 静态导出版本，**是当前唯一前端真相**。

## 技术栈

- Vite 8 + React 19 + TypeScript
- react-router-dom 7（BrowserRouter）
- Tailwind CSS 3（`preflight: false`，与 `globals.css` 共存）

## 开发

```bash
npm install
npm run dev          # http://localhost:5173
```

Python Agent（工勘）仍在原仓库，需单独启动：

```bash
cd ../agent
uvicorn main:app --host 127.0.0.1 --port 7401 --reload
```

## 构建

```bash
npm run build        # dist/
npm run preview      # 本地预览（含 SPA fallback）
npm run build:desktop  # 构建并复制到桌面目录
```

## 从 Next 项目同步 UI 改动

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
| … | 见 `src/router.tsx` |

## 离线 file://

BrowserRouter 在纯 `file://` 下深链需每路由一份 `index.html`。构建后运行：

```bash
node scripts/gen-offline-html.mjs
```

或 `npm run build:desktop`（会自动尝试生成）。
