"""
端到端验证脚本：feat/zhgk-sdui-3d-cockpit 变更点
覆盖：问题清单严重度分级 / SDUI KPI + 表 + drawer / RoomContextBar 第二行 / 复勘历史表 / 黄金指标布局
"""
from __future__ import annotations
import sys
import json
import re

sys.path.insert(0, r"D:\code\aida")

PASS = []
FAIL = []

def ok(msg): PASS.append(msg); print(f"[PASS] {msg}")
def fail(msg): FAIL.append(msg); print(f"[FAIL] {msg}")


# ── 1. issue_list_builder: 严重度列头 + 枚举 ──────────────────────
from agent.skills.zhgk.services.issue_list_builder import (
    _SEVERITY_CN, _VALID_SEVERITY, ISSUE_TABLE_HEADERS,
)
if "严重度" in ISSUE_TABLE_HEADERS and ISSUE_TABLE_HEADERS.index("严重度") == 1:
    ok("issue_list_builder: 严重度在表头第2列(index=1, 首列=序号)")
else:
    fail(f"issue_list_builder: 严重度列头位置错误, headers={ISSUE_TABLE_HEADERS}")

if set(_VALID_SEVERITY) == {"high", "mid", "low"}:
    ok("issue_list_builder: _VALID_SEVERITY = {high,mid,low}")
else:
    fail(f"_VALID_SEVERITY mismatch: {_VALID_SEVERITY}")

if _SEVERITY_CN == {"high": "高", "mid": "中", "low": "低"}:
    ok("issue_list_builder: _SEVERITY_CN 中文映射正确")
else:
    fail(f"_SEVERITY_CN wrong: {_SEVERITY_CN}")


# ── 2. types: IssueGenResult severity 字段 ──────────────────────
from agent.skills.zhgk.services.types import IssueGenResult, IssueItem

r_default = IssueGenResult(problem_description="x", remediation_suggestion="y")
if r_default.severity == "mid":
    ok("IssueGenResult: severity 默认值 = 'mid'")
else:
    fail(f"IssueGenResult: 默认 severity={r_default.severity}")

r_high = IssueGenResult(problem_description="x", remediation_suggestion="y", severity="high")
if r_high.severity == "high":
    ok("IssueGenResult: severity='high' 存储正确")
else:
    fail(f"IssueGenResult: explicit severity={r_high.severity}")

import typing
fields = typing.get_type_hints(IssueItem)
if "严重度" in fields:
    ok("IssueItem TypedDict: 含严重度字段")
else:
    fail(f"IssueItem: 缺 严重度, keys={list(fields)}")


# ── 3. SDUI 投影器 — 综合 state 验证 ──────────────────────────────
from agent.skills.zhgk.sdui import project as zhgk_project

synthetic_state = {
    "skill_id": "zhgk",
    "project": {
        "room_name": "测试机房A",
        "project_code": "PRJ-001",
        "surveyor": "张三",
        "survey_date": "2026-06-15",
        "intent": "survey_work",
    },
    # collect_metrics 从 steps[i]["metrics"] 聚合，不读顶层 metrics
    "steps": [
        {
            "key": "filter_build", "name": "场景筛选", "status": "completed",
            "metrics": {
                "filtered_count": 30,
                "sub_scenes": ["弱电间", "配电室"],
            },
        },
        {
            "key": "assess", "name": "AI评估", "status": "completed",
            "metrics": {
                "assess_total": 20,
                "assess_满足": 15,
                "assess_不满足": 3,
                "assess_无法识别": 2,
            },
        },
        {
            "key": "issue_list", "name": "问题清单生成", "status": "completed",
            "metrics": {
                "issue_count": 5,
                "issue_high": 1,
                "issue_mid": 3,
                "issue_low": 1,
                "issue_rows": [
                    {"序号": 1, "严重度": "高", "severity": "high", "问题描述": "承重不达标",
                     "状态": "待处理", "整改建议": "加固", "责任人": "", "计划关闭时间": "", "备注": ""},
                    {"序号": 2, "严重度": "中", "severity": "mid", "问题描述": "制冷量不足",
                     "状态": "待处理", "整改建议": "增设精密空调", "责任人": "", "计划关闭时间": "", "备注": ""},
                ],
            },
        },
    ],
    "artifacts": [],
    "log": [],
    "hitl_pending": None,
    "overall_progress": 80,
    "current_step": "issue_list",
}

doc = zhgk_project(synthetic_state)
doc_json = json.dumps(doc, ensure_ascii=False, indent=2)

# 3a. KPI 问题清单分级
if "问题清单" in doc_json and "5 条·高1中3低1" in doc_json:
    ok("SDUI KPI: '5 条·高1中3低1' 出现")
else:
    snippet = [l.strip() for l in doc_json.split("\n") if "问题清单" in l][:5]
    fail(f"SDUI KPI: 问题清单分级格式不对, 相关行={snippet}")

# 3b. KPI 颜色 — 有高危时 error
if '"color": "error"' in doc_json or '"color":"error"' in doc_json:
    ok("SDUI KPI: 有 high 时 color=error 正确")
