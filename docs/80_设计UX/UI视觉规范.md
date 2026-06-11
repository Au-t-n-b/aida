# UI 视觉规范与设计 Tokens

> 本文档沉淀 AIDA 前端**已选定的界面视觉骨架与配色 Tokens**，供原型、组件库与实现阶段直接引用。
>
> **关键词**：浅色底、深色侧边栏、蓝色品牌主色、低圆角、细边框、弱阴影、紧凑表格。
>
> 配套阅读：[设计 Brief](设计Brief.md)（气质与信息架构）、[DESIGN.md](DESIGN.md)（设计 token 真相）。界面主色以本文 Tokens / DESIGN.md 为准；Logo 语义在 `aida-delivery` 知识库。

---

## 1. 视觉关键词

| 维度 | 约定 |
| --- | --- |
| 整体基调 | 浅色底、高可读、企业级克制 |
| 导航 | 深色侧边栏，与主内容区形成稳定对比 |
| 品牌 | 蓝色为主品牌色，红色仍保留「要紧事」语义（见 Brief） |
| 形状 | 低圆角，仅状态类 pill 使用大圆角 |
| 层级 | 细边框区分，弱阴影，避免强烈卡片漂浮感 |
| 数据展示 | 紧凑表格为主 |

---

## 2. 视觉骨架（应用壳）

### 2.1 布局结构

页面采用**固定应用壳**：

| 区域 | 规格 | 说明 |
| --- | --- | --- |
| 左侧 Sidebar | 固定宽度 `220px`，深色背景 | 主导航与模块入口 |
| 顶部 Topbar | 固定高度 `56px`，白色背景 | 全局操作、视角切换等 |
| 主内容区 | 剩余区域，**可滚动** | 页面主体与面板 |

### 2.2 表面与层级

- **主背景**：`#f6f8fb`，营造浅色、冷静的整页底色。
- **内容面板**：多为白色 `#ffffff`，通过 `#e3e8ef` **细边框**区分层级，而非依赖重阴影。
- **阴影**：很轻，仅用于按钮 active、浮层、甘特条 hover 等必要反馈；不做强烈「漂浮卡片」效果。

### 2.3 圆角

组件圆角偏克制：

| 场景 | 圆角 |
| --- | --- |
| 小控件（按钮、输入框等） | `4px` / `6px` |
| 卡片、浮层、弹层 | `8px` |
| Pill 类状态标签 | 大圆角（胶囊形） |

---

## 3. 设计 Tokens

### 3.1 基础色

| Token 名称 | 色值 | 用途 |
| --- | --- | --- |
| `bg` | `#f6f8fb` | 页面主背景 |
| `bg-muted` | `#eef2f7` | 弱背景、区块底色 |
| `surface` | `#ffffff` | 主表面（卡片、面板） |
| `surface-secondary` | `#fafbfc` | 次表面、表头、嵌套区域 |
| `border` | `#e3e8ef` | 主边框、面板描边 |
| `border-strong` | `#cbd5e1` | 强边框、聚焦/分隔强调 |
| `divider` | `#eef2f7` | 分割线 |

### 3.2 文本色

| Token 名称 | 色值 | 用途 |
| --- | --- | --- |
| `text-primary` | `#0f172a` | 主文本、标题 |
| `text-secondary` | `#334155` | 次文本、说明 |
| `text-muted` | `#64748b` | 弱文本、辅助标签 |
| `text-faint` | `#94a3b8` | 极弱文本、占位、时间戳 |

### 3.3 品牌色

| Token 名称 | 色值 | 用途 |
| --- | --- | --- |
| `brand` | `#3551d8` | 主品牌蓝（主按钮、链接、选中态） |
| `brand-subtle` | `#eef1fc` | 品牌浅底（选中行、标签底） |
| `brand-hover` | `#2a44c2` | 品牌 hover / active |
| `brand-text` | `#1e34a8` | 品牌深色文字（链接、强调文案） |

### 3.4 CSS 变量参考（可选）

实现时可映射为：

```css
:root {
  --bg: #f6f8fb;
  --bg-muted: #eef2f7;
  --surface: #ffffff;
  --surface-secondary: #fafbfc;
  --border: #e3e8ef;
  --border-strong: #cbd5e1;
  --divider: #eef2f7;

  --text-primary: #0f172a;
  --text-secondary: #334155;
  --text-muted: #64748b;
  --text-faint: #94a3b8;

  --brand: #3551d8;
  --brand-subtle: #eef1fc;
  --brand-hover: #2a44c2;
  --brand-text: #1e34a8;

  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;

  --sidebar-width: 220px;
  --topbar-height: 56px;
}
```

---

## 4. 与 Brief 的关系

- [设计 Brief](设计Brief.md) 第 9 节保留**气质护栏**（企业级、克制、禁廉价特效等）；本文档在其基础上**锁定一版可落地的浅色壳 + 蓝色品牌 Tokens**。
- Sidebar 深色具体色值、表格行高、字号阶梯等待原型阶段补全后，可追加为 `3.5 布局尺寸` / `3.6 排版` 小节。

---

## 5. 修订记录

| 日期 | 说明 |
| --- | --- |
| 2026-05-22 | 初版：视觉骨架 + 基础色 / 文本色 / 品牌色 Tokens |
