"""
意图识别规则引擎 · 对齐原始 a3 `lld-intent-recognition`（Step 0 确定性匹配链）。

数据单一来源 = vendored a3_engine 的三份 MD（taxonomy / aliases / keywords），
解析失败时回退内置最小命令集，保证 robust。

匹配链（命中即停，与原始 SKILL.md §2 CLASSIFYING 一致）：
  1. 三级精准   2. LLD 特殊规则   3. 二级精准   4. 一级精准
  5. 别名精准   6. 关键词全包含（最长优先 + 规划类型消歧）

结果三态（原始 §3 结果判定）：
  - RESOLVED   ：单一标准命令
  - CLARIFYING ：多候选并列，需追问（不得擅自选定）
  - FAILED     ：无任何合理分类（含不支持范围）→ 固定失败话术

语义近似（需 LLM）不在本引擎内：规则链耗尽返回 FAILED，由 step 决定是否调 LLM 兜底。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from ..pipelines.a3_paths import get_a3_code_root

# 固定失败话术（原始 intent-recognition SKILL.md §输出约束 / intent_router.FAILED_MESSAGE）
FAILED_MESSAGE = (
    "当前问题不属于LLD设计支持范围，请输入地址规划、互联规划、接入规划、LLD设计等相关指令。"
)

# CLARIFYING 追问时最多给出的候选数（原始 skill 追问列出候选，本工程限制为 3 项，避免选项过多）
MAX_CLARIFY_CANDIDATES = 3

# 不支持范围（Raw Skill A016）：识别到也归 FAILED，不进入执行
UNSUPPORTED_COMMANDS = {
    "防火墙互联规划",
    "知识问答",
    "网络地址规划知识",
    "LLD设计知识",
    "系统能能力与使用指南",
    "使用指引",
}

# MD 解析失败时的兜底命令集（仅精准匹配可用）
_FALLBACK_COMMANDS = [
    "生成完整LLD设计", "融合完整LLD设计",
    "地址规划", "互联规划", "接入规划", "网管规划", "路由规划",
    "计算带外管理地址规划", "网络带外管理地址规划",
    "存储带外管理地址规划", "灵衢带外管理地址规划",
    "检查输入件是否妥当", "生成ZTP设计文件", "生成灵衢开局文件", "替换设备名称",
]


@dataclass
class IntentMatch:
    status: str  # resolved | clarifying | failed
    command: str = ""
    candidates: list[str] = field(default_factory=list)
    message: str = ""
    source: str = ""  # exact_l3 | lld_rule | exact_l2 | exact_l1 | alias | keyword | unsupported


# ── MD 解析 ──────────────────────────────────────────────────────────────

def _md_dir():
    return get_a3_code_root() / "subskills" / "lld-intent-recognition.code1"


def _read_md(name: str) -> str:
    p = _md_dir() / name
    try:
        return p.read_text("utf-8") if p.is_file() else ""
    except Exception:
        return ""


def _sections(md: str) -> dict[str, str]:
    secs: dict[str, str] = {}
    cur, buf = None, []
    for line in md.splitlines():
        if line.startswith("## "):
            if cur is not None:
                secs[cur] = "\n".join(buf)
            cur, buf = line[3:].strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        secs[cur] = "\n".join(buf)
    return secs


def _table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells if c) and any(cells):
            continue  # 分隔行 |---|
        rows.append(cells)
    return rows


def _split_terms(cell: str) -> list[str]:
    """按 、，/ 拆分一个单元格为多个词条。"""
    parts = re.split(r"[、,，/]", cell)
    return [p.strip() for p in parts if p.strip()]


@lru_cache(maxsize=1)
def _load_taxonomy() -> tuple[list[str], list[str], list[str]]:
    """返回 (一级, 二级, 三级) 标准命令列表。"""
    md = _read_md("intent-taxonomy.md")
    if not md:
        return (["地址规划", "互联规划", "接入规划", "网管规划", "路由规划", "LLD设计"],
                [], list(_FALLBACK_COMMANDS))
    secs = _sections(md)
    level1: list[str] = []
    for line in secs.get("一级分类", "").splitlines():
        line = line.strip()
        if line and not line.startswith("|") and not line.startswith("#"):
            level1.extend(_split_terms(line))

    def _second_col(section: str) -> list[str]:
        out: list[str] = []
        for row in _table_rows(secs.get(section, "")):
            if len(row) >= 2 and row[0] not in ("一级", "二级"):
                out.extend(_split_terms(row[1]))
        return out

    level2 = _second_col("二级分类")
    level3 = _second_col("三级分类")
    # 去重保序
    def _dedup(xs: list[str]) -> list[str]:
        seen, out = set(), []
        for x in xs:
            if x and x not in seen:
                seen.add(x)
                out.append(x)
        return out
    return _dedup(level1), _dedup(level2), _dedup(level3)


@lru_cache(maxsize=1)
def _load_aliases() -> dict[str, str]:
    """用户表达(小写、去空格) → 标准命令。"""
    md = _read_md("intent-aliases.md")
    aliases: dict[str, str] = {}
    for sec in _sections(md).values():
        for row in _table_rows(sec):
            if len(row) >= 2 and row[0] not in ("用户表达", "用户输入"):
                cmd = row[1].strip()
                for term in _split_terms(row[0]):
                    key = term.lower().replace(" ", "")
                    if key:
                        aliases[key] = cmd
    return aliases


@lru_cache(maxsize=1)
def _load_keywords() -> list[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    """[(标准命令, 必选关键词, 可选关键词)]，仅保留命令在 taxonomy 内的行。"""
    md = _read_md("intent-keywords.md")
    all_cmds = set(all_commands())
    rules: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    for sec in _sections(md).values():
        for row in _table_rows(sec):
            if len(row) < 2 or row[0] in ("标准命令", "用户口语", "用户输入特征"):
                continue
            cmd = row[0].strip()
            if cmd not in all_cmds:
                continue
            req: list[str] = []
            opt: list[str] = []
            for kw in _split_terms(row[1]):
                m = re.fullmatch(r"\{(.+)\}", kw)
                if m:
                    opt.append(m.group(1).strip().lower())
                else:
                    req.append(kw.strip().lower())
            if req:
                rules.append((cmd, tuple(req), tuple(opt)))
    return rules


@lru_cache(maxsize=1)
def all_commands() -> list[str]:
    l1, l2, l3 = _load_taxonomy()
    seen, out = set(), []
    for x in (*l3, *l2, *l1):  # 三级优先
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out or list(_FALLBACK_COMMANDS)


@lru_cache(maxsize=1)
def _load_l2_to_l3() -> dict[str, list[str]]:
    """二级 → 三级子命令列表（taxonomy 三级分类表）。"""
    md = _read_md("intent-taxonomy.md")
    mapping: dict[str, list[str]] = {}
    for row in _table_rows(_sections(md).get("三级分类", "")):
        if len(row) < 2 or row[0] in ("二级", "一级"):
            continue
        l2 = row[0].strip()
        l3s = _split_terms(row[1])
        if l2 and l3s:
            mapping[l2] = l3s
    return mapping


def canonicalize_command(cmd: str) -> str:
    """L2 且仅有一个 L3 子项时下沉到 L3，确保走 single dispatch（如 超平面地址规划 → 计算超平面地址规划）。"""
    c = (cmd or "").strip()
    if not c:
        return c
    children = _load_l2_to_l3().get(c) or []
    if len(children) == 1:
        return children[0]
    return c


# ── 归一化（关键词匹配前 · 原始 intent-keywords.md §归一化）──────────────────

_SYNONYM_REPL = [
    ("ip地址", "地址"), ("ip规划", "地址规划"), ("网段", "地址"), ("ip", "地址"),
    ("双活", "mlag"), ("堆叠", "mlag"), ("跨框聚合", "mlag"),
    ("零配置开局", "ztp"),
    ("改设备名", "替换设备名称"), ("重命名", "替换设备名称"),
]
_PLANE_REPL = [
    ("带外管理面", "带外管理"), ("oob", "带外管理"),
    ("计算节点", "计算"), ("存储节点", "存储"), ("网络节点", "网络"),
]
_GREETING = ("帮我", "请", "让我们执行", "让我们", "麻烦", "我想要", "我想", "我要")
_ACTION_PREFIX = ("进行", "执行", "做")


def _normalize(text: str) -> str:
    t = "".join(c.lower() if c.isascii() else c for c in text.strip())
    for g in _GREETING:
        t = t.replace(g, "")
    for a in _ACTION_PREFIX:
        if t.startswith(a):
            t = t[len(a):]
    for k, v in _SYNONYM_REPL:
        t = t.replace(k, v)
    for k, v in _PLANE_REPL:
        t = t.replace(k, v)
    # 「带外」单独出现（后不接「管理」）→ 带外管理
    t = re.sub(r"带外(?!管理)", "带外管理", t)
    return t


def _planning_type_of(cmd: str) -> str:
    if "互联" in cmd:
        return "互联"
    if "接入" in cmd:
        return "接入"
    if "地址" in cmd:
        return "地址"
    return "other"


def _pick_top_commands(
    hits: list[tuple[str, int, int]],
    limit: int = MAX_CLARIFY_CANDIDATES,
) -> list[str]:
    """按关键词得分、必选词数量降序，取最相关的前 limit 条（去重保序）。"""
    ordered: list[str] = []
    for cmd, _sc, _req in sorted(hits, key=lambda h: (h[1], h[2]), reverse=True):
        if cmd in ordered:
            continue
        ordered.append(cmd)
        if len(ordered) >= limit:
            break
    return ordered


def _keyword_match(normalized: str) -> list[str]:
    rules = _load_keywords()
    hits: list[tuple[str, int, int]] = []  # (cmd, score, required_count)
    for cmd, req, opt in rules:
        if all(k in normalized for k in req):
            score = sum(1 for k in (*req, *opt) if k and k in normalized)
            hits.append((cmd, score, len(req)))
    if not hits:
        return []

    # 规划类型显式信号（互联 / 接入 / 地址）
    present_types = [t for t in ("互联", "接入", "地址") if t in normalized]

    # 用户明确并列 ≥2 个规划类型（如「地址还是互联」）：各类型取最具体代表 → CLARIFYING。
    # 须先于 score 收敛（否则「互联」关键词更多会擅自吃掉地址候选，违反 §13 不得擅自选定）。
    if len(present_types) >= 2:
        reps: list[str] = []
        for t in present_types:
            group = [h for h in hits if _planning_type_of(h[0]) == t]
            if not group:
                continue
            max_req = max(g[2] for g in group)
            cand = [g for g in group if g[2] == max_req]
            max_sc = max(g[1] for g in cand)
            reps.extend(g[0] for g in cand if g[1] == max_sc)
        reps = list(dict.fromkeys(reps))  # 去重保序
        if len(reps) >= 2:
            hit_map = {h[0]: h for h in hits}
            rep_hits = [hit_map[r] for r in reps if r in hit_map]
            return _pick_top_commands(rep_hits)
        if len(reps) == 1:
            return reps

    ptype = present_types[0] if len(present_types) == 1 else None

    max_score = max(h[1] for h in hits)
    top = [h for h in hits if h[1] == max_score]
    if len(top) == 1:
        return [top[0][0]]

    # 总数相同 → 取必选关键词最多者（最具体，原始 keywords §3「最具体优先」）
    max_req = max(h[2] for h in top)
    specific = [h for h in top if h[2] == max_req]
    if len(specific) == 1:
        return [specific[0][0]]
    top = specific

    # 单一类型词 → 收敛到该类型
    if ptype:
        typed = [h for h in top if _planning_type_of(h[0]) == ptype]
        if len(typed) == 1:
            return [typed[0][0]]
        if typed:
            top = typed

    # 仍多候选 → 取得分最高的前 MAX_CLARIFY_CANDIDATES 条（CLARIFYING）
    return _pick_top_commands(top)


# ── 主入口 ───────────────────────────────────────────────────────────────

def _clarify_message(candidates: list[str]) -> str:
    if len(candidates) <= 1:
        return ""
    head = "、".join(candidates[:-1])
    return f"请问您要做{head}还是{candidates[-1]}？"


def _resolved_or_unsupported(cmd: str, source: str) -> IntentMatch:
    if cmd in UNSUPPORTED_COMMANDS:
        return IntentMatch(status="failed", message=FAILED_MESSAGE, source="unsupported")
    return IntentMatch(status="resolved", command=cmd, source=source)


def recognize(raw: str) -> IntentMatch:
    """确定性规则匹配链（不含 LLM 语义近似；耗尽返回 FAILED）。"""
    text = (raw or "").strip()
    if not text:
        return IntentMatch(status="failed", message=FAILED_MESSAGE)

    l1, l2, l3 = _load_taxonomy()
    compact = text.replace(" ", "")
    upper = compact.upper()

    # 1. 三级精准
    for c in l3:
        if upper == c.upper():
            return _resolved_or_unsupported(c, "exact_l3")

    # 2. LLD 特殊规则（生成/融合 + LLD；单独 LLD 不匹配）
    if "LLD" in upper:
        if "生成" in compact:
            return _resolved_or_unsupported("生成完整LLD设计", "lld_rule")
        if "融合" in compact:
            return _resolved_or_unsupported("融合完整LLD设计", "lld_rule")

    # 3. 二级精准
    for c in l2:
        if upper == c.upper():
            return _resolved_or_unsupported(c, "exact_l2")

    # 4. 一级精准
    for c in l1:
        if upper == c.upper():
            return _resolved_or_unsupported(c, "exact_l1")

    # 5. 别名精准
    alias_key = compact.lower()
    aliases = _load_aliases()
    if alias_key in aliases:
        return _resolved_or_unsupported(aliases[alias_key], "alias")

    # 6. 关键词全包含 + 消歧
    normalized = _normalize(text)
    cands = _keyword_match(normalized)
    if len(cands) == 1:
        return _resolved_or_unsupported(cands[0], "keyword")
    if len(cands) > 1:
        # 过滤不支持命令后再判断
        cands = [c for c in cands if c not in UNSUPPORTED_COMMANDS]
        if len(cands) == 1:
            return _resolved_or_unsupported(cands[0], "keyword")
        if len(cands) > 1:
            cands = cands[:MAX_CLARIFY_CANDIDATES]
            return IntentMatch(
                status="clarifying",
                candidates=cands,
                message=_clarify_message(cands),
                source="keyword",
            )

    # 7. 规则耗尽 → FAILED（语义近似交给 step 的 LLM 兜底）
    return IntentMatch(status="failed", message=FAILED_MESSAGE)