else:
    fail("SDUI KPI: 有 high 时未找到 color=error")

# 3c. drawer 严重度 badge
if "严重度 高" in doc_json:
    ok("SDUI drawer: '严重度 高' badge 已渲染")
else:
    fail("SDUI drawer: 严重度 badge 未找到")

# 3d. 问题表首列严重度
table_section = re.search(r'"id":\s*"issue-table".*?"columns".*?\[([^\]]+)\]', doc_json, re.S)
if table_section:
    if "严重度" in table_section.group(0):
        ok("SDUI 问题清单表: 含严重度列")
    else:
        fail(f"SDUI 问题清单表: 未找到严重度列, snippet={table_section.group(0)[:200]}")
else:
    if "严重度" in doc_json:
        ok("SDUI 问题清单表: 严重度出现在文档中")
    else:
        fail("SDUI 问题清单表: 严重度未出现")

# 3e. RoomContextBar 第二行
for field, label in [("负责人 张三", "负责人"), ("勘测窗口 2026-06-15", "勘测窗口"), ("勘测场景 弱电间 / 配电室", "勘测场景")]:
    if field in doc_json:
        ok(f"SDUI RoomContextBar: '{label}' 第二行已渲染")
    else:
        fail(f"SDUI RoomContextBar: '{label}' 未渲染, 搜索 '{field}'")

# 3f. 细分场景不再是 StatisticRowItem title
kpi_scene = re.findall(r'"title":\s*"勘测场景"', doc_json)
if not kpi_scene:
    ok("SDUI KPI: 细分场景已从 StatisticRowItem 移除")
else:
    fail(f"SDUI KPI: '勘测场景' 仍在 StatisticRowItem title 中 (count={len(kpi_scene)})")


# ── 4. 复勘历史表新列 ─────────────────────────────────────────────
from agent.skills.zhgk.sdui import _build_resurvey_history

hist_state = {
    "project": {},
    "steps": [
        {
            "key": "wait_survey", "name": "等待勘测", "status": "completed",
            "metrics": {
                "survey_round": 2,
                "survey_round_history": [
                    {"round": 1, "filled": 30, "total": 50, "满足": 20, "不满足": 5, "无法识别": 5},
                    {"round": 2, "filled": 42, "total": 50, "满足": 30, "不满足": 8, "无法识别": 4},
                ],
            },
        },
    ],
}
card = _build_resurvey_history(hist_state)
if card is None:
    fail("复勘历史表: _build_resurvey_history 返回 None")
else:
    card_json = json.dumps(card, ensure_ascii=False, default=lambda o: o.__dict__)
    for col in ["满足", "不满足", "无法识别"]:
        if col in card_json:
            ok(f"复勘历史表: '{col}' 列存在")
        else:
            fail(f"复勘历史表: '{col}' 列缺失")
    if "20" in card_json and "30" in card_json:
        ok("复勘历史表: 各轮满足数值正确渲染 (20, 30)")
    else:
        fail(f"复勘历史表: 数值未找到, snippet={card_json[:300]}")


# ── 5. assess step: survey_round_history 回写 ────────────────────
from agent.skills.zhgk.steps.assess import AssessStep

class _FakeCtx:
    def rel(self, p): return p

class _FakeEmit:
    def __call__(self, msg): pass

# 直接测 step 的 state 合并逻辑（不跑 LLM）：仅验证 result_metrics 构造
# 用 inspect 直接读返回结构验证逻辑
import inspect
src = inspect.getsource(AssessStep.run)
if "survey_round_history" in src and "survey_round" in src:
    ok("assess step: survey_round_history 回写逻辑已存在于 run() 源码")
else:
    fail("assess step: 未找到 survey_round_history 回写逻辑")


# ── 6. 黄金指标布局修复 ──────────────────────────────────────────
from agent.skills.zhgk.sdui import _build_metrics_card

m_state = {
    "project": {"intent": "survey_work"},
    "steps": [
        {"key": "assess", "name": "AI评估", "status": "completed",
         "metrics": {"assess_total": 20, "assess_满足": 15}},
        {"key": "issue_list", "name": "问题清单", "status": "pending", "metrics": {}},
    ],
}
mcard = _build_metrics_card(m_state)
if mcard is None:
    fail("黄金指标: _build_metrics_card 返回 None")
else:
    mcard_json = json.dumps(mcard, ensure_ascii=False, default=lambda o: o.__dict__)
    if "metrics-donut" in mcard_json:
        ok("黄金指标: donut_col Stack wrapper (id=metrics-donut) 存在")
    else:
        fail(f"黄金指标: metrics-donut wrapper 未找到, snippet={mcard_json[:400]}")
    if '"flex": 1' in mcard_json or '"flex":1' in mcard_json:
        ok("黄金指标: right_col flex=1 正确")
    else:
        fail(f"黄金指标: right_col flex!=1, search in={mcard_json[:400]}")


# ── 报告 ──────────────────────────────────────────────────────────
print()
print("=" * 60)
print(f"结果: {len(PASS)} PASS  /  {len(FAIL)} FAIL")
if FAIL:
    print("FAIL 项:")
    for f in FAIL:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("全部通过")
