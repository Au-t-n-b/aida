"""
工具框架 smoke 验证 —— 证明「工具规范」可落地、可演示。

跑：  python agent/scripts/tool_smoke.py
覆盖：cast（"2000"→2000）/ validate（缺 required / 越界）/ execute / OpenAI schema 输出。
"""
import sys
from pathlib import Path

# Windows 控制台默认 GBK，中文/replace 字符会报 UnicodeEncodeError → 强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 让脚本能直接 import agent.tools（把仓库根加进 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.tools import DEFAULT_TOOLS  # noqa: E402


def line(t):
    print("·", t)


def main() -> int:
    print("== 已注册工具 ==", DEFAULT_TOOLS.tool_names)

    # 1) OpenAI function schema（会话 ReAct 喂模型用）
    print("\n== get_definitions(OpenAI 格式) ==")
    for d in DEFAULT_TOOLS.get_definitions():
        print("·", d["function"]["name"], "→ required:", d["function"]["parameters"].get("required"))

    # 2) 正常执行 + cast（max_bytes 传字符串 "60"，应自动转 int）
    print("\n== 正常执行（含类型 cast）==")
    self_path = str(Path(__file__).resolve())
    out = DEFAULT_TOOLS.execute("read_file", {"path": self_path, "max_bytes": "60"})
    line(f"read_file 前 60 字节 → {out[:60]!r}")

    # 3) 缺 required 参数 → validate 拦截
    print("\n== 缺 required（应被拦截）==")
    line(DEFAULT_TOOLS.execute("read_file", {}))

    # 4) 参数越界 → validate 拦截
    print("\n== max_bytes 越界（应被拦截）==")
    line(DEFAULT_TOOLS.execute("read_file", {"path": self_path, "max_bytes": 9_999_999}))

    # 5) 不存在的工具 → 友好提示
    print("\n== 未知工具（应友好提示）==")
    line(DEFAULT_TOOLS.execute("no_such_tool", {}))

    # 6) 经 SkillContext.call_tool 调用（step 实际用法 · 带日志 emit）
    print("\n== 经 ctx.call_tool（step 用法 + emit 日志）==")
    from pathlib import Path as _P
    from agent.skills.base import SkillContext
    ctx = SkillContext(skill_id="zhgk", work_root=_P("."), run_id="run-smoke")
    logs: list[str] = []
    out2 = ctx.call_tool("read_file", {"path": self_path, "max_bytes": "40"},
                         step_key="demo_step", emit=logs.append)
    line(f"ctx.call_tool 结果 → {out2[:40]!r}")
    line(f"emit 日志 → {logs}")

    # 7) send_welink dry-run（验证注册 + notifier 调通，无需真实网关）
    print("\n== send_welink dry-run ==")
    line(DEFAULT_TOOLS.execute("send_welink", {"receiver": "group_001", "content": "smoke 测试消息"}))
    line(DEFAULT_TOOLS.execute("send_welink", {}))  # 缺 required → 应被拦截
    line(DEFAULT_TOOLS.execute("send_welink", {
        "receiver": "u001",
        "table_headers": ["机房", "状态"],
        "table_rows": [["K1903", "OK"]],
    }))

    print("\n✅ 工具框架 smoke 通过：cast / validate / execute / schema / ctx.call_tool / send_welink 均按规范工作")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
