#!/usr/bin/env python3
"""gen_team_portal · 把 docs/onboarding/portal.json 派生成「团队协作门户」单文件 HTML（派生制品，勿手改）

真相源：docs/onboarding/portal.json（角色路径 + 提示词 + 命令 + 文档链接）。本脚本把它渲染成一个
按角色（新人 / 架构师 / 模块开发者）逐层引导的门户页 docs/site/portal.html，和「图书馆」index.html
并排。门户自己不存文档正文，只做「分流 + 引导 + 提示词」，正文一律链回 Gitea 仓渲染页 / 文档站。

视觉语言：精密仪器 · 亮面拉丝钛 · 蓝图栅格 · 大留白（见 portal_assets/aida.css）。

为什么是门户而非文档站：index.html（gen_docs_site）是平铺阅读器（图书馆）；本页是接待台——
「你是谁 → 跟我走这条路 → 每步给你该读的文档 + 喂给 AI 的提示词 + 验收命令」。

零外部依赖（针对产物）：CSS/JS/SVG 雪碧图作为构建期素材存在 portal_assets/，本脚本读取后**内联**进
单文件 HTML。故产物 portal.html 双击 file:// 即开，不需要 markdown-it / mermaid / 字体 CDN 等外链资产。
（构建期读同仓素材文件 → 同输入同字节，仍满足确定性；素材当真正的 .css/.js 维护，免 Python 字符串转义。）

图标：emoji → SVG/sdot 转换只施加于「非可复制的呈现 chrome」（导航/门图标/块标题/读链前导图标/note 状态点）；
可复制的 <pre class="prompt|cmd"> 与完成标志（done）一律保留 emoji 字面量，避免污染剪贴板内容。

输出确定性：不含时间戳；按 portal.json 源顺序渲染 → 同 JSON + 同素材 → 同字节，供 lint_team_portal diff。

用法：
    python agent/scripts/gen_team_portal.py
    （纯 stdlib，无需 venv）
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "docs" / "onboarding" / "portal.json"
OUT = REPO / "docs" / "site" / "portal.html"
ASSETS = Path(__file__).resolve().parent / "portal_assets"

# read/link 的 path 条目 → 指向 Gitea 仓渲染页（跨机/托管均可点开，且总是该分支最新内容）。
# 形如 {GITEA_BASE}/src/branch/{GITEA_BRANCH}/<repo-relative-path>。改仓库地址/分支只改这两行。
GITEA_BASE = "http://10.143.2.109:3010/jintao/aida"
GITEA_BRANCH = "feat/merge-delivery-frontend"

# emoji → SVG symbol id（仅用于非可复制 chrome）。含 VS16（FE0F）变体写法。
_EMOJI_ICON = {
    "📖": "i-read",
    "🔍": "i-search",
    "⚠️": "i-warn", "⚠": "i-warn",
    "📚": "i-library",
    "🆕": "i-newcomer",
    "🏗️": "i-architect", "🏗": "i-architect",
    "🤖": "i-developer",
}
# note 文本里的状态圆点：🟡/🔴/🟢 → 拉丝钛风的 sdot
_SDOT = {
    "🟡": '<span class="sdot amber"></span>',
    "🔴": '<span class="sdot red"></span>',
    "🟢": '<span class="sdot green"></span>',
}


def load_portal() -> dict:
    text = SRC.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    return json.loads(text)


def _asset(name: str) -> str:
    """读构建期素材并归一行尾为 LF（无论检出 autocrlf 与否，内联文本恒为 LF）。"""
    return (ASSETS / name).read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _icon(symbol_id: str, extra: str = "") -> str:
    cls = ' style="' + extra + '"' if extra else ""
    return f'<svg class="i"{cls}><use href="#{symbol_id}"></use></svg>'


def _split_lead_emoji(label: str) -> tuple[str | None, str]:
    """剥离标签前导 emoji → (symbol_id|None, 剩余文本)。匹配 VS16 变体在前。"""
    for emo in sorted(_EMOJI_ICON, key=len, reverse=True):
        if label.startswith(emo):
            return _EMOJI_ICON[emo], label[len(emo):].lstrip()
    return None, label


def _icon_for_emoji(emoji: str) -> str | None:
    sid = _EMOJI_ICON.get(emoji)
    if sid:
        return sid
    # 容错：去掉 VS16 再查
    return _EMOJI_ICON.get(emoji.rstrip("️"))


def _href_of(entry: dict) -> str:
    """read / link 条目 → href。'href' 字面照用（docs/site 同级，如 index.html）；
    'path' 视为仓库相对路径 → 指向 Gitea 渲染页（跨机可点开、内容随分支最新）。
    path 可带 '#锚点'（深链到小节，如 docs/x.md#sec）；直接拼到 URL 末尾即合法 fragment。"""
    if entry.get("href"):
        return _esc(entry["href"])
    return _esc(f"{GITEA_BASE}/src/branch/{GITEA_BRANCH}/{entry['path']}")


