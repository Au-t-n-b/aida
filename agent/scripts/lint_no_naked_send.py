"""
no-naked-send · 禁止裸外发调用守门（规范 4 · 副作用统一）

规则：
  agent/ 下所有 .py 文件中：
  - 只有 agent/mailer.py   可直接 import smtplib / win32com（邮件通道）
  - 只有 agent/notifier.py 可直接调用 httpx.post / requests.post（IM 通道）
  其他文件发邮件必须经 agent.mailer.send_mail()
  其他文件发 IM 必须经 agent.notifier.send_welink()

被 ban 的模式：
  - import smtplib / from smtplib import   （仅 agent/mailer.py 允许）
  - import win32com / from win32com import  （仅 agent/mailer.py 允许）
  - httpx.post(                             （仅 agent/notifier.py 允许）
  - requests.post(                          （仅 agent/notifier.py 允许）

退出码：发现违规 → 1；干净 → 0。

用法：
    python agent/scripts/lint_no_naked_send.py
    # 或加到 npm run lint:no-naked-send / prebuild
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]       # agent/
PROJECT_ROOT = ROOT.parent                        # aida/

MAILER_FILE = (ROOT / "mailer.py").resolve()
NOTIFIER_FILE = (ROOT / "notifier.py").resolve()
# 仿真软件 API 统一出口（guihua 建模仿真）：与 notifier 同级的「唯一外发通道」，
# 内置 dry-run + 留痕，是 requests.post 的合法白名单文件。
SIM_API_FILE = (ROOT / "skills" / "guihua" / "services" / "sim_api.py").resolve()

SKIP_DIRS = {".venv", "__pycache__", "node_modules", ".git", "scripts", "evals"}

# (pattern, human-reason, whitelisted-file(s))
# 最后一项可为单个 Path 或一组 Path（多个合法出口文件）。
RULES: list[tuple[re.Pattern[str], str, object]] = [
    (
        re.compile(r"^\s*(import|from)\s+smtplib(\.|\s|$)"),
        "import smtplib → 邮件必须经 agent.mailer.send_mail()",
        MAILER_FILE,
    ),
    (
        re.compile(r"^\s*(import|from)\s+win32com(\.|\s|$)"),
        "import win32com → 邮件必须经 agent.mailer.send_mail()",
        MAILER_FILE,
    ),
    (
        re.compile(r"httpx\.post\s*\("),
        "httpx.post → IM/外发必须经 agent.notifier.send_welink()",
        NOTIFIER_FILE,
    ),
    (
        re.compile(r"requests\.post\s*\("),
        "requests.post → IM/外发必须经 agent.notifier.send_welink()（仿真 API 经 services/sim_api.py）",
        frozenset({NOTIFIER_FILE, SIM_API_FILE}),
    ),
]


def _is_comment_or_string(line: str) -> bool:
    s = line.strip()
    if s.startswith("#"):
        return True
    if (s.startswith('"""') and s.endswith('"""') and len(s) > 6) or \
       (s.startswith("'''") and s.endswith("'''") and len(s) > 6):
        return True
    return False


def scan_file(
    path: Path,
    applicable_rules: list[tuple[re.Pattern[str], str]],
) -> list[tuple[int, str, str]]:
    """返回 (lineno, line, reason) 违规列表"""
    hits: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return hits

    in_block_string = False
    for i, raw in enumerate(text.splitlines(), start=1):
        triple = raw.count('"""') + raw.count("'''")
        if triple % 2 == 1:
            in_block_string = not in_block_string
            continue
        if in_block_string:
            continue
        if _is_comment_or_string(raw):
            continue
        for pat, reason in applicable_rules:
            if pat.search(raw):
                hits.append((i, raw.rstrip(), reason))
                break
    return hits


def main() -> int:
    total_violations: list[tuple[Path, int, str, str]] = []

    for py in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in py.relative_to(ROOT).parts):
            continue
        resolved = py.resolve()
        # 仅保留该文件不在白名单的规则（allowed 可为单文件或一组合法出口文件）
        applicable = [
            (pat, reason) for pat, reason, allowed in RULES
            if resolved not in (allowed if isinstance(allowed, (set, frozenset)) else {allowed})
        ]
        if not applicable:
            continue
        for lineno, line, reason in scan_file(py, applicable):
            total_violations.append((py, lineno, line, reason))

    if not total_violations:
        sys.stdout.write("[no-naked-send] OK · 没有发现裸外发调用\n")
        return 0

    sys.stdout.write(f"[no-naked-send] ❌ 发现 {len(total_violations)} 处违规：\n\n")
    for path, lineno, line, reason in total_violations:
        rel = path.relative_to(PROJECT_ROOT)
        sys.stdout.write(f"  {rel}:{lineno}\n")
        sys.stdout.write(f"    {line}\n")
        sys.stdout.write(f"    → {reason}\n\n")
    sys.stdout.write(
        "说明：邮件统一走 agent.mailer.send_mail()，"
        "IM 统一走 agent.notifier.send_welink()。\n"
        "白名单：agent/mailer.py（smtplib/win32com）、"
        "agent/notifier.py（httpx.post/requests.post）、"
        "agent/skills/guihua/services/sim_api.py（requests.post · 仿真 API 统一出口）。\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
