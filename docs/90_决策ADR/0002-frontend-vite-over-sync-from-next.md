# 0002. 前端以 vite 版为唯一真相，弃用 sync:from-next

- **状态**: Accepted
- **日期**: 2026-06-03
- **相关**: `aida-vite/`（vite 版）；`claw-delivery-ui/src/components/`（Next 版·遗留）；`aida-vite/scripts/sync-from-next.mjs`；`D:\code\.claude\launch.json`（preview 配置）

## 背景（Context）

存在**两个前端项目，都含 `src/components/claw-rail.tsx`**：

- `aida`：Next.js，且 Python Agent 后端就在此仓内；
- `aida-vite`：Vite + react-router-dom，含 `sync:from-next` 脚本（从 aida **单向覆盖** `components/data/lib/types` + `globals.css`），用于桌面打包（`build:desktop`）。

历史上 aida(Next) 像是主、aida-vite 是同步下游。但开发中 preview 默认起的是 aida，导致"改了 aida-vite 却看不到效果"，且 `sync:from-next` 会把 aida-vite 的改动覆盖掉——真相来源不清。

## 考虑的选项（Options）

- **A. 以 aida(Next) 为主，aida-vite 为同步下游**：保持 `sync:from-next` 单向。代价：Vite 桌面版永远滞后；前端改动要在 Next 做再同步。
- **B. 以 aida-vite(Vite) 为唯一前端真相，弃用 sync:from-next**：今后前端改动直接在 aida-vite；aida 的 Next 前端转为遗留。

## 决策（Decision）

**选 B**（用户拍板："项目已选好用 vite 框架"）。

- 前端唯一真相 = `aida-vite`；所有前端改动落在这里。
- **不再运行 `npm run sync:from-next`**（会用 Next 版覆盖 vite 版改动）。
- preview 经 `D:\code\.claude\launch.json` 的 `aida-vite` 配置启动（`npm run dev --prefix aida-vite`，port 5173）。

## 后果（Consequences）

- **正面**：单一前端真相，无"改了看不到"的困惑；对齐桌面打包路径（`build:desktop`）。
- **负面 / 代价**：`claw-delivery-ui/src/` 的 Next 前端成为遗留（仍含旧 `claw-rail.tsx` 等）；`sync:from-next` 脚本作废却仍在仓内，有被误跑覆盖 vite 的风险。
- **后续 / 触发回流**：
  1. 给 `sync-from-next.mjs` 加显式失效警告或删除，避免误跑；
  2. 评估清理 aida 前端遗留（与后端同仓，注意不要误删后端）；
  3. 若未来需要 Next 形态，再评估反向同步方向。