def _link_chip(entry: dict) -> str:
    href = _href_of(entry)
    raw_label = entry.get("label", entry.get("path", entry.get("href", "link")))
    sid, rest = _split_lead_emoji(str(raw_label))
    label_html = (_icon(sid) + " " if sid else "") + _esc(rest)
    # path 条目附 @path 小码，方便直接复制成 coding agent 的 @ 引用。
    # path 可带 '#锚点'（href 深链到小节）；@ 小码去掉锚点——coding agent 的 @ 引用是文件级。
    at = ""
    if entry.get("path"):
        file_only = entry["path"].split("#", 1)[0]
        at = f'<code>@{_esc(file_only)}</code>'
    # 图标+标签包进 .t：flex 下「图标 标签 …… @小码」一行排开，标签左对齐、小码靠右
    return (f'<a class="readlink" href="{href}" target="_blank" rel="noopener">'
            f'<span class="t">{label_html}</span>{at}</a>')


def _note_html(text: str) -> str:
    """note 正文：先转义，再把状态 emoji 注成 sdot 点。前导 warn 图标在外层补。"""
    out = _esc(text)
    for emo, span in _SDOT.items():
        out = out.replace(emo, span)
    return out


def build_step(step: dict, num: int, first: bool, door_id: str) -> str:
    parts: list[str] = []
    open_cls = " open" if first else ""
    # data-step 作 localStorage 勾选键（door_id-序号），全门唯一
    parts.append(f'<div class="step{open_cls} reveal" data-step="{door_id}-{num}">')

    # 头（点击/Enter/Space 折叠）：role=button + tabindex 让键盘可达
    parts.append('<div class="step-head" role="button" tabindex="0" '
                 'onclick="toggleStep(this)" onkeydown="stepKey(event,this)">')
    parts.append(f'<span class="step-index">{num}</span>')
    parts.append('<div class="step-titles">')
    parts.append(f'<div class="step-title">{_esc(step["title"])}</div>')
    if step.get("goal"):
        parts.append(f'<div class="step-goal">{_esc(step["goal"])}</div>')
    parts.append("</div>")
    parts.append(f'<span class="step-toggle">{_icon("i-chevron")}</span>')
    parts.append("</div>")  # /step-head

    # 体（平滑高度展开：step-wrap > step-body > step-inner）
    parts.append('<div class="step-wrap"><div class="step-body"><div class="step-inner">')

    reads = step.get("read") or []
    if reads:
        parts.append(f'<div class="block"><div class="block-label">{_icon("i-read")} 读什么</div>')
        parts.append('<div class="readlinks">' + "".join(_link_chip(r) for r in reads) + "</div>")
        parts.append("</div>")

    prompt_lines = step.get("prompt") or []
    if prompt_lines:
        prompt_text = "\n".join(prompt_lines)
        parts.append('<div class="block">')
        parts.append(
            f'<div class="block-label">{_icon("i-prompt")} 给 AI 的提示词'
            '<button class="copy" type="button" onclick="copyBlock(this)">复制</button></div>'
        )
        parts.append(f'<pre class="prompt">{_esc(prompt_text)}</pre>')
        parts.append("</div>")

    cmds = step.get("commands") or []
    if cmds:
        parts.append('<div class="block">')
        parts.append(
            f'<div class="block-label">{_icon("i-cmd")} 命令'
            '<button class="copy" type="button" onclick="copyBlock(this)">复制</button></div>'
        )
        parts.append(f'<pre class="cmd">{_esc(chr(10).join(cmds))}</pre>')
        parts.append("</div>")

    if step.get("done"):
        # 可勾选完成标志：勾选态存 localStorage、驱动门内进度环（toggleDone）
        # done 不可复制但保留 emoji 字面量（✅⚠️❌ 等语义一致、不混 SVG）
        parts.append(
            '<label class="done"><input type="checkbox" onchange="toggleDone(this)">'
            f'<span class="done-txt">完成标志：{_esc(step["done"])}</span></label>'
        )

    if step.get("note"):
        parts.append(f'<div class="note">{_icon("i-warn")} {_note_html(step["note"])}</div>')

    if step.get("next"):
        parts.append(f'<div class="next">{_icon("i-arrow")} {_esc(step["next"])}</div>')

    parts.append("</div></div></div>")  # /step-inner /step-body /step-wrap
    parts.append("</div>")  # /step
    return "".join(parts)


