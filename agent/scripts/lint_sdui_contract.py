"""
sdui-contract · SDUI 协议前后端一致守门（规范 0 守门 + 规范 5 契约先行 / SDUI.md §4）

问题：SDUI 协议的节点类型必须在三处同步声明——
  ① 后端 agent/sdui/builder.py 的 SduiNode union（能产出哪些节点）
  ② 前端 frontend/src/lib/sdui.ts 的 SduiNode union（前端类型认哪些）
  ③ 前端 SduiNodeView.tsx 的 switch case（渲染器画哪些）
任一处漏改就漂移：后端能产出、前端 union 没有、渲染器落到「未知节点」静默降级（最难查）。
历史上 DataGrid 正是后端 union 有、前端 union 与渲染器都无 → 投影器一旦用就静默空白。

本 lint 把「SDUI 协议三方一致」纳入守门（与 lint_skill_contract「皮骨一致」同级）：
  1. 后端 union 节点 type 集合 == 前端 union 节点 type 集合（协议对齐）
  2. 后端 union 的每个 type 都有 SduiNodeView 的 case（渲染器全覆盖）

退出码：违规 → 1；干净 → 0；缺 venv 无法 import agent.sdui → 0 + 警告（不阻断构建）。

用法：
    agent/.venv/Scripts/python agent/scripts/lint_sdui_contract.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK，✓/❌/中文会 UnicodeEncodeError → 强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # aida/
sys.path.insert(0, str(PROJECT_ROOT))

SDUI_TS = PROJECT_ROOT / "frontend" / "src" / "lib" / "sdui.ts"
NODEVIEW_TSX = PROJECT_ROOT / "frontend" / "src" / "components" / "sdui" / "SduiNodeView.tsx"


# ─── 纯逻辑核心（正则解析前端 · 无 IO / 无 agent import，便于单测）───

def parse_frontend_union(sdui_ts: str) -> tuple[set[str], list[str]]:
    """从 sdui.ts 的 `export type SduiNode = A | B | …;` 解析每个成员的 type 字面量。
    返回 (type 字面量集合, 无法解析出 type 的成员名列表)。"""
    m = re.search(r"export\s+type\s+SduiNode\s*=\s*(.+?);", sdui_ts, re.S)
    if not m:
        return set(), ["<未找到 export type SduiNode union>"]
    member_names = sorted(set(re.findall(r"(Sdui\w+Node)", m.group(1))))
    types: set[str] = set()
    unresolved: list[str] = []
    for name in member_names:
        # 节点定义形如：export type SduiStackNode = OptId & { type: 'Stack'; … }
        mm = re.search(rf"export\s+type\s+{name}\b.*?type:\s*['\"](\w+)['\"]", sdui_ts, re.S)
        if mm:
            types.add(mm.group(1))
        else:
            unresolved.append(name)
    return types, unresolved


def parse_nodeview_cases(nodeview_tsx: str) -> set[str]:
    """抽 SduiNodeView switch 的 `case 'Xxx':` 集合。"""
    return set(re.findall(r"case\s+['\"](\w+)['\"]\s*:", nodeview_tsx))


def check_sdui_contract(
    backend_types: set[str],
    frontend_types: set[str],
    nodeview_cases: set[str],
    unresolved: list[str],
) -> list[str]:
    """三方一致校验，返回违规信息列表（空 = 通过）。"""
    v: list[str] = []
    for name in unresolved:
        v.append(f"前端 sdui.ts 成员 `{name}` 未解析到 type 字面量（正则失配或定义异常）")

    for t in sorted(backend_types - frontend_types):
        v.append(
            f"节点 `{t}`：后端 builder union 有、前端 sdui.ts union 无 "
            f"→ 前端将渲染为「未知节点」（补前端类型或从后端 union 移除）"
        )
    for t in sorted(frontend_types - backend_types):
        v.append(
            f"节点 `{t}`：前端 sdui.ts union 有、后端 builder union 无 "
            f"→ 后端无法产出（补后端模型或从前端 union 移除）"
        )
    for t in sorted(backend_types - nodeview_cases):
        v.append(
            f"节点 `{t}`：协议中声明但 SduiNodeView 无 `case '{t}'` "
            f"→ 运行时落到 UnknownNode"
        )
    return v


# ─── IO 外壳：import 后端 union ───

def load_backend_types() -> set[str]:
    """import builder，从 SduiNode union 取所有节点的 type 默认值。
    缺依赖（ModuleNotFoundError）冒泡给 main → SKIP。"""
    from typing import get_args
    from agent.sdui.builder import SduiNode

    args = get_args(SduiNode)              # Annotated[Union[...], Field] → (Union[...], FieldInfo)
    union = args[0] if args else SduiNode
    members = get_args(union)
    types: set[str] = set()
    for m in members:
        field = getattr(m, "model_fields", {}).get("type")
        if field is not None and field.default is not None:
            types.add(field.default)
    return types


def main() -> int:
    try:
        backend_types = load_backend_types()
    except ImportError as e:  # ModuleNotFoundError 是其子类
        sys.stdout.write(
            f"[sdui-contract] ⚠ SKIP · 无法 import agent.sdui.builder（{e}）。\n"
            f"  请在 agent venv 下运行：agent\\.venv\\Scripts\\python agent\\scripts\\lint_sdui_contract.py\n"
        )
        return 0

    if not SDUI_TS.exists():
        sys.stdout.write(f"[sdui-contract] ⚠ SKIP · 找不到前端协议 {SDUI_TS}\n")
        return 0

    sdui_ts = SDUI_TS.read_text(encoding="utf-8", errors="replace")
    nodeview = NODEVIEW_TSX.read_text(encoding="utf-8", errors="replace") if NODEVIEW_TSX.exists() else ""
    frontend_types, unresolved = parse_frontend_union(sdui_ts)
    nodeview_cases = parse_nodeview_cases(nodeview)

    violations = check_sdui_contract(backend_types, frontend_types, nodeview_cases, unresolved)

    if not violations:
        sys.stdout.write(
            f"[sdui-contract] OK · SDUI 协议三方一致："
            f"builder ↔ sdui.ts ↔ SduiNodeView = {len(backend_types)} 个节点类型\n"
        )
        return 0

    sys.stdout.write(f"[sdui-contract] ❌ 发现 {len(violations)} 处 SDUI 协议漂移：\n\n")
    for msg in violations:
        sys.stdout.write(f"  · {msg}\n")
    sys.stdout.write(
        "\n说明：SDUI 协议节点类型必须三方同步（builder union ↔ sdui.ts union ↔ NodeView case）。\n"
        "  新增节点：后端 builder 加模型并入 union → 前端 sdui.ts 加类型并入 union → SduiNodeView 加 case。\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
