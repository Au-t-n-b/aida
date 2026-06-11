"""
no-naked-llm · 禁止裸 LLM 调用守门

规则：
  agent/ 下所有 .py 文件中，**只有 agent/llm.py** 可以直接 import openai / langchain_openai。
  其他文件想用 LLM 必须经过 agent.llm.get_llm() 或 ctx.llm（SkillContext 注入）。

被 ban 的模式（行级匹配，跳过注释和字符串字面量）：
  - from openai import / import openai
  - from anthropic import / import anthropic
  - import litellm / from litellm import
  - httpx / requests + chat/completions URL（智谱 / openai 兼容端点）
  - from langchain_openai import（仅 agent/llm.py 允许）

退出码：发现违规 → 1；干净 → 0。

用法：
    python agent/scripts/lint_no_naked_llm.py
    # 或加到 npm script / pre-commit
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # agent/
PROJECT_ROOT = ROOT.parent                       # aida/

# 白名单：以下文件可以直接持有 LLM 客户端
ALLOWED_FILES = {
    (ROOT / "llm.py").resolve(),
}

# 跳过这些目录
SKIP_DIRS = {".venv", "__pycache__", "node_modules", ".git", "scripts"}

# 违规模式（编译后逐行匹配）
PATTERNS = [
    (re.compile(r"^\s*(from|import)\s+openai(\.|\s|$)"), "import openai → 用 agent.llm.get_llm()"),
    (re.compile(r"^\s*(from|import)\s+anthropic(\.|\s|$)"), "import anthropic → 用 agent.llm.get_llm()"),
    (re.compile(r"^\s*(from|import)\s+litellm(\.|\s|$)"), "import litellm → 用 agent.llm.get_llm()"),
    (re.compile(r"^\s*(from|import)\s+langchain_openai(\.|\s|$)"), "import langchain_openai → 用 agent.llm.get_llm()"),
    (re.compile(r"(requests|httpx|aiohttp)\.\w+\([^)]*chat/completions"), "HTTP 直打 chat/completions → 用 agent.llm.chat_once/chat_stream"),
    (re.compile(r"open\.bigmodel\.cn.+chat/completions"), "直 POST 智谱端点 → 用 agent.llm"),
]


def _is_comment_or_string(line: str) -> bool:
    """粗略判断整行是否为注释 / docstring（避免误杀文档里举例的字符串）"""
    s = line.strip()
    if s.startswith("#"):
        return True
    # 单行 docstring
    if (s.startswith('"""') and s.endswith('"""') and len(s) > 6) or \
       (s.startswith("'''") and s.endswith("'''") and len(s) > 6):
        return True
    return False


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """返回 (lineno, line, reason) 违规列表"""
    hits: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return hits

    in_block_string = False
    for i, raw in enumerate(text.splitlines(), start=1):
        # 简单 docstring 块跳过（"""..."""）
        triple = raw.count('"""') + raw.count("'''")
        if triple % 2 == 1:
            in_block_string = not in_block_string
            continue
        if in_block_string:
            continue
        if _is_comment_or_string(raw):
            continue
        for pat, reason in PATTERNS:
            if pat.search(raw):
                hits.append((i, raw.rstrip(), reason))
                break
    return hits


def main() -> int:
    total_violations: list[tuple[Path, int, str, str]] = []

    for py in ROOT.rglob("*.py"):
        # 跳过 venv / cache
        if any(part in SKIP_DIRS for part in py.relative_to(ROOT).parts):
            continue
        resolved = py.resolve()
        if resolved in ALLOWED_FILES:
            continue
        for lineno, line, reason in scan_file(py):
            total_violations.append((py, lineno, line, reason))

    if not total_violations:
        sys.stdout.write("[no-naked-llm] OK · 没有发现裸 LLM 调用\n")
        return 0

    sys.stdout.write(f"[no-naked-llm] ❌ 发现 {len(total_violations)} 处违规：\n\n")
    for path, lineno, line, reason in total_violations:
        rel = path.relative_to(PROJECT_ROOT)
        sys.stdout.write(f"  {rel}:{lineno}\n")
        sys.stdout.write(f"    {line}\n")
        sys.stdout.write(f"    → {reason}\n\n")
    sys.stdout.write(
        "说明：所有 LLM 调用必须经 agent.llm.get_llm() / chat_once() / chat_stream() / SkillContext.llm。\n"
        "白名单：agent/llm.py（唯一允许直接持有 ChatOpenAI 实例的文件）。\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
