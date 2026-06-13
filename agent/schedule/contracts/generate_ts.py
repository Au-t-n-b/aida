"""Pydantic 契约 → TypeScript 类型生成器（零外部依赖、离线可跑、输出确定性）。

用法（在仓根执行）：
  python contracts/generate_ts.py          # 重新生成前端 src/contracts/schedule.gen.ts
  python contracts/generate_ts.py --check  # 新鲜度校验：生成内容 ≠ 现存文件 → exit 1（改了模型没重新生成）

规矩（宪法 §1）：生成物**禁止手改**；改了 /contracts 模型必须重新生成并与模型**同一次 commit**。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEDULE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SCHEDULE_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT))

OUT_PATH = REPO_ROOT / "frontend" / "src" / "features" / "schedule" / "contracts" / "schedule.gen.ts"

HEADER = """\
/* AUTO-GENERATED from /contracts (Pydantic, 唯一权威) — DO NOT EDIT.
 * 重新生成：仓根执行 `python contracts/generate_ts.py`；校验：`--check`。
 * 字段为 snake_case（线上格式）；前端如需 camelCase 在入口处映射（宪法 §2）。
 */
"""


def _collect() -> tuple[dict[str, dict], dict[str, str]]:
    from agent.schedule import contracts as c
    from agent.schedule.contracts import api as api_mod

    models = [
        c.DateRange, c.ScopeRef, c.TargetRef,
        c.Project, c.Room, c.Pod, c.ArrivalItem, c.Team, c.WorkloadRule, c.RiskRule,
        c.Activity, c.Dependency, c.Batch, c.Anchor, c.DemandRequest, c.ReworkEvent,
        c.IncidentEvent, c.RuleConfig, c.InputBundle,
        c.ScheduledActivity, c.PlanResult, c.ReadinessSuggestion, c.RiskItem, c.UnmetItem,
        c.MovedActivity, c.Explanation, c.PlanKpis, c.PulledInput, c.StrategyPlan,
        c.GenerateRequest, c.GenerateResponse, c.ChangeSet, c.AdjustRequest, c.AdjustResponse,
        c.ParseChangesResponse, c.CommitRequest, c.CommitResponse, c.ConflictDetail, c.ErrorResponse,
    ]
    consts = {
        "API_PREFIX": api_mod.API_PREFIX,
        "GENERATE_PATH": api_mod.GENERATE_PATH,
        "ADJUST_PATH": api_mod.ADJUST_PATH,
        "COMMIT_PATH": api_mod.COMMIT_PATH,
        "PARSE_CHANGES_PATH": api_mod.PARSE_CHANGES_PATH,
        "PROJECT_DATA_PATH": api_mod.PROJECT_DATA_PATH,
        "EXPORT_PLAN_PATH": api_mod.EXPORT_PLAN_PATH,
    }
    defs: dict[str, dict] = {}
    for m in models:
        schema = m.model_json_schema(ref_template="#/$defs/{model}")
        for name, sub in schema.pop("$defs", {}).items():
            defs.setdefault(name, sub)
        defs.setdefault(m.__name__, schema)
    return defs, consts


def _lit(v: object) -> str:
    return json.dumps(v, ensure_ascii=False)


def _wrap(t: str) -> str:
    return f"({t})" if " | " in t else t


def _ts_type(s: dict) -> str:
    if "$ref" in s:
        return s["$ref"].split("/")[-1]
    if "anyOf" in s:
        parts: list[str] = []
        for sub in s["anyOf"]:
            p = _ts_type(sub)
            if p not in parts:
                parts.append(p)
        return " | ".join(parts)
    if "enum" in s:
        return " | ".join(_lit(v) for v in s["enum"])
    if "const" in s:
        return _lit(s["const"])
    t = s.get("type")
    if t == "string":
        return "string"
    if t in ("integer", "number"):
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "null":
        return "null"
    if t == "array":
        return f"{_wrap(_ts_type(s.get('items', {})))}[]"
    if t == "object":
        ap = s.get("additionalProperties")
        if isinstance(ap, dict):
            return f"Record<string, {_ts_type(ap)}>"
        return "Record<string, unknown>"
    return "unknown"


def _doc(text: str | None, indent: str = "") -> str:
    if not text:
        return ""
    one = " ".join(text.replace("*/", "*\\/").split())
    return f"{indent}/** {one} */\n"


def _emit_def(name: str, schema: dict) -> str:
    if "properties" not in schema:
        return f"{_doc(schema.get('description'))}export type {name} = {_ts_type(schema)};\n"
    required = set(schema.get("required", []))
    out = _doc(schema.get("description"))
    out += f"export interface {name} {{\n"
    for fname, fs in schema["properties"].items():
        out += _doc(fs.get("description"), "  ")
        opt = "" if fname in required else "?"
        out += f"  {fname}{opt}: {_ts_type(fs)};\n"
    out += "}\n"
    return out


def generate() -> str:
    defs, consts = _collect()
    parts = [HEADER]
    for k, v in consts.items():
        parts.append(f"export const {k} = {_lit(v)} as const;")
    parts.append("")
    for name in sorted(defs):
        parts.append(_emit_def(name, defs[name]))
    return "\n".join(parts)


def main() -> int:
    text = generate()
    if "--check" in sys.argv:
        if not OUT_PATH.exists():
            print(f"[契约新鲜度] 生成物不存在：{OUT_PATH}", file=sys.stderr)
            return 1
        current = OUT_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
        if current != text:
            print("[契约新鲜度] ❌ /contracts 模型已变、TS 未重新生成。执行：python contracts/generate_ts.py", file=sys.stderr)
            return 1
        print("[契约新鲜度] ✅ 生成物与模型一致")
        return 0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"已生成 {OUT_PATH.relative_to(REPO_ROOT)}（{len(text.splitlines())} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
