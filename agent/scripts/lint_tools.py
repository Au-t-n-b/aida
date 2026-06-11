"""
lint_tools · 工具契约守门（团队范式 §3 工具规范 / EVAL-STANDARDS §3）

范式一直标注「❌待补」的守门，现补上。静态检查所有注册工具的契约质量，违规即
prebuild 阻断（与 lint_no_naked_llm / lint_no_naked_send 同级）：

  - name        非空 · 小写下划线（^[a-z][a-z0-9_]*$）· 与注册键一致
  - description 非空 · ≥10 字符（description 质量 = 召回质量）
  - parameters  合法 JSON Schema：type=object + properties + required⊆properties + 每参数有 type

孤儿检测（warn 不阻断）：tools/ 下定义的 Tool 子类未在 __init__.py 导入。

跑：python agent/scripts/lint_tools.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # aida
sys.path.insert(0, str(ROOT))

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
MIN_DESC = 10


def check_tool(tool) -> list[str]:
    """对单个工具实例做契约校验，返回错误列表（空 = 合规）。"""
    errs: list[str] = []
    cls = type(tool).__name__
    name = getattr(tool, "name", None)
    if not name or not isinstance(name, str):
        return [f"{cls}: name 为空或非字符串"]
    if not NAME_RE.match(name):
        errs.append(f"{name}: name 应为小写下划线（^[a-z][a-z0-9_]*$）")

    desc = (getattr(tool, "description", "") or "").strip()
    if len(desc) < MIN_DESC:
        errs.append(f"{name}: description 过短（<{MIN_DESC} 字符），影响模型召回")

    params = getattr(tool, "parameters", None)
    if not isinstance(params, dict):
        return errs + [f"{name}: parameters 不是 dict"]
    if params.get("type") != "object":
        errs.append(f"{name}: parameters.type 必须为 'object'")
    props = params.get("properties")
    if not isinstance(props, dict):
        errs.append(f"{name}: parameters 缺 properties")
        props = {}
    required = params.get("required", [])
    if not isinstance(required, list):
        errs.append(f"{name}: parameters.required 必须为 list")
        required = []
    for r in required:
        if r not in props:
            errs.append(f"{name}: required 项 '{r}' 不在 properties 中")
    for pname, pschema in props.items():
        if not isinstance(pschema, dict) or "type" not in pschema:
            errs.append(f"{name}.{pname}: 参数缺 type")
    return errs


def orphan_warnings() -> list[str]:
    """tools/ 下定义的 Tool 子类未在 __init__.py 导入 → 疑似孤儿（warn）。"""
    warns: list[str] = []
    tools_dir = ROOT / "agent" / "tools"
    init_txt = (tools_dir / "__init__.py").read_text(encoding="utf-8")
    cls_re = re.compile(r"^class\s+(\w+)\s*\([^)]*Tool[^)]*\)\s*:", re.M)
    skip = {"__init__.py", "base.py", "registry.py", "trace.py"}
    for py in sorted(tools_dir.glob("*.py")):
        if py.name in skip or py.name.endswith(".template.py"):
            continue
        for m in cls_re.finditer(py.read_text(encoding="utf-8")):
            cls = m.group(1)
            if cls not in init_txt:
                warns.append(f"{py.name}: class {cls} 未在 tools/__init__.py 导入（疑似孤儿，局部 allowed 工具可忽略）")
    return warns


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    from agent.tools import DEFAULT_TOOLS

    errors: list[str] = []
    names = DEFAULT_TOOLS.tool_names
    for name in names:
        tool = DEFAULT_TOOLS.get(name)
        if tool.name != name:
            errors.append(f"{name}: 注册键与 tool.name='{tool.name}' 不一致")
        errors.extend(check_tool(tool))

    for w in orphan_warnings():
        print(f"[lint-tools] ⚠ {w}")

    if errors:
        print(f"[lint-tools] ✗ {len(errors)} 项契约违规：")
        for e in errors:
            print(f"  · {e}")
        return 1
    print(f"[lint-tools] OK ✓ {len(names)} 个工具契约合规：{', '.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
