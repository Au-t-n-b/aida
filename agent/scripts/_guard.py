"""_guard · 守门通用：fail-open ↔ AIDA_GUARD_STRICT 严格模式（单一真相）

问题：多个 lint「缺 venv 依赖 / 缺契约文件 → SKIP(exit 0)」是 fail-open——在缺依赖的
环境（CI runner 没装、agent 执行环境、Gitea 强制层）下**静默放行**，违背「守门优先」。

策略（分层）：
  - 普通（本地开发）：缺依赖/缺文件 → SKIP（exit 0），不阻断手头开发。
  - 强制层 / CI（设 AIDA_GUARD_STRICT=1）：缺依赖/缺文件 = 配置错 = 该红（exit 1），杜绝假绿。

各 lint 的 import-fail / 缺文件分支统一调 skip_or_fail()，strict 判定只此一处（改这里即可）。
scripts/preflight.sh 已 export AIDA_GUARD_STRICT=1。
"""
from __future__ import annotations
import os
import sys

# 自给：本模块输出 ⚠/❌/中文，不依赖调用方先 reconfigure（Windows GBK 控制台会 UnicodeEncodeError）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def strict() -> bool:
    """AIDA_GUARD_STRICT 是否开启（强制层/CI 下设 1）。"""
    return os.environ.get("AIDA_GUARD_STRICT", "").strip() not in ("", "0", "false", "False")


def skip_or_fail(label: str, reason: str, hint: str = "请在 agent venv 下运行") -> int:
    """宽容模式打印 SKIP 返 0；strict 模式打印 STRICT 返 1。"""
    if strict():
        sys.stdout.write(
            f"[{label}] ❌ STRICT · {reason}\n"
            f"  AIDA_GUARD_STRICT=1（强制层/CI）下缺依赖/缺文件 = 配置错 = 不放行。\n"
        )
        return 1
    sys.stdout.write(
        f"[{label}] ⚠ SKIP · {reason}\n"
        f"  {hint}（强制层请设 AIDA_GUARD_STRICT=1 令此情形变红）\n"
    )
    return 0
