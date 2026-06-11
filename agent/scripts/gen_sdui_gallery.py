#!/usr/bin/env python3
"""gen_sdui_gallery · 从 SDUI 契约生成自包含 HTML 组件目录（派生制品，勿手改）

真相源：agent/sdui/builder.py（Pydantic 判别联合，与 frontend/src/lib/sdui.ts 由
lint_sdui_contract 焊住三方一致）。本脚本用 Pydantic 内省读出每个节点的 type / props /
枚举 / 默认，并合成最小样例 JSON，输出单文件自包含 HTML 到 agent/docs/sdui-gallery.html。

为什么是「生成」而非「手写」：SDUI 是活的三方契约，手写一份 HTML 画廊 = 第 4 份会漂移
的副本（正是「单一真相 + lint 守门」要消灭的）。生成 + 新鲜度 lint（lint_sdui_gallery.py）
让这份 HTML 永远 ≡ 契约。

输出确定性：不含时间戳 / 不用 set 排序 —— 同契约 → 同字节，供 lint diff。

用法：
    agent/.venv/Scripts/python agent/scripts/gen_sdui_gallery.py
"""
from __future__ import annotations

import html
import json
import sys
import types
import typing
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "docs" / "site" / "sdui-gallery.html"

from pydantic import BaseModel  # noqa: E402
from agent.sdui import builder as B  # noqa: E402

_NoneType = type(None)

# 节点分类（对齐 builder.py 注释分区）；未登记的归 Other（生成不报错，仅归类兜底）
CATEGORY: dict[str, str] = {
    "Stack": "布局 Layout", "Card": "布局 Layout", "Row": "布局 Layout",
    "Divider": "布局 Layout", "Skeleton": "布局 Layout",
    "Stepper": "步骤 Stepper",
    "Text": "文本 Text", "Markdown": "文本 Text",
    "Badge": "数据展示 Data", "Statistic": "数据展示 Data", "StatisticRow": "数据展示 Data",
    "KeyValueList": "数据展示 Data", "Table": "数据展示 Data", "GoldenMetrics": "数据展示 Data",
    "DonutChart": "图表 Chart", "BarChart": "图表 Chart",
    "Button": "动作 Action", "Link": "动作 Action",
    "ArtifactGrid": "产物 Artifact",
    "Alert": "展示 v1.1", "Timeline": "展示 v1.1", "NumberCard": "展示 v1.1", "PlaneMatrix": "展示 v1.1",
    "FilePicker": "人在回路 HITL", "ChoiceCard": "人在回路 HITL", "HitlTextInput": "人在回路 HITL",
}
CATEGORY_ORDER = [
    "布局 Layout", "步骤 Stepper", "文本 Text", "数据展示 Data", "图表 Chart",
    "动作 Action", "产物 Artifact", "展示 v1.1", "人在回路 HITL", "Other",
]
# 布局容器：样例里注入一个子节点，示意 children 用法
_CONTAINERS = {"Stack", "Card", "Row"}


def _unwrap_annotated(ann):
    return typing.get_args(ann)[0] if hasattr(ann, "__metadata__") else ann


def node_classes() -> list[type[BaseModel]]:
    """从 SduiNode = Annotated[Union[...], Field(discriminator='type')] 取出节点类（联合顺序）。"""
    inner = _unwrap_annotated(B.SduiNode)
    return [c for c in typing.get_args(inner) if isinstance(c, type) and issubclass(c, BaseModel)]


def type_literal(cls: type[BaseModel]) -> str:
    info = cls.model_fields.get("type")
    if info is not None and isinstance(info.default, str):
        return info.default
    return cls.__name__


def _is_model(t) -> bool:
    return isinstance(t, type) and issubclass(t, BaseModel)


def render_annotation(ann) -> str:
    ann = _unwrap_annotated(ann)
    origin = typing.get_origin(ann)
    if origin is typing.Literal:
        return "enum: " + " | ".join(str(a) for a in typing.get_args(ann))
    if origin in (typing.Union, getattr(types, "UnionType", ())):
        args = [a for a in typing.get_args(ann) if a is not _NoneType]
        if len(args) > 4:  # 大联合 = SduiNode
            return "SduiNode"
        return " | ".join(render_annotation(a) for a in args)
    if origin in (list, typing.List):  # noqa: UP006
        return f"{render_annotation(typing.get_args(ann)[0])}[]"
    if origin in (dict, typing.Dict):  # noqa: UP006
        return "object"
    if _is_model(ann):
        return ann.__name__.replace("Sdui", "")
    return {str: "string", int: "int", float: "number", bool: "bool",
            _NoneType: "null", typing.Any: "any"}.get(ann, getattr(ann, "__name__", str(ann)))


def enum_of(ann):
    ann = _unwrap_annotated(ann)
    if typing.get_origin(ann) is typing.Literal:
        return list(typing.get_args(ann))
    if typing.get_origin(ann) in (typing.Union, getattr(types, "UnionType", ())):
        for a in typing.get_args(ann):
            if typing.get_origin(_unwrap_annotated(a)) is typing.Literal:
                return list(typing.get_args(_unwrap_annotated(a)))
    return None


