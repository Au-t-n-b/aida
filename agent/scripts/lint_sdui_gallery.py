"""
sdui-gallery · SDUI 组件目录 HTML 新鲜度守门（规范 0：没有守门的规范会退化成 PPT）

agent/docs/sdui-gallery.html 是派生制品——gen_sdui_gallery.py 从 agent/sdui/builder.py
内省生成。契约一改、画廊不重生成 → HTML 与代码漂移，正是「单一真相」要消灭的第 4 份副本
（前端 sdui.ts、NodeView 之外又一份）。本 lint 在内存里重跑生成器、与磁盘上的 HTML 比对：
不一致 → 过期 → fail（附一键重生成命令）。

与 lint_sdui_contract 互补：那个守「协议三方对齐」（builder ↔ sdui.ts ↔ NodeView），
这个守「目录 ≡ 协议」（sdui-gallery.html ≡ builder）。

退出码：过期/缺失 → 1；新鲜 → 0；缺 venv 无法 import 契约 → 0 + SKIP（不阻断构建）。

用法：
    agent/.venv/Scripts/python agent/scripts/lint_sdui_gallery.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Windows 控制台默认 GBK，✓/❌/中文会 UnicodeEncodeError → 强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _norm(s: str) -> str:
    """归一行尾。autocrlf=true 的 Windows 检出会把 LF 变 CRLF，
    diff 只看内容不看行尾，避免行尾差异造成假阳性。"""
    return s.replace("\r\n", "\n").replace("\r", "\n")


def main() -> int:
    # 顶层即 import agent.sdui.builder → 缺 venv 抛 ImportError（与 lint_sdui_contract 同款 SKIP）
    try:
        import gen_sdui_gallery as G
    except ImportError as e:  # ModuleNotFoundError 是其子类
        sys.stdout.write(
            f"[sdui-gallery] ⚠ SKIP · 无法 import 生成器/契约（{e}）。\n"
            f"  请在 agent venv 下运行："
            f"agent\\.venv\\Scripts\\python agent\\scripts\\lint_sdui_gallery.py\n"
        )
        return 0

    out_path: Path = G.OUT
    rel = out_path.relative_to(G.REPO)

    if not out_path.exists():
        sys.stdout.write(
            f"[sdui-gallery] ❌ 缺失 · {rel} 不存在。\n"
            f"  生成：agent\\.venv\\Scripts\\python agent\\scripts\\gen_sdui_gallery.py\n"
        )
        return 1

    expected = _norm(G.build_html())
    actual = _norm(out_path.read_text(encoding="utf-8", errors="replace"))

    if expected == actual:
        n = len(G.node_classes())
        sys.stdout.write(
            f"[sdui-gallery] OK · 组件目录新鲜 ≡ 契约（{n} 节点）：{rel}\n"
        )
        return 0

    # 过期：给出首处分歧诊断（截断）+ 一键重生成
    import difflib

    diff = list(
        difflib.unified_diff(
            actual.splitlines(),
            expected.splitlines(),
            fromfile="磁盘 (旧)",
            tofile="重生成 (新)",
            lineterm="",
            n=1,
        )
    )
    sys.stdout.write(
        f"[sdui-gallery] ❌ 过期 · {rel} 与契约不一致"
        f"（builder.py 改了但没重生成画廊）。\n\n"
    )
    for line in diff[:40]:
        sys.stdout.write(f"  {line}\n")
    if len(diff) > 40:
        sys.stdout.write(f"  …（共 {len(diff)} 行差异，已截断）\n")
    sys.stdout.write(
        "\n修复：重新生成并提交——\n"
        "  agent\\.venv\\Scripts\\python agent\\scripts\\gen_sdui_gallery.py\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