def build_door(door: dict) -> str:
    door_id = _esc(door["id"])
    steps = door.get("steps", [])
    n = len(steps)
    idx = door.get("_index", 0) + 1
    sid = _icon_for_emoji(door.get("icon", "")) or "i-developer"
    title = str(door.get("title", ""))
    role = title[2:] if title.startswith("我是") else title  # 「我是新人」→「新人」

    parts: list[str] = []
    parts.append(f'<section class="door" id="{door_id}" data-door>')
    parts.append('<div class="shell">')

    # 门头 band
    parts.append('<div class="door-hero" data-stagger>')
    parts.append(f'<a class="door-back" href="#home">{_icon("i-arrow", "transform:rotate(180deg)")} 返回选择角色</a>')
    parts.append(f'<div class="door-kicker reveal"><span class="idx">{idx:02d}</span>'
                 f'<span class="ic">{_icon(sid)}</span></div>')
    parts.append(f'<h2 class="door-title reveal">{_esc(title)}</h2>')
    parts.append(f'<p class="door-sub reveal">{_esc(door["subtitle"])}</p>')
    if door.get("intro"):
        parts.append(f'<blockquote class="door-quote reveal">{_esc(door["intro"])}</blockquote>')
    parts.append("</div>")  # /door-hero

    # 两栏：左侧 sticky 时间轴导航 + 右侧步骤器
    parts.append('<div class="door-body">')
    parts.append('<aside class="door-aside">')
    parts.append('<div class="door-rail">')
    parts.append('<div class="rail-ring"><svg width="46" height="46" viewBox="0 0 46 46">'
                 '<circle class="track" cx="23" cy="23" r="20"></circle>'
                 '<circle class="prog" cx="23" cy="23" r="20"></circle></svg>'
                 '<span class="pct-mini">0</span></div>')
    parts.append(f'<div class="rail-label"><span class="rail-count">0 <em>/ {n}</em></span>'
                 '<span class="rail-hint">完成进度</span></div>')
    parts.append('<span class="rail-bar"><span class="rail-fill"></span></span>')
    parts.append('<div class="rail-tools">'
                 '<button class="tool" type="button" onclick="expandAll(this)">展开全部</button>'
                 '<button class="tool" type="button" onclick="collapseAll(this)">折叠全部</button>'
                 '</div>')
    parts.append("</div>")  # /door-rail
    parts.append('<ol class="tl" data-tl></ol>')
    parts.append('<div class="kbd-hint">键盘 <kbd>J</kbd><kbd>K</kbd> 切换步骤 · '
                 '<kbd>X</kbd> 标记完成 · <kbd>Enter</kbd> 展开</div>')
    parts.append("</aside>")  # /door-aside

    parts.append('<div class="stepper" data-stagger>')
    for i, step in enumerate(steps):
        parts.append(build_step(step, i + 1, first=(i == 0), door_id=door["id"]))
    parts.append("</div>")  # /stepper
    parts.append("</div>")  # /door-body

    parts.append("</div>")  # /shell
    parts.append(f'<div class="door-clear">{_icon("i-flag")}这条{_esc(role)}路线已全部跑通 — 关键动作已完成。</div>')
    parts.append('<div class="door-foot"></div>')
    parts.append("</section>")
    return "".join(parts)