def sample_value(ann):
    ann = _unwrap_annotated(ann)
    origin = typing.get_origin(ann)
    if origin is typing.Literal:
        return typing.get_args(ann)[0]
    if origin in (typing.Union, getattr(types, "UnionType", ())):
        args = [a for a in typing.get_args(ann) if a is not _NoneType]
        if len(args) > 4:
            return {"type": "Text", "content": "示例"}
        return sample_value(args[0])
    if origin in (list, typing.List):  # noqa: UP006
        return [sample_value(typing.get_args(ann)[0])]
    if origin in (dict, typing.Dict):  # noqa: UP006
        return {}
    if _is_model(ann):
        return sample_model(ann)
    return {str: "示例", int: 1, float: 1.0, bool: True}.get(ann, "...")


def sample_model(cls: type[BaseModel]) -> dict:
    out: dict = {}
    for name, info in cls.model_fields.items():
        if name == "type":
            out["type"] = type_literal(cls)
        elif info.is_required():
            out[name] = sample_value(info.annotation)
    return out


def sample_for_node(cls: type[BaseModel]) -> dict:
    s = sample_model(cls)
    if type_literal(cls) in _CONTAINERS:  # 容器示意一个子节点
        s["children"] = [{"type": "Text", "content": "示例内容"}]
    return s


def collect_helpers(nodes: list[type[BaseModel]]) -> list[type[BaseModel]]:
    """递归收集被节点引用、但本身不是顶层节点的嵌套子模型（去重保序）。"""
    node_set = set(nodes)
    seen: dict[type, None] = {}

    def walk(ann):
        ann = _unwrap_annotated(ann)
        for a in typing.get_args(ann):
            walk(a)
        if _is_model(ann) and ann not in node_set and ann not in seen:
            seen[ann] = None
            for info in ann.model_fields.values():
                walk(info.annotation)

    for n in nodes:
        for info in n.model_fields.values():
            walk(info.annotation)
    return list(seen)


def _props_rows(cls: type[BaseModel]) -> str:
    rows = []
    for name, info in cls.model_fields.items():
        req = "✓" if info.is_required() else "—"
        enum = enum_of(info.annotation)
        if name == "type":
            extra = f"<code>{html.escape(type_literal(cls))}</code>"
        elif enum:
            extra = " | ".join(f"<code>{html.escape(str(e))}</code>" for e in enum)
        elif not info.is_required() and info.default is not None:
            extra = f"默认 <code>{html.escape(str(info.default))}</code>"
        else:
            extra = ""
        rows.append(
            f"<tr><td><b>{html.escape(name)}</b></td>"
            f"<td><code>{html.escape(render_annotation(info.annotation))}</code></td>"
            f"<td class='req'>{req}</td><td>{extra}</td></tr>"
        )
    return "\n".join(rows)


def _json_block(obj) -> str:
    return html.escape(json.dumps(obj, ensure_ascii=False, indent=2))


_CSS = """
:root{--bg:#0b0d13;--surface:#151822;--surface2:#1e2230;--border:#2e3344;
--text:#e1e4ed;--dim:#9aa0b8;--cyan:#22d3ee;--blue:#4f8ff7;--green:#34d399;--orange:#fb923c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);line-height:1.6;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif}
code,pre{font-family:'SF Mono',Consolas,'Cascadia Code',monospace}
header{padding:28px 6%;border-bottom:1px solid var(--border);background:var(--surface)}
header h1{margin:0 0 6px;font-size:26px;background:linear-gradient(135deg,#fff,var(--cyan),var(--blue));
-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.banner{color:var(--orange);font-size:13px;margin-top:8px}
.meta{color:var(--dim);font-size:13px}
.wrap{display:grid;grid-template-columns:230px 1fr;gap:0;align-items:start}
nav{position:sticky;top:0;align-self:start;max-height:100vh;overflow:auto;
padding:20px 16px;border-right:1px solid var(--border);font-size:13px}
nav h4{color:var(--cyan);margin:14px 0 6px;font-size:12px;letter-spacing:.5px;text-transform:uppercase}
nav a{display:block;color:var(--dim);text-decoration:none;padding:2px 0}
nav a:hover{color:var(--text)}
main{padding:24px 6% 80px;min-width:0}
h2.cat{margin:34px 0 10px;color:#fff;font-size:19px;border-left:4px solid var(--cyan);padding-left:10px}
section{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:18px 20px;margin:14px 0}
section:target{border-color:var(--cyan);box-shadow:0 0 0 2px rgba(34,211,238,.2)}
section h3{margin:0 0 4px;font-size:17px}
section h3 code{color:var(--green);font-size:14px}
.tag{float:right;font-size:11px;color:var(--dim);border:1px solid var(--border);
border-radius:999px;padding:2px 10px}
.desc{color:var(--dim);font-size:14px;margin:4px 0 12px}
table{width:100%;border-collapse:collapse;font-size:13px;margin:6px 0 12px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--border);vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:12px}
td .req,td code{font-size:12px}
td code{background:var(--surface2);padding:1px 5px;border-radius:4px;color:var(--cyan)}
.req{text-align:center;color:var(--green)}
pre{background:#0e1017;border:1px solid var(--border);border-radius:8px;
padding:12px 14px;overflow:auto;font-size:12.5px;margin:0}
.lbl{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;margin:0 0 4px}
footer{padding:24px 6%;border-top:1px solid var(--border);color:var(--dim);font-size:13px}
footer code{color:var(--cyan)}
""".strip()


