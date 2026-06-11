# GKCLAW 邮件链路（zhgk = backagent）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AIDA 的 zhgk skill 作为 GKCLAW backagent，通过 mailgw 邮件网关完成「任务下发 ZIP → 收 ACK → 收阶段/最终结果 → 回流勘测表」的全链路。

**Architecture:** 全部代码落 AIDA 仓（`D:\.claude_workplace\aida`）。协议层（ids/schema/package/registry/mapping/dispatch/ingest）放 `agent/skills/zhgk/services/gkclaw/`；发送走 `agent/mailer.py` 新增的 mailgw backend，接收走新增统一收件入口 `agent/mailbox.py`（均 urllib，过 lint_no_naked_send）；流水线在 confirm_table 与 wait_survey 之间插入 `task_dispatch` step（HITL，仅 survey_work），wait_survey 的 check_inputs 增加邮件拉取钩子；final 结果转写为 `Input/已填写_全量勘测结果表.xlsx` 复用现有合并通道。mailgw 仓零改动。

**Tech Stack:** Python 3.11+（stdlib zipfile/hashlib/urllib/json）+ openpyxl；测试用 `agent/evals/eval_gkclaw.py`（assert 式离线回归，仓内 evals 惯例，无 pytest）；守门 = 仓内 10 个 lint 脚本。

---

## 设计决策速查（已与用户确认）

| 决策点 | 结论 |
|---|---|
| 落点 | 全部在 AIDA 仓；mailgw 仓零改动（运维仅需把 frontagent 邮箱域加白名单） |
| items 来源 | 全量勘测结果表中 `勘测方法=="现场勘测"` 的行 |
| 字段映射 | 问题序号=str(序号)；勘测项=检查内容；选项列表=[]；to_front_备注=底表 join 的`视频勘测背景知识`（前缀`【勘测要素/项目】`，`语音助手背景知识`不同则附加）；to_back_备注=""；示例图=[]；溯源进 item.metadata |
| 底表 join | 下发时按自然键 `(细分场景,勘测要素,项目,检查内容)` 回连底表取背景知识列；join 失败→空+警告不阻断 |
| item_clusters | **物理空间维度**。v1 底表无该字段→单一兜底簇 `cluster-all`，cluster_name=room_name（空则「全部条目」）；`derive_clusters(cluster_field=None)` 预留按列分簇 |
| dependency_rules | v1 下发空数组 |
| assignees | project payload `assignees` 或 `RunTime/gkclaw/assignees.json`；缺失→文件型 HITL 阻断 |
| 下发范围 | **仅 survey_work 意图**（supplement 不开放，用户拍板）；复勘轮结构性不重发（DAG 不回经 task_dispatch） |
| 重发语义 | 契约无撤销包类型：内容变更重发=新 task_id，旧任务标 `superseded`，其回传只落档不合并；confirm_table redo 同时清 dispatch_decision |
| 表指纹 | 下发时记全量表 sha256；final 合并前校验一致，不一致→不合并+告警 |
| staged | 只记录+展示，不推进流程；final（session.status=="completed"）才转写已填写表 |
| 双源冲突 | 先到先得：Input/ 已有待合并表时邮件结果暂存 `RunTime/gkclaw/<task>/pending_results/`+告警，不覆盖（用户拍板） |
| 收件箱共享 | 只 save 附件、不调 read 接口（避免标已读）；自建 mail_id 扫描账本 `mail_scan.json` |
| dry-run | `AIDA_SEND_EMAIL≠1` 时建包+登记+标 dry_run，不发邮件 |
| 状态机 | planned→dispatched→accepted→staged_returned→completed；failed/quarantined/superseded；无 in_progress（无 App 事件通道） |
| 幂等（§20） | 同 package_id 同 checksum=duplicate；同 package_id 异 checksum=conflict；final 后 staged=quarantine；final 后异内容 final=conflict；未知 task_id=quarantine |
| 安全 | submitted_by.surveyor_code ∉ assignees → 整包隔离；ZIP 路径禁绝对/禁 `..`；密钥只进 .env |
| 真相位置 | 任务状态真相=`ProjectData/RunTime/gkclaw/<task_id>/`（文件，单写者）；run 关联=project_info.json 的 `gkclaw_task_id` |

## 文件结构

```
aida/
├─ agent/
│  ├─ mailer.py                                 # 修改：+mailgw backend（urllib POST /api/send）
│  ├─ mailbox.py                                # 新增：统一收件入口（mailgw inbox API 客户端，urllib）
│  ├─ evals/eval_gkclaw.py                      # 新增：离线契约回归（assert 式，逐任务追加）
│  └─ skills/zhgk/
│     ├─ skill.py                               # 修改：插入 TaskDispatchStep + resume 处理 + step_retry_keys
│     ├─ sdui.py                                # 修改：步骤名册/宏观阶段/新增 GKCLAW 状态卡
│     ├─ steps/
│     │  ├─ __init__.py                         # 修改：导出 TaskDispatchStep
│     │  ├─ _intent_guard.py                    # 修改：task_dispatch → {survey_work}
│     │  ├─ task_dispatch.py                    # 新增：下发 step（HITL）
│     │  ├─ confirm_table.py                    # 修改：redo 时清 dispatch_decision（在 skill.py 改）
│     │  └─ wait_survey.py                      # 修改：check_inputs 增加邮件拉取钩子 + 状态 note
│     └─ services/gkclaw/
│        ├─ __init__.py                         # 新增：空包标记
│        ├─ ids.py                              # 新增：task_id/package_id 生成与校验
│        ├─ schema.py                           # 新增：manifest/task/ack/result/error 校验
│        ├─ package.py                          # 新增：建包/解析/checksum/路径安全
│        ├─ registry.py                         # 新增：状态机+幂等账本（文件存储）
│        ├─ mapping.py                          # 新增：表→task.json（含分簇+底表 join）
│        ├─ dispatch.py                         # 新增：下发服务
│        └─ ingest.py                           # 新增：收件处理（ack/result/error→落库/转写）
├─ skills/zhgk/SKILL.md                         # 修改：A 层流程表 +task_dispatch 行（lint_skill_contract）
├─ docs/50_数据与接口/
│  ├─ back-agent-development-guide_ch.md        # 新增：契约文档入库（从邮件仓复制）
│  └─ GKCLAW邮件链路.md                          # 新增：实现说明+联调手册+验收对照
├─ AGENTS.md                                    # 修改：核心模块表 +「邮件收件」行
├─ agent/.env.example                           # 修改：+MAILGW/GKCLAW 配置块
└─ ROADMAP.md                                   # 修改：立项小节（任务唯一真相）
```

**约定（全部任务通用）：**
- 工作目录：`D:\.claude_workplace\aida`，分支 `feat/gkclaw-mail-link`（自 master）。
- Python 解释器：`agent\.venv\Scripts\python.exe`（Task 0 确保存在）。
- 测试命令：`agent\.venv\Scripts\python.exe agent\evals\eval_gkclaw.py`，期望输出末行 `[eval-gkclaw] OK · N/N`。
- 每个任务收尾跑受影响的守门；**最终 Task 13 跑全部 10 个守门**。commit 不 push（仓规：push 前向用户确认）。
- 所有新文件 UTF-8、中文 docstring、风格对齐仓内现有代码（见 confirm_table.py / table_filter.py）。

---

### Task 0: 分支、venv、ROADMAP 立项、契约文档入库

**Files:**
- Create: `docs/50_数据与接口/back-agent-development-guide_ch.md`（复制自 `D:\.claude_workplace\邮件\back-agent-development-guide_ch.md`）
- Modify: `ROADMAP.md`（文末「文档治理 backlog」节之前插入立项小节）

- [ ] **Step 0.1: 创建分支**

```powershell
git -C D:\.claude_workplace\aida checkout -b feat/gkclaw-mail-link
```
Expected: `Switched to a new branch 'feat/gkclaw-mail-link'`

- [ ] **Step 0.2: 确保 venv 与依赖**

```powershell
Test-Path D:\.claude_workplace\aida\agent\.venv\Scripts\python.exe
```
若 False：
```powershell
python -m venv D:\.claude_workplace\aida\agent\.venv
D:\.claude_workplace\aida\agent\.venv\Scripts\python.exe -m pip install -r D:\.claude_workplace\aida\agent\requirements.txt
```
Expected: 安装成功（pywin32 仅 win32；网络代理告警可忽略，以最终 `Successfully installed` 为准）。

- [ ] **Step 0.3: 契约文档入库**

```powershell
Copy-Item D:\.claude_workplace\邮件\back-agent-development-guide_ch.md D:\.claude_workplace\aida\docs\50_数据与接口\back-agent-development-guide_ch.md
```

- [ ] **Step 0.4: ROADMAP 立项**

在 `ROADMAP.md` 的「## 文档治理 backlog」标题**之前**插入：

```markdown
---

## GKCLAW 邮件链路（zhgk = backagent）· 2026-06-11 立项

> 契约真相源：[docs/50_数据与接口/back-agent-development-guide_ch.md](docs/50_数据与接口/back-agent-development-guide_ch.md)
> 设计决策与边界：见实现说明 docs/50_数据与接口/GKCLAW邮件链路.md（完成后补链）
> 分支：feat/gkclaw-mail-link

- [ ] gkclaw 协议层（ids/schema/package/registry/mapping，eval_gkclaw 离线回归）
- [ ] mailer.py mailgw backend + mailbox.py 统一收件入口
- [ ] dispatch/ingest 服务（下发建包发送；ack/result/error 处理、final 转写已填写表）
- [ ] task_dispatch step（HITL·仅 survey_work）+ wait_survey 拉取钩子
- [ ] A 层 SKILL.md 契约同步 + SDUI 状态卡
- [ ] .env.example / AGENTS.md 收件入口行 / GKCLAW邮件链路.md / docs site 重生成
- [ ] 全部 10 守门绿 + 真实联调（待 frontagent 邮箱配置，见实现说明§联调）
```

- [ ] **Step 0.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add docs/50_数据与接口/back-agent-development-guide_ch.md ROADMAP.md
git -C D:\.claude_workplace\aida commit -m "docs(gkclaw): 立项 GKCLAW 邮件链路 + back-agent 契约文档入库"
```

---

### Task 1: eval 骨架 + gkclaw/ids.py

**Files:**
- Create: `agent/evals/eval_gkclaw.py`
- Create: `agent/skills/zhgk/services/gkclaw/__init__.py`
- Create: `agent/skills/zhgk/services/gkclaw/ids.py`

- [ ] **Step 1.1: 写 eval 骨架与 ids 的失败测试**

创建 `agent/evals/eval_gkclaw.py`：

```python
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
    d = Path(tempfile.mkdtemp(prefix="gkclaw-eval-"))
    return d


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
    assert ids.sanitize_code("智算K19/03") == "K19.03".replace(".", "") or ids.sanitize_code("智算K19/03") == "K1903"
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
```

注意 `ids_sanitize_project_code` 里第二个断言写死期望：净化规则=剔除 `[A-Za-z0-9._-]` 以外字符，所以 `"智算K19/03"` → `"K1903"`。把该行改为单一断言：

```python
    assert ids.sanitize_code("智算K19/03") == "K1903"
```

- [ ] **Step 1.2: 跑 eval 确认失败**

```powershell
D:\.claude_workplace\aida\agent\.venv\Scripts\python.exe D:\.claude_workplace\aida\agent\evals\eval_gkclaw.py
```
Expected: 4 个 ❌（`ModuleNotFoundError`/`ImportError`），末行 `[eval-gkclaw] FAIL · 0/4`

- [ ] **Step 1.3: 实现 ids.py**

创建空 `agent/skills/zhgk/services/gkclaw/__init__.py`：

```python
"""gkclaw · GKCLAW 邮件链路协议层（zhgk = backagent）

契约真相源：docs/50_数据与接口/back-agent-development-guide_ch.md（gkclaw.mail.v1）
模块：ids / schema / package / registry / mapping / dispatch / ingest
"""
```

创建 `agent/skills/zhgk/services/gkclaw/ids.py`：

```python
"""
gkclaw ids · 标识符生成与校验（契约 §6）

task_id:    task-{YYYYMMDD}-{净化 project_code}-{6位序列}，registry 目录下 seq.txt 持久化
            （单写者假设：uvicorn workers=1，见部署手册）
package_id: pkg-{YYYYMMDD}-{uuid4 前 12 位 hex}
路径安全:    ZIP 内仅允许相对路径、正斜杠、无 ..（契约 §6 path / §22 安全基线）
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

# 契约 §6 推荐正则
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_CODE_ALLOWED = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_code(code: str) -> str:
    """project_code → task_id 片段：剔除非法字符，空则回退 ZHGK。"""
    cleaned = _CODE_ALLOWED.sub("", code or "")
    return cleaned or "ZHGK"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def new_task_id(project_code: str, registry_root: Path | str) -> str:
    """生成全局唯一 task_id。registry_root 下 seq.txt 持久化序列（单写者）。"""
    root = Path(registry_root)
    root.mkdir(parents=True, exist_ok=True)
    seq_file = root / "seq.txt"
    seq = 0
    if seq_file.exists():
        try:
            seq = int(seq_file.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            seq = 0
    seq += 1
    seq_file.write_text(str(seq), encoding="utf-8")
    tid = f"task-{_today()}-{sanitize_code(project_code)}-{seq:06d}"
    if not TASK_ID_RE.match(tid):  # project_code 极端超长时兜底
        tid = f"task-{_today()}-ZHGK-{seq:06d}"
    return tid


def new_package_id() -> str:
    return f"pkg-{_today()}-{uuid.uuid4().hex[:12]}"


def is_valid_task_id(s: str) -> bool:
    return bool(TASK_ID_RE.match(s or ""))


def is_safe_zip_path(p: str) -> bool:
    """ZIP 内相对路径安全检查：非空、无反斜杠、非绝对、无 .. 段、无盘符。"""
    if not p or "\\" in p or p.startswith("/") or ":" in p:
        return False
    parts = p.split("/")
    return all(part not in ("", "..", ".") for part in parts)
```

- [ ] **Step 1.4: 跑 eval 确认通过**

```powershell
D:\.claude_workplace\aida\agent\.venv\Scripts\python.exe D:\.claude_workplace\aida\agent\evals\eval_gkclaw.py
```
Expected: `[eval-gkclaw] OK · 4/4`

- [ ] **Step 1.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add agent/evals/eval_gkclaw.py agent/skills/zhgk/services/gkclaw/
git -C D:\.claude_workplace\aida commit -m "feat(gkclaw): eval 骨架 + 标识符生成与 ZIP 路径安全校验"
```

---

### Task 2: gkclaw/schema.py（payload 契约校验）

**Files:**
- Create: `agent/skills/zhgk/services/gkclaw/schema.py`
- Modify: `agent/evals/eval_gkclaw.py`（追加测试）

- [ ] **Step 2.1: 追加失败测试**

在 `eval_gkclaw.py` 的 `# ─── main ───` 之前追加：

```python
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
```

- [ ] **Step 2.2: 跑 eval 确认新增 5 个失败**

```powershell
D:\.claude_workplace\aida\agent\.venv\Scripts\python.exe D:\.claude_workplace\aida\agent\evals\eval_gkclaw.py
```
Expected: `[eval-gkclaw] FAIL · 4/9`

- [ ] **Step 2.3: 实现 schema.py**

```python
"""
gkclaw schema · 四种 payload + manifest 的契约校验（契约 §9-§14/§17/§19）

