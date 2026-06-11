"""
验证 GLM 是否支持原生 tool-calling（OpenAI function calling）。

跑：./agent/.venv/Scripts/python.exe agent/scripts/verify_tool_calling.py
作用：决定会话 ReAct（MVP-2）走「原生 function calling」还是降级「prompt 引导 + 解析」。
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.llm import get_llm          # noqa: E402
from agent.tools import DEFAULT_TOOLS   # noqa: E402


def main() -> int:
    defs = DEFAULT_TOOLS.get_definitions()
    print("绑定工具:", [d["function"]["name"] for d in defs])

    llm = get_llm()
    try:
        bound = llm.bind_tools(defs)
    except Exception as e:
        print(f"\n❌ bind_tools 失败：{e}")
        return 1

    try:
        resp = bound.invoke([
            ("system", "你可以调用工具完成任务。需要读取文件内容时调用 read_file 工具。"),
            ("human", "帮我读一下 README.md 文件的前 200 字节"),
        ])
    except Exception as e:
        print(f"\n❌ 调用失败（API key / 网络 / 模型）：{e}")
        return 1

    tcs = getattr(resp, "tool_calls", None)
    print("\n=== GLM 响应 ===")
    print("content:", (resp.content or "")[:160] if isinstance(resp.content, str) else resp.content)
    print("tool_calls:", tcs)

    if tcs:
        print("\n✅ GLM 支持原生 tool-calling → 会话 ReAct（MVP-2）走原生 function calling")
        return 0
    print("\n⚠️ 未返回 tool_calls → MVP-2 需降级为「prompt 引导 + 文本解析」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
