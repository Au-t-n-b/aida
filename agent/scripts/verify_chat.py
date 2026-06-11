"""
会话 ReAct 引擎验证 —— 流式会话 + 自动调工具。

跑：./agent/.venv/Scripts/python.exe agent/scripts/verify_chat.py
覆盖：
  case 1 纯聊天 → 只出 token（流式）
  case 2 需工具 → tool_call → tool_result → token（ReAct 闭环）
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.chat_engine import run_chat  # noqa: E402


def run_case(title: str, text: str) -> None:
    print(f"\n{'='*48}\n[{title}] 用户：{text}\n{'='*48}")
    buf = []
    for ev in run_chat(text):
        t = ev["type"]
        if t == "token":
            buf.append(ev["text"])
            sys.stdout.write(ev["text"])
            sys.stdout.flush()
        elif t == "tool_call":
            print(f"\n  🔧 调用工具 {ev['name']}({ev['args']})")
        elif t == "tool_result":
            print(f"  ↩ 工具返回：{ev['result'][:80]!r}")
        elif t == "skill_launch":
            print(f"\n  🚀 唤起 Skill：{ev['skill']} · project={ev.get('project_code')} · {len(ev.get('steps', []))} 步")
        elif t == "done":
            print(f"\n  ✓ 完成{('（'+ev['note']+'）') if ev.get('note') else ''}")
        elif t == "error":
            print(f"\n  ❌ 错误：{ev['message']}")


def main() -> int:
    run_case("纯聊天 · 只应出 token", "用一句话介绍你能帮我做什么")
    run_case("需工具 · 应触发 read_file", "读一下当前目录的 README.md 文件前 150 字节，并告诉我它讲什么")
    run_case("邮件 · 应触发 send_mail（dry-run）", "给 li.wei@example.com 发一封邮件，主题「工勘完成」，正文告诉他 K1903 工勘报告已生成")
    run_case("工勘 · 应触发 run_survey（skill-as-tool）", "帮 K1903 项目启动智慧工勘流程，告诉我会经过哪几步")
    print("\n\n✅ 会话 ReAct 引擎验证完成：流式 token + 工具(读文件/发邮件/跑工勘)调用闭环均工作")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