def build_html() -> str:
    nodes = node_classes()
    helpers = collect_helpers(nodes)
    ver = getattr(B.SduiDocument.model_fields["schemaVersion"], "default", 1)

    # 分组（保序）
    by_cat: dict[str, list[type[BaseModel]]] = {}
    for cls in nodes:
        by_cat.setdefault(CATEGORY.get(type_literal(cls), "Other"), []).append(cls)

    # 侧栏
    nav = []
    for cat in CATEGORY_ORDER:
        if cat not in by_cat:
            continue
        nav.append(f"<h4>{html.escape(cat)}</h4>")
        for cls in by_cat[cat]:
            t = type_literal(cls)
            nav.append(f'<a href="#{html.escape(t)}">{html.escape(t)}</a>')
    if helpers:
        nav.append('<h4>嵌套子类型</h4>')
        for h in helpers:
            nav.append(f'<a href="#{html.escape(h.__name__)}">{html.escape(h.__name__.replace("Sdui",""))}</a>')

    # 主体
    body = []
    for cat in CATEGORY_ORDER:
        if cat not in by_cat:
            continue
        body.append(f'<h2 class="cat">{html.escape(cat)}</h2>')
        for cls in by_cat[cat]:
            t = type_literal(cls)
            desc = (cls.__doc__ or "").strip().replace("\n", " ")
            body.append(
                f'<section id="{html.escape(t)}">'
                f'<h3><code>{html.escape(t)}</code> {html.escape(cls.__name__)}'
                f'<span class="tag">{html.escape(cat)}</span></h3>'
                + (f'<p class="desc">{html.escape(desc)}</p>' if desc else "")
                + '<table><tr><th>字段</th><th>类型</th><th>必填</th><th>枚举 / 默认</th></tr>'
                + _props_rows(cls) + "</table>"
                + '<p class="lbl">样例 JSON</p>'
                + f"<pre>{_json_block(sample_for_node(cls))}</pre>"
                + "</section>"
            )

    if helpers:
        body.append('<h2 class="cat">嵌套子类型（被上面节点引用）</h2>')
        for h in helpers:
            desc = (h.__doc__ or "").strip().replace("\n", " ")
            body.append(
                f'<section id="{html.escape(h.__name__)}">'
                f'<h3><code>{html.escape(h.__name__.replace("Sdui", ""))}</code></h3>'
                + (f'<p class="desc">{html.escape(desc)}</p>' if desc else "")
                + '<table><tr><th>字段</th><th>类型</th><th>必填</th><th>枚举 / 默认</th></tr>'
                + _props_rows(h) + "</table></section>"
            )

    parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN"><head><meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "<title>SDUI 组件目录 · AIDA</title>",
        f"<style>{_CSS}</style></head><body>",
        "<header><h1>SDUI 组件目录</h1>",
        f'<div class="meta">schemaVersion {ver} · {len(nodes)} 个节点类型 · '
        f"{len(helpers)} 个嵌套子类型</div>",
        '<div class="banner">⚠ 自动生成自 <code>agent/sdui/builder.py</code> —— '
        "请勿手改；改契约后跑 <code>gen_sdui_gallery.py</code> 重新生成（"
        "<code>lint_sdui_gallery.py</code> 守门）</div></header>",
        '<div class="wrap"><nav>' + "\n".join(nav) + "</nav>",
        "<main>" + "\n".join(body) + "</main></div>",
        "<footer>真相源：<code>agent/sdui/builder.py</code> ↔ "
        "<code>frontend/src/lib/sdui.ts</code> ↔ <code>SduiNodeView.tsx</code>"
        "（三方由 <code>lint_sdui_contract</code> 焊住）· "
        "本目录由 <code>gen_sdui_gallery.py</code> 派生 · "
        "新鲜度由 <code>lint_sdui_gallery.py</code> 守门 · "
        "细则见 <code>docs/30_skill开发/31_手写规范/SDUI.md</code></footer>",
        "</body></html>",
        "",
    ]
    return "\n".join(parts)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    out = build_html()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print(f"[gen-sdui-gallery] 写入 {OUT.relative_to(REPO)} · "
          f"{len(node_classes())} 节点 · {len(out)} 字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())