def build_glossary(data: dict) -> str:
    """首页可折叠术语表：每个一句白话。降低冷启动新人的理解门槛。"""
    terms = data.get("glossary") or []
    if not terms:
        return ""
    rows = "".join(
        f'<dt>{_esc(t["term"])}</dt><dd>{_esc(t["plain"])}</dd>' for t in terms
    )
    return (
        '<section class="section" style="padding-top:0"><div class="shell">'
        '<div class="sec-head" data-stagger>'
        '<span class="sec-eyebrow reveal">GLOSSARY</span>'
        '<h2 class="sec-title reveal" style="font-size:clamp(28px,3.6vw,46px)">术语表</h2>'
        '</div>'
        '<details class="glossary reveal">'
        f'<summary>{_icon("i-read")} 术语表 · 看不懂上面的词？'
        f'<span class="gnum">点开（{len(terms)} 个）</span><span class="gx">+</span></summary>'
        f"<dl>{rows}</dl>"
        "</details>"
        "</div></section>"
    )


def build_hero(data: dict) -> str:
    proj = data["project"]
    doors = data["doors"]
    parts: list[str] = []
    parts.append('<section id="home" data-door>')

    # 全屏 Hero：蓝图栅格 / 弧线 / 辉光三层背景 + 标题逐行揭示
    parts.append('<header class="hero">')
    parts.append('<div class="hero-bg" aria-hidden="true">'
                 '<div class="hero-grid"></div><div class="hero-arc"></div><div class="hero-glow"></div>'
                 '</div>')
    parts.append('<div class="shell"><div class="hero-inner" data-stagger>')
    parts.append(f'<p class="hero-eyebrow reveal"><span class="pip"></span>{_esc(proj["name"])}</p>')
    elev = str(proj.get("elevator", ""))
    parts.append('<h1 class="hero-title">')
    if "，" in elev:
        lead, main = elev.split("，", 1)
        lead += "，"
        parts.append(f'<span class="ln hero-line-lead"><span>{_esc(lead)}</span></span>')
        parts.append(f'<span class="ln hero-line-main"><span>{_esc(main)}</span></span>')
    else:
        parts.append(f'<span class="ln hero-line-main"><span>{_esc(elev)}</span></span>')
    parts.append("</h1>")
    if proj.get("tagline"):
        parts.append(f'<p class="hero-sub reveal">{_esc(proj["tagline"])}</p>')
    parts.append("</div></div>")  # /hero-inner /shell
    parts.append('<div class="hero-cue" aria-hidden="true"><span class="line"></span>SCROLL</div>')
    parts.append("</header>")

    # 角色入口
    parts.append('<section class="section"><div class="shell">')
    parts.append('<div class="sec-head" data-stagger>'
                 '<span class="sec-eyebrow reveal">ROLES</span>'
                 '<h2 class="sec-title reveal titanium">选择你的角色</h2>'
                 '<p class="sec-desc reveal">三条路径，对应三种身份。挑一个进去，按步骤一路跑通。</p>'
                 '</div>')
    parts.append('<div class="role-grid" data-stagger>')
    for i, d in enumerate(doors):
        sid = _icon_for_emoji(d.get("icon", "")) or "i-developer"
        n = len(d.get("steps", []))
        parts.append(
            f'<a class="role-card reveal" href="#{_esc(d["id"])}">'
            f'<div class="role-top"><span class="role-index">{i + 1:02d}</span>'
            f'<span class="role-icon">{_icon(sid)}</span></div>'
            f'<h3 class="role-name">{_esc(d["title"])}</h3>'
            f'<p class="role-desc">{_esc(d["subtitle"])}</p>'
            f'<div class="role-go"><span class="txt">{n} 步 · 进入</span>'
            f'<span class="arr">{_icon("i-arrow")}</span></div>'
            f"</a>"
        )
    parts.append("</div>")  # /role-grid
    parts.append("</div></section>")

    parts.append(build_glossary(data))
    parts.append("</section>")
    return "".join(parts)


