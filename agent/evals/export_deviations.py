"""
偏离导出 + Cursor/CC prompt ·《团队 Agent 开发范式》规范 6 闭环最后一公里

读 evals/results/ 历次 zhgk + 最新 tools 评测 → 生成：
  - deviations-{ts}.json          完整偏离包（SKILL + 工具）
  - cursor-skill-{ts}.md          可直接粘贴给 Cursor 的 SKILL 优化 prompt
  - cursor-tools-{ts}.md          可直接粘贴给 Cursor 的工具优化 prompt

跑：
    python agent/evals/export_deviations.py
    python agent/evals/export_deviations.py --threshold 0.15
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent.evals.deviations import build_skill_deviations, build_tool_deviations  # noqa: E402

RESULTS = Path(__file__).parent / "results"


def _load_zhgk_runs(limit: int = 30) -> list[dict]:
    files = sorted(RESULTS.glob("zhgk-*.json"), reverse=True)[:limit]
    runs = []
    for f in files:
        try:
            runs.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return runs


def _load_latest_tools() -> dict | None:
    files = sorted(RESULTS.glob("tools-*.json"), reverse=True)
    if not files:
        return None
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return None


def _cursor_md(title: str, payload: dict) -> str:
    """生成 Cursor 友好 markdown：说明 + JSON 代码块。"""
    lines = [
        f"# {title}",
        "",
        "## 任务",
        payload.get("prompt", ""),
        "",
        "## 偏离数据（JSON）",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 建议动作",
        "- 先读偏离项里 `target` 指向的源码文件",
        "- 每项给出：根因（1 句）+ 具体改法（改哪几个字段/函数）+ 预期指标改善",
        "- 按 ROI 排序，不要泛泛而谈",
        "",
    ]
    if payload.get("deviations"):
        lines.append("## 偏离清单")
        for d in payload["deviations"]:
            lines.append(f"- **{d.get('target')}** · {d.get('metric')} · {d.get('delta', d.get('detail', ''))}")
        lines.append("")
    if payload.get("flagged"):
        lines.append("## 待优化工具")
        for d in payload["flagged"]:
            lines.append(
                f"- **{d.get('target')}** 自纠率 {d.get('value')} "
                f"(阈值 {d.get('threshold')}) · {d.get('calls')} 次调用"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    threshold = 0.15
    if "--threshold" in sys.argv:
        i = sys.argv.index("--threshold")
        if i + 1 < len(sys.argv):
            threshold = float(sys.argv[i + 1])

    runs = _load_zhgk_runs()
    tools_report = _load_latest_tools()
    skill_dev = build_skill_deviations(runs)
    tool_dev = build_tool_deviations(
        (tools_report or {}).get("tools") or {},
        threshold=threshold,
    )

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    RESULTS.mkdir(parents=True, exist_ok=True)

    bundle = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "skill": skill_dev,
        "tools": tool_dev,
        "meta": {
            "zhgk_runs": len(runs),
            "tools_eval_at": tools_report.get("evaluated_at") if tools_report else None,
        },
    }
    out_json = RESULTS / f"deviations-{ts}.json"
    out_json.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    out_skill = RESULTS / f"cursor-skill-{ts}.md"
    out_skill.write_text(_cursor_md("SKILL 评测偏离 · Cursor Prompt", skill_dev), encoding="utf-8")

    out_tools = RESULTS / f"cursor-tools-{ts}.md"
    out_tools.write_text(_cursor_md("工具评测偏离 · Cursor Prompt", tool_dev), encoding="utf-8")

    print(f"[export] zhgk runs={len(runs)} · tools flagged={len(tool_dev.get('flagged', []))}")
    print(f"  → {out_json}")
    print(f"  → {out_skill}")
    print(f"  → {out_tools}")
    if not runs:
        print("  ⚠ 无 zhgk 评测结果，先跑: python agent/evals/eval_zhgk.py")
    if not tools_report:
        print("  ⚠ 无 tools 评测结果，先跑: python agent/evals/eval_tools.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
