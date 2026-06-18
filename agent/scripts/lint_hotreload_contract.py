"""
hotreload-contract · P4 热加载「附加不改泛化」守门（纯 stdlib · 无需 venv）

红线本质：`agent/main.py` / `agent/graph.py` 的**泛化路由分发 + `build_graph` 构图逻辑零改**；
热加载能力只能以**附加**形式存在（独立 admin router + `graph.invalidate` 附加函数 + `registry.reload`）。
本 lint 把这条红线钉成可阻断的契约，防止未来回归（删 invalidate / 把 reload 内联进泛化文件 / 去掉鉴权）：

  1. graph.py 有 `invalidate()`，失效 `_compiled`/`_compiled_async` 两层编译图、且**不清**共享 `_async_saver`
  2. _registry.py 有 `reload()`（①工厂表 ②实例缓存失效）
  3. admin_routes.py 存在：定义 `POST /skills/reload` + 带鉴权（`_check_admin_auth` / `AIDA_ADMIN_TOKEN`）
  4. main.py 仅以 `include_router(admin_router)` 挂载，**不把** reload 端点内联进泛化文件
  5. main.py / graph.py 泛化锚点仍在（`/agent/{skill}/start` 泛化路由 · `get_graph_async(skill_id` 泛化构图）

违规 → 退出码 1。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "agent"


def _read(rel: str) -> str | None:
    p = AGENT / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else None


def check() -> list[str]:
    v: list[str] = []

    graph = _read("graph.py")
    if graph is None:
        v.append("缺 agent/graph.py")
    else:
        m = re.search(r"\ndef invalidate\b.*?(?=\n(?:async def|def) |\Z)", graph, re.S)
        if not m:
            v.append("graph.py 缺 invalidate()（P4 第 ③ 层编译图缓存失效附加函数）")
        else:
            body = m.group(0)
            if "_compiled" not in body or "_compiled_async" not in body:
                v.append("graph.invalidate() 必须失效 _compiled 与 _compiled_async 两层编译图缓存")
            if re.search(r"_async_saver\s*=", body):
                v.append("graph.invalidate() 不得清空共享 _async_saver（checkpoint 须持久、旧 run 不丢）")
        if "def get_graph_async(skill_id" not in graph:
            v.append("graph.py 泛化锚点缺失：get_graph_async(skill_id ...)（疑似改了泛化构图）")

    reg = _read("skills/_registry.py")
    if reg is None:
        v.append("缺 agent/skills/_registry.py")
    elif "def reload(" not in reg:
        v.append("_registry.py 缺 reload()（P4 ①②层缓存失效）")

    admin = _read("admin_routes.py")
    if admin is None:
        v.append("缺 agent/admin_routes.py（reload 端点须独立成 router，不内联进泛化文件）")
    else:
        if not re.search(r'@router\.(post|get)\(\s*["\']/skills/reload["\']', admin):
            v.append('admin_routes.py 缺 @router.post("/skills/reload")')
        if "_check_admin_auth" not in admin and "AIDA_ADMIN_TOKEN" not in admin:
            v.append("admin_routes.py 的 reload 端点缺鉴权（_check_admin_auth / AIDA_ADMIN_TOKEN）")

    main = _read("main.py")
    if main is None:
        v.append("缺 agent/main.py")
    else:
        if "include_router(admin_router)" not in main:
            v.append("main.py 未挂载 admin_router（应有 app.include_router(admin_router)）")
        if re.search(r'@app\.(post|get)\(\s*["\']/admin/skills/reload', main):
            v.append("main.py 内联了 /admin/skills/reload —— reload 必须留在 admin_routes router（泛化文件零业务/运维端点内联）")
        if "/agent/{skill}/start" not in main:
            v.append("main.py 泛化锚点缺失：/agent/{skill}/start（疑似改了泛化路由）")

    return v


def main() -> int:
    v = check()
    if not v:
        sys.stdout.write(
            "[hotreload-contract] OK · P4 热加载附加契约完整"
            "（invalidate / reload / admin router 挂载 / 鉴权 / 泛化锚点均在）\n"
        )
        return 0
    sys.stdout.write(f"[hotreload-contract] ❌ 发现 {len(v)} 处违规：\n")
    for x in v:
        sys.stdout.write(f"  - {x}\n")
    sys.stdout.write(
        "\n说明：热加载是**附加**能力——main.py/graph.py 泛化逻辑零改、reload 端点留在 "
        "agent/admin_routes.py，graph.invalidate 只失效编译图不动共享 saver。\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
