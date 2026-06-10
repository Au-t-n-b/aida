# UX / 设计先行（docs/ux）

> AIDA 的 **UX 先行**文档（范式 [03 §5 契约先行 + UX 先行](../20_架构与范式/03_团队Agent开发范式.md)）——动手写前端代码前的**前置环**：先冻设计意图与视觉 token，再冻 `state` 读契约，前后端并行实现。
> 从 `aida-delivery` 知识库 `03_前端效果/` 迁入（设计意图 + token 真相）。**前端实现在本仓 [`frontend/`](../../frontend/)**（Vite + React + Tailwind），不再是 aida-delivery 的原型。

## 读什么

| 文件 | 是什么 |
|------|--------|
| [设计 Brief](设计Brief.md) | **设计意图唯一真相**：态势优先 / 逐级披露 / AI 可信 / 企业级克制视觉 / 主页两版 |
| [页面设计偏好](页面设计偏好.md) | 领导汇报视角的原始偏好 |
| [UI 视觉规范](UI视觉规范.md) | 已选定的视觉骨架与配色 Tokens 说明 |
| [DESIGN.md](DESIGN.md) + [visual-system.css](visual-system.css) | **设计 token 真相**：slate + indigo 控制台语言、颜色 / 字阶 / 间距 / 组件 |

## ⚠️ token 体系待统一（已知 gap）

`DESIGN.md` / `visual-system.css` 是**纯 CSS 变量**体系（`--c-brand` 等，源自 aida-delivery 原型）；本仓 `frontend/` 用的是 **Tailwind**（`src/styles/globals.css`）。两套命名不同。

- **现状**：`DESIGN.md` 是**设计规范真相**，`frontend/` 实现时对齐它的语义（颜色角色、8pt 间距制、组件公式）。
- **待办**：把 `frontend/` 的 Tailwind 主题与 `DESIGN.md` token 对齐成单一真相（它同时是 SDUI 组件的视觉底座）。这是后续工作，不是搬文件能解决的。

## 不在这里的

- **前端实现** → 本仓 [`frontend/`](../../frontend/)。
- **品牌 Logo** → 已并入 [`品牌与草图/`](品牌与草图/)（Logo 设计方案 + 关键 Logo 资产）。大草图 PNG / pptx 留 `aida-delivery` 知识库（探索参考，不进代码仓）。
- **可运行原型**（React 单页）→ 仍在 `aida-delivery/03_前端效果/04_前端实现/`（知识库，按需查）。