全部校验函数返回 list[str]（空 = 通过），不抛异常——调用方据此决定拒发/隔离。
按字符串比较 item key（契约 §6「所有引用建议按字符串值比较」）。
"""
from __future__ import annotations

from typing import Any

from .ids import is_valid_task_id, is_safe_zip_path

SCHEMA_VERSION = "gkclaw.mail.v1"
PACKAGE_TYPES = ("task.dispatch", "task.import_ack", "task.result", "task.error")


def _s(d: dict, key: str) -> str:
    v = d.get(key, "")
    return v.strip() if isinstance(v, str) else ""


def validate_manifest(m: dict[str, Any]) -> list[str]:
    v: list[str] = []
    if _s(m, "schema_version") != SCHEMA_VERSION:
        v.append(f"schema_version 不支持: {m.get('schema_version')!r}（期望 {SCHEMA_VERSION}）")
    if _s(m, "package_type") not in PACKAGE_TYPES:
        v.append(f"package_type 非法: {m.get('package_type')!r}")
    for k in ("package_id", "created_at", "source", "target", "task_id"):
        if not _s(m, k):
            v.append(f"manifest 缺必填字段 {k}")
    checksum = m.get("checksum")
    if not isinstance(checksum, dict) or not checksum:
        v.append("manifest 缺 checksum 映射")
    else:
        for path, digest in checksum.items():
            if not is_safe_zip_path(str(path)):
                v.append(f"checksum 含不安全路径: {path!r}")
            if not str(digest).startswith("sha256:"):
                v.append(f"checksum 值须为 sha256:<hex>: {path}")
    return v


def validate_task(t: dict[str, Any]) -> list[str]:
    v: list[str] = []
    if not is_valid_task_id(_s(t, "task_id")):
        v.append(f"task_id 不合契约正则: {t.get('task_id')!r}")
    if not _s(t, "task_name"):
        v.append("task_name 必填")
    project = t.get("project") or {}
    for k in ("project_id", "project_code", "project_name"):
        if not _s(project, k):
            v.append(f"project.{k} 必填")

    assignees = t.get("assignees") or []
    if not assignees:
        v.append("assignees 至少包含一个人员")
    for a in assignees:
        if not _s(a, "surveyor_name") or not _s(a, "surveyor_code"):
            v.append(f"assignees 成员缺 surveyor_name/surveyor_code: {a!r}")

    items = t.get("items") or []
    if not items:
        v.append("items 至少包含一个工勘项")
    keys: list[str] = []
    for it in items:
        key = _s(it, "问题序号")
        if not key:
            v.append(f"工勘项缺 问题序号: {it.get('勘测项', '')!r}")
            continue
        if key in keys:
            v.append(f"问题序号 {key} 不唯一（任务内必须唯一）")
        keys.append(key)
        if not _s(it, "勘测项"):
            v.append(f"工勘项 {key} 缺 勘测项")
        if not isinstance(it.get("选项列表", []), list):
            v.append(f"工勘项 {key} 选项列表须为数组")
        for img in it.get("示例图") or []:
            if not is_safe_zip_path(_s(img, "path")):
                v.append(f"工勘项 {key} 示例图 path 不安全: {img.get('path')!r}")
    key_set = set(keys)

    clusters = t.get("item_clusters") or []
    if not clusters:
        v.append("item_clusters 正式任务必须非空（无分组也要兜底簇）")
    cluster_ids: set[str] = set()
    covered: set[str] = set()
    for c in clusters:
        cid = _s(c, "cluster_id")
        if not cid:
            v.append(f"簇缺 cluster_id: {c!r}")
        elif cid in cluster_ids:
            v.append(f"cluster_id {cid} 重复")
        cluster_ids.add(cid)
        c_keys = c.get("item_keys") or []
        if not c_keys:
            v.append(f"簇 {cid} item_keys 为空")
        for k in c_keys:
            if str(k) not in key_set:
                v.append(f"簇 {cid} 引用不存在的工勘项 {k}")
            covered.add(str(k))
    for k in keys:
        if k not in covered:
            v.append(f"工勘项 {k} 未出现在任何簇中（每项必须至少入一簇）")

    rule_ids: set[str] = set()
    for r in t.get("dependency_rules") or []:
        rid = _s(r, "rule_id")
        if not rid:
            v.append(f"依赖规则缺 rule_id: {r!r}")
        elif rid in rule_ids:
            v.append(f"rule_id {rid} 重复")
        rule_ids.add(rid)
        if not _s(r, "trigger_semantics"):
            v.append(f"规则 {rid} 缺 trigger_semantics（须写自然语言语义）")
        for field in ("trigger_item_keys", "target_item_keys"):
            for k in r.get(field) or []:
                if str(k) not in key_set:
                    v.append(f"规则 {rid} {field} 引用不存在的工勘项 {k}")
        action = r.get("action") or {}
        if action.get("type") != "mark_not_applicable":
            v.append(f"规则 {rid} action.type 仅支持 mark_not_applicable")
    return v


def validate_ack(a: dict[str, Any]) -> list[str]:
    v: list[str] = []
    for k in ("status", "task_id", "web_access_url"):
        if not _s(a, k):
            v.append(f"ack 缺必填字段 {k}")
    return v


def validate_result(r: dict[str, Any]) -> list[str]:
    v: list[str] = []
    if not _s(r, "task_id"):
        v.append("result 缺 task_id")
    session = r.get("session") or {}
    if not _s(session, "status"):
        v.append("result 缺 session.status（最终性唯一权威字段）")
    submitted = r.get("submitted_by") or {}
    if not _s(submitted, "surveyor_code"):
        v.append("result 缺 submitted_by.surveyor_code")
    if not isinstance(r.get("items", []), list):
        v.append("result items 须为数组")
    return v


def validate_error(e: dict[str, Any]) -> list[str]:
    v: list[str] = []
    for k in ("task_id", "code", "message"):
        if not _s(e, k):
            v.append(f"error 缺必填字段 {k}")
    return v
```

- [ ] **Step 2.4: 跑 eval 确认通过**

Expected: `[eval-gkclaw] OK · 9/9`

- [ ] **Step 2.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add agent/evals/eval_gkclaw.py agent/skills/zhgk/services/gkclaw/schema.py
git -C D:\.claude_workplace\aida commit -m "feat(gkclaw): payload/manifest 契约校验（簇引用·依赖规则·路径安全）"
```

---

### Task 3: gkclaw/package.py（建包/解析/防篡改/防逃逸）

**Files:**
- Create: `agent/skills/zhgk/services/gkclaw/package.py`
- Modify: `agent/evals/eval_gkclaw.py`（追加测试）

- [ ] **Step 3.1: 追加失败测试**

```python
# ─── package ───

@test
def package_build_parse_roundtrip():
    from agent.skills.zhgk.services.gkclaw import package
    out = tmpdir()
    task = _valid_task()
    zp = package.build_package(
        package_type="task.dispatch", task_id=task["task_id"],
        project=task["project"], payload=task,
        assets={"assets/items/1/example-1.jpg": b"\xff\xd8fakejpg"},
        out_dir=out,
    )
    assert zp.name == f"task-{task['task_id']}.zip"
    parsed = package.parse_package(zp)
    assert parsed["ok"], parsed["errors"]
    assert parsed["manifest"]["package_type"] == "task.dispatch"
    assert parsed["payload"]["task_id"] == task["task_id"]
    assert parsed["payload_name"] == "task.json"
    assert "assets/items/1/example-1.jpg" in parsed["manifest"]["checksum"]


@test
def package_checksum_tamper_detected():
    import zipfile
    from agent.skills.zhgk.services.gkclaw import package
    out = tmpdir()
    task = _valid_task()
    zp = package.build_package(package_type="task.dispatch", task_id=task["task_id"],
                               project=task["project"], payload=task, out_dir=out)
    # 重写 task.json 内容但保留 manifest → checksum 不匹配
    tampered = out / "tampered.zip"
    with zipfile.ZipFile(zp) as src, zipfile.ZipFile(tampered, "w") as dst:
        for name in src.namelist():
            data = src.read(name)
            if name == "task.json":
                data = data.replace(b"K1903", b"HACKED")
            dst.writestr(name, data)
    parsed = package.parse_package(tampered)
    assert not parsed["ok"]
    assert any("checksum" in e for e in parsed["errors"])


@test
def package_path_escape_rejected():
    import json, zipfile
    from agent.skills.zhgk.services.gkclaw import package
    out = tmpdir()
    evil = out / "evil.zip"
    manifest = {"schema_version": "gkclaw.mail.v1", "package_id": "pkg-x",
                "package_type": "task.result", "created_at": "2026-06-11T00:00:00+00:00",
                "source": "front-agent", "target": "back-agent", "task_id": "t1",
                "checksum": {"result.json": "sha256:dead"}}
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("result.json", "{}")
        zf.writestr("../escape.txt", "evil")
    parsed = package.parse_package(evil)
    assert not parsed["ok"]
    assert any("路径" in e or "path" in e.lower() for e in parsed["errors"])


@test
def package_missing_manifest_and_type_mismatch():
    import json, zipfile
    from agent.skills.zhgk.services.gkclaw import package
    out = tmpdir()
    z1 = out / "nomanifest.zip"
    with zipfile.ZipFile(z1, "w") as zf:
        zf.writestr("task.json", "{}")
    parsed = package.parse_package(z1)
    assert not parsed["ok"] and any("manifest" in e for e in parsed["errors"])

    # 类型与 payload 文件不匹配：声明 task.result 但只有 task.json
    z2 = out / "mismatch.zip"
    payload = json.dumps({"x": 1})
    import hashlib
    digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
    manifest = {"schema_version": "gkclaw.mail.v1", "package_id": "pkg-y",
                "package_type": "task.result", "created_at": "2026-06-11T00:00:00+00:00",
                "source": "front-agent", "target": "back-agent", "task_id": "t1",
                "checksum": {"task.json": digest}}
    with zipfile.ZipFile(z2, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("task.json", payload)
    parsed = package.parse_package(z2)
    assert not parsed["ok"] and any("result.json" in e for e in parsed["errors"])


@test
def package_unlisted_files_policy():
    import json, zipfile, hashlib
    from agent.skills.zhgk.services.gkclaw import package
    out = tmpdir()
    payload = json.dumps({"task_id": "t1", "session": {"status": "active"},
                          "submitted_by": {"surveyor_code": "S001"}, "items": []})
    digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
    manifest = {"schema_version": "gkclaw.mail.v1", "package_id": "pkg-z",
                "package_type": "task.result", "created_at": "2026-06-11T00:00:00+00:00",
                "source": "front-agent", "target": "back-agent", "task_id": "t1",
                "checksum": {"result.json": digest}}
    # evidence 未列入 manifest → 仅 warning；根目录未列文件 → error
    z1 = out / "evidence-unlisted.zip"
    with zipfile.ZipFile(z1, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("result.json", payload)
        zf.writestr("evidence/photo1.jpg", b"img")
    parsed = package.parse_package(z1)
    assert parsed["ok"], parsed["errors"]
    assert any("evidence" in w for w in parsed["warnings"])

    z2 = out / "root-unlisted.zip"
    with zipfile.ZipFile(z2, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("result.json", payload)
        zf.writestr("extra.json", "{}")
    parsed = package.parse_package(z2)
    assert not parsed["ok"] and any("extra.json" in e for e in parsed["errors"])


@test
def package_extract_evidence():
    from agent.skills.zhgk.services.gkclaw import package
    out = tmpdir()
    res = {"task_id": "task-20260611-K1903-000009", "session": {"status": "completed"},
           "submitted_by": {"surveyor_name": "张三", "surveyor_code": "S001"}, "items": []}
    zp = package.build_package(package_type="task.result", task_id=res["task_id"],
                               project={"project_id": "ACT001", "project_code": "K1903"},
                               payload=res, assets={"evidence/p1.jpg": b"img1"}, out_dir=out)
    dest = out / "ev"
    saved = package.extract_files(zp, ["evidence/p1.jpg"], dest)
    assert saved[0].read_bytes() == b"img1"
    assert saved[0] == dest / "evidence" / "p1.jpg"
```

- [ ] **Step 3.2: 跑 eval 确认新增 6 个失败**

Expected: `[eval-gkclaw] FAIL · 9/15`

- [ ] **Step 3.3: 实现 package.py**

```python
"""
gkclaw package · ZIP 包构建与解析（契约 §8/§9）

构建：manifest.json + payload + assets，全文件 sha256 进 manifest.checksum。
解析：五道校验 —— manifest 可解析 / schema_version·必填 / package_type↔payload 匹配 /
checksum 防篡改 / 路径安全（拒绝 ..·绝对路径）。manifest 未列出的文件：
evidence/ 下仅 warning（现场证据宽容），其余视为违规（防夹带）。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import ids, schema

# 包类型 → (zip 文件名前缀, payload 文件名)（契约 §8）
PACKAGE_LAYOUT: dict[str, tuple[str, str]] = {
    "task.dispatch":   ("task",   "task.json"),
    "task.import_ack": ("ack",    "ack.json"),
    "task.result":     ("result", "result.json"),
    "task.error":      ("error",  "error.json"),
}


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    return sha256_bytes(Path(path).read_bytes())


def build_package(
    *,
    package_type: str,
    task_id: str,
    project: dict[str, Any],
    payload: dict[str, Any],
    assets: dict[str, bytes] | None = None,
    out_dir: Path | str,
    source: str = "back-agent",
    target: str = "front-agent",
    package_id: str | None = None,
) -> Path:
    """构建 gkclaw.mail.v1 ZIP，返回 zip 路径。assets 键 = ZIP 内相对路径。"""
    import zipfile

    prefix, payload_name = PACKAGE_LAYOUT[package_type]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"{prefix}-{task_id}.zip"

    payload_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    checksum: dict[str, str] = {payload_name: sha256_bytes(payload_bytes)}
    for arcname, data in (assets or {}).items():
        if not ids.is_safe_zip_path(arcname):
            raise ValueError(f"资产路径不安全: {arcname!r}")
        checksum[arcname] = sha256_bytes(data)

    manifest = {
        "schema_version": schema.SCHEMA_VERSION,
        "package_id": package_id or ids.new_package_id(),
        "package_type": package_type,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "source": source,
        "target": target,
        "task_id": task_id,
        "project_id": str((project or {}).get("project_id", "")),
        "project_code": str((project or {}).get("project_code", "")),
        "checksum": checksum,
    }
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(payload_name, payload_bytes)
        for arcname, data in (assets or {}).items():
            zf.writestr(arcname, data)
    return zip_path


