#!/usr/bin/env python3
"""lint_module_boundaries · 守门：模块边界契约 ≡ 代码

纯文本扫描（不 import / 不实例化 skill，无需 venv），校验四件事：

  1) 跨 skill 隔离（硬阻断）
     agent/skills/<A>/ 下任意 .py 不得 import 另一个已注册 skill <B>。
     业务场景 Skill之间零横向依赖；共享只走通用底座（base/llm/tools/mailer）或数据中心运行时目录。
     对齐 docs/20_架构与范式/architecture/02_module_boundaries.md §3 依赖矩阵。

  2) 目录自动发现约定（硬阻断）
     每个 agent/skills/<id>/（非下划线开头、含 skill.py）必须暴露 get_<id>_skill 工厂——
     这是运行时自动注册的契约（VIBECODING_HARNESS.md §7·P1a），缺工厂则该 skill 静默不注册。

  3) 自动发现 ↔ 边界图（硬阻断）
     每个自动发现的 <id> 必须出现在 docs/20_架构与范式/architecture/02_module_boundaries.md（§1 模块清单）。

  4) A 层门面（仅告警）
     每个已注册 skill 宜有 skills/<id>/SKILL.md。

命中 (1)/(2)/(3) → 退出码 1；(4) 仅打印告警。输出风格对齐 lint_skill_contract.py。

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
    """目录自动发现的 skill id —— 与 agent/skills/__init__.py 运行时同规则：
    agent/skills/<id>/ 且非下划线/点开头、含 skill.py。
    （P1a 后注册表不再有 registry.register 字面量，真相 = 目录约定。）"""
    if not SKILLS_DIR.is_dir():
        return []
    ids: list[str] = []
    for child in sorted(SKILLS_DIR.iterdir()):
        name = child.name
        if not child.is_dir() or name[0] in "_." or not (child / "skill.py").is_file():
            continue
        ids.append(name)
    return ids


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
        print("[module-boundaries] SKIP · 未发现任何 skill 目录（agent/skills/<id>/skill.py）")
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

    # (2) 目录自动发现约定：每个 skill 目录必须暴露 get_<id>_skill 工厂（否则运行时静默不注册）
    for sid in ids:
        skill_py = SKILLS_DIR / sid / "skill.py"
        if not re.search(rf"def\s+get_{re.escape(sid)}_skill\b", _read(skill_py)):
            errors.append(
                f"  缺工厂：agent/skills/{sid}/skill.py 未定义 get_{sid}_skill —— "
                f"目录自动发现注册的契约（VIBECODING_HARNESS §7·P1a），缺则该 skill 静默不注册"
            )

    # (3) 自动发现 ↔ 边界图
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

    # (4) A 层门面（告警）
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
