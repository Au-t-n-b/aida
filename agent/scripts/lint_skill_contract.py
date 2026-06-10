"""
skill-contract · SKILL.md ↔ LangGraph steps 契约一致守门（规范 0 守门 + 规范 5 契约先行）

问题：A 层 SKILL.md 用「后端节点」列声明业务步骤，B 层 agent/skills/<name>/ 用 Python
steps 实现。两者靠人工维护对应关系会漂移——工程改了 steps 不改 SKILL.md（或反之），
文档与执行就对不上（皮骨分离）。本 lint 把「皮骨一致」纳入守门：不一致即 prebuild 阻断。

每个已注册 skill 校验：
  1. SKILL.md 必须有「…节点」列（声明业务步骤的后端 step key）
  2. 文档声明的每个节点，必须是代码里真实存在的 step.key   （文档 → 代码）
  3. 代码里每个业务 step（internal=False）必须在 SKILL.md 声明（代码 → 文档）
  4. 文档节点顺序 == 代码业务 step 顺序（SOP 顺序不漂移）

基础设施步骤（step.internal=True，如 preflight 环境预检）豁免 2/3/4。

退出码：违规 → 1；干净 → 0；缺 venv 依赖无法 import agent → 0 + 警告（不阻断构建）。

用法：
    agent/.venv/Scripts/python agent/scripts/lint_skill_contract.py
    # 或 npm run lint:skill-contract（建议在 agent venv 下运行，否则会 SKIP）
"""
from __future__ import annotations
import sys
from pathlib import Path

# Windows 控制台默认 GBK，✓/❌/中文会 UnicodeEncodeError → 强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # aida/
sys.path.insert(0, str(PROJECT_ROOT))


# ─── 纯逻辑核心（无 IO / 无 agent import，便于单测）───

def parse_backend_nodes(skill_md_text: str) -> list[str] | None:
    """从 SKILL.md 找含「节点」的表格列，返回该列节点 key 列表（doc 顺序）。
    找不到该列 → None。"""
    lines = skill_md_text.splitlines()
    header_idx, col_idx = -1, -1

    for i, line in enumerate(lines):
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        for ci, cell in enumerate(cells):
            if "节点" in cell:
                header_idx, col_idx = i, ci
                break
        if header_idx >= 0:
            break

    if header_idx < 0:
        return None

    nodes: list[str] = []
    for line in lines[header_idx + 1:]:
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            break  # 表格结束
        cells = [c.strip() for c in s.strip("|").split("|")]
        # 分隔行 |---|:--| 跳过
        if all(c and set(c) <= {"-", ":"} for c in cells):
            continue
        if col_idx >= len(cells):
            continue
        token = cells[col_idx].strip().strip("`").strip()
        if token and not (set(token) <= {"-", ":"}):
            nodes.append(token)
    return nodes


def check_contract(
    skill_name: str,
    code_steps: list[tuple[str, bool]],   # [(key, internal), ...] 执行顺序
    skill_md_text: str | None,
) -> list[str]:
    """对单个 skill 做契约校验，返回违规信息列表（空 = 通过）。"""
    if skill_md_text is None:
        return [f"找不到 SKILL.md（{skill_name} 缺 A 层门面文件）"]

    doc_nodes = parse_backend_nodes(skill_md_text)
    if doc_nodes is None:
        first_biz = next((k for k, internal in code_steps if not internal), "step_key")
        return [
            "SKILL.md 缺『后端节点』列：业务流程表需有一列声明每步后端 step key（列名含「节点」）。\n"
            f"      期望形如：| Step | 名称 | … | 后端节点 |，单元格用反引号标注如 `{first_biz}`。"
        ]

    code_set = {k for k, _ in code_steps}
    business_keys = [k for k, internal in code_steps if not internal]
    business_set = set(business_keys)
    doc_set = set(doc_nodes)

    v: list[str] = []

    # 2. 文档 → 代码
    for n in doc_nodes:
        if n not in code_set:
            v.append(f"文档声明的节点 `{n}` 在代码中不存在（rename/删除 step 后忘改 SKILL.md？）")

    # 3. 代码 → 文档（仅业务 step）
    for k in business_keys:
        if k not in doc_set:
            v.append(
                f"代码业务步骤 `{k}` 未在 SKILL.md 声明"
                f"（新增 step 忘写文档？基础设施步骤用 internal=True 豁免）"
            )

    # 4. 顺序（仅当业务步骤集合两侧一致时才比顺序，避免与 2/3 重复报噪声）
    documented_in_code_order = [k for k in business_keys if k in doc_set]
    if doc_set == business_set and doc_nodes != documented_in_code_order:
        v.append(f"步骤顺序漂移：SKILL.md={doc_nodes} ≠ 代码={documented_in_code_order}")

    return v


# ─── IO 外壳：枚举注册表里的 skill ───

def _load_skills() -> list[tuple[str, list[tuple[str, bool]] | None, str | None, str | None]]:
    """import 注册表，返回 [(name, code_steps, skill_md_text, load_err), ...]。
    缺依赖（ModuleNotFoundError）冒泡给 main → SKIP。"""
    from agent.skills import registry  # 触发 _register_all（会 import 各 skill 模块）

    out: list[tuple[str, list[tuple[str, bool]] | None, str | None, str | None]] = []
    for name in registry.names():
        try:
            skill = registry.get(name)
        except ModuleNotFoundError:
            raise  # 缺 venv 依赖 → 冒泡 → SKIP，不阻断构建
        except Exception as e:  # noqa: BLE001
            out.append((name, None, None, f"实例化失败：{e}"))
            continue
        code_steps = [(s.key, bool(getattr(s, "internal", False))) for s in skill.steps]
        md_path = Path(getattr(skill.metadata, "source_path", "") or "")
        text = md_path.read_text(encoding="utf-8", errors="replace") if md_path.exists() else None
        out.append((name, code_steps, text, None))
    return out


def main() -> int:
    try:
        skills = _load_skills()
    except ImportError as e:  # ModuleNotFoundError 是其子类
        sys.stdout.write(
            f"[skill-contract] ⚠ SKIP · 无法 import agent.skills（{e}）。\n"
            f"  请在 agent venv 下运行：agent\\.venv\\Scripts\\python agent\\scripts\\lint_skill_contract.py\n"
        )
        return 0

    violations: list[tuple[str, str]] = []
    for name, code_steps, text, load_err in skills:
        if load_err:
            violations.append((name, load_err))
            continue
        for msg in check_contract(name, code_steps or [], text):
            violations.append((name, msg))

    if not violations:
        names = ", ".join(n for n, *_ in skills) or "（无）"
        sys.stdout.write(f"[skill-contract] OK · SKILL.md ↔ steps 契约一致（skills: {names}）\n")
        return 0

    sys.stdout.write(f"[skill-contract] ❌ 发现 {len(violations)} 处契约漂移：\n\n")
    for name, msg in violations:
        sys.stdout.write(f"  [{name}] {msg}\n")
    sys.stdout.write(
        "\n说明：A 层 SKILL.md「后端节点」列与 B 层 steps 必须一致（规范5 契约先行）。\n"
        "  改 steps 同步改 SKILL.md 流程表；基础设施步骤用 step.internal=True 豁免。\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
