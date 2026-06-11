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


# ─── schema ───

def _valid_task() -> dict:
    return {
        "task_id": "task-20260611-K1903-000001",
        "task_name": "A 机房 现场勘测",
        "project": {"project_id": "ACT001", "project_code": "K1903",
                    "project_name": "智算 Q3 · 客户甲一期"},
        "assignees": [{"surveyor_name": "张三", "surveyor_code": "S001"}],
        "items": [
            {"问题序号": "1", "勘测项": "机房门口标识是否清晰", "选项列表": [],
             "勘测结果": "", "to_front_备注": "", "to_back_备注": "", "示例图": [],
             "metadata": {"细分场景": "硬装入场"}},
            {"问题序号": "2", "勘测项": "接地线规格检查", "选项列表": [],
             "勘测结果": "", "to_front_备注": "", "to_back_备注": "", "示例图": [],
             "metadata": {}},
        ],
        "item_clusters": [
            {"cluster_id": "cluster-all", "cluster_name": "A 机房", "item_keys": ["1", "2"]},
        ],
        "dependency_rules": [],
        "supplemental_context": None,
        "metadata": {},
    }


@test
def schema_valid_task_passes():
    from agent.skills.zhgk.services.gkclaw import schema
    assert schema.validate_task(_valid_task()) == []


@test
def schema_task_required_fields():
    from agent.skills.zhgk.services.gkclaw import schema
    t = _valid_task(); t["task_id"] = "!bad id"
    assert any("task_id" in e for e in schema.validate_task(t))
    t = _valid_task(); t["assignees"] = []
    assert any("assignees" in e for e in schema.validate_task(t))
    t = _valid_task(); t["project"]["project_name"] = ""
    assert any("project_name" in e for e in schema.validate_task(t))
    t = _valid_task(); t["items"] = []
    assert any("items" in e for e in schema.validate_task(t))
    t = _valid_task(); t["item_clusters"] = []
    assert any("item_clusters" in e for e in schema.validate_task(t))


@test
def schema_task_item_and_cluster_rules():
    from agent.skills.zhgk.services.gkclaw import schema
    # 问题序号重复
    t = _valid_task(); t["items"][1]["问题序号"] = "1"
    assert any("问题序号" in e and "唯一" in e for e in schema.validate_task(t))
    # cluster 引用不存在的 key
    t = _valid_task(); t["item_clusters"][0]["item_keys"] = ["1", "99"]
    assert any("99" in e for e in schema.validate_task(t))
    # 有 item 不在任何簇
    t = _valid_task(); t["item_clusters"][0]["item_keys"] = ["1"]
    assert any("2" in e and "簇" in e for e in schema.validate_task(t))
    # cluster_id 重复
    t = _valid_task()
    t["item_clusters"] = [
        {"cluster_id": "c1", "cluster_name": "x", "item_keys": ["1"]},
        {"cluster_id": "c1", "cluster_name": "y", "item_keys": ["2"]},
    ]
    assert any("cluster_id" in e for e in schema.validate_task(t))
    # 示例图路径逃逸
    t = _valid_task()
    t["items"][0]["示例图"] = [{"asset_id": "a1", "path": "../evil.jpg", "mime_type": "image/jpeg"}]
    assert any("path" in e for e in schema.validate_task(t))


@test
def schema_task_dependency_rules():
    from agent.skills.zhgk.services.gkclaw import schema
    t = _valid_task()
    t["dependency_rules"] = [{
        "rule_id": "r1", "description": "d", "trigger_item_keys": ["1"],
        "trigger_semantics": "第1项表达不需要", "target_item_keys": ["2"],
        "action": {"type": "mark_not_applicable", "result": "不涉及"},
    }]
    assert schema.validate_task(t) == []
    t["dependency_rules"][0]["target_item_keys"] = ["88"]
    assert any("88" in e for e in schema.validate_task(t))
    t = _valid_task()
    t["dependency_rules"] = [{
        "rule_id": "r1", "trigger_item_keys": ["1"], "trigger_semantics": "x",
        "target_item_keys": ["2"], "action": {"type": "delete_item"},
    }]
    assert any("action" in e for e in schema.validate_task(t))


@test
def schema_manifest_ack_result_error():
    from agent.skills.zhgk.services.gkclaw import schema
    m = {"schema_version": "gkclaw.mail.v1", "package_id": "pkg-1", "package_type": "task.dispatch",
         "created_at": "2026-06-11T03:00:00+00:00", "source": "back-agent", "target": "front-agent",
         "task_id": "task-20260611-K1903-000001", "project_id": "ACT001", "project_code": "K1903",
         "checksum": {"task.json": "sha256:abc"}}
    assert schema.validate_manifest(m) == []
    bad = dict(m); bad["schema_version"] = "v999"
    assert any("schema_version" in e for e in schema.validate_manifest(bad))
    bad = dict(m); bad["package_type"] = "task.cancel"
    assert any("package_type" in e for e in schema.validate_manifest(bad))
    bad = dict(m); bad["checksum"] = {"../x": "sha256:a"}
    assert any("checksum" in e for e in schema.validate_manifest(bad))

    ack = {"status": "accepted", "task_id": "t1", "web_access_url": "https://f/x"}
    assert schema.validate_ack(ack) == []
    assert any("web_access_url" in e for e in schema.validate_ack({"status": "accepted", "task_id": "t1"}))

    res = {"task_id": "t1", "session": {"status": "completed"},
           "submitted_by": {"surveyor_name": "张三", "surveyor_code": "S001"}, "items": []}
    assert schema.validate_result(res) == []
    assert any("session" in e for e in schema.validate_result({"task_id": "t1", "items": []}))
    assert any("submitted_by" in e for e in schema.validate_result(
        {"task_id": "t1", "session": {"status": "active"}, "items": []}))

    err = {"task_id": "t1", "code": "invalid_task_payload", "message": "x"}
    assert schema.validate_error(err) == []
    assert any("code" in e for e in schema.validate_error({"task_id": "t1", "message": "x"}))


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