def parse_package(zip_path: Path | str) -> dict[str, Any]:
    """解析并校验入站 ZIP。返回:
    {ok, errors[], warnings[], manifest, payload, payload_name, files[]}"""
    import zipfile

    result: dict[str, Any] = {"ok": False, "errors": [], "warnings": [],
                              "manifest": None, "payload": None,
                              "payload_name": "", "files": []}
    errors: list[str] = result["errors"]
    try:
        zf = zipfile.ZipFile(zip_path)
    except Exception as e:  # noqa: BLE001
        errors.append(f"ZIP 无法打开: {e}")
        return result

    with zf:
        names = zf.namelist()
        result["files"] = names
        # 1. 路径安全（目录项以 / 结尾的跳过内容校验但仍查安全）
        for n in names:
            check = n[:-1] if n.endswith("/") else n
            if check and not ids.is_safe_zip_path(check):
                errors.append(f"ZIP 含不安全路径: {n!r}")
        if errors:
            return result

        # 2. manifest 存在且可解析
        if "manifest.json" not in names:
            errors.append("缺 manifest.json")
            return result
        try:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            errors.append(f"manifest.json 解析失败: {e}")
            return result
        result["manifest"] = manifest
        errors.extend(schema.validate_manifest(manifest))
        if errors:
            return result

        # 3. package_type ↔ payload 文件匹配
        package_type = manifest["package_type"]
        payload_name = PACKAGE_LAYOUT[package_type][1]
        result["payload_name"] = payload_name
        if payload_name not in names:
            errors.append(f"包类型 {package_type} 缺 payload 文件 {payload_name}")
            return result

        # 4. checksum 防篡改（manifest 列出的每个文件都必须存在且匹配）
        checksum: dict[str, str] = manifest["checksum"]
        if payload_name not in checksum:
            errors.append(f"manifest.checksum 未覆盖 payload {payload_name}")
        for arcname, expected in checksum.items():
            if arcname not in names:
                errors.append(f"manifest 声明的文件不存在: {arcname}")
                continue
            actual = sha256_bytes(zf.read(arcname))
            if actual != expected:
                errors.append(f"checksum 不匹配: {arcname}")

        # 5. 未列入 manifest 的文件：evidence/ 宽容（warning），其余拒绝
        listed = set(checksum) | {"manifest.json"}
        for n in names:
            if n.endswith("/") or n in listed:
                continue
            if n.startswith("evidence/"):
                result["warnings"].append(f"evidence 文件未列入 manifest（放行）: {n}")
            else:
                errors.append(f"未列入 manifest 的文件: {n}")
        if errors:
            return result

        # 6. 解析 payload
        try:
            result["payload"] = json.loads(zf.read(payload_name).decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{payload_name} 解析失败: {e}")
            return result

    result["ok"] = True
    return result


def extract_files(zip_path: Path | str, names: list[str], dest_dir: Path | str) -> list[Path]:
    """把 ZIP 内指定文件按相对路径解出到 dest_dir（路径已经 parse 校验过仍二次防御）。"""
    import zipfile

    dest = Path(dest_dir)
    saved: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for n in names:
            if not ids.is_safe_zip_path(n):
                raise ValueError(f"拒绝解出不安全路径: {n!r}")
            target = dest / Path(*n.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(n))
            saved.append(target)
    return saved
```

- [ ] **Step 3.4: 跑 eval 确认通过**

Expected: `[eval-gkclaw] OK · 15/15`

- [ ] **Step 3.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add agent/evals/eval_gkclaw.py agent/skills/zhgk/services/gkclaw/package.py
git -C D:\.claude_workplace\aida commit -m "feat(gkclaw): ZIP 建包与五道校验解析（checksum 防篡改·路径防逃逸）"
```

---

### Task 4: gkclaw/registry.py（状态机 + 幂等账本）

**Files:**
- Create: `agent/skills/zhgk/services/gkclaw/registry.py`
- Modify: `agent/evals/eval_gkclaw.py`（追加测试）

文件布局（真相位置，单写者）：

```
<runtime_dir>/gkclaw/
  seq.txt                       # task_id 序列（ids.py 写）
  mail_scan.json                # 收件扫描账本 {mail_id: verdict}
  _quarantine/                  # 隔离包落盘
  <task_id>/
    state.json                  # 任务状态 {task_id, state, web_access_url, table_fingerprint, ...}
    packages.json               # 包账本 [{package_id, checksum, package_type, direction, disposition, mail_id, at}]
    task.json                   # 下发 payload 快照
    outbox/task-<task_id>.zip   # 下发包
    results/result-001.json …   # 回传版本（staged 多版 + final）
    result-notes.json           # to_back_备注 留档
    evidence/                   # 解出的证据文件
    pending_results/            # 双源冲突时暂存的转写表
```

- [ ] **Step 4.1: 追加失败测试**

```python
# ─── registry ───

def _registry(root=None):
    from agent.skills.zhgk.services.gkclaw.registry import TaskRegistry
    return TaskRegistry(root or tmpdir())


def _create_task(reg, tid="task-20260611-K1903-000001"):
    t = _valid_task()
    t["task_id"] = tid
    return reg.create_task(
        task_id=tid, task_payload=t, zip_path="outbox/x.zip",
        table_fingerprint="sha256:tbl", project=t["project"], dry_run=False,
    )


@test
def registry_create_get_and_states():
    reg = _registry()
    task = _create_task(reg)
    assert task["state"] == "planned"
    reg.set_state(task["task_id"], "dispatched", mailgw_task_id="m1")
    got = reg.get(task["task_id"])
    assert got["state"] == "dispatched" and got["mailgw_task_id"] == "m1"
    assert reg.get("task-not-exists") is None
    assert [t["task_id"] for t in reg.list_tasks()] == [task["task_id"]]
    reg.mark_superseded(task["task_id"])
    assert reg.get(task["task_id"])["state"] == "superseded"


@test
def registry_decide_inbound_idempotency_matrix():
    """契约 §20 幂等/冲突矩阵 + 边界规则。"""
    from agent.skills.zhgk.services.gkclaw.registry import decide_inbound
    base_task = {"task_id": "t1", "state": "dispatched"}
    known = [{"package_id": "p1", "checksum": "sha256:aaa",
              "package_type": "task.import_ack", "disposition": "processed"}]

    # 未知 task_id → quarantine
    d, _ = decide_inbound(None, [], package_type="task.import_ack",
                          package_id="px", checksum="sha256:x", session_status="")
    assert d == "quarantine"
    # 同 package_id 同 checksum → duplicate
    d, _ = decide_inbound(base_task, known, package_type="task.import_ack",
                          package_id="p1", checksum="sha256:aaa", session_status="")
    assert d == "duplicate"
    # 同 package_id 异 checksum → conflict
    d, _ = decide_inbound(base_task, known, package_type="task.import_ack",
                          package_id="p1", checksum="sha256:bbb", session_status="")
    assert d == "conflict"
    # superseded 任务 → archived（落档不生效）
    d, _ = decide_inbound({"task_id": "t1", "state": "superseded"}, [],
                          package_type="task.result", package_id="p2",
                          checksum="sha256:c", session_status="completed")
    assert d == "archived"
    # dispatched 收 ack → processed
    d, _ = decide_inbound(base_task, [], package_type="task.import_ack",
                          package_id="p2", checksum="sha256:c", session_status="")
    assert d == "processed"
    # accepted 收 staged result → processed
    d, _ = decide_inbound({"task_id": "t1", "state": "accepted"}, [],
                          package_type="task.result", package_id="p3",
                          checksum="sha256:d", session_status="active")
    assert d == "processed"
    # completed 后收 staged → quarantine（final 后 staged）
    d, _ = decide_inbound({"task_id": "t1", "state": "completed"}, [],
                          package_type="task.result", package_id="p4",
                          checksum="sha256:e", session_status="active")
    assert d == "quarantine"
    # completed 后收异内容 final → conflict
    d, _ = decide_inbound({"task_id": "t1", "state": "completed"}, [],
                          package_type="task.result", package_id="p5",
                          checksum="sha256:f", session_status="completed")
    assert d == "conflict"
    # error 包任意状态 → processed
    d, _ = decide_inbound(base_task, [], package_type="task.error",
                          package_id="p6", checksum="sha256:g", session_status="")
    assert d == "processed"


@test
def registry_result_versions_and_notes():
    reg = _registry()
    task = _create_task(reg, "task-20260611-K1903-000002")
    p1 = reg.store_result_version(task["task_id"], {"session": {"status": "active"}, "items": []},
                                  final=False)
    p2 = reg.store_result_version(task["task_id"], {"session": {"status": "completed"}, "items": []},
                                  final=True)
    assert p1.name == "result-001.json" and p2.name == "result-002.json"
    got = reg.get(task["task_id"])
    assert got["result_versions"] == 2 and got["final_result"] == "results/result-002.json"
    reg.append_result_notes(task["task_id"], [{"问题序号": "5", "to_back_备注": "[规则自动处理] x"}])
    notes = reg.read_result_notes(task["task_id"])
    assert notes and notes[0]["问题序号"] == "5"


@test
def registry_package_ledger_and_scan_ledger():
    reg = _registry()
    task = _create_task(reg, "task-20260611-K1903-000003")
    reg.record_package(task["task_id"], {"package_id": "p1", "checksum": "sha256:a",
                                         "package_type": "task.import_ack",
                                         "direction": "in", "disposition": "processed",
                                         "mail_id": 7})
    pkgs = reg.packages(task["task_id"])
    assert len(pkgs) == 1 and pkgs[0]["package_id"] == "p1" and pkgs[0]["at"]
    # 扫描账本
    assert reg.scanned_mail_ids() == set()
    reg.mark_mail_scanned(7, "processed")
    reg.mark_mail_scanned(8, "ignored")
    assert reg.scanned_mail_ids() == {7, 8}
```

- [ ] **Step 4.2: 跑 eval 确认新增 4 个失败**

Expected: `[eval-gkclaw] FAIL · 15/19`

- [ ] **Step 4.3: 实现 registry.py**

```python
"""
gkclaw registry · 任务状态机 + 包级幂等账本（契约 §5/§20）

文件存储（真相位置）：<runtime_dir>/gkclaw/<task_id>/{state.json,packages.json,...}
单写者假设（uvicorn workers=1）；写入走 临时文件+os.replace 原子替换。

状态机（v1 简化：无 App 事件通道，不单独维护 in_progress）：
  planned → dispatched → accepted → staged_returned → completed
  任意 → failed / superseded；包级异常 → 隔离（任务状态不动）
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATES = ("planned", "dispatched", "accepted", "staged_returned",
          "completed", "failed", "superseded")
DISPOSITIONS = ("processed", "duplicate", "conflict", "quarantine", "archived", "ignored")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def decide_inbound(
    task: dict[str, Any] | None,
    known_packages: list[dict[str, Any]],
    *,
    package_type: str,
    package_id: str,
    checksum: str,
    session_status: str,
) -> tuple[str, str]:
    """纯函数：入站包处置判定（契约 §20 矩阵）。返回 (disposition, note)。"""
    if task is None:
        return "quarantine", "未知 task_id：本地无此任务，留档不创建（契约 §7）"
    for p in known_packages:
        if p.get("package_id") == package_id:
            if p.get("checksum") == checksum:
                return "duplicate", "同 package_id 同 checksum：幂等成功"
            return "conflict", "同 package_id 异 checksum：包冲突，隔离"
    if task.get("state") == "superseded":
        return "archived", "任务已被取代（superseded）：仅留档，不合并不推进"

    if package_type == "task.import_ack":
        if task.get("state") == "completed":
            return "archived", "任务已完成后收到 ACK：留档"
        return "processed", ""
    if package_type == "task.result":
        is_final = session_status == "completed"
        if task.get("state") == "completed":
            if is_final:
                return "conflict", "final 后收到异内容 final：冲突，隔离"
            return "quarantine", "final 后收到阶段性结果：隔离（契约 §20）"
        return "processed", ""
    if package_type == "task.error":
        return "processed", ""
    return "quarantine", f"未知包类型 {package_type}"


class TaskRegistry:
    """任务/包/扫描三本账的文件持久层。"""

    def __init__(self, runtime_dir: Path | str):
        self.root = Path(runtime_dir) / "gkclaw"
        self.root.mkdir(parents=True, exist_ok=True)

    # ── 任务 ──

    def _dir(self, task_id: str) -> Path:
        return self.root / task_id

    def _state_file(self, task_id: str) -> Path:
        return self._dir(task_id) / "state.json"

    def create_task(self, *, task_id: str, task_payload: dict, zip_path: str,
                    table_fingerprint: str, project: dict,
                    dry_run: bool = False, **extra: Any) -> dict:
        d = self._dir(task_id)
        (d / "outbox").mkdir(parents=True, exist_ok=True)
        _atomic_write(d / "task.json", task_payload)
        task = {
            "task_id": task_id,
            "state": "planned",
            "project": dict(project or {}),
            "task_name": task_payload.get("task_name", ""),
            "assignees": task_payload.get("assignees", []),
            "zip_path": zip_path,
            "table_fingerprint": table_fingerprint,
            "dry_run": bool(dry_run),
            "web_access_url": "",
            "result_versions": 0,
            "final_result": "",
            "last_error": "",
            "created_at": _now(),
            "updated_at": _now(),
        }
        task.update(extra)
        _atomic_write(self._state_file(task_id), task)
        _atomic_write(d / "packages.json", [])
        return task

    def get(self, task_id: str) -> dict | None:
        f = self._state_file(task_id)
        if not f.exists():
            return None
        return json.loads(f.read_text(encoding="utf-8"))

    def task_payload(self, task_id: str) -> dict | None:
        f = self._dir(task_id) / "task.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

    def list_tasks(self) -> list[dict]:
        out = []
        for d in sorted(self.root.iterdir()):
            if d.is_dir() and not d.name.startswith("_") and (d / "state.json").exists():
                out.append(json.loads((d / "state.json").read_text(encoding="utf-8")))
        return out

    def save(self, task: dict) -> None:
        task["updated_at"] = _now()
        _atomic_write(self._state_file(task["task_id"]), task)

    def set_state(self, task_id: str, state: str, **extra: Any) -> dict:
        assert state in STATES, f"非法状态 {state}"
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"任务不存在: {task_id}")
        task["state"] = state
        task.update(extra)
        self.save(task)
        return task

    def mark_superseded(self, task_id: str) -> None:
        if self.get(task_id) is not None:
            self.set_state(task_id, "superseded")

    # ── 包账本 ──

    def packages(self, task_id: str) -> list[dict]:
        f = self._dir(task_id) / "packages.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

    def record_package(self, task_id: str, entry: dict) -> None:
        self._dir(task_id).mkdir(parents=True, exist_ok=True)
        entries = self.packages(task_id)
        entries.append({**entry, "at": _now()})
        _atomic_write(self._dir(task_id) / "packages.json", entries)

    # ── 结果版本与备注留档 ──

    def store_result_version(self, task_id: str, payload: dict, *, final: bool) -> Path:
        d = self._dir(task_id) / "results"
        d.mkdir(parents=True, exist_ok=True)
        task = self.get(task_id)
        n = int(task.get("result_versions", 0)) + 1
        p = d / f"result-{n:03d}.json"
        _atomic_write(p, payload)
        task["result_versions"] = n
        if final:
            task["final_result"] = f"results/{p.name}"
        self.save(task)
        return p

    def append_result_notes(self, task_id: str, notes: list[dict]) -> None:
        f = self._dir(task_id) / "result-notes.json"
        existing = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
        existing.extend(notes)
        _atomic_write(f, existing)

    def read_result_notes(self, task_id: str) -> list[dict]:
        f = self._dir(task_id) / "result-notes.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

    # ── 隔离区与扫描账本 ──

    def quarantine_dir(self) -> Path:
        d = self.root / "_quarantine"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _scan_file(self) -> Path:
        return self.root / "mail_scan.json"

    def scanned_mail_ids(self) -> set[int]:
        f = self._scan_file()
        if not f.exists():
            return set()
        return {int(k) for k in json.loads(f.read_text(encoding="utf-8"))}

    def mark_mail_scanned(self, mail_id: int, verdict: str) -> None:
        f = self._scan_file()
        data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        data[str(mail_id)] = {"verdict": verdict, "at": _now()}
        _atomic_write(f, data)
```

- [ ] **Step 4.4: 跑 eval 确认通过**

Expected: `[eval-gkclaw] OK · 19/19`

- [ ] **Step 4.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add agent/evals/eval_gkclaw.py agent/skills/zhgk/services/gkclaw/registry.py
git -C D:\.claude_workplace\aida commit -m "feat(gkclaw): 任务状态机与包级幂等账本（§20 冲突矩阵全覆盖）"
```

---

### Task 5: gkclaw/mapping.py（全量表 → task.json 字段映射）

**Files:**
- Create: `agent/skills/zhgk/services/gkclaw/mapping.py`
- Modify: `agent/evals/eval_gkclaw.py`（追加测试）

- [ ] **Step 5.1: 追加失败测试**

```python
# ─── mapping ───

def _survey_rows() -> list[dict]:
    """模拟 read_survey_table 输出（列结构见 survey_table_builder.RESULT_TABLE_HEADERS）。"""
    return [
        {"序号": 1, "细分场景": "硬装入场", "勘测要素": "接地", "项目": "接地线",
         "检查内容": "检查机房接地线规格是否达标", "勘测方法": "现场勘测",
         "最新检查结果": "", "AI评估结果": "", "备注": ""},
        {"序号": 2, "细分场景": "硬装入场", "勘测要素": "层高", "项目": "梁下净高",
         "检查内容": "测量梁下净高是否≥3m", "勘测方法": "数据",
         "最新检查结果": "", "AI评估结果": "", "备注": ""},
        {"序号": 3, "细分场景": "通液前", "勘测要素": "管路", "项目": "排水管",
         "检查内容": "检查排水管走向与坡度", "勘测方法": "现场勘测",
         "最新检查结果": "", "AI评估结果": "", "备注": ""},
    ]


def _base_items() -> list[dict]:
    """模拟 load_base_table 输出（含建表时被丢弃的背景知识列）。"""
    return [
        {"序号": 11, "代际_制冷": "G5-液冷", "分类": "标准", "细分场景": "硬装入场",
         "勘测要素": "接地", "项目": "接地线", "检查内容": "检查机房接地线规格是否达标",
         "是否支持视频勘测": "是", "勘测方法": "现场勘测", "检查结果": "", "备注": "",
         "语音助手背景知识": "接地线常见 35/50mm²", "视频勘测背景知识": "拍摄接地排与标识牌"},
        {"序号": 12, "代际_制冷": "G5-液冷", "分类": "标准", "细分场景": "通液前",
         "勘测要素": "管路", "项目": "排水管", "检查内容": "检查排水管走向与坡度",
         "是否支持视频勘测": "否", "勘测方法": "现场勘测", "检查结果": "", "备注": "",
         "语音助手背景知识": "", "视频勘测背景知识": "沿管路全程拍摄"},
    ]


def _project() -> dict:
    return {"project_code": "K1903", "project_name": "智算 Q3 · 客户甲一期",
            "room_name": "A 机房", "activity_id": "ACT001"}


@test
def mapping_builds_contract_task():
    from agent.skills.zhgk.services.gkclaw import mapping, schema
    task = mapping.build_task_payload(
        task_id="task-20260611-K1903-000001",
        rows=_survey_rows(), base_items=_base_items(),
        project=_project(),
        assignees=[{"surveyor_name": "张三", "surveyor_code": "S001"}],
    )
    assert schema.validate_task(task) == [], schema.validate_task(task)
    # 只下发 现场勘测 条目（序号 2 是数据类，不下发）
    keys = [it["问题序号"] for it in task["items"]]
    assert keys == ["1", "3"]
    it1 = task["items"][0]
    assert it1["勘测项"] == "检查机房接地线规格是否达标"
    assert it1["选项列表"] == [] and it1["勘测结果"] == "" and it1["to_back_备注"] == ""
    # to_front_备注 = 【勘测要素/项目】+ 视频勘测背景知识 + 语音助手背景知识
    assert it1["to_front_备注"].startswith("【接地/接地线】")
    assert "拍摄接地排与标识牌" in it1["to_front_备注"]
    assert "接地线常见 35/50mm²" in it1["to_front_备注"]
    # metadata 溯源
    assert it1["metadata"]["细分场景"] == "硬装入场"
    assert it1["metadata"]["是否支持视频勘测"] == "是"
    assert it1["metadata"]["底表序号"] == 11
    # 顶层
    assert task["task_name"] == "智算 Q3 · 客户甲一期·A 机房 现场勘测"
    assert task["project"] == {"project_id": "ACT001", "project_code": "K1903",
                               "project_name": "智算 Q3 · 客户甲一期"}
    assert task["dependency_rules"] == [] and task["supplemental_context"] is None
    assert task["metadata"]["generation_cooling"] == "" and task["metadata"]["room_name"] == "A 机房"


@test
def mapping_join_miss_is_tolerated():
    from agent.skills.zhgk.services.gkclaw import mapping
    task = mapping.build_task_payload(
        task_id="task-20260611-K1903-000002",
        rows=_survey_rows(), base_items=[],  # 底表 join 全失败
        project=_project(),
        assignees=[{"surveyor_name": "张三", "surveyor_code": "S001"}],
    )
    it1 = task["items"][0]
    assert it1["to_front_备注"] == "【接地/接地线】"
    assert "底表序号" not in it1["metadata"]


@test
def mapping_clusters_default_single():
    """物理空间分簇：v1 无字段 → 单一兜底簇 cluster-all（cluster_name=机房名）。"""
    from agent.skills.zhgk.services.gkclaw import mapping
    clusters = mapping.derive_clusters(["1", "3"], room_name="A 机房")
    assert clusters == [{"cluster_id": "cluster-all", "cluster_name": "A 机房",
                         "item_keys": ["1", "3"]}]
    assert mapping.derive_clusters(["1"], room_name="")[0]["cluster_name"] == "全部条目"


@test
def mapping_clusters_by_field_when_present():
    """预留升级点：提供 cluster_values（key→物理位置标签）时按标签分簇 + 空值落兜底。"""
    from agent.skills.zhgk.services.gkclaw import mapping
    clusters = mapping.derive_clusters(
        ["1", "2", "3", "4"], room_name="A 机房",
        cluster_values={"1": "配电区", "2": "制冷区", "3": "配电区", "4": ""},
    )
    assert clusters == [
        {"cluster_id": "cluster-01", "cluster_name": "配电区", "item_keys": ["1", "3"]},
        {"cluster_id": "cluster-02", "cluster_name": "制冷区", "item_keys": ["2"]},
        {"cluster_id": "cluster-other", "cluster_name": "其他", "item_keys": ["4"]},
    ]
```

- [ ] **Step 5.2: 跑 eval 确认新增 4 个失败**

Expected: `[eval-gkclaw] FAIL · 19/23`

- [ ] **Step 5.3: 实现 mapping.py**

```python
"""
gkclaw mapping · 全量勘测结果表 → task.json（契约 §10/§11/§12）

入选范围：勘测方法 == "现场勘测" 的行（数据类由 backagent 自行处理，不下发）。
背景知识来源：建表时被丢弃的底表列（视频勘测背景知识/语音助手背景知识/是否支持视频勘测），
下发时按自然键 (细分场景,勘测要素,项目,检查内容) 回连底表取回；join 失败→空+不阻断。

分簇 = 物理空间维度。v1 底表无该字段 → 单一兜底簇 cluster-all（契约 §12 规定动作）；
cluster_values 入参预留按「物理位置」列分簇的升级点（零代码切换，见设计决策）。
"""
from __future__ import annotations

from typing import Any

ON_SITE_METHOD = "现场勘测"


def _nat_key(d: dict[str, Any]) -> tuple[str, str, str, str]:
    return (str(d.get("细分场景", "")).strip(), str(d.get("勘测要素", "")).strip(),
            str(d.get("项目", "")).strip(), str(d.get("检查内容", "")).strip())


def join_base_enrichment(rows: list[dict], base_items: list[dict]) -> dict[int, dict]:
    """全量表行 → 底表行 的自然键 join。返回 {表序号: 底表行}；撞键以首条为准。"""
    index: dict[tuple, dict] = {}
    for b in base_items:
        index.setdefault(_nat_key(b), b)
    out: dict[int, dict] = {}
    for r in rows:
        hit = index.get(_nat_key(r))
        if hit is not None:
            out[int(r.get("序号", 0))] = hit
    return out


def derive_clusters(
    item_keys_in_order: list[str],
    *,
    room_name: str,
    cluster_values: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """物理空间分簇。cluster_values=None → 单兜底簇；否则按标签首现顺序分簇，空标签落「其他」。"""
    if not cluster_values:
        return [{
            "cluster_id": "cluster-all",
            "cluster_name": room_name.strip() or "全部条目",
            "item_keys": list(item_keys_in_order),
        }]
    ordered_labels: list[str] = []
    by_label: dict[str, list[str]] = {}
    leftovers: list[str] = []
    for k in item_keys_in_order:
        label = (cluster_values.get(k) or "").strip()
        if not label:
            leftovers.append(k)
            continue
        if label not in by_label:
            ordered_labels.append(label)
            by_label[label] = []
        by_label[label].append(k)
    clusters = [
        {"cluster_id": f"cluster-{i + 1:02d}", "cluster_name": label, "item_keys": by_label[label]}
        for i, label in enumerate(ordered_labels)
    ]
    if leftovers:
        clusters.append({"cluster_id": "cluster-other", "cluster_name": "其他",
                         "item_keys": leftovers})
    return clusters


def _to_front_note(row: dict, base: dict | None) -> str:
    prefix = f"【{str(row.get('勘测要素', '')).strip()}/{str(row.get('项目', '')).strip()}】"
    if not base:
        return prefix
    video = str(base.get("视频勘测背景知识", "")).strip()
    voice = str(base.get("语音助手背景知识", "")).strip()
    parts = [prefix + video if video else prefix]
    if voice and voice != video:
        parts.append(f"语音助手提示：{voice}")
    return "\n".join(parts)


def build_task_payload(
    *,
    task_id: str,
    rows: list[dict],
    base_items: list[dict],
    project: dict[str, Any],
    assignees: list[dict[str, str]],
    survey_round: int = 1,
    generation_cooling: str = "",
    cluster_values: dict[str, str] | None = None,
) -> dict[str, Any]:
    """组装契约 task.json（纯函数，不校验——校验交给 schema.validate_task）。"""
    enrich = join_base_enrichment(rows, base_items)
    items: list[dict[str, Any]] = []
    for r in rows:
        if str(r.get("勘测方法", "")).strip() != ON_SITE_METHOD:
            continue
        seq = int(r.get("序号", 0))
        base = enrich.get(seq)
        meta: dict[str, Any] = {
            "细分场景": str(r.get("细分场景", "")).strip(),
            "勘测要素": str(r.get("勘测要素", "")).strip(),
            "项目": str(r.get("项目", "")).strip(),
            "勘测方法": ON_SITE_METHOD,
        }
        if base is not None:
            meta["是否支持视频勘测"] = str(base.get("是否支持视频勘测", "")).strip()
            meta["底表序号"] = int(base.get("序号", 0))
        items.append({
            "问题序号": str(seq),
            "勘测项": str(r.get("检查内容", "")).strip(),
            "选项列表": [],
            "勘测结果": "",
            "to_front_备注": _to_front_note(r, base),
            "to_back_备注": "",
            "示例图": [],
            "metadata": meta,
        })

    room_name = str(project.get("room_name", "")).strip()
    project_name = str(project.get("project_name", "")).strip()
    round_suffix = f"（第{survey_round}轮）" if survey_round > 1 else ""
    return {
        "task_id": task_id,
        "task_name": f"{project_name}·{room_name} 现场勘测{round_suffix}".strip("·"),
        "project": {
            "project_id": str(project.get("activity_id", "")).strip()
                          or str(project.get("project_code", "")).strip(),
            "project_code": str(project.get("project_code", "")).strip(),
            "project_name": project_name,
        },
        "assignees": [
            {"surveyor_name": str(a.get("surveyor_name", "")).strip(),
             "surveyor_code": str(a.get("surveyor_code", "")).strip()}
            for a in assignees
        ],
        "items": items,
        "item_clusters": derive_clusters(
            [it["问题序号"] for it in items],
            room_name=room_name, cluster_values=cluster_values,
        ),
        "dependency_rules": [],
        "supplemental_context": None,
        "metadata": {
            "activity_id": str(project.get("activity_id", "")).strip(),
            "room_name": room_name,
            "generation_cooling": generation_cooling,
            "survey_round": survey_round,
            "location_label": room_name,
            "priority": "normal",
        },
    }
```

- [ ] **Step 5.4: 跑 eval 确认通过**

Expected: `[eval-gkclaw] OK · 23/23`

- [ ] **Step 5.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add agent/evals/eval_gkclaw.py agent/skills/zhgk/services/gkclaw/mapping.py
git -C D:\.claude_workplace\aida commit -m "feat(gkclaw): 勘测表到 task.json 映射（底表背景知识回连·物理空间分簇）"
```

---

### Task 6: mailer.py 增加 mailgw backend

**Files:**
- Modify: `agent/mailer.py`
- Modify: `agent/evals/eval_gkclaw.py`（追加测试）

- [ ] **Step 6.1: 追加失败测试**

```python
# ─── mailer mailgw backend ───

class _FakeHttpResp:
    def __init__(self, data: dict):
        import json as _json
        self._raw = _json.dumps(data).encode()
    def read(self):
        return self._raw
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


@test
def mailer_mailgw_backend_sends():
    import os, json as _json
    import agent.mailer as mailer
    os.environ["MAILGW_BASE"] = "http://127.0.0.1:8025"
    os.environ["MAILGW_TOKEN"] = "tok-aida"
    os.environ["AIDA_MAIL_BACKEND"] = "mailgw"
    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["auth"] = req.get_header("Authorization")
        captured["body"] = _json.loads(req.data.decode())
        return _FakeHttpResp({"task_id": "mgw-1", "status": "pending_approval",
                              "message": "已转入待审批队列"})

    orig = mailer.urllib.request.urlopen
    mailer.urllib.request.urlopen = fake_urlopen
    try:
        r = mailer.send_mail(["front@corp.com"], "[GKCLAW][TASK_DISPATCH] K1903/t1",
                             "正文", attachments=["D:/x.zip"], dry_run=False)
    finally:
        mailer.urllib.request.urlopen = orig
        os.environ.pop("AIDA_MAIL_BACKEND", None)
    assert r["ok"] and r["via"] == "mailgw"
    assert r["mailgw_task_id"] == "mgw-1" and r["mailgw_status"] == "pending_approval"
    assert captured["url"].endswith("/api/send")
    assert captured["auth"] == "Bearer tok-aida"
    assert captured["body"]["to"] == ["front@corp.com"]
    assert captured["body"]["attachments"] == ["D:/x.zip"]


@test
def mailer_mailgw_requires_token():
    import os
    import agent.mailer as mailer
    os.environ.pop("MAILGW_TOKEN", None)
    os.environ["AIDA_MAIL_BACKEND"] = "mailgw"
    try:
        r = mailer.send_mail("a@b.com", "s", "b", dry_run=False)
    finally:
        os.environ.pop("AIDA_MAIL_BACKEND", None)
    assert not r["ok"] and "MAILGW_TOKEN" in r["error"]
```

- [ ] **Step 6.2: 跑 eval 确认新增 2 个失败**

Expected: `[eval-gkclaw] FAIL · 23/25`（KeyError/断言失败，因 send_mail 现在走 smtp 分支）

- [ ] **Step 6.3: 实现 mailgw backend**

`agent/mailer.py` 三处修改。① 模块 docstring 的 backend 清单行改为：

```python
    AIDA_MAIL_BACKEND=outlook | smtp | outlook_http | mailgw
      outlook      — Windows 本地 Outlook COM（华为内网常用，与 nanobot 一致）
      outlook_http — nanobot outlook_service_full.py（默认 http://127.0.0.1:5123）
      smtp         — SMTP_HOST / SMTP_USER / SMTP_PASSWORD …
      mailgw       — mailgw 邮件网关 HTTP API（MAILGW_BASE / MAILGW_TOKEN；
                     白名单分级管控 + 人工审批，GKCLAW 链路推荐通道）
```

② 在 `_send_via_smtp` 之后新增：

```python
def _send_via_mailgw(
    recipients: list[str],
    subject: str,
    body: str,
    attachments: list[str] | None,
) -> dict[str, Any]:
    """经 mailgw 邮件网关发送（白名单外收件人会进入人工审批队列）。

    返回扩展字段：mailgw_task_id / mailgw_status（sent | pending_approval），
    供 GKCLAW 链路登记追踪。attachments 为网关所在机器上的本地绝对路径（同机部署约定）。
    """
    base = os.environ.get("MAILGW_BASE", "http://127.0.0.1:8025").rstrip("/")
    token = os.environ.get("MAILGW_TOKEN", "").strip()
    if not token:
        return {"ok": False, "error": "MAILGW_TOKEN 未配置（mailgw Bearer token）", "via": "mailgw"}
    payload = {"to": recipients, "cc": [], "subject": subject,
               "body": body, "attachments": attachments or []}
    req = urllib.request.Request(
        f"{base}/api/send",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = err.get("detail", str(err))
        except Exception:
            msg = str(e)
        return {"ok": False, "error": msg, "via": "mailgw"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "via": "mailgw"}

    status = data.get("status", "")
    out: dict[str, Any] = {
        "ok": status in ("sent", "pending_approval"),
        "via": "mailgw", "to": recipients, "subject": subject,
        "attachments": attachments or [],
        "mailgw_task_id": data.get("task_id", ""),
        "mailgw_status": status,
        "message": data.get("message", ""),
    }
    if not out["ok"]:
        out["error"] = data.get("message", str(data))
    return out
```

③ `send_mail` 末尾分发处，在 `if backend == "outlook_http":` 之后插入：

```python
    if backend == "mailgw":
        return _send_via_mailgw(recipients, subject, body, attachments)
```

- [ ] **Step 6.4: 跑 eval 确认通过 + lint_no_naked_send 仍绿**

```powershell
D:\.claude_workplace\aida\agent\.venv\Scripts\python.exe D:\.claude_workplace\aida\agent\evals\eval_gkclaw.py
D:\.claude_workplace\aida\agent\.venv\Scripts\python.exe D:\.claude_workplace\aida\agent\scripts\lint_no_naked_send.py
```
Expected: `[eval-gkclaw] OK · 25/25` 且 `[no-naked-send] OK`（urllib 不在禁用名单；smtplib/win32com 仍只在 mailer.py）

- [ ] **Step 6.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add agent/mailer.py agent/evals/eval_gkclaw.py
git -C D:\.claude_workplace\aida commit -m "feat(mailer): 第 4 个发信 backend=mailgw（网关白名单管控+审批通道）"
```

---

### Task 7: agent/mailbox.py（统一收件入口）

**Files:**
- Create: `agent/mailbox.py`
- Modify: `agent/evals/eval_gkclaw.py`（追加测试）

- [ ] **Step 7.1: 追加失败测试**

```python
# ─── mailbox ───

@test
def mailbox_list_inbox_request_shape():
    import os, json as _json
    import agent.mailbox as mailbox
    os.environ["MAILGW_BASE"] = "http://127.0.0.1:8025"
    os.environ["MAILGW_TOKEN"] = "tok-aida"
    assert mailbox.is_configured()
    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["auth"] = req.get_header("Authorization")
        captured["method"] = req.get_method()
        return _FakeHttpResp({"new_count": 1, "mails": [
            {"mail_id": 3, "from": "front@corp.com",
             "subject": "[GKCLAW][TASK_IMPORT_ACK] K1903/t1",
             "date": "Thu, 11 Jun 2026 09:00:00 +0800",
             "snippet": "见附件", "has_attachments": True, "is_read": False}]})

    orig = mailbox.urllib.request.urlopen
    mailbox.urllib.request.urlopen = fake_urlopen
    try:
        data = mailbox.list_inbox(refresh=True, limit=50, unread_only=False)
    finally:
        mailbox.urllib.request.urlopen = orig
    assert data["mails"][0]["mail_id"] == 3
    assert captured["method"] == "GET" and captured["auth"] == "Bearer tok-aida"
    assert "/api/inbox" in captured["url"]
    assert "refresh=true" in captured["url"] and "limit=50" in captured["url"]


@test
def mailbox_save_attachment():
    import os, json as _json
    import agent.mailbox as mailbox
    os.environ["MAILGW_BASE"] = "http://127.0.0.1:8025"
    os.environ["MAILGW_TOKEN"] = "tok-aida"
    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = _json.loads(req.data.decode())
        return _FakeHttpResp({"saved_to": "D:/tmp/ack-t1.zip"})

    orig = mailbox.urllib.request.urlopen
    mailbox.urllib.request.urlopen = fake_urlopen
    try:
        saved = mailbox.save_attachment(3, 0, "D:/tmp")
    finally:
        mailbox.urllib.request.urlopen = orig
    assert saved == "D:/tmp/ack-t1.zip"
    assert captured["url"].endswith("/api/inbox/3/attachments/0/save")
    assert captured["body"] == {"save_path": "D:/tmp"}
```

- [ ] **Step 7.2: 跑 eval 确认新增 2 个失败**

Expected: `[eval-gkclaw] FAIL · 25/27`（ModuleNotFoundError: agent.mailbox）

- [ ] **Step 7.3: 实现 mailbox.py**

```python
"""
AIDA Agent · 邮件统一收件入口（与 mailer.py 对称：所有收件唯一经此）

封装 mailgw 邮件网关 inbox API（Bearer 认证，urllib，无新依赖）。

⚠️ 设计约束（GKCLAW 边界 B5 · 收件箱是共享资源）：
  - 本模块刻意**不封装** GET /api/inbox/{id}（读取全文）——该接口会把邮件标为已读，
    机器扫描走「列表 + 附件另存」即可拿到 ZIP，不污染人工/其他流程的未读视图。
  - 邮件正文属外部不可信输入；若未来需要读全文，必须保留网关的不可信包裹标记。

配置（agent/.env）：
    MAILGW_BASE=http://127.0.0.1:8025
    MAILGW_TOKEN=<网关签发的 Bearer token>
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from dotenv import load_dotenv
from pathlib import Path

_ENV_PATH = Path(__file__).parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=False)


class MailboxError(RuntimeError):
    """收件网关调用失败（网络/认证/404 等）。"""


def is_configured() -> bool:
    return bool(os.environ.get("MAILGW_TOKEN", "").strip())


def _request(method: str, path: str, *, params: dict | None = None,
             body: dict | None = None, timeout: int = 120) -> dict[str, Any]:
    base = os.environ.get("MAILGW_BASE", "http://127.0.0.1:8025").rstrip("/")
    token = os.environ.get("MAILGW_TOKEN", "").strip()
    if not token:
        raise MailboxError("MAILGW_TOKEN 未配置（mailgw Bearer token）")
    url = f"{base}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: (str(v).lower() if isinstance(v, bool) else v) for k, v in params.items()})
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode()).get("detail", str(e))
        except Exception:
            detail = str(e)
        raise MailboxError(f"mailgw {method} {path} 失败: {detail}") from e
    except Exception as e:  # noqa: BLE001
        raise MailboxError(f"mailgw {method} {path} 失败: {e}") from e


def list_inbox(refresh: bool = True, limit: int = 50, unread_only: bool = False) -> dict[str, Any]:
    """收件箱摘要列表（不含正文，不改已读状态）。refresh=True 先从邮箱服务器拉新邮件。"""
    return _request("GET", "/api/inbox",
                    params={"refresh": refresh, "limit": limit, "unread_only": unread_only})


def save_attachment(mail_id: int, index: int, save_dir: str) -> str:
    """把附件另存到 save_dir（网关同机本地路径），返回保存后的完整路径。
    附件序号越界时网关返回 404 → 抛 MailboxError（调用方用于探测附件数量）。"""
    data = _request("POST", f"/api/inbox/{mail_id}/attachments/{index}/save",
                    body={"save_path": save_dir}, timeout=60)
    return str(data.get("saved_to", ""))
```

- [ ] **Step 7.4: 跑 eval 确认通过**

Expected: `[eval-gkclaw] OK · 27/27`

- [ ] **Step 7.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add agent/mailbox.py agent/evals/eval_gkclaw.py
git -C D:\.claude_workplace\aida commit -m "feat(mailbox): 统一收件入口（mailgw inbox API·不触碰已读状态）"
```

---

### Task 8: gkclaw/dispatch.py（下发服务）

**Files:**
- Create: `agent/skills/zhgk/services/gkclaw/dispatch.py`
- Modify: `agent/evals/eval_gkclaw.py`（追加测试）

- [ ] **Step 8.1: 追加失败测试**

```python
# ─── dispatch ───

def _make_survey_xlsx(out_dir) -> str:
    """用真实 builder 生成全量勘测结果表（3 条：2 现场 + 1 数据）。"""
    from agent.skills.zhgk.services.survey_table_builder import build_survey_table
    items = [
        {"细分场景": "硬装入场", "勘测要素": "接地", "项目": "接地线",
         "检查内容": "检查机房接地线规格是否达标", "勘测方法": "现场勘测", "备注": ""},
        {"细分场景": "硬装入场", "勘测要素": "层高", "项目": "梁下净高",
         "检查内容": "测量梁下净高是否≥3m", "勘测方法": "数据", "备注": ""},
        {"细分场景": "通液前", "勘测要素": "管路", "项目": "排水管",
         "检查内容": "检查排水管走向与坡度", "勘测方法": "现场勘测", "备注": ""},
    ]
    return build_survey_table(items, str(out_dir), "ACT001", "智算 Q3 · 客户甲一期", "A 机房")


_ASSIGNEES = [{"surveyor_name": "张三", "surveyor_code": "S001"}]


@test
def dispatch_dry_run_creates_task_and_zip():
    from agent.skills.zhgk.services.gkclaw import dispatch, package
    from agent.skills.zhgk.services.gkclaw.registry import TaskRegistry
    root = tmpdir()
    table = _make_survey_xlsx(root / "Output")
    r = dispatch.dispatch_task(
        runtime_dir=root / "RunTime", survey_table_path=table,
        project=_project(), assignees=_ASSIGNEES, dry_run=True,
    )
    assert r["dry_run"] is True and r["state"] == "dispatched"
    assert r["items_count"] == 2
    reg = TaskRegistry(root / "RunTime")
    task = reg.get(r["task_id"])
    assert task["state"] == "dispatched" and task["dry_run"] is True
    assert task["table_fingerprint"].startswith("sha256:")
    zp = reg.root / r["task_id"] / "outbox" / f"task-{r['task_id']}.zip"
    assert zp.exists()
    parsed = package.parse_package(zp)
    assert parsed["ok"] and parsed["payload"]["task_id"] == r["task_id"]
    assert len(reg.packages(r["task_id"])) == 1  # 出站包入账本


@test
def dispatch_real_send_and_supersede():
    from agent.skills.zhgk.services.gkclaw import dispatch
    from agent.skills.zhgk.services.gkclaw.registry import TaskRegistry
    root = tmpdir()
    table = _make_survey_xlsx(root / "Output")
    sent: list[dict] = []

    def fake_send(to, subject, body, *, attachments=None, dry_run=None):
        sent.append({"to": to, "subject": subject, "attachments": attachments})
        return {"ok": True, "via": "mailgw", "mailgw_task_id": "mgw-7", "mailgw_status": "sent"}

    r1 = dispatch.dispatch_task(
        runtime_dir=root / "RunTime", survey_table_path=table,
        project=_project(), assignees=_ASSIGNEES, dry_run=True,
    )
    r2 = dispatch.dispatch_task(
        runtime_dir=root / "RunTime", survey_table_path=table,
        project=_project(), assignees=_ASSIGNEES,
        dry_run=False, send_fn=fake_send,
        frontagent_mailbox="front@corp.com", previous_task_id=r1["task_id"],
    )
    reg = TaskRegistry(root / "RunTime")
    assert reg.get(r1["task_id"])["state"] == "superseded"          # 重发=新 task_id+旧任务取代
    task2 = reg.get(r2["task_id"])
    assert task2["state"] == "dispatched" and task2["mailgw_task_id"] == "mgw-7"
    assert sent[0]["to"] == ["front@corp.com"]
    assert sent[0]["subject"] == f"[GKCLAW][TASK_DISPATCH] K1903/{r2['task_id']}"
    assert sent[0]["attachments"][0].endswith(f"task-{r2['task_id']}.zip")


@test
def dispatch_send_failure_marks_failed():
    from agent.skills.zhgk.services.gkclaw import dispatch
    from agent.skills.zhgk.services.gkclaw.registry import TaskRegistry
    root = tmpdir()
    table = _make_survey_xlsx(root / "Output")

    def bad_send(to, subject, body, *, attachments=None, dry_run=None):
        return {"ok": False, "error": "connection refused", "via": "mailgw"}

    try:
        dispatch.dispatch_task(
            runtime_dir=root / "RunTime", survey_table_path=table,
            project=_project(), assignees=_ASSIGNEES,
            dry_run=False, send_fn=bad_send, frontagent_mailbox="front@corp.com",
        )
        assert False, "应抛 RuntimeError"
    except RuntimeError as e:
        assert "connection refused" in str(e)
    reg = TaskRegistry(root / "RunTime")
    tasks = reg.list_tasks()
    assert len(tasks) == 1 and tasks[0]["state"] == "failed"
    assert "connection refused" in tasks[0]["last_error"]
```

- [ ] **Step 8.2: 跑 eval 确认新增 3 个失败**

Expected: `[eval-gkclaw] FAIL · 27/30`

- [ ] **Step 8.3: 实现 dispatch.py**

```python
"""
gkclaw dispatch · 任务下发服务（建包 → 经 mailer 发送 → 状态登记）

发送唯一出口 = agent.mailer.send_mail（lint_no_naked_send 铁律）；send_fn 仅供测试注入。
dry-run（AIDA_SEND_EMAIL≠1 或显式 dry_run=True）：照常建包+登记，标 dry_run，不发邮件。
重发语义（契约无撤销包类型）：内容变更重发 = 新 task_id；previous_task_id 标 superseded。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from . import ids, mapping, package, schema
from .registry import TaskRegistry


def dispatch_task(
    *,
    runtime_dir: Path | str,
    survey_table_path: str,
    project: dict[str, Any],
    assignees: list[dict[str, str]],
    dry_run: bool | None = None,
    send_fn: Callable[..., dict] | None = None,
    frontagent_mailbox: str | None = None,
    generation_cooling: str = "",
    survey_round: int = 1,
    previous_task_id: str = "",
) -> dict[str, Any]:
    """下发一个 GKCLAW 任务。返回 {task_id, state, dry_run, zip_path, items_count, send_result}。

    校验失败抛 ValueError；发送失败任务标 failed 并抛 RuntimeError（step 层据此呈现/重试）。
    """
    from ..survey_table_builder import read_survey_table

    rows = read_survey_table(survey_table_path)

    # 底表回连（背景知识 enrich）：失败不阻断，join 不到=空备注
    base_items: list[dict] = []
    try:
        from ..table_filter import load_base_table
        from ...path_config import get_base_table_path
        base_items = load_base_table(get_base_table_path())
    except Exception:  # noqa: BLE001
        base_items = []

    reg = TaskRegistry(runtime_dir)
    task_id = ids.new_task_id(str(project.get("project_code", "")), reg.root)
    payload = mapping.build_task_payload(
        task_id=task_id, rows=rows, base_items=base_items,
        project=project, assignees=assignees,
        survey_round=survey_round, generation_cooling=generation_cooling,
    )
    errors = schema.validate_task(payload)
    if errors:
        raise ValueError("task.json 契约校验失败: " + "；".join(errors))

    if dry_run is None:
        dry_run = os.environ.get("AIDA_SEND_EMAIL", "0").strip() != "1"

    package_id = ids.new_package_id()
    out_dir = reg.root / task_id / "outbox"
    zip_path = package.build_package(
        package_type="task.dispatch", task_id=task_id,
        project=payload["project"], payload=payload,
        out_dir=out_dir, package_id=package_id,
    )
    fingerprint = package.sha256_file(survey_table_path)
    reg.create_task(
        task_id=task_id, task_payload=payload,
        zip_path=f"outbox/{zip_path.name}",
        table_fingerprint=fingerprint, project=payload["project"], dry_run=dry_run,
    )
    reg.record_package(task_id, {
        "package_id": package_id, "checksum": package.sha256_file(zip_path),
        "package_type": "task.dispatch", "direction": "out", "disposition": "processed",
    })
    if previous_task_id and previous_task_id != task_id:
        reg.mark_superseded(previous_task_id)

    project_code = payload["project"]["project_code"]
    send_result: dict[str, Any] = {}
    if dry_run:
        reg.set_state(task_id, "dispatched", mailgw_status="dry_run")
        send_result = {"ok": True, "dry_run": True,
                       "note": "dry-run：任务包已生成未发送（设 AIDA_SEND_EMAIL=1 才发）"}
    else:
        to = (frontagent_mailbox or os.environ.get("GKCLAW_FRONTAGENT_MAILBOX", "")).strip()
        if not to:
            reg.set_state(task_id, "failed", last_error="GKCLAW_FRONTAGENT_MAILBOX 未配置")
            raise RuntimeError("GKCLAW_FRONTAGENT_MAILBOX 未配置（frontagent 收件邮箱）")
        if send_fn is None:
            from agent.mailer import send_mail as send_fn  # type: ignore[no-redef]
        subject = f"[GKCLAW][TASK_DISPATCH] {project_code}/{task_id}"
        body = (f"GKCLAW 任务下发：{payload['task_name']}\n"
                f"task_id: {task_id}\n项目: {project_code}\n"
                f"权威数据见附件 ZIP（manifest.json / task.json）。")
        send_result = send_fn(to, subject, body, attachments=[str(zip_path)], dry_run=False)
        if not send_result.get("ok"):
            err = str(send_result.get("error", send_result))
            reg.set_state(task_id, "failed", last_error=err)
            raise RuntimeError(f"任务包发送失败: {err}")
        reg.set_state(
            task_id, "dispatched",
            mailgw_task_id=str(send_result.get("mailgw_task_id", "")),
            mailgw_status=str(send_result.get("mailgw_status", "")),
        )

    return {"task_id": task_id, "state": "dispatched", "dry_run": bool(dry_run),
            "zip_path": str(zip_path), "items_count": len(payload["items"]),
            "send_result": send_result}
```

- [ ] **Step 8.4: 跑 eval 确认通过**

Expected: `[eval-gkclaw] OK · 30/30`

- [ ] **Step 8.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add agent/evals/eval_gkclaw.py agent/skills/zhgk/services/gkclaw/dispatch.py
git -C D:\.claude_workplace\aida commit -m "feat(gkclaw): 下发服务（建包·mailer 发送·superseded 重发语义·dry-run 贯通）"
```

---

### Task 9: gkclaw/ingest.py（收件处理：ack / result / error）

**Files:**
- Create: `agent/skills/zhgk/services/gkclaw/ingest.py`
- Modify: `agent/evals/eval_gkclaw.py`（追加测试）

- [ ] **Step 9.1: 追加失败测试**

```python
# ─── ingest ───

def _dispatched_env():
    """构造已下发环境：返回 (root, reg, task_id, task_payload, survey_table_path, input_dir)。"""
    from agent.skills.zhgk.services.gkclaw import dispatch
    from agent.skills.zhgk.services.gkclaw.registry import TaskRegistry
    root = tmpdir()
    (root / "Input").mkdir()
    table = _make_survey_xlsx(root / "Output")
    r = dispatch.dispatch_task(runtime_dir=root / "RunTime", survey_table_path=table,
                               project=_project(), assignees=_ASSIGNEES, dry_run=True)
    reg = TaskRegistry(root / "RunTime")
    return root, reg, r["task_id"], reg.task_payload(r["task_id"]), table, root / "Input"


def _ack_zip(task_payload, out, *, assignees=None, package_id=None) -> "Path":
    from agent.skills.zhgk.services.gkclaw import package
    ack = {"status": "accepted", "task_id": task_payload["task_id"],
           "task_name": task_payload["task_name"], "project": task_payload["project"],
           "assignees": assignees if assignees is not None else task_payload["assignees"],
           "web_access_url": "https://front-agent.example.com/tasks/web/wa_7b4f",
           "accepted_at": "2026-06-11T03:01:00.000Z"}
    return package.build_package(package_type="task.import_ack", task_id=task_payload["task_id"],
                                 project=task_payload["project"], payload=ack, out_dir=out,
                                 source="front-agent", target="back-agent", package_id=package_id)


def _result_zip(task_payload, out, *, status, items=None, submitted_code="S001",
                package_id=None, notes=False, evidence=False) -> "Path":
    from agent.skills.zhgk.services.gkclaw import package
    r_items = items if items is not None else [
        {"问题序号": "1", "勘测项": "检查机房接地线规格是否达标", "勘测结果": "满足",
         "to_back_备注": "[规则自动处理: r1] 语义等价不涉及" if notes else ""},
        {"问题序号": "3", "勘测项": "检查排水管走向与坡度", "勘测结果": "不满足"},
    ]
    res = {"task_id": task_payload["task_id"], "task_name": task_payload["task_name"],
           "project": task_payload["project"], "assignees": task_payload["assignees"],
           "submitted_by": {"surveyor_name": "张三", "surveyor_code": submitted_code},
           "session": {"task_id": task_payload["task_id"], "status": status},
           "items": r_items, "evidence": [], "updates": [], "observations": [],
           "exported_at": "2026-06-11T03:31:00.000Z"}
    assets = {"evidence/p1.jpg": b"img1"} if evidence else None
    return package.build_package(package_type="task.result", task_id=task_payload["task_id"],
                                 project=task_payload["project"], payload=res, out_dir=out,
                                 assets=assets, source="front-agent", target="back-agent",
                                 package_id=package_id)


@test
def ingest_ack_updates_state_and_mismatch_quarantines():
    from agent.skills.zhgk.services.gkclaw import ingest
    root, reg, tid, tp, table, input_dir = _dispatched_env()
    out = ingest.ingest_zip(_ack_zip(tp, tmpdir()), runtime_dir=root / "RunTime",
                            input_dir=input_dir, survey_table_path=table)
    assert out["disposition"] == "processed", out
    task = reg.get(tid)
    assert task["state"] == "accepted"
    assert task["web_access_url"].startswith("https://front-agent")
    # 人员不一致的 ACK → 隔离，状态不动
    bad = _ack_zip(tp, tmpdir(), assignees=[{"surveyor_name": "李四", "surveyor_code": "S099"}])
    out2 = ingest.ingest_zip(bad, runtime_dir=root / "RunTime",
                             input_dir=input_dir, survey_table_path=table)
    assert out2["disposition"] == "quarantine" and "不一致" in out2["note"]
    assert reg.get(tid)["state"] == "accepted"


@test
def ingest_staged_records_final_writes_filled_table():
    import openpyxl
    from agent.skills.zhgk.services.gkclaw import ingest
    root, reg, tid, tp, table, input_dir = _dispatched_env()
    ingest.ingest_zip(_ack_zip(tp, tmpdir()), runtime_dir=root / "RunTime",
                      input_dir=input_dir, survey_table_path=table)
    # staged：记录版本，不落 Input，不推进到 completed
    out = ingest.ingest_zip(_result_zip(tp, tmpdir(), status="active"),
                            runtime_dir=root / "RunTime", input_dir=input_dir,
                            survey_table_path=table)
    assert out["disposition"] == "processed"
    task = reg.get(tid)
    assert task["state"] == "staged_returned" and task["result_versions"] == 1
    assert not (input_dir / "已填写_全量勘测结果表.xlsx").exists()
    # final：转写已填写表落 Input + completed + 备注留档 + evidence 解出
    out = ingest.ingest_zip(_result_zip(tp, tmpdir(), status="completed",
                                        notes=True, evidence=True),
                            runtime_dir=root / "RunTime", input_dir=input_dir,
                            survey_table_path=table)
    assert out["disposition"] == "processed" and out["merged"] is True
    task = reg.get(tid)
    assert task["state"] == "completed" and task["final_result"]
    filled = input_dir / "已填写_全量勘测结果表.xlsx"
    assert filled.exists()
    ws = openpyxl.load_workbook(filled, data_only=True).active
    headers = [c.value for c in ws[1]]
    col = headers.index("最新检查结果") + 1
    assert ws.cell(2, col).value == "满足"      # 序号1
    assert ws.cell(4, col).value == "不满足"    # 序号3
    assert reg.read_result_notes(tid)[0]["问题序号"] == "1"
    assert (reg.root / tid / "evidence" / "p1.jpg").read_bytes() == b"img1"


@test
def ingest_idempotency_and_conflicts():
    from agent.skills.zhgk.services.gkclaw import ingest
    root, reg, tid, tp, table, input_dir = _dispatched_env()
    kw = dict(runtime_dir=root / "RunTime", input_dir=input_dir, survey_table_path=table)
    final1 = _result_zip(tp, tmpdir(), status="completed", package_id="pkg-final-1")
    assert ingest.ingest_zip(final1, **kw)["disposition"] == "processed"
    # 同一 ZIP 原包重放（同 package_id 同 checksum）→ duplicate（幂等成功）
    # 注意不能重新 build：created_at 变化会导致 zip checksum 不同 → 会判 conflict（符合契约）
    assert ingest.ingest_zip(final1, **kw)["disposition"] == "duplicate"
    # final 后异内容 final（新 package_id）→ conflict + 隔离落盘
    final2 = _result_zip(tp, tmpdir(), status="completed",
                         items=[{"问题序号": "1", "勘测结果": "不涉及"}])
    out = ingest.ingest_zip(final2, **kw)
    assert out["disposition"] == "conflict"
    assert any(reg.quarantine_dir().iterdir())
    # final 后 staged → quarantine
    staged = _result_zip(tp, tmpdir(), status="active")
    assert ingest.ingest_zip(staged, **kw)["disposition"] == "quarantine"
    assert reg.get(tid)["state"] == "completed"  # 状态不被污染


@test
def ingest_submitted_by_guard():
    from agent.skills.zhgk.services.gkclaw import ingest
    root, reg, tid, tp, table, input_dir = _dispatched_env()
    bad = _result_zip(tp, tmpdir(), status="completed", submitted_code="S999")
    out = ingest.ingest_zip(bad, runtime_dir=root / "RunTime",
                            input_dir=input_dir, survey_table_path=table)
    assert out["disposition"] == "quarantine" and "submitted_by" in out["note"]
    assert reg.get(tid)["state"] == "dispatched"


@test
def ingest_dual_source_and_fingerprint_guard():
    from agent.skills.zhgk.services.gkclaw import ingest
    # 双源冲突：Input 已有待合并表 → 邮件结果暂存 pending_results，不覆盖
    root, reg, tid, tp, table, input_dir = _dispatched_env()
    (input_dir / "已填写_全量勘测结果表.xlsx").write_bytes(b"manual upload")
    out = ingest.ingest_zip(_result_zip(tp, tmpdir(), status="completed"),
                            runtime_dir=root / "RunTime", input_dir=input_dir,
                            survey_table_path=table)
    assert out["disposition"] == "processed" and out["merged"] is False
    assert "先到先得" in out["note"]
    assert any((reg.root / tid / "pending_results").iterdir())
    assert (input_dir / "已填写_全量勘测结果表.xlsx").read_bytes() == b"manual upload"
    # 表指纹漂移：下发后表被改 → final 不合并
    root, reg, tid, tp, table, input_dir = _dispatched_env()
    import openpyxl
    wb = openpyxl.load_workbook(table); wb.active.cell(2, 5, "被改过的检查内容"); wb.save(table)
    out = ingest.ingest_zip(_result_zip(tp, tmpdir(), status="completed"),
                            runtime_dir=root / "RunTime", input_dir=input_dir,
                            survey_table_path=table)
    assert out["merged"] is False and "指纹" in out["note"]
    assert not (input_dir / "已填写_全量勘测结果表.xlsx").exists()
    assert reg.get(tid)["state"] == "completed"  # 任务仍完成，仅合并阻塞


@test
def ingest_unknown_task_and_broken_zip():
    from agent.skills.zhgk.services.gkclaw import ingest
    from agent.skills.zhgk.services.gkclaw.registry import TaskRegistry
    root = tmpdir(); (root / "Input").mkdir()
    reg = TaskRegistry(root / "RunTime")
    # 未知 task_id：合法包但本地无任务 → 隔离留档，不创建任务
    fake_tp = _valid_task()
    out = ingest.ingest_zip(_ack_zip(fake_tp, tmpdir()), runtime_dir=root / "RunTime",
                            input_dir=root / "Input", survey_table_path=None)
    assert out["disposition"] == "quarantine"
    assert reg.get(fake_tp["task_id"]) is None
    # 坏 ZIP → 隔离不抛
    bad = root / "bad.zip"; bad.write_bytes(b"\xff\xfe not a zip")
    out = ingest.ingest_zip(bad, runtime_dir=root / "RunTime",
                            input_dir=root / "Input", survey_table_path=None)
    assert out["disposition"] == "quarantine"


@test
def poll_and_ingest_with_fake_mailbox():
    from agent.skills.zhgk.services.gkclaw import ingest
    root, reg, tid, tp, table, input_dir = _dispatched_env()
    ack_zip = _ack_zip(tp, tmpdir())

    class FakeMailbox:
        @staticmethod
        def is_configured(): return True
        @staticmethod
        def list_inbox(refresh=True, limit=50, unread_only=False):
            return {"new_count": 2, "mails": [
                {"mail_id": 1, "subject": "[GKCLAW][TASK_IMPORT_ACK] K1903/x",
                 "has_attachments": True},
                {"mail_id": 2, "subject": "普通邮件", "has_attachments": False},
            ]}
        @staticmethod
        def save_attachment(mail_id, index, save_dir):
            from agent.skills.zhgk.services.gkclaw.ingest import MailboxExhausted
            import shutil
            if mail_id == 1 and index == 0:
                dest = Path(save_dir) / ack_zip.name
                Path(save_dir).mkdir(parents=True, exist_ok=True)
                shutil.copy(ack_zip, dest)
                return str(dest)
            raise MailboxExhausted("404")

    summary = ingest.poll_and_ingest(runtime_dir=root / "RunTime", input_dir=input_dir,
                                     survey_table_path=table, mailbox_mod=FakeMailbox)
    assert summary["checked"] == 2 and summary["processed"] == 1
    assert reg.get(tid)["state"] == "accepted"
    assert reg.scanned_mail_ids() == {1, 2}
    # 第二次轮询：账本生效，全部跳过
    summary2 = ingest.poll_and_ingest(runtime_dir=root / "RunTime", input_dir=input_dir,
                                      survey_table_path=table, mailbox_mod=FakeMailbox)
    assert summary2["checked"] == 0
```

注意：FakeMailbox 抛的异常用 `ingest.MailboxExhausted`——实现里 ingest 捕获 `agent.mailbox.MailboxError` 与自身 `MailboxExhausted` 二者皆可（`MailboxExhausted` 继承 `MailboxError` 之外的简单 RuntimeError，见实现）。

- [ ] **Step 9.2: 跑 eval 确认新增 7 个失败**

Expected: `[eval-gkclaw] FAIL · 30/37`

- [ ] **Step 9.3: 实现 ingest.py**

```python
"""
gkclaw ingest · 入站包处理（契约 §14/§17-§20 + 项目边界 A2/B5/B6/双源拍板）

路由：task.import_ack → accepted（一致性校验）；task.result → staged 只记录 /
final 转写已填写表走 wait_survey 原有合并通道；task.error → 留痕。
处置不抛栈（单包失败隔离，不阻断批次）；所有判定走 registry.decide_inbound 纯函数。

final 合并三道闸（任一不过 → 暂存 pending_results/ + 告警，merged=False）：
  1) submitted_by ∈ assignees（§22 安全基线，不过=整包隔离）
  2) 表指纹一致（下发后表未被 redo/追加）
  3) Input/ 无待合并的人工上传表（先到先得，用户拍板）
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from . import package, schema
from .registry import TaskRegistry, decide_inbound

FILLED_TABLE_NAME = "已填写_全量勘测结果表.xlsx"


class MailboxExhausted(RuntimeError):
    """附件序号越界（探测附件数量用）。"""


def write_filled_table(survey_table_path: str, results: dict[int, str], dest_path: Path) -> int:
    """复制全量表并按序号写入「最新检查结果」列，存为已填写表。返回写入条数。"""
    import openpyxl

    wb = openpyxl.load_workbook(survey_table_path)
    ws = wb.active
    headers = [str(c.value or "").strip() for c in ws[1]]
    seq_col = headers.index("序号") + 1
    res_col = headers.index("最新检查结果") + 1
    written = 0
    for row in ws.iter_rows(min_row=2):
        raw = row[seq_col - 1].value
        if raw is None:
            continue
        try:
            seq = int(raw)
        except (TypeError, ValueError):
            continue
        if seq in results:
            ws.cell(row[0].row, res_col, results[seq])
            written += 1
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dest_path)
    wb.close()
    return written


def _quarantine(reg: TaskRegistry, zip_path: Path | str, note: str) -> dict[str, Any]:
    dest = reg.quarantine_dir() / Path(zip_path).name
    try:
        shutil.copy(zip_path, dest)
    except Exception:  # noqa: BLE001
        pass
    return {"disposition": "quarantine", "note": note, "merged": False}


def _apply_ack(reg: TaskRegistry, task: dict, payload: dict) -> tuple[str, str]:
    """ACK 一致性校验（§14）：项目/任务名/人员与原任务不一致 → 隔离。"""
    orig = reg.task_payload(task["task_id"]) or {}
    mismatches = []
    if payload.get("task_name") and payload["task_name"] != orig.get("task_name"):
        mismatches.append("task_name")
    if (payload.get("project") or {}).get("project_code") != (orig.get("project") or {}).get("project_code"):
        mismatches.append("project_code")
    orig_codes = {a.get("surveyor_code") for a in orig.get("assignees", [])}
    ack_codes = {a.get("surveyor_code") for a in payload.get("assignees", [])}
    if ack_codes and ack_codes != orig_codes:
        mismatches.append("assignees")
    if mismatches:
        return "quarantine", f"ACK 与原任务不一致（{'/'.join(mismatches)}），隔离待人工核查"
    reg.set_state(task["task_id"], "accepted",
                  web_access_url=str(payload.get("web_access_url", "")),
                  accepted_at=str(payload.get("accepted_at", "")))
    return "processed", "frontagent 已导入任务"


def _apply_result(
    reg: TaskRegistry, task: dict, payload: dict, zip_path: Path,
    *, input_dir: Path, survey_table_path: str | None,
) -> dict[str, Any]:
    tid = task["task_id"]
    # 安全闸 1：submitted_by ∈ assignees（隔离，不入库）
    code = str((payload.get("submitted_by") or {}).get("surveyor_code", ""))
    allowed = {a.get("surveyor_code") for a in task.get("assignees", [])}
    if code not in allowed:
        return _quarantine(reg, zip_path, f"submitted_by({code}) 不在任务 assignees 中，整包隔离")

    is_final = (payload.get("session") or {}).get("status") == "completed"
    reg.store_result_version(tid, payload, final=is_final)

    # evidence 解出 + to_back_备注 留档
    parsed_names = [n for n in package.parse_package(zip_path)["files"]
                    if n.startswith("evidence/") and not n.endswith("/")]
    if parsed_names:
        package.extract_files(zip_path, parsed_names, reg.root / tid)
    notes = [{"问题序号": str(it.get("问题序号", "")), "to_back_备注": it["to_back_备注"]}
             for it in payload.get("items", []) if str(it.get("to_back_备注", "")).strip()]
    if notes:
        reg.append_result_notes(tid, notes)

    if not is_final:
        reg.set_state(tid, "staged_returned")
        return {"disposition": "processed", "merged": False,
                "note": "阶段性回传已记录（不推进流程，final 才合并）"}

    # final：任务完成；合并需过闸 2/3
    reg.set_state(tid, "completed")
    known_keys = {it["问题序号"] for it in (reg.task_payload(tid) or {}).get("items", [])}
    results: dict[int, str] = {}
    skipped: list[str] = []
    for it in payload.get("items", []):
        key = str(it.get("问题序号", ""))
        val = str(it.get("勘测结果", "")).strip()
        if not val:
            continue
        if key not in known_keys or not key.isdigit():
            skipped.append(key)
            continue
        results[int(key)] = val

    def _stash(reason: str) -> dict[str, Any]:
        pend = reg.root / tid / "pending_results"
        pend.mkdir(parents=True, exist_ok=True)
        if survey_table_path:
            write_filled_table(survey_table_path, results, pend / FILLED_TABLE_NAME)
        else:
            shutil.copy(zip_path, pend / Path(zip_path).name)
        reg.set_state(tid, "completed", merge_blocked=True, merge_blocked_reason=reason)
        return {"disposition": "processed", "merged": False, "note": reason}

    if not survey_table_path:
        return _stash("找不到当前全量勘测结果表，结果已暂存 pending_results/ 待人工合并")
    fingerprint = package.sha256_file(survey_table_path)
    if fingerprint != task.get("table_fingerprint"):
        return _stash("表指纹不一致（下发后勘测表已变更），结果暂存 pending_results/ 待人工裁决")
    dest = Path(input_dir) / FILLED_TABLE_NAME
    if dest.exists():
        return _stash("先到先得：Input/ 已有待合并的人工上传表，邮件结果暂存 pending_results/")
    written = write_filled_table(survey_table_path, results, dest)
    note = f"最终回传已转写 {written} 条到 Input/{FILLED_TABLE_NAME}（走 wait_survey 合并通道）"
    if skipped:
        note += f"；跳过未下发条目 {skipped}"
    return {"disposition": "processed", "merged": True, "note": note}


def ingest_zip(
    zip_path: Path | str,
    *,
    runtime_dir: Path | str,
    input_dir: Path | str,
    survey_table_path: str | None,
    mail_id: int | None = None,
) -> dict[str, Any]:
    """处理单个入站 ZIP。永不抛栈；返回 {disposition, note, merged, task_id?}。"""
    reg = TaskRegistry(runtime_dir)
    try:
        parsed = package.parse_package(zip_path)
        if not parsed["ok"]:
            return _quarantine(reg, zip_path, "包校验失败: " + "；".join(parsed["errors"]))
        manifest = parsed["manifest"]
        payload = parsed["payload"]
        ptype = manifest["package_type"]
        validator = {"task.import_ack": schema.validate_ack,
                     "task.result": schema.validate_result,
                     "task.error": schema.validate_error}.get(ptype)
        if validator is None:
            return _quarantine(reg, zip_path, f"backagent 不接收 {ptype} 包")
        errors = validator(payload)
        if errors:
            return _quarantine(reg, zip_path, "payload 校验失败: " + "；".join(errors))

        task_id = manifest["task_id"]
        task = reg.get(task_id)
        checksum = package.sha256_file(zip_path)
        session_status = str((payload.get("session") or {}).get("status", "")) \
            if ptype == "task.result" else ""
        disposition, note = decide_inbound(
            task, reg.packages(task_id) if task else [],
            package_type=ptype, package_id=manifest["package_id"],
            checksum=checksum, session_status=session_status,
        )
        out: dict[str, Any] = {"disposition": disposition, "note": note,
                               "merged": False, "task_id": task_id}
        if disposition == "processed":
            if ptype == "task.import_ack":
                disposition, note = _apply_ack(reg, task, payload)
                out.update({"disposition": disposition, "note": note})
                if disposition == "quarantine":
                    _quarantine(reg, zip_path, note)
            elif ptype == "task.result":
                out.update(_apply_result(reg, task, payload, Path(zip_path),
                                         input_dir=Path(input_dir),
                                         survey_table_path=survey_table_path))
            elif ptype == "task.error":
                recoverable = bool(payload.get("recoverable", False))
                err = f"[{payload.get('code')}] {payload.get('message')}"
                if recoverable:
                    reg.set_state(task_id, "dispatched", last_error=err)
                    out["note"] = f"frontagent 报可恢复错误：{err}（修复后用新 task_id 重发）"
                else:
                    reg.set_state(task_id, "failed", last_error=err)
                    out["note"] = f"frontagent 报不可恢复错误：{err}"
        elif disposition in ("conflict", "quarantine"):
            _quarantine(reg, zip_path, note)
        if task is not None:
            reg.record_package(task_id, {
                "package_id": manifest["package_id"], "checksum": checksum,
                "package_type": ptype, "direction": "in",
                "disposition": out["disposition"], "mail_id": mail_id,
            })
        return out
    except Exception as e:  # noqa: BLE001 — 单包异常隔离，不阻断批次
        return _quarantine(reg, zip_path, f"处理异常: {type(e).__name__}: {e}")


def poll_and_ingest(
    *,
    runtime_dir: Path | str,
    input_dir: Path | str,
    survey_table_path: str | None,
    mailbox_mod: Any = None,
    limit: int = 50,
    max_attachments: int = 10,
) -> dict[str, Any]:
    """拉取 mailgw 收件箱并处理 GKCLAW 包。

    边界 B5：只列表+另存附件（不读正文/不动已读）；mail_id 账本去重；
    非 ZIP/非 GKCLAW 邮件记 ignored 不再重扫。返回 {checked, processed, alerts[]}。
    """
    if mailbox_mod is None:
        import agent.mailbox as mailbox_mod  # type: ignore[no-redef]
    reg = TaskRegistry(runtime_dir)
    summary: dict[str, Any] = {"checked": 0, "processed": 0, "alerts": []}
    if not mailbox_mod.is_configured():
        summary["alerts"].append("mailgw 未配置（MAILGW_TOKEN），跳过邮件拉取")
        return summary

    try:
        mails = mailbox_mod.list_inbox(refresh=True, limit=limit, unread_only=False)["mails"]
    except Exception as e:  # noqa: BLE001
        summary["alerts"].append(f"收件箱拉取失败: {e}")
        return summary

    scanned = reg.scanned_mail_ids()
    for mail in mails:
        mail_id = int(mail.get("mail_id", -1))
        if mail_id in scanned:
            continue
        summary["checked"] += 1
        if not mail.get("has_attachments"):
            reg.mark_mail_scanned(mail_id, "ignored")
            continue
        tmp = reg.root / "_inbox_tmp" / str(mail_id)
        tmp.mkdir(parents=True, exist_ok=True)
        verdict = "ignored"
        for idx in range(max_attachments):
            try:
                saved = mailbox_mod.save_attachment(mail_id, idx, str(tmp))
            except Exception:  # noqa: BLE001 — 序号越界/网关错误 → 该邮件附件取尽
                break
            if not saved.lower().endswith(".zip"):
                continue
            out = ingest_zip(saved, runtime_dir=runtime_dir, input_dir=input_dir,
                             survey_table_path=survey_table_path, mail_id=mail_id)
            verdict = out["disposition"]
            if out["disposition"] == "processed":
                summary["processed"] += 1
            if out.get("note"):
                summary["alerts"].append(f"mail#{mail_id}: {out['note']}")
        reg.mark_mail_scanned(mail_id, verdict)
    return summary
```

- [ ] **Step 9.4: 跑 eval 确认通过**

Expected: `[eval-gkclaw] OK · 37/37`

- [ ] **Step 9.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add agent/evals/eval_gkclaw.py agent/skills/zhgk/services/gkclaw/ingest.py
git -C D:\.claude_workplace\aida commit -m "feat(gkclaw): 收件处理（ack/result/error·三道合并闸·隔离不阻断批次）"
```

---

### Task 10: task_dispatch step + 流水线接线

**Files:**
- Create: `agent/skills/zhgk/steps/task_dispatch.py`
- Modify: `agent/skills/zhgk/steps/__init__.py`
- Modify: `agent/skills/zhgk/steps/_intent_guard.py`
- Modify: `agent/skills/zhgk/skill.py`
- Modify: `agent/evals/eval_gkclaw.py`（追加测试）

- [ ] **Step 10.1: 追加失败测试**

```python
# ─── task_dispatch step ───

def _step_ctx(intent="survey_work", extra_project=None):
    """构造 step 级测试环境：work_root + 全量表 + project_info.json。"""
    import json as _json
    from agent.skills.base import SkillContext
    root = tmpdir()
    project = {"intent": intent, "project_code": "K1903",
               "project_name": "智算 Q3 · 客户甲一期", "room_name": "A 机房",
               "activity_id": "ACT001"}
    project.update(extra_project or {})
    ctx = SkillContext(skill_id="zhgk", work_root=root, run_id="r1", project=project)
    ctx.ensure_dirs()
    table = _make_survey_xlsx(ctx.output_dir)
    (ctx.runtime_dir / "project_info.json").write_text(
        _json.dumps({"survey_table_path": table}, ensure_ascii=False), encoding="utf-8")
    return ctx


@test
def step_guard_hitl_and_skip():
    from agent.skills.zhgk.steps.task_dispatch import TaskDispatchStep
    from agent.skills.zhgk.steps._intent_guard import should_skip
    # 仅 survey_work：supplement 守卫直接跳过（用户拍板）
    assert should_skip("task_dispatch", {"intent": "supplement"})
    assert should_skip("task_dispatch", {"intent": "report_gen"})
    assert not should_skip("task_dispatch", {"intent": "survey_work"})
    step = TaskDispatchStep()
    # 无决策 → ChoiceCard HITL（下发/跳过）
    ctx = _step_ctx()
    check = step.check_inputs(ctx)
    assert not check["ok"]
    values = [o["value"] for o in check["need_inputs"][0]["options"]]
    assert values == ["dispatch", "skip"]
    # 决策=skip → 放行，run 记录跳过
    ctx = _step_ctx(extra_project={"dispatch_decision": "skip"})
    assert step.check_inputs(ctx)["ok"]
    result = step.run(ctx, {}, lambda m: None)
    assert result["metrics"]["gkclaw_skipped"] is True


@test
def step_dispatch_dry_run_idempotent():
    import json as _json, os
    from agent.skills.zhgk.steps.task_dispatch import TaskDispatchStep
    from agent.skills.zhgk.services.gkclaw.registry import TaskRegistry
    os.environ.pop("AIDA_SEND_EMAIL", None)   # 默认 dry-run
    step = TaskDispatchStep()
    ctx = _step_ctx(extra_project={"dispatch_decision": "dispatch", "assignees": _ASSIGNEES})
    assert step.check_inputs(ctx)["ok"]
    logs = []
    result = step.run(ctx, {}, logs.append)
    m = result["metrics"]
    assert m["gkclaw_task_id"].startswith("task-") and m["gkclaw_dry_run"] is True
    assert m["gkclaw_state"] == "dispatched" and m["gkclaw_items"] == 2
    info = _json.loads((ctx.runtime_dir / "project_info.json").read_text(encoding="utf-8"))
    assert info["gkclaw_task_id"] == m["gkclaw_task_id"]
    # 再跑（resume 重放）→ 不重复下发，仍报同一任务状态
    result2 = step.run(ctx, {}, logs.append)
    assert result2["metrics"]["gkclaw_task_id"] == m["gkclaw_task_id"]
    assert len(TaskRegistry(ctx.runtime_dir).list_tasks()) == 1


@test
def step_missing_assignees_blocks():
    from agent.skills.zhgk.steps.task_dispatch import TaskDispatchStep
    step = TaskDispatchStep()
    ctx = _step_ctx(extra_project={"dispatch_decision": "dispatch"})  # 无 assignees
    check = step.check_inputs(ctx)
    assert not check["ok"]
    assert any("assignees.json" in x for x in check["missing"])
```

- [ ] **Step 10.2: 跑 eval 确认新增 3 个失败**

Expected: `[eval-gkclaw] FAIL · 37/40`

- [ ] **Step 10.3: 实现 task_dispatch.py**

```python
"""
task_dispatch · GKCLAW 任务下发（视频工勘 App 邮件链路）

意图: survey_work 专属（supplement 不开放，复勘轮 DAG 不回经本步 → 结构性不重发）

HITL ChoiceCard：confirm_table 之后询问「下发到现场 App / 跳过」。
  - dispatch → 现场勘测条目 → gkclaw.mail.v1 ZIP → mailer(mailgw) 发往 frontagent 邮箱
  - skip     → 本地人工勘测，wait_survey 走原有上传通道
重发语义：confirm_table redo 会清 dispatch_decision（skill.apply_resume_payload），
再次下发 = 新 task_id + 旧任务 superseded（contract 无撤销包类型）。
人员来源：project["assignees"] 或 RunTime/gkclaw/assignees.json（缺失 → 文件型 HITL）。
"""
from __future__ import annotations

import json
import os

from ...base import BaseStep, SkillContext, SkillState, StepResult, Emit, CheckResult
from ._intent_guard import should_skip

ASSIGNEES_FILE = "ProjectData/RunTime/gkclaw/assignees.json"


def _get_survey_table(ctx: SkillContext) -> str | None:
    info_path = ctx.runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            path = json.loads(info_path.read_text(encoding="utf-8")).get("survey_table_path", "")
            if path and os.path.exists(path):
                return path
        except Exception:
            pass
    tables = sorted(ctx.output_dir.glob("*全量勘测结果表*.xlsx")) if ctx.output_dir.exists() else []
    return str(tables[0]) if tables else None


def _read_project_info(ctx: SkillContext) -> dict:
    info_path = ctx.runtime_dir / "project_info.json"
    if info_path.exists():
        try:
            return json.loads(info_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _update_project_info(ctx: SkillContext, key: str, value) -> None:
    info = _read_project_info(ctx)
    info[key] = value
    ctx.runtime_dir.mkdir(parents=True, exist_ok=True)
    (ctx.runtime_dir / "project_info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_assignees(ctx: SkillContext) -> list[dict]:
    """人员来源：project payload 优先，其次 RunTime/gkclaw/assignees.json。"""
    a = ctx.project.get("assignees") or []
    if a:
        return list(a)
    f = ctx.runtime_dir / "gkclaw" / "assignees.json"
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


class TaskDispatchStep(BaseStep):
    key = "task_dispatch"
    name = "任务下发"
    artifacts_pattern = []

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        if should_skip(self.key, ctx.project):
            return {"ok": True, "missing": []}

        decision = ctx.project.get("dispatch_decision", "")
        if decision == "skip":
            return {"ok": True, "missing": []}

        # 已下发过（resume 重放）→ 放行，run 内幂等处理
        if _read_project_info(ctx).get("gkclaw_task_id"):
            return {"ok": True, "missing": []}

        survey_table = _get_survey_table(ctx)
        if not survey_table:
            return {"ok": False, "missing": ["ProjectData/Output/*全量勘测结果表*.xlsx"]}

        if decision == "dispatch":
            if not _load_assignees(ctx):
                return {
                    "ok": False,
                    "missing": [ASSIGNEES_FILE],
                    "note": (
                        "下发需要任务分配人员（App/Web 按姓名+工号校验身份）。"
                        '请上传 assignees.json，格式：[{"surveyor_name": "张三", '
                        '"surveyor_code": "S001"}]'
                    ),
                }
            return {"ok": True, "missing": []}

        # 无决策 → ChoiceCard
        return {
            "ok": False,
            "missing": [],
            "need_inputs": [{
                "id": "dispatch_decision",
                "label": "是否下发视频工勘任务到现场 App",
                "options": [
                    {"label": "📤 下发到现场 App（邮件链路）", "value": "dispatch",
                     "description": "现场勘测条目打包为 GKCLAW 任务，经邮件网关发往 frontagent，"
                                    "回传结果自动合并"},
                    {"label": "⏭ 跳过下发（本地人工勘测）", "value": "skip",
                     "description": "沿用原有流程：下载勘测表，现场填写后人工上传"},
                ],
            }],
            "note": "勘测表已确认，可选择经 GKCLAW 邮件链路下发到现场 App",
        }

    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        if should_skip(self.key, ctx.project):
            return {}

        if ctx.project.get("dispatch_decision", "") == "skip":
            emit("[task_dispatch] ⏭ 用户选择跳过下发（本地人工勘测）")
            return {"metrics": {"gkclaw_skipped": True}}

        from ..services.gkclaw.registry import TaskRegistry

        info = _read_project_info(ctx)
        existing = info.get("gkclaw_task_id", "")
        reg = TaskRegistry(ctx.runtime_dir)
        if existing:
            task = reg.get(existing)
            if task and task["state"] not in ("failed", "superseded"):
                emit(f"[task_dispatch] ✓ 任务已下发过：{existing}（状态 {task['state']}），不重复下发")
                return {"metrics": {
                    "gkclaw_task_id": existing,
                    "gkclaw_state": task["state"],
                    "gkclaw_dry_run": bool(task.get("dry_run")),
                    "gkclaw_items": len((reg.task_payload(existing) or {}).get("items", [])),
                    "gkclaw_web_url": task.get("web_access_url", ""),
                }}

        survey_table = _get_survey_table(ctx)
        if not survey_table:
            raise RuntimeError("task_dispatch: 全量勘测结果表不存在")

        from ..services.gkclaw.dispatch import dispatch_task

        emit("[task_dispatch] 打包 GKCLAW 任务（现场勘测条目 + 底表背景知识）…")
        result = dispatch_task(
            runtime_dir=ctx.runtime_dir,
            survey_table_path=survey_table,
            project=ctx.project,
            assignees=_load_assignees(ctx),
            generation_cooling=str(info.get("generation_cooling", "")
                                   or ctx.project.get("generation_cooling", "")),
            previous_task_id=existing,
        )
        _update_project_info(ctx, "gkclaw_task_id", result["task_id"])

        if result["dry_run"]:
            emit(f"[task_dispatch] ✓ dry-run：任务包已生成未发送（{result['task_id']}，"
                 f"{result['items_count']} 条现场条目）")
        else:
            emit(f"[task_dispatch] ✓ 任务包已发出：{result['task_id']}"
                 f"（{result['items_count']} 条，mailgw: "
                 f"{result['send_result'].get('mailgw_status', '')}）")

        return {"metrics": {
            "gkclaw_task_id": result["task_id"],
            "gkclaw_state": result["state"],
            "gkclaw_dry_run": result["dry_run"],
            "gkclaw_items": result["items_count"],
            "gkclaw_message": str(result["send_result"].get("message", "")
                                  or result["send_result"].get("note", "")),
        }}
```

- [ ] **Step 10.4: 接线（三个文件）**

`steps/_intent_guard.py`——`"confirm_table"` 行之后插入：

```python
    "task_dispatch":     frozenset({"survey_work"}),
```

`steps/__init__.py`——`from .confirm_table import ConfirmTableStep` 之后插入一行 import，`__all__` 的 `"ConfirmTableStep",` 之后插入一行；首行 docstring 改为 `"""zhgk skill v4 — 15 个业务 step + preflight（意图驱动单流水线）"""`：

```python
from .task_dispatch import TaskDispatchStep
```
```python
    "TaskDispatchStep",
```

`skill.py` 四处：
① steps import 列表 `ConfirmTableStep,` 之后加 `TaskDispatchStep,`；
② `steps = [...]` 中 `ConfirmTableStep(),` 之后插入：

```python
        TaskDispatchStep(),     # GKCLAW 任务下发（HITL·survey_work 专属）
```

③ `step_retry_keys = ["assess", "report_distribute"]` → `["assess", "report_distribute", "task_dispatch"]`；
④ `apply_resume_payload`：confirm_table 的 redo 分支 `project.pop("data_append_choice", None)` 之后加一行，并新增 task_dispatch 分支（放在 `elif hitl_step == "wait_survey":` 之前）：

```python
                project.pop("dispatch_decision", None)   # 重建表后须重新决策是否下发
```
```python
        elif hitl_step == "task_dispatch" and choice:
            project["dispatch_decision"] = choice
```

同时把 skill.py 顶部 docstring 中 survey_work 流程描述「建表 → 勘测 → …」改为「建表 → 下发/勘测 → 评估 → 问题清单 → 复勘」，apply_resume_payload docstring 的 HITL 门列表加一行 `task_dispatch → project["dispatch_decision"] = choice`。

- [ ] **Step 10.5: 跑 eval 确认通过**

Expected: `[eval-gkclaw] OK · 40/40`

- [ ] **Step 10.6: Commit**

```powershell
git -C D:\.claude_workplace\aida add agent/skills/zhgk/steps/ agent/skills/zhgk/skill.py agent/evals/eval_gkclaw.py
git -C D:\.claude_workplace\aida commit -m "feat(zhgk): task_dispatch step（HITL 下发/跳过·dry-run·幂等重放·redo 清决策）"
```

⚠️ 此时 `lint_skill_contract` 预期**红**（代码有 task_dispatch、SKILL.md 还没有）——Task 12 修复，本任务不跑该守门。

---

### Task 11: wait_survey 邮件拉取钩子

**Files:**
- Modify: `agent/skills/zhgk/steps/wait_survey.py`
- Modify: `agent/evals/eval_gkclaw.py`（追加测试）

- [ ] **Step 11.1: 追加失败测试**

```python
# ─── wait_survey gkclaw 钩子 ───

@test
def wait_survey_shows_gkclaw_state_and_accepts_mailed_result():
    import json as _json
    from agent.skills.zhgk.steps.task_dispatch import TaskDispatchStep
    from agent.skills.zhgk.steps.wait_survey import WaitSurveyStep
    from agent.skills.zhgk.services.gkclaw import ingest
    from agent.skills.zhgk.services.gkclaw.registry import TaskRegistry
    # 下发（dry-run）后进入 wait_survey：note 应展示 GKCLAW 任务状态
    ctx = _step_ctx(extra_project={"dispatch_decision": "dispatch", "assignees": _ASSIGNEES})
    TaskDispatchStep().run(ctx, {}, lambda m: None)
    ws = WaitSurveyStep()
    check = ws.check_inputs(ctx)
    assert not check["ok"]
    tid = _json.loads((ctx.runtime_dir / "project_info.json").read_text(encoding="utf-8"))["gkclaw_task_id"]
    assert tid in check["note"] and "dispatched" in check["note"]
    # 模拟邮件 final 到达（直接走 ingest，等价于钩子拉取后的落盘效果）
    tp = TaskRegistry(ctx.runtime_dir).task_payload(tid)
    table = _json.loads((ctx.runtime_dir / "project_info.json").read_text(encoding="utf-8"))["survey_table_path"]
    out = ingest.ingest_zip(_result_zip(tp, tmpdir(), status="completed"),
                            runtime_dir=ctx.runtime_dir, input_dir=ctx.input_dir,
                            survey_table_path=table)
    assert out["merged"] is True
    # 已填写表落 Input → wait_survey 放行，run 走原有合并通道
    check2 = ws.check_inputs(ctx)
    assert check2["ok"]
    result = ws.run(ctx, {}, lambda m: None)
    assert result["metrics"]["filled_count"] == 2
```

- [ ] **Step 11.2: 跑 eval 确认新增 1 个失败**

Expected: `[eval-gkclaw] FAIL · 40/41`（note 中无 task_id —— 钩子未实现）

- [ ] **Step 11.3: 实现钩子**

`wait_survey.py` ① `WaitSurveyStep` 类中新增方法（放在 `check_inputs` 之前）：

```python
    def _gkclaw_status_note(self, ctx: SkillContext) -> str:
        """GKCLAW 链路钩子：有已下发任务时拉取邮件回传并返回状态行（异常不阻断流程）。

        dry-run 任务或 mailgw 未配置时只展示状态不拉取（边界 C9/C10：拉取发生在
        本 check 被调用时——run 启动与每次 resume；无后台轮询）。
        """
        try:
            info_path = ctx.runtime_dir / "project_info.json"
            if not info_path.exists():
                return ""
            info = json.loads(info_path.read_text(encoding="utf-8"))
            tid = info.get("gkclaw_task_id", "")
            if not tid:
                return ""
            from ..services.gkclaw.registry import TaskRegistry
            reg = TaskRegistry(ctx.runtime_dir)
            task = reg.get(tid)
            if task is None:
                return ""
            alerts: list[str] = []
            if not task.get("dry_run"):
                import agent.mailbox as mailbox
                if mailbox.is_configured() and task["state"] in (
                        "dispatched", "accepted", "staged_returned"):
                    from ..services.gkclaw.ingest import poll_and_ingest
                    summary = poll_and_ingest(
                        runtime_dir=ctx.runtime_dir, input_dir=ctx.input_dir,
                        survey_table_path=_get_survey_table(ctx))
                    alerts = list(summary.get("alerts", []))
                    task = reg.get(tid) or task
            bits = [f"GKCLAW 任务 {tid} · 状态 {task['state']}"]
            if task.get("dry_run"):
                bits.append("dry-run 未真发")
            if task.get("web_access_url"):
                bits.append(f"现场 Web 入口 {task['web_access_url']}")
            if task.get("merge_blocked"):
                bits.append(f"⚠ 合并阻塞：{task.get('merge_blocked_reason', '')}")
            return "；".join(bits) + ("；" + "；".join(alerts[-3:]) if alerts else "")
        except Exception as e:  # noqa: BLE001 — 邮件链路异常绝不阻断人工上传通道
            return f"[gkclaw] 拉取回传失败：{e}"
```

② `check_inputs` 中，`resurvey_pending = ...` 一行之前插入 `gk_note = self._gkclaw_status_note(ctx)`；两处「等待上传」返回分支的 `"note":` 值改为在原文案后拼接 GKCLAW 状态行：

```python
        gk_note = self._gkclaw_status_note(ctx)
```

正常流程分支的返回改为：

```python
        base_note = (
            "请从 Output/ 下载全量勘测结果表，完成现场勘测后填写「最新检查结果」列，"
            f"将文件保存为 {UPLOADED_FILENAME} 后上传到 ProjectData/Input/"
        )
        return {
            "ok": False,
            "missing": [f"ProjectData/Input/{UPLOADED_FILENAME}"],
            "note": base_note + (f"\n{gk_note}" if gk_note else ""),
        }
```

复勘分支同理在原 note 末尾拼 `(f"\n{gk_note}" if gk_note else "")`。

- [ ] **Step 11.4: 跑 eval 确认通过**

Expected: `[eval-gkclaw] OK · 41/41`

- [ ] **Step 11.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add agent/skills/zhgk/steps/wait_survey.py agent/evals/eval_gkclaw.py
git -C D:\.claude_workplace\aida commit -m "feat(zhgk): wait_survey 接 GKCLAW 拉取钩子（双源·状态可见·异常不阻断）"
```

---

### Task 12: A 层 SKILL.md 契约同步 + SDUI 状态卡

**Files:**
- Modify: `skills/zhgk/SKILL.md`
- Modify: `agent/skills/zhgk/sdui.py`
- Modify: `agent/evals/eval_gkclaw.py`（追加测试）

- [ ] **Step 12.1: 更新 SKILL.md（lint_skill_contract 的 A≡B 契约）**

① 标题 `## A. 业务流程（14 个步骤 · 意图驱动）` → `（15 个步骤 · 意图驱动）`；
② 流程表在 confirm_table 行后插入新行并将原 8-14 行重编号为 9-15（仅改步骤号列，其余列不动）：

```markdown
| 8 | 任务下发 | 确认后的勘测表 → GKCLAW 任务包邮件下发（HITL） | survey_work | `task_dispatch` |
```

③ §D 意图选项表适用步骤号同步：survey_work `步骤 3-11` → `步骤 3-12`；report_gen `步骤 3, 9-10, 13-14` → `步骤 3, 10-11, 14-15`；supplement `步骤 3, 12` → `步骤 3, 13`；
④ §E HITL 表 confirm_table 行后插入：

```markdown
| task_dispatch | ChoiceCard | 勘测表确认完成后 | 下发到现场 App / 跳过（本地人工勘测） |
```

- [ ] **Step 12.2: 追加 SDUI 卡失败测试**

```python
# ─── sdui gkclaw 卡 ───

@test
def sdui_gkclaw_card_renders():
    from agent.skills.zhgk.sdui import _build_gkclaw_card, ZHGK_STEP_NAMES, ZHGK_MACRO_PHASES
    assert ZHGK_STEP_NAMES.get("task_dispatch") == "任务下发"
    assert "task_dispatch" in ZHGK_MACRO_PHASES[2][3]   # survey 阶段含 task_dispatch
    state = {"metrics": {"gkclaw_task_id": "task-20260611-K1903-000001",
                         "gkclaw_state": "accepted", "gkclaw_dry_run": False,
                         "gkclaw_items": 12,
                         "gkclaw_web_url": "https://front-agent.example.com/tasks/web/wa_x"},
             "steps": [], "logs": [], "project": {"intent": "survey_work"}}
    card = _build_gkclaw_card(state)
    assert card is not None and card.id == "gkclaw-card"
    assert _build_gkclaw_card({"metrics": {}, "steps": [], "logs": []}) is None
```

- [ ] **Step 12.3: 跑 eval 确认新增 1 个失败 → 实现 sdui.py 三处修改**

① `ZHGK_STEP_NAMES` 的 `"confirm_table": "勘测表确认",` 行后插入：

```python
    "task_dispatch":     "任务下发",
```

② `ZHGK_MACRO_PHASES` survey 阶段的 step 列表 `"confirm_table",` 后插入 `"task_dispatch",`；
③ 文件头部 Metrics 键约定注释块加一行：

```python
  task_dispatch    → gkclaw_task_id · gkclaw_state · gkclaw_dry_run · gkclaw_items · gkclaw_web_url
```

④ `_build_resurvey_history` 之后新增卡构建器，并在 `project()` 的 `center_children` 元组中 `_build_resurvey_history(state),` 之后插入 `_build_gkclaw_card(state),`：

```python
def _build_gkclaw_card(state: dict[str, Any]) -> SduiCardNode | None:
    """GKCLAW 任务下发状态卡（task_dispatch 后出现）。
    展示 task_id / 链路状态 / dry-run 提示 / 现场 Web 入口 / 合并告警。"""
    m = collect_metrics(state)
    tid = m.get("gkclaw_task_id")
    if not tid:
        return None
    labels = {"planned": "已编排", "dispatched": "已下发", "accepted": "对端已导入",
              "staged_returned": "已收阶段回传", "completed": "已完成",
              "failed": "失败", "superseded": "已被新任务取代"}
    st = str(m.get("gkclaw_state", ""))
    badge = {"completed": "done", "failed": "fail"}.get(st, "run")
    children: list[SduiNode] = [
        SduiStatusBannerNode(id="gkclaw-banner", items=[
            SduiStatusItem(status=badge, text=f"{tid} · {labels.get(st, st)}"),  # type: ignore[arg-type]
        ]),
    ]
    bits: list[str] = []
    if m.get("gkclaw_dry_run"):
        bits.append("dry-run：任务包已生成未发送（设 AIDA_SEND_EMAIL=1 真发）")
    if m.get("gkclaw_items") is not None:
        bits.append(f"下发现场条目 {m['gkclaw_items']} 条")
    if m.get("gkclaw_web_url"):
        bits.append(f"现场 Web 入口：{m['gkclaw_web_url']}")
    if m.get("gkclaw_message"):
        bits.append(str(m["gkclaw_message"]))
    if bits:
        children.append(SduiAlertNode(id="gkclaw-info", tone="info",
                                      title="GKCLAW 邮件链路", message="；".join(bits)))
    return SduiCardNode(id="gkclaw-card", title="任务下发（GKCLAW）", children=children)
```

- [ ] **Step 12.4: 跑 eval + 契约守门**

```powershell
D:\.claude_workplace\aida\agent\.venv\Scripts\python.exe D:\.claude_workplace\aida\agent\evals\eval_gkclaw.py
D:\.claude_workplace\aida\agent\.venv\Scripts\python.exe D:\.claude_workplace\aida\agent\scripts\lint_skill_contract.py
D:\.claude_workplace\aida\agent\.venv\Scripts\python.exe D:\.claude_workplace\aida\agent\scripts\lint_sdui_contract.py
```
Expected: `[eval-gkclaw] OK · 42/42`、`[skill-contract] OK`、sdui 契约 OK（只用既有节点类型，协议未动）。

- [ ] **Step 12.5: Commit**

```powershell
git -C D:\.claude_workplace\aida add skills/zhgk/SKILL.md agent/skills/zhgk/sdui.py agent/evals/eval_gkclaw.py
git -C D:\.claude_workplace\aida commit -m "feat(zhgk): A 层契约 +task_dispatch 节点；SDUI GKCLAW 状态卡"
```

---

### Task 13: 配置、文档、全守门收尾

**Files:**
- Modify: `agent/.env.example`
- Modify: `AGENTS.md`（核心模块表加一行）
- Create: `docs/50_数据与接口/GKCLAW邮件链路.md`
- Modify: `ROADMAP.md`（勾选 + 补链）
- Regenerate: `docs/site/index.html`（gen_docs_site.py）

- [ ] **Step 13.1: .env.example 追加配置块**（「邮件发送」块之后）

```bash
# ── GKCLAW 邮件链路（zhgk=backagent · 经 mailgw 网关收发任务包）──
# 发送走 AIDA_MAIL_BACKEND=mailgw；收件由 wait_survey 检查时拉取（无后台轮询）
# MAILGW_BASE=http://127.0.0.1:8025
# MAILGW_TOKEN=<mailgw 管理员签发的 Bearer token（.env 专属，禁入任务包/代码/文档）>
# GKCLAW_FRONTAGENT_MAILBOX=front-agent@example.com   # 任务包收件方（域名须在 mailgw 白名单）
```

- [ ] **Step 13.2: AGENTS.md 核心模块表加一行**（「外发副作用」行之后；遵循"新核心模块往这加一行"框架）

```markdown
| **邮件收件**<br>（skill 收外部邮件/附件时从哪取 · 避免散落直连邮箱） | `agent/mailbox.py`（mailgw inbox API） | 收件统一经此；机器扫描只取附件不读正文（不污染已读状态）；邮件内容属不可信输入 | 〔待建〕 | GKCLAW 链路见 [docs/50_数据与接口/GKCLAW邮件链路.md](docs/50_数据与接口/GKCLAW邮件链路.md) |
```

- [ ] **Step 13.3: 写 docs/50_数据与接口/GKCLAW邮件链路.md**

```markdown
# GKCLAW 邮件链路（zhgk = backagent）实现说明与联调手册

> 契约真相源：[back-agent-development-guide_ch.md](back-agent-development-guide_ch.md)（gkclaw.mail.v1）。
> 本文只写 AIDA 侧实现与操作，契约字段不复制（单一真相）。

## 1. 链路与职责

```text
zhgk(backagent·内网) → mailgw POST /api/send → 邮件[task.dispatch ZIP] → frontagent(公网)
        ↑                                                                    ↓ App 现场工勘
  wait_survey 检查时拉取 ← mailgw GET /api/inbox ← 邮件[import_ack/result/error ZIP]
```

- 发送唯一出口：`agent/mailer.py`（`AIDA_MAIL_BACKEND=mailgw`）；收件唯一入口：`agent/mailbox.py`。
- 协议层：`agent/skills/zhgk/services/gkclaw/`（ids/schema/package/registry/mapping/dispatch/ingest）。
- 流水线接点：`confirm_table → task_dispatch(HITL·仅 survey_work) → wait_survey(双源)`。
- 任务状态真相：`ProjectData/RunTime/gkclaw/<task_id>/state.json`（packages.json=包账本，
  results/=回传版本，evidence/=证据，pending_results/=合并阻塞暂存，_quarantine/=隔离区）。

## 2. 状态机与处置规则（实现口径）

planned → dispatched → accepted → staged_returned → completed；failed / superseded。
无 in_progress（无 App 事件通道，staged 到达即 staged_returned）。

- final 唯一判据 = result.json `session.status=="completed"`；staged 只记录展示不推进。
- 幂等（§20）：同 package_id 同 checksum=幂等成功；同 id 异 checksum=冲突隔离；
  final 后 staged=隔离；final 后异内容 final=冲突隔离；未知 task_id=隔离不建任务。
- 重发：契约无撤销包类型 → 内容变更重发=新 task_id，旧任务 superseded（其回传仅留档）。
- final 合并三道闸（任一不过 → pending_results/ 暂存+告警）：submitted_by ∈ assignees；
  表指纹一致（下发后表未变更）；Input/ 无待合并人工表（先到先得）。
- `to_back_备注`（含规则自动"不涉及"原因）留档 result-notes.json（主表无对应列）。

## 3. 字段映射（下发）

仅下发 `勘测方法=="现场勘测"` 行。问题序号=str(序号)；勘测项=检查内容；选项列表=[]；
to_front_备注=【勘测要素/项目】+ 底表`视频勘测背景知识`（自然键回连底表取回，join 失败置空），
`语音助手背景知识`不同则附加；细分场景/是否支持视频勘测/底表序号进 item.metadata。
分簇=物理空间维度：v1 单兜底簇 cluster-all（cluster_name=机房名）；底表增设「物理位置」
列后经 `mapping.derive_clusters(cluster_values=…)` 零代码切换多簇。

## 4. 配置（agent/.env）

| 变量 | 说明 |
|---|---|
| `AIDA_SEND_EMAIL=1` | 真发开关（默认 dry-run：建包登记不发邮件） |
| `AIDA_MAIL_BACKEND=mailgw` | 发送走 mailgw 网关 |
| `MAILGW_BASE` / `MAILGW_TOKEN` | 网关地址与 Bearer token（密钥只进 .env） |
| `GKCLAW_FRONTAGENT_MAILBOX` | frontagent 收件邮箱（**域名须加入 mailgw 白名单**，否则下发卡审批队列） |

人员配置：start payload `assignees` 或 `ProjectData/RunTime/gkclaw/assignees.json`
（`[{"surveyor_name":"张三","surveyor_code":"S001"}]`）；缺失时 task_dispatch 文件型 HITL 阻断。

## 5. 联调流程（契约 §23 对应）

前置交换：对方 frontagent 收件邮箱→填 `GKCLAW_FRONTAGENT_MAILBOX` 并加 mailgw 白名单；
我方 mailgw 邮箱地址告知对方（回传目的地）；双方确认 schema_version=gkclaw.mail.v1、
附件大小上限（mailgw `max_attachment_mb`）。

1. zhgk 跑 survey_work 至 confirm_table 确认 → task_dispatch 选「下发」。
2. 对端导入后回 ACK → wait_survey 卡片出现「对端已导入 + 现场 Web 入口」。
3. App 按 assignees 姓名+工号登录可见任务；阶段回传 → 状态 staged_returned（不推进）。
4. 现场结束任务（final）→ 自动转写 `Input/已填写_全量勘测结果表.xlsx` → wait_survey
   合并 → assess 继续。提示：拉取发生在 wait_survey 检查时（run 启动/每次 resume），
   等邮件期间在页面上提交一次空 resume 即触发刷新。
5. 异常对账：`RunTime/gkclaw/` 下看 state.json/packages.json；隔离包看 `_quarantine/`；
   合并阻塞看任务 `merge_blocked_reason` 与 `pending_results/`。

## 6. 验收对照（契约 §24 → 实现/证据）

| 验收项 | 实现 | 证据 |
|---|---|---|
| 合法 dispatch ZIP（manifest+task.json） | package.build_package | eval: package_build_parse_roundtrip |
| task_id 全局唯一稳定 | ids.new_task_id（seq.txt） | eval: ids_task_id_format_and_uniqueness |
| 项目/人员/任务名下发 | mapping.build_task_payload | eval: mapping_builds_contract_task |
| 非空 item_clusters | derive_clusters 兜底簇 | eval: mapping_clusters_default_single |
| 依赖规则引用校验 | schema.validate_task | eval: schema_task_dependency_rules |
| 发送任务邮件 | mailer mailgw backend | eval: mailer_mailgw_backend_sends |
| 接收并保存 web_access_url | ingest._apply_ack | eval: ingest_ack_updates_state… |
| manifest/checksum 校验 | package.parse_package | eval: package_checksum_tamper_detected |
| staged/final 区分（session.status） | ingest._apply_result | eval: ingest_staged_records_final… |
| 按 task_id 关联、按 submitted_by 识别 | registry + 安全闸 1 | eval: ingest_submitted_by_guard |
| 规则"不涉及"作为正常结果入库+备注留档 | 合并通道 + result-notes.json | eval: final 用例断言 notes |
| 重复包/重复 ACK/重复结果幂等 | decide_inbound | eval: registry_decide_inbound… / ingest_idempotency… |
| 冲突隔离（同 id 异内容/final 后） | decide_inbound + _quarantine | 同上 |
| 对账诊断 | state.json/packages.json/mail_scan.json + SDUI 卡 | 人工巡检（自动对账=后续增强） |

## 7. 已知边界与后续增强

仅 survey_work 下发（supplement 下期）；复勘轮不自动重发（人工上传）；无后台轮询
（cron 自动拉取=后续）；evidence 不回填表内图片列；单 mailgw ↔ 单 AIDA 实例
（workers=1 单写者）；依赖规则编排器、示例图资产、对账页面=后续增强。
```

- [ ] **Step 13.4: ROADMAP 勾选**

把立项小节 7 个 checkbox 全部改 `[x]`（最后一条改为 `[x] 全部 10 守门绿；真实联调待 frontagent 邮箱配置（操作见 GKCLAW邮件链路.md §5）`），并把小节引言第二行补上实链。

- [ ] **Step 13.5: 重生成 docs site + 全守门**

```powershell
cd D:\.claude_workplace\aida
agent\.venv\Scripts\python.exe agent\scripts\gen_docs_site.py
agent\.venv\Scripts\python.exe agent\evals\eval_gkclaw.py
agent\.venv\Scripts\python.exe agent\evals\eval_zhgk.py --fixture
agent\.venv\Scripts\python.exe agent\scripts\lint_no_naked_llm.py
agent\.venv\Scripts\python.exe agent\scripts\lint_no_naked_send.py
agent\.venv\Scripts\python.exe agent\scripts\lint_skill_contract.py
agent\.venv\Scripts\python.exe agent\scripts\lint_tools.py
agent\.venv\Scripts\python.exe agent\scripts\lint_sdui_contract.py
agent\.venv\Scripts\python.exe agent\scripts\lint_sdui_gallery.py
agent\.venv\Scripts\python.exe agent\scripts\lint_docs_site.py
agent\.venv\Scripts\python.exe agent\scripts\lint_team_portal.py
agent\.venv\Scripts\python.exe agent\scripts\lint_runtime_contract.py
agent\.venv\Scripts\python.exe agent\scripts\lint_module_boundaries.py
```
Expected: eval_gkclaw `OK · 42/42`；eval_zhgk fixture 不回退；10 个 lint 全 `OK`。
任何红灯：修复后重跑（lint_docs_site 红=忘跑 gen_docs_site；lint_module_boundaries 红=检查
gkclaw 是否被其他 skill 横向 import——本设计只在 zhgk 内部与 agent/ 层，不应触发）。

- [ ] **Step 13.6: 收尾 Commit（不 push）**

```powershell
git -C D:\.claude_workplace\aida add -A
git -C D:\.claude_workplace\aida commit -m "docs(gkclaw): 配置模板/AGENTS 收件入口/链路实现说明与联调手册；ROADMAP 勾选"
git -C D:\.claude_workplace\aida log --oneline master..HEAD
```

**完成定义（DoD）**：42/42 eval 全绿 + 10 守门全绿 + SKILL.md≡steps + ROADMAP 已勾选。
**不做**：push（仓规须用户确认）、mailgw 仓改动、真实邮箱联调（等对方信息，按文档 §5 执行）。

---

## Self-Review 记录

- **Spec 覆盖**：契约 §24 验收清单 15 项逐条映射见 Task 13 文档 §6 表；用户拍板项
  （仅 survey_work / 先到先得 / 物理空间分簇 / superseded 重发 / staged 不推进 / dry-run 贯通 /
  收件箱不动已读）分别落在 Task 10/9/5/8/9/8/7+9，各有对应 eval 断言。
- **占位符扫描**：全计划无 TBD/TODO；每个代码步骤含完整可落盘代码。
- **类型一致性**：跨任务签名已互查——`dispatch_task(runtime_dir, survey_table_path, project,
  assignees, dry_run, send_fn, frontagent_mailbox, generation_cooling, survey_round,
  previous_task_id)`、`ingest_zip(zip_path, runtime_dir, input_dir, survey_table_path, mail_id)`、
  `decide_inbound(task, known_packages, package_type, package_id, checksum, session_status)`、
  metrics 键 `gkclaw_*` 与 SDUI 卡读取一致；幂等测试已修正为"原包重放"（重 build 会因
  created_at 变 checksum，正确判 conflict）。
- **eval 计数**：T1=4 → T2=9 → T3=15 → T4=19 → T5=23 → T6=25 → T7=27 → T8=30 → T9=37
  → T10=40 → T11=41 → T12=42。




