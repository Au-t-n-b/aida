"""
清空 zhgk 工勘运行时数据，重置流程（不重启 Agent / 前端）。

默认清除 Output / RunTime / Images（含旧全量勘测结果表、project_info、GKCLAW 任务登记），
保留 Template 底表与 Input 用户文件；可选清除底表、输入件与 LangGraph checkpoint。

用法：
  # 本地（读 agent/.env 的 ZHGK_ROOT）
  python agent/scripts/reset_zhgk_workspace.py

  # 换底表后彻底重来：清底表 + 清产物，重新走 filter_build HITL
  python agent/scripts/reset_zhgk_workspace.py --clear-template --clear-input

  # 指定工作区
  python agent/scripts/reset_zhgk_workspace.py --zhgk-root /srv/zhgk

  # 连同 LangGraph checkpoint 一并清（前端旧 run 无法 resume）
  python agent/scripts/reset_zhgk_workspace.py --clear-checkpoints
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _AGENT_DIR.parent
_ENV_FILE = _AGENT_DIR / ".env"
_NANOBOT_DEFAULT = Path.home() / ".nanobot" / "workspace" / "skills" / "zhgk"
_RUNTIME_SUBDIRS = ("Output", "RunTime", "Images")
_ALL_SUBDIRS = ("Template", "Input", "Output", "RunTime", "Images")


def _load_agent_env() -> None:
    try:
        from dotenv import load_dotenv

        if _ENV_FILE.exists():
            load_dotenv(_ENV_FILE, override=True)
    except ImportError:
        if not _ENV_FILE.exists():
            return
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip().strip('"').strip("'")


def _resolve_zhgk_root(explicit: str | None) -> Path:
    _load_agent_env()
    raw = (explicit or os.environ.get("ZHGK_ROOT", "")).strip()
    root = Path(raw) if raw else _NANOBOT_DEFAULT
    return root.expanduser().resolve()


def _clear_directory(path: Path, *, dry_run: bool) -> int:
    """删除目录下全部内容，保留目录本身。返回删除的顶层项数。"""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return 0
    resolved = path.resolve()
    drive_root = Path(resolved.anchor)
    if resolved == drive_root:
        raise RuntimeError(f"拒绝清空盘符根目录: {resolved}")
    children = list(path.iterdir())
    if not dry_run:
        for child in children:
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
    return len(children)


def _clear_checkpoints(*, dry_run: bool) -> list[Path]:
    removed: list[Path] = []
    candidates = [
        _AGENT_DIR / "runtime" / "checkpoints.db",
        Path("/app/.data/runtime/checkpoints.db"),
    ]
    for base in candidates:
        if not base.exists():
            continue
        for p in base.parent.glob(base.name + "*"):
            removed.append(p)
            if not dry_run:
                p.unlink(missing_ok=True)
    return removed


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="清空 zhgk 工勘运行时数据并重置流程")
    ap.add_argument("--zhgk-root", help="工勘工作区根目录（默认 agent/.env 的 ZHGK_ROOT）")
    ap.add_argument(
        "--clear-input",
        action="store_true",
        help="同时清空 ProjectData/Input（之后可重新 seed 演示报告）",
    )
    ap.add_argument(
        "--clear-template",
        action="store_true",
        help="同时清空 ProjectData/Template（底表），下次须重新 HITL 上传",
    )
    ap.add_argument(
        "--no-seed-report",
        action="store_true",
        help="不清空 Input 时跳过；清空 Input 时默认从项目 demo 复制本地工勘报告.pdf",
    )
    ap.add_argument(
        "--project-id",
        default="70e5ca737ae5433e9f0f3134d216acf7",
        help="演示工勘报告来源项目 ID",
    )
    ap.add_argument(
        "--clear-checkpoints",
        action="store_true",
        help="删除 agent/runtime/checkpoints.db（LangGraph 续跑状态）",
    )
    ap.add_argument("--dry-run", action="store_true", help="仅打印将清除的路径，不实际删除")
    ap.add_argument(
        "--full",
        action="store_true",
        help="等价于 --clear-template --clear-input --clear-checkpoints",
    )
    args = ap.parse_args()

    if args.full:
        args.clear_template = True
        args.clear_input = True
        args.clear_checkpoints = True

    zhgk_root = _resolve_zhgk_root(args.zhgk_root)
    project_data = zhgk_root / "ProjectData"
    mode = "dry-run" if args.dry_run else "reset"
    print(f"[zhgk-{mode}] 工作区: {zhgk_root}")

    to_clear = list(_RUNTIME_SUBDIRS)
    if args.clear_input:
        to_clear.insert(0, "Input")
    if args.clear_template:
        to_clear.insert(0, "Template")

    total_removed = 0
    for sub in dict.fromkeys(to_clear):
        target = project_data / sub
        n = _clear_directory(target, dry_run=args.dry_run)
        total_removed += n
        print(f"[zhgk-{mode}] 清空 {target} ({n} 项)")

    for sub in _ALL_SUBDIRS:
        if not args.dry_run:
            (project_data / sub).mkdir(parents=True, exist_ok=True)

    exec_log = zhgk_root / "exec_log.json"
    if exec_log.exists():
        print(f"[zhgk-{mode}] 删除 {exec_log}")
        if not args.dry_run:
            exec_log.unlink(missing_ok=True)

    legacy_start = project_data / "Start"
    if legacy_start.exists():
        n = _clear_directory(legacy_start, dry_run=args.dry_run)
        print(f"[zhgk-{mode}] 清空旧版目录 {legacy_start} ({n} 项)")

    if args.clear_checkpoints:
        removed = _clear_checkpoints(dry_run=args.dry_run)
        if removed:
            for p in removed:
                print(f"[zhgk-{mode}] 删除 checkpoint {p}")
        else:
            print(f"[zhgk-{mode}] 未找到 checkpoint 文件（跳过）")

    seed_report = args.clear_input and not args.no_seed_report
    if seed_report and not args.dry_run:
        sys.path.insert(0, str(_REPO_ROOT))
        from agent.skills.zhgk.demo_assets import seed_mock_report_to_workspace

        dest = seed_mock_report_to_workspace(
            project_data / "Input",
            project_id=args.project_id,
        )
        if dest:
            print(f"[zhgk-reset] 已预置演示工勘报告: {dest}")
        else:
            print("[zhgk-reset] 跳过演示工勘报告：项目 demo 资产不存在")

    print()
    print(f"[zhgk-{mode}] 完成（共清理 {total_removed} 个顶层文件/目录）")
    if not args.clear_template:
        print("  · Template 底表已保留；换底表请重跑并加 --clear-template，或手动覆盖 Template/*.xlsx")
    else:
        print("  · Template 已清空 → 下次工勘须在 filter_build HITL 重新上传两张底表")
    print("  · 前端请刷新页面后重新「开始工勘」（旧 run_id 可能已失效）")
    if args.clear_checkpoints:
        print("  · checkpoint 已清 → 无法 resume 历史 run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
