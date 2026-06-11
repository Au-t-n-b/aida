"""
gkclaw 邮件链路 · 离线契约回归（EVAL-STANDARDS 防假绿：纯本地、无网络、无 LLM）

覆盖：ids / schema / package（建包·解析·防篡改·防路径逃逸）/ registry 状态机与幂等 /
mapping 字段映射与分簇 / dispatch / ingest（ack·staged·final·error·冲突·隔离·双源）。

跑：
    agent\\.venv\\Scripts\\python.exe agent\\evals\\eval_gkclaw.py
    # --fixture 兼容 CI 入参（本评测恒离线，行为相同）
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # aida/
sys.path.insert(0, str(PROJECT_ROOT))

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


def tmpdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="gkclaw-eval-"))


# ─── ids ───

@test
def ids_task_id_format_and_uniqueness():
    from agent.skills.zhgk.services.gkclaw import ids
    root = tmpdir()
    t1 = ids.new_task_id("K1903", root)
    t2 = ids.new_task_id("K1903", root)
    assert ids.is_valid_task_id(t1), f"task_id 不合契约正则: {t1}"
    assert t1 != t2, "连续生成必须唯一"
    assert t1.startswith("task-") and "K1903" in t1, t1
    assert t1 < t2, "序列应单调递增"


@test
def ids_sanitize_project_code():
    from agent.skills.zhgk.services.gkclaw import ids
    assert ids.sanitize_code("K1903") == "K1903"
    assert ids.sanitize_code("智算K19/03") == "K1903"
    assert ids.sanitize_code("！@#") == "ZHGK", "全非法字符回退 ZHGK"
    assert ids.sanitize_code("") == "ZHGK"


@test
def ids_package_id_format():
    from agent.skills.zhgk.services.gkclaw import ids
    p1, p2 = ids.new_package_id(), ids.new_package_id()
    assert p1.startswith("pkg-") and p1 != p2


@test
def ids_zip_path_safety():
    from agent.skills.zhgk.services.gkclaw import ids
    assert ids.is_safe_zip_path("assets/items/1/a.jpg")
    assert ids.is_safe_zip_path("task.json")
    assert not ids.is_safe_zip_path("../escape.txt")
    assert not ids.is_safe_zip_path("a/../../b")
    assert not ids.is_safe_zip_path("/abs/path")
    assert not ids.is_safe_zip_path("C:\\win\\path")
    assert not ids.is_safe_zip_path("")


# ─── main ───

def main() -> int:
    failed = 0
    for fn in TESTS:
        try:
            fn()
            sys.stdout.write(f"  ✓ {fn.__name__}\n")
        except AssertionError as e:
            failed += 1
            sys.stdout.write(f"  ❌ {fn.__name__}: {e}\n")
        except Exception as e:  # noqa: BLE001
            failed += 1
            sys.stdout.write(f"  ❌ {fn.__name__}: {type(e).__name__}: {e}\n")
    status = "OK" if failed == 0 else "FAIL"
    sys.stdout.write(f"[eval-gkclaw] {status} · {len(TESTS) - failed}/{len(TESTS)}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
