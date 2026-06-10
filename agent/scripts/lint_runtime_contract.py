"""
runtime-contract · AIDA 运行时契约 ↔ 代码 一致守门（团队范式 §0 守门元规范）

问题：`docs/30_skill开发/31_手写规范/AIDA-RUNTIME-CONTRACT.md` 是「散文契约」，给三种 coding agent
（Claude Code / Cursor / Codex）和外部 skill2langgraph 生成工厂对齐用。散文靠人手
维护必漂——已发生：§2.2 更新到 `is_tool_error`，§2.4 工具清单却仍写「仅 5 个」（实 7 个）；
外部工厂据旧契约把 dict 工具失败误判成功（复刻了 AIDA 早已修过的 P1 bug）。

本 lint 把「契约 ≡ 代码」纳入守门（与 lint_skill_contract / lint_sdui_contract 同级）：
  1. CONTRACT §2.4 的 DEFAULT_TOOLS 清单 == 代码 `DEFAULT_TOOLS.tool_names`
  2. CONTRACT §2.2 工具成败判定提及 `is_tool_error`（非仅 `startswith("Error")`）

这样契约文档不再手维护漂移；同事的工厂无论何时拉 AIDA 契约，拉到的都是 CI 校验过 ≡ 代码的版本。

退出码：违规 → 1；干净 → 0；缺 venv 无法 import agent → 0 + 警告（不阻断构建）。

用法：agent/.venv/Scripts/python agent/scripts/lint_runtime_contract.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK，中文/✓ 会 UnicodeEncodeError → 强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # aida/
sys.path.insert(0, str(PROJECT_ROOT))

CONTRACT_MD = PROJECT_ROOT / "docs" / "30_skill开发" / "31_手写规范" / "AIDA-RUNTIME-CONTRACT.md"


# ─── 纯逻辑核心（无 IO / 无 agent import，便于单测）───

def parse_contract_tools(md: str) -> set[str]:
    """从 §2.4「DEFAULT_TOOLS 真实清单」表抽工具名（表格第一列反引号 token）。
    定位标题「DEFAULT_TOOLS … 真实清单」到下一个 `## ` / `---` 之间的 section。"""
    m = re.search(r"DEFAULT_TOOLS`?\s*真实清单.*?(?=\n##\s|\n---)", md, re.S)
    section = m.group(0) if m else ""
    return set(re.findall(r"^\|\s*`([a-z_][a-z0-9_]*)`", section, re.M))


def check_runtime_contract(
    contract_tools: set[str], code_tools: set[str], md: str
) -> list[str]:
    """契约 ≡ 代码 校验，返回违规信息列表（空 = 通过）。"""
    v: list[str] = []
    if not contract_tools:
        v.append("CONTRACT §2.4 未解析到 DEFAULT_TOOLS 表（标题/表格格式变化？）")
    for t in sorted(code_tools - contract_tools):
        v.append(f"DEFAULT_TOOLS `{t}`：代码已注册、CONTRACT §2.4 未列 → 契约滞后于代码")
    for t in sorted(contract_tools - code_tools):
        v.append(f"DEFAULT_TOOLS `{t}`：CONTRACT §2.4 列了、代码无 → 契约超前（工具已删/改名？）")
    if "is_tool_error" not in md:
        v.append(
            "工具成败判定：CONTRACT 未提及 `is_tool_error` → 旧契约（仅 `startswith('Error')`）"
            "会把 dict 工具失败误判成功"
        )
    return v


# ─── IO 外壳：import 代码真身 ───

def load_code_tools() -> set[str]:
    """import DEFAULT_TOOLS，取真实工具名集合。缺依赖冒泡给 main → SKIP。"""
    from agent.tools import DEFAULT_TOOLS
    return set(DEFAULT_TOOLS.tool_names)


def main() -> int:
    try:
        code_tools = load_code_tools()
    except ImportError as e:  # ModuleNotFoundError 是其子类
        sys.stdout.write(
            f"[runtime-contract] ⚠ SKIP · 无法 import agent.tools（{e}）。\n"
            f"  请在 agent venv 下运行：agent\\.venv\\Scripts\\python agent\\scripts\\lint_runtime_contract.py\n"
        )
        return 0

    if not CONTRACT_MD.exists():
        sys.stdout.write(f"[runtime-contract] ⚠ SKIP · 找不到契约 {CONTRACT_MD}\n")
        return 0

    md = CONTRACT_MD.read_text(encoding="utf-8", errors="replace")
    contract_tools = parse_contract_tools(md)
    violations = check_runtime_contract(contract_tools, code_tools, md)

    if not violations:
        sys.stdout.write(
            f"[runtime-contract] OK · 契约 ≡ 代码：DEFAULT_TOOLS {len(code_tools)} 个一致"
            f"（{', '.join(sorted(code_tools))}）、判定用 is_tool_error\n"
        )
        return 0

    sys.stdout.write(f"[runtime-contract] ❌ 发现 {len(violations)} 处契约漂移：\n\n")
    for msg in violations:
        sys.stdout.write(f"  · {msg}\n")
    sys.stdout.write(
        "\n说明：AIDA-RUNTIME-CONTRACT.md 是给三种 agent 工具 + skill2langgraph 工厂对齐的单一真相，必须 ≡ 代码。\n"
        "  改 DEFAULT_TOOLS / 工具返回契约后，同步改 docs/30_skill开发/31_手写规范/AIDA-RUNTIME-CONTRACT.md（§2.2 判定 / §2.4 清单）。\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