def build_nav(data: dict) -> str:
    proj = data["project"]
    link_parts: list[str] = []
    for l in proj.get("links", []):
        sid, rest = _split_lead_emoji(str(l.get("label", "")))
        if l.get("href"):  # 站内链接（如图书馆 index.html）→ 主按钮 + 库图标
            icon = _icon(sid or "i-library")
            link_parts.append(
                f'<a class="nav-link primary" href="{_href_of(l)}">{icon} {_esc(rest)}</a>'
            )
        else:  # 仓库文档深链 → 朴素链接，新窗口打开
            label = (_icon(sid) + " " if sid else "") + _esc(rest)
            link_parts.append(
                f'<a class="nav-link" href="{_href_of(l)}" target="_blank" rel="noopener">{label}</a>'
            )
    links = "".join(link_parts)

    role_tabs = "".join(
        f'<a class="nav-role" href="#{_esc(d["id"])}" data-role="{_esc(d["id"])}">'
        f'{_icon(_icon_for_emoji(d.get("icon", "")) or "i-developer")} {_esc(d["title"])}</a>'
        for d in data["doors"]
    )
    return (
        '<nav class="nav">'
        f'<a class="nav-brand" href="#home"><span class="dot"></span>{_esc(proj["name"])}</a>'
        f'<div class="nav-roles">{role_tabs}</div>'
        f'<div class="nav-links">{links}</div>'
        "</nav>"
    )


def build_html(data: dict) -> str:
    # 给每道门标序号（角色卡 / 门头 kicker 复用）
    for i, d in enumerate(data["doors"]):
        d["_index"] = i

    nav = build_nav(data)
    hero = build_hero(data)
    doors = "".join(build_door(d) for d in data["doors"])
    proj = data["project"]
    css = _asset("aida.css")
    js = _asset("aida.js")
    svg_defs = _asset("icons.svg")
    parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN"><head><meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>{_esc(proj['name'])} · 团队协作门户</title>",
        f"<style>{css}</style></head><body>",
        "<!-- 派生制品 · 自动生成 gen_team_portal.py · 改 docs/onboarding/portal.json 或 portal_assets/ 后重生成 · lint_team_portal.py 守门 · 勿手改 -->",
        svg_defs,
        '<div class="scrollbar"></div>',
        '<div class="curtain"></div>',
        nav,
        hero,
        doors,
        # 深色页脚：明暗收底 + mono 签名角注（uniEx 编辑风手法，拉丝钛收边线见 .foot::before）
        f'<footer class="foot"><span class="brand"><span class="dot"></span>{_esc(proj["name"])}</span>'
        '<span class="sig">TEAM PORTAL · DERIVED FROM portal.json · GUARDED BY lint_team_portal</span></footer>',
        '<button class="totop" type="button" aria-label="回到顶部">↑</button>',
        f"<script>{js}</script>",
        "</body></html>",
        "",
    ]
    return "\n".join(parts)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    data = load_portal()
    out = build_html(data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    n_doors = len(data["doors"])
    n_steps = sum(len(d.get("steps", [])) for d in data["doors"])
    print(f"[gen-team-portal] 写入 {OUT.relative_to(REPO)} · {n_doors} 门 · {n_steps} 步 · {len(out)} 字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())
