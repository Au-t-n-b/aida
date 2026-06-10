"""
docs-site · 开发者文档站 HTML 新鲜度守门（规范 0：没有守门的规范会退化成 PPT）

docs/site/index.html 是派生制品——gen_docs_site.py 把 docs/ + agent/docs/ 的 Markdown
内嵌生成。改了 MD 但没重生成 → 站点与文档漂移（又一份会过期的副本）。本 lint 在内存里重跑
生成器、与磁盘 HTML 比对：不一致 → 过期 → fail（附一键重生成命令）。归一行尾避免 autocrlf
假阳性；输出近乎单行巨串，故只定位首处分歧的字符偏移 + 小窗口，不打印整行（防刷屏）。

退出码：过期/缺失 → 1；新鲜 → 0。生成器纯 stdlib，无需 venv。

用法：
    python agent/scripts/lint_docs_site.py
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _norm(s: str) -> str:
    """归一行尾。autocrlf=true 的 Windows 检出会把 LF 变 CRLF，diff 只看内容不看行尾。"""
    return s.replace("\r\n", "\n").replace("\r", "\n")


def _first_divergence(a: str, b: str) -> str:
    i = 0
    n = min(len(a), len(b))
    while i < n and a[i] == b[i]:
        i += 1
    return (
        f"  首处分歧 @ 第 {i} 字符（磁盘 {len(a)} 字节 / 重生成 {len(b)} 字节）：\n"
        f"  磁盘  …{a[max(0, i - 40):i + 40]!r}…\n"
        f"  重生成…{b[max(0, i - 40):i + 40]!r}…\n"
    )


def main() -> int:
    import gen_docs_site as G

    out_path: Path = G.OUT
    rel = out_path.relative_to(G.REPO)

    if not out_path.exists():
        sys.stdout.write(
            f"[docs-site] ❌ 缺失 · {rel} 不存在。\n"
            f"  生成：python agent\\scripts\\gen_docs_site.py\n"
        )
        return 1

    docs = G.build_docs()
    expected = _norm(G.build_html(docs))
    actual = _norm(out_path.read_text(encoding="utf-8", errors="replace"))

    if expected == actual:
        sys.stdout.write(
            f"[docs-site] OK · 文档站新鲜 ≡ MD 源（{len(docs)} 篇）：{rel}\n"
        )
        return 0

    sys.stdout.write(
        f"[docs-site] ❌ 过期 · {rel} 与 MD 源不一致（改了 docs/ 或 agent/docs/ 但没重生成）。\n\n"
    )
    sys.stdout.write(_first_divergence(actual, expected))
    sys.stdout.write(
        "\n修复：重新生成并提交——\n"
        "  python agent\\scripts\\gen_docs_site.py\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
