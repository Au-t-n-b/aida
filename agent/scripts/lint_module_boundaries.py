#!/usr/bin/env python3
"""lint_module_boundaries · 守门：模块边界契约 ≡ 代码

纯文本扫描（不 import / 不实例化 skill，无需 venv），校验三件事：

  1) 跨 skill 隔离（硬阻断）
     agent/skills/<A>/ 下任意 .py 不得 import 另一个已注册 skill <B>。
     业务场景 Skill之间零横向依赖；共享只走通用底座（base/llm/tools/mailer）或数据中心运行时目录。
     对齐 docs/20_架构与范式/architecture/02_module_boundaries.md §3 依赖矩阵。

  2) 注册表 ↔ 边界图（硬阻断）
     agent/skills/__init__.py 里每个 registry.register("<id>", ...) 的 <id>
     必须出现在 docs/20_架构与范式/architecture/02_module_boundaries.md（§1 模块清单）。

  3) A 层门面（仅告警）
     每个已注册 skill 宜有 skills/<id>/SKILL.md。

命中 (1)/(2) → 退出码 1；(3) 仅打印告警。输出风格对齐 lint_skill_contract.py。

用法：  python agent/scripts/lint_module_boundaries.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK，·/中文会 UnicodeEncodeError 或乱码 → 强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO / "agent" / "skills"
REGISTRY_INIT = SKILLS_DIR / "__init__.py"
BOUNDARIES = REPO / "docs" / "20_架构与范式" / "architecture" / "02_module_boundaries.md"
SKILL_MD_DIR = REPO / "skills"

# 通用底座 / 脚手架包 —— 任意 skill 都可依赖，不算横向耦合
INFRA = {"base", "_registry", "_loader", "_template", "sdui", "__pycache__"}

# from ..<other>   |   [agent.]skills.<other>
_IMPORT_RE = re.compile(
    r"from\s+\.\.([a-z0-9_]+)"          # 相对：from ..<other>
    r"|(?:agent\.)?skills\.([a-z0-9_]+)"  # 绝对：[agent.]skills.<other>
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def registered_skill_ids() -> list[str]:
    text = _read(REGISTRY_INIT)
    return re.findall(r'registry\.register\(\s*["\']([a-z0-9_]+)["\']', text)


def scan_cross_skill_imports(skill_id: str, others: set[str]) -> list[tuple[str, int, str]]:
    """返回 [(相对路径, 行号, 行内容)] —— 本 skill 目录里引用了另一个已注册 skill 的 import 行。"""
    hits: list[tuple[str, int, str]] = []
    pkg = SKILLS_DIR / skill_id
    if not pkg.is_dir():
        return hits
    for py in sorted(pkg.rglob("*.py")):
        for lineno, line in enumerate(_read(py).splitlines(), 1):
            stripped = line.strip()
            if not (stripped.startswith("from") or stripped.startswith("import")):
                continue
            for m in _IMPORT_RE.finditer(line):
                other = m.group(1) or m.group(2)
                if other and other != skill_id and other in others and other not in INFRA:
                    hits.append((str(py.relative_to(REPO)), lineno, stripped))
    return hits


def main() -> int:
    if not SKILLS_DIR.is_dir():
        print(f"[module-boundaries] SKIP · 未找到 {SKILLS_DIR.relative_to(REPO)}")
        return 0

    ids = registered_skill_ids()
    if not ids:
        print("[module-boundaries] SKIP · 注册表为空（agent/skills/__init__.py 无 registry.register）")
        return 0

    id_set = set(ids)
    errors: list[str] = []
    warnings: list[str] = []

    # (1) 跨 skill 隔离
    for sid in ids:
        for rel, lineno, line in scan_cross_skill_imports(sid, id_set):
            errors.append(
                f"  跨 skill 依赖：{rel}:{lineno} 模块 '{sid}' import 了另一个模块\n"
                f"      {line}\n"
                f"      → 业务场景 Skill 间零横向依赖（02_module_boundaries §3）；共享走 base/llm/tools 或数据中心运行时目录"
            )

    # (2) 注册表 ↔ 边界图
    if not BOUNDARIES.is_file():
        errors.append(
            f"  边界图缺失：{BOUNDARIES.relative_to(REPO)} 不存在 —— 治理骨架未落盘"
        )
    else:
        bdoc = _read(BOUNDARIES)
        for sid in ids:
            if not re.search(rf"\b{re.escape(sid)}\b", bdoc):
                errors.append(
                    f"  未入边界图：已注册模块 '{sid}' 未出现在 "
                    f"{BOUNDARIES.relative_to(REPO)} §1 模块清单 —— 跑 Workflow C 基线重置补登"
                )

    # (3) A 层门面（告警）
    for sid in ids:
        if not (SKILL_MD_DIR / sid / "SKILL.md").is_file():
            warnings.append(f"  模块 '{sid}' 缺 skills/{sid}/SKILL.md（A 层门面建议补齐）")

    for w in warnings:
        print(f"[module-boundaries] WARN\n{w}")

    if errors:
        print("[module-boundaries] FAIL · 模块边界契约与代码不一致：")
        for e in errors:
            print(e)
        return 1

    print(
        f"[module-boundaries] OK · 模块边界契约 ≡ 代码"
        f"（modules: {', '.join(ids)}；跨 skill 零横向依赖；均已入边界图）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
