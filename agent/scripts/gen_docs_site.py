#!/usr/bin/env python3
"""gen_docs_site · 把 docs/ + agent/docs/ 的 Markdown 派生成单文件自包含文档站（派生制品，勿手改）

真相源：仓库里的 .md 本身。本脚本把每篇 MD 的**原始文本**内嵌进一个 HTML，浏览器端用
vendored markdown-it 渲染、mermaid 画图（都在 docs/site/assets/，零运行时 CDN）。改 MD →
跑本脚本重生成 → lint_docs_site.py 守新鲜度。HTML 由 MD 派生，零内容重复（不违反单一真相）。

为什么内嵌而非 fetch：双击 file:// 打开时 fetch/XHR 被浏览器拦截，<script src> 与内嵌数据
不受限。故 MD 文本内嵌为 JS 数据、markdown-it/mermaid 走相对 <script src>，双击即开。

mermaid 优雅降级：assets/mermaid.min.js 在 → 渲染真图；不在（仓库默认 gitignore 该 3.3MB）→
显示带样式的源码块。站点两种情况都能用。

输出确定性：不含时间戳；文档按固定分组/路径排序内嵌 → 同 MD → 同字节，供 lint diff。

用法：
    agent/.venv/Scripts/python agent/scripts/gen_docs_site.py
    （纯 stdlib，无需 venv 也可：python agent/scripts/gen_docs_site.py）
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "site" / "index.html"
# 视觉令牌单一真相源：与「团队协作门户」共用同一份构建期素材（亮面拉丝钛 / 蓝图栅格）。
# 本脚本只取其 :root{} 令牌块内联，文档站组件样式（侧栏/正文）在 _CSS 里基于这些 var() 复刻——
# 两页同源同风，改配色只改 aida.css。素材按行尾归一后字节确定（供 lint_docs_site diff）。
ASSETS = Path(__file__).resolve().parent / "portal_assets"

# 扫描根（顺序即分组顺序的兜底）；docs/site 自身排除，避免自包含
ROOTS = [REPO / "docs"]
EXCLUDE_DIRS = {REPO / "docs" / "site", REPO / "docs" / "archive", REPO / "docs" / "_generated"}

# 路径前缀 → 分组标签（命中第一个即归组）；未命中走「其他」
GROUPS: list[tuple[Path, str]] = [
    (REPO / "docs" / "10_快速开始", "快速开始"),
    (REPO / "docs" / "20_架构与范式", "架构与范式"),
    (REPO / "docs" / "30_skill开发", "skill 开发"),
    (REPO / "docs" / "40_评测", "评测"),
    (REPO / "docs" / "50_数据与接口", "数据与接口"),
    (REPO / "docs" / "60_部署运维", "部署运维"),
    (REPO / "docs" / "70_业务设计", "业务设计"),
    (REPO / "docs" / "80_设计UX", "设计 UX"),
    (REPO / "docs" / "90_决策ADR", "决策 ADR"),
    (REPO / "docs", "开发者地图与规范"),  # docs 根，放最后兜 docs/ 直属
]
# 分组展示顺序（地图在最前）
GROUP_ORDER = [
    "开发者地图与规范", "快速开始", "架构与范式", "skill 开发", "评测",
    "数据与接口", "部署运维", "业务设计", "设计 UX", "决策 ADR", "其他",
]
# 落地默认页（总入口）
LANDING_REL = "docs/00_开发者地图.md"


def iter_md() -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for root in ROOTS:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.md")):
            rp = p.resolve()
            if rp in seen or any(ex in rp.parents for ex in EXCLUDE_DIRS):
                continue
            seen.add(rp)
            out.append(p)
    return out


def group_of(p: Path) -> str:
    rp = p.resolve()
    for prefix, label in GROUPS:
        if prefix == rp.parent or prefix in rp.parents:
            return label
    return "其他"


def title_of(text: str, p: Path) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return p.stem


def build_docs() -> list[dict]:
    """收集所有 MD → 有序 dict 列表。地图置顶，其余按分组顺序 + 路径。"""
    items: list[dict] = []
    for p in iter_md():
        rel = p.relative_to(REPO).as_posix()
        # 归一行尾：autocrlf=true 的 Windows 检出读到 CRLF，归 LF 保证内嵌字节跨平台确定（供 lint diff）
        text = p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        items.append({"path": rel, "title": title_of(text, p),
                      "group": group_of(p), "md": text})

    def sort_key(d: dict):
        g = GROUP_ORDER.index(d["group"]) if d["group"] in GROUP_ORDER else len(GROUP_ORDER)
        landing = 0 if d["path"] == LANDING_REL else 1
        return (g, landing, d["path"])

    items.sort(key=sort_key)
    for i, d in enumerate(items):
        d["idx"] = i
    return items


def _embed(docs: list[dict]) -> str:
    """内嵌为 JS 安全字面量：把 </ 转成 <\\/，防 MD 内出现 </script> 提前闭合脚本标签。
    （U+2028/2029 在 ES2019+ 字符串里已合法，现代浏览器无需再转义。）"""
    payload = [{"path": d["path"], "title": d["title"], "group": d["group"], "md": d["md"]}
               for d in docs]
    s = json.dumps(payload, ensure_ascii=False)
    return s.replace("</", "<\\/")


def _root_tokens() -> str:
    """从门户素材 aida.css 抽出 :root{} 设计令牌块（颜色/字体/阴影/圆角的单一真相源）。
    :root 内无嵌套花括号，故 :root{ 后第一个 } 即闭合。行尾归一保证字节确定。"""
    css = (ASSETS / "aida.css").read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    start = css.index(":root{")
    end = css.index("}", start) + 1
    return css[start:end]


# 文档站组件样式（侧栏阅读器布局），基于 aida.css 的 :root 令牌复刻门户语言：
# 亮面拉丝钛标题 + 蓝图栅格氛围 + 大留白 + 发丝线描边 + 柔性悬浮阴影。
_COMPONENTS = """
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--ink-3);line-height:1.65;font-family:var(--font-cn);
font-weight:400;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
/* 全局氛围：顶部冷光 + 极淡蓝图栅格（与门户同源） */
body::before{content:'';position:fixed;inset:0;z-index:-2;pointer-events:none;
background:
radial-gradient(1100px 680px at 50% -20%,rgba(58,84,196,.07),transparent 58%),
radial-gradient(820px 560px at 90% 6%,rgba(120,132,150,.08),transparent 55%),
linear-gradient(180deg,#eef1f5,#e6e9ee 60%,#e8ebef)}
body::after{content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.5;
background-image:
linear-gradient(rgba(20,26,34,.022) 1px,transparent 1px),
linear-gradient(90deg,rgba(20,26,34,.022) 1px,transparent 1px);
background-size:60px 60px;
-webkit-mask-image:radial-gradient(130% 100% at 50% 0%,#000,transparent 78%);
mask-image:radial-gradient(130% 100% at 50% 0%,#000,transparent 78%)}
code,pre,kbd{font-family:var(--font-mono)}
::selection{background:rgba(58,84,196,.18);color:var(--ink)}

/* 顶栏：磨砂玻璃 + 发丝线 + 拉丝钛标题 */
header{position:sticky;top:0;z-index:50;height:var(--nav-h);
padding:0 clamp(20px,5vw,40px);display:flex;align-items:center;gap:16px;flex-wrap:wrap;
background:rgba(244,246,249,.72);backdrop-filter:blur(18px) saturate(150%);
-webkit-backdrop-filter:blur(18px) saturate(150%);border-bottom:1px solid var(--hair)}
header h1{margin:0;font-size:18px;font-weight:700;letter-spacing:.01em;color:var(--ink);
display:flex;align-items:center;gap:11px}
header h1::before{content:'';width:9px;height:9px;border-radius:50%;flex:none;
background:linear-gradient(135deg,var(--accent),var(--accent-2));box-shadow:0 0 10px rgba(58,84,196,.5)}
header .meta{color:var(--ink-4);font-size:13px}
header .banner{color:var(--ink-4);font-size:10px;margin-left:auto;
font-family:var(--font-mono);letter-spacing:.14em;text-transform:uppercase}

.wrap{display:grid;grid-template-columns:288px 1fr;height:calc(100% - var(--nav-h))}

/* 侧栏导航 */
nav{overflow:auto;padding:18px 14px;border-right:1px solid var(--hair);
background:rgba(255,255,255,.55);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}
nav input{width:100%;padding:9px 12px;margin-bottom:12px;background:var(--paper);color:var(--ink);
border:1px solid var(--hair);border-radius:10px;font-size:13px;font-family:var(--font-cn);
box-shadow:var(--sh-1);transition:border-color .18s,box-shadow .18s}
nav input::placeholder{color:var(--ink-4)}
nav input:focus{outline:none;border-color:var(--accent-soft-2);box-shadow:0 0 0 3px var(--accent-soft)}
nav h4{color:var(--accent);margin:18px 8px 6px;font-size:11px;font-weight:600;letter-spacing:.18em;
text-transform:uppercase;font-family:var(--font-tech);display:flex;align-items:center;gap:10px}
nav h4::before{content:'';width:18px;height:2px;border-radius:2px;flex:none;
background:linear-gradient(90deg,var(--accent),transparent)}
nav a{display:block;color:var(--ink-3);text-decoration:none;padding:6px 12px;border-radius:9px;
border-left:2px solid transparent;
font-size:13px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
transition:color .16s,background .16s,border-color .16s}
nav a:hover{background:rgba(20,26,34,.04);color:var(--ink)}
nav a.active{background:var(--accent-soft);color:var(--accent-ink);font-weight:600;
border-left-color:var(--accent);border-radius:0 9px 9px 0}
nav a.hidden{display:none}

main{overflow:auto;padding:36px clamp(28px,5vw,64px) 90px}
.md-body{max-width:880px;font-size:14.5px}
.crumb{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
color:var(--ink-4);font-size:11px;margin-bottom:22px;font-family:var(--font-mono);letter-spacing:.04em}
.crumb code{background:var(--paper);border:1px solid var(--hair);padding:3px 10px;border-radius:7px;color:var(--ink-3)}
.crumb .chip{padding:3px 11px;border-radius:999px;background:var(--accent-soft);
color:var(--accent-ink);font-weight:600;font-family:var(--font-cn);font-size:11px;letter-spacing:.02em}

/* Markdown 正文 */
.md-body h1{font-size:30px;font-weight:800;letter-spacing:-.02em;color:var(--ink);
margin:.1em 0 .7em;padding-bottom:.4em;border-bottom:1px solid var(--hair)}
.md-body h2{font-size:22px;font-weight:700;color:var(--ink);margin:1.5em 0 .6em;
padding-left:12px;border-left:4px solid var(--accent);line-height:1.3}
.md-body h3{font-size:17.5px;font-weight:700;margin:1.3em 0 .4em;color:var(--ink)}
.md-body h4{font-size:15px;font-weight:600;margin:1em 0 .3em;color:var(--ink-2)}
.md-body p,.md-body li{color:var(--ink-2);line-height:1.85}
.md-body li{margin:.22em 0}
.md-body a{color:var(--accent-ink);text-decoration:none;border-bottom:1px solid var(--accent-soft-2)}
.md-body a:hover{border-bottom-color:var(--accent)}
.md-body code{background:var(--bg-3);border:1px solid var(--hair-2);padding:1.5px 6px;border-radius:6px;
font-size:.86em;color:var(--accent-ink)}
.md-body pre{background:#1d2128;border:1px solid #2a2f37;border-left:3px solid var(--accent-2);
border-radius:12px;padding:16px 18px;overflow:auto;font-size:13px;line-height:1.7;box-shadow:var(--sh-1)}
.md-body pre:not(.mermaid-src){position:relative;padding-top:40px}
.md-body pre:not(.mermaid-src)::before{content:'';position:absolute;top:15px;left:18px;
width:10px;height:10px;border-radius:50%;background:#3a4150;
box-shadow:18px 0 0 #3a4150,36px 0 0 #3a4150}
.md-body pre code{background:none;border:none;padding:0;color:#cdd2da}
.md-body blockquote{margin:1.2em 0;padding:14px 18px;border:1px solid var(--hair);
border-left:3px solid var(--accent);background:var(--paper);color:var(--ink-2);
border-radius:0 12px 12px 0;box-shadow:var(--sh-1)}
.md-body table{border-collapse:separate;border-spacing:0;width:100%;margin:1.2em 0;font-size:13.5px;
display:block;overflow:auto;border:1px solid var(--hair);border-radius:12px;box-shadow:var(--sh-1)}
.md-body th,.md-body td{border-bottom:1px solid var(--hair-2);border-right:1px solid var(--hair-2);
padding:9px 12px;text-align:left;vertical-align:top}
.md-body th{background:var(--bg-3);color:var(--ink-3);font-weight:600;
font-family:var(--font-tech);font-size:12px;letter-spacing:.06em;white-space:nowrap}
.md-body tr:last-child td{border-bottom:none}
.md-body th:last-child,.md-body td:last-child{border-right:none}
.md-body hr{border:0;border-top:1px solid var(--hair);margin:1.8em 0}
.md-body .mermaid{background:var(--paper);border:1px solid var(--hair);border-radius:14px;
padding:18px;margin:1.2em 0;text-align:center;box-shadow:var(--sh-1)}
.md-body pre.mermaid-src{background:var(--bg-3);border:1px dashed var(--warn);border-left:3px dashed var(--warn);
box-shadow:none}
.md-body pre.mermaid-src code{color:var(--ink-2)}
.md-body pre.mermaid-src::before{content:'mermaid 源（缺 assets/mermaid.min.js，未渲染为图）';
display:block;color:var(--warn);font-size:11px;margin-bottom:8px}

@media (max-width:820px){
.wrap{grid-template-columns:1fr;height:auto}
nav{border-right:none;border-bottom:1px solid var(--hair);max-height:42vh}
main{padding:24px 18px 64px}
}
"""

_CSS = (_root_tokens() + "\n" + _COMPONENTS).strip()


# 客户端渲染脚本（vanilla；markdown-it + 可选 mermaid；hash 路由）
_JS = r"""
(function(){
  var md = window.markdownit({html:true, linkify:true, breaks:false, typographer:false});
  var nav = document.getElementById('nav');
  var main = document.getElementById('main');
  var hasMermaid = !!(window.mermaid);
  if(hasMermaid){ try{ window.mermaid.initialize({startOnLoad:false, theme:'neutral', securityLevel:'loose'}); }catch(e){ hasMermaid=false; } }

  function renderMermaid(scope){
    var blocks = scope.querySelectorAll('pre code.language-mermaid');
    blocks.forEach(function(code){
      var src = code.textContent;
      var pre = code.parentElement;
      if(hasMermaid){
        var box = document.createElement('div');
        box.className = 'mermaid';
        box.textContent = src;
        pre.replaceWith(box);
      } else {
        pre.className = 'mermaid-src';
      }
    });
    if(hasMermaid){
      try{ window.mermaid.run({nodes: scope.querySelectorAll('.mermaid')}); }catch(e){}
    }
  }

  function show(idx){
    var d = DOCS[idx]; if(!d) return;
    main.innerHTML = '<div class="crumb"><code>'+d.path+'</code><span class="chip">'+d.group+'</span></div>'
      + '<div class="md-body">'+ md.render(d.md) +'</div>';
    renderMermaid(main);
    main.scrollTop = 0;
    document.querySelectorAll('nav a').forEach(function(a){
      a.classList.toggle('active', a.dataset.idx === String(idx));
    });
  }

  function route(){
    var h = location.hash.replace(/^#doc-/, '');
    var idx = parseInt(h, 10);
    show(isNaN(idx) ? 0 : idx);
  }
  window.addEventListener('hashchange', route);

  var filter = document.getElementById('filter');
  filter.addEventListener('input', function(){
    var q = filter.value.trim().toLowerCase();
    document.querySelectorAll('nav a').forEach(function(a){
      a.classList.toggle('hidden', q && a.textContent.toLowerCase().indexOf(q) < 0);
    });
  });

  route();
})();
"""


def build_html(docs: list[dict]) -> str:
    # 侧栏（按 GROUP_ORDER 分组）
    nav: list[str] = ['<input id="filter" placeholder="过滤文档…" autocomplete="off">']
    by_group: dict[str, list[dict]] = {}
    for d in docs:
        by_group.setdefault(d["group"], []).append(d)
    for g in GROUP_ORDER:
        if g not in by_group:
            continue
        nav.append(f"<h4>{html.escape(g)}</h4>")
        for d in by_group[g]:
            nav.append(
                f'<a data-idx="{d["idx"]}" href="#doc-{d["idx"]}" '
                f'title="{html.escape(d["path"])}">{html.escape(d["title"])}</a>'
            )

    # 始终引用 mermaid.min.js：缺省/gitignore 时浏览器 404 → 客户端 hasMermaid=false 优雅降级为
    # 源码块。不依赖资产是否在本地存在，保证生成输出确定（供 lint diff，本机与 CI 一致）。
    mermaid_tag = '<script src="assets/mermaid.min.js"></script>'

    parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN"><head><meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "<title>AIDA 开发者文档站</title>",
        f"<style>{_CSS}</style></head><body>",
        '<header><h1>AIDA 开发者文档站</h1>',
        f'<span class="meta">{len(docs)} 篇 · 派生自 docs/ + agent/docs/</span>',
        '<span class="banner">⚠ 自动生成（gen_docs_site.py）· 改 MD 后重生成 · lint_docs_site.py 守门</span>',
        "</header>",
        '<div class="wrap">',
        f'<nav id="nav">{"".join(nav)}</nav>',
        '<main id="main"></main>',
        "</div>",
        f'<script>const DOCS={_embed(docs)};</script>',
        '<script src="assets/markdown-it.min.js"></script>',
        mermaid_tag,
        f"<script>{_JS}</script>",
        "</body></html>",
        "",
    ]
    return "\n".join(parts)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    docs = build_docs()
    out = build_html(docs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print(f"[gen-docs-site] 写入 {OUT.relative_to(REPO)} · {len(docs)} 篇文档 · {len(out)} 字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())
