"""
在任意目录初始化 zhgk 工勘工作区（ProjectData 五子目录）。

v4 目录结构：Template/（底表/模板）· Input/（BOQ/人员）· Output/（产物）· RunTime/（快照）· Images/（照片）

跑：
  # 桌面 · 空目录（缺文件 → preflight / filter_build HITL）
  python agent/scripts/init_zhgk_workspace.py --dest "%USERPROFILE%\\Desktop\\zhgk-desktop"

  # 从源目录复制 Template/ 底表（仅缺 Input/BOQ → 测 BOQ HITL）
  python agent/scripts/init_zhgk_workspace.py --dest "%USERPROFILE%\\Desktop\\zhgk-desktop" --copy-template

  # 完整复制整个 ProjectData（不触发缺文件 HITL）
  python agent/scripts/init_zhgk_workspace.py --dest "%USERPROFILE%\\Desktop\\zhgk-desktop" --copy-all
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

DEFAULT_SRC = Path(os.environ.get(
    "ZHGK_ROOT",
    Path.home() / ".nanobot" / "workspace" / "skills" / "zhgk",
))
# 若已指向桌面，回退到 nanobot 默认源
if "Desktop" in str(DEFAULT_SRC) or "desktop" in str(DEFAULT_SRC).lower():
    DEFAULT_SRC = Path.home() / ".nanobot" / "workspace" / "skills" / "zhgk"

# v4 子目录（Template 替代旧 Start）
SUBDIRS = ("Template", "Input", "RunTime", "Output", "Images")

README = """# zhgk 桌面工勘工作区（v4）

本目录由 `init_zhgk_workspace.py` 创建。Agent 通过 **ZHGK_ROOT** 指向这里读写文件。

## 配置 Agent

在 `aida/agent/.env` 中设置（改完后**重启 uvicorn**）：

```
ZHGK_ROOT={dest}
```

## HITL 测试场景

| 你想测什么 | 做法 |
|-----------|------|
| **缺底表（HITL 上传）** | 保持 `Template/` 为空 → 启动工勘 → `preflight` / `filter_build` HITL |
| **缺 BOQ** | `--copy-template` 后，确保 `Input/` 里没有 `*BOQ*.xlsx` → HITL 提示补 BOQ |
| **缺报告模板** | Template 有底表但缺 `新版项目工勘报告模板.docx` → report_gen 用内置模板降级 |
| **补齐后续跑** | 把文件放进对应目录，或 `POST /agent/zhgk/upload` → `/resume` |

## 目录说明（v4）

- `Template/` — 固定底表（入场评估标准表.xlsx / 工勘常见高风险库.xlsx / 新版项目工勘报告模板.docx）
- `Input/`    — 项目输入（BOQ.xlsx / 远近一体化人员信息.xlsx / 勘测结果.xlsx）
- `RunTime/`  — 中间状态（project_info.json / 过滤底表）
- `Output/`   — 产物（全量勘测结果表 / 问题清单 / 风险表 / 工勘报告）
- `Images/`   — 勘测照片

## 上传 API（补料）

```powershell
# BOQ
curl -F "kind=boq" -F "file=@D:\\path\\BOQ.xlsx" http://127.0.0.1:7401/agent/zhgk/upload

# 入场评估标准表（底表）
curl -F "kind=template" -F "file=@D:\\path\\入场评估标准表.xlsx" http://127.0.0.1:7401/agent/zhgk/upload

# 工勘常见高风险库
curl -F "kind=template" -F "file=@D:\\path\\工勘常见高风险库.xlsx" http://127.0.0.1:7401/agent/zhgk/upload
```
"""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="初始化 zhgk ProjectData v4 工作区")
    ap.add_argument(
        "--dest",
        default=str(Path.home() / "Desktop" / "zhgk-desktop"),
        help="工作区根目录（将创建 ProjectData/ 子目录）",
    )
    ap.add_argument("--copy-template", action="store_true",
                    help="从源目录复制 ProjectData/Template（底表/模板文件）")
    ap.add_argument("--copy-all", action="store_true",
                    help="复制整个 ProjectData（含 Input/Output 等）")
    ap.add_argument("--src", default=str(DEFAULT_SRC), help="复制源（默认 ZHGK_ROOT）")
    args = ap.parse_args()

    dest = Path(args.dest).expanduser().resolve()
    src = Path(args.src).expanduser().resolve()
    pd = dest / "ProjectData"

    for sub in SUBDIRS:
        (pd / sub).mkdir(parents=True, exist_ok=True)

    if args.copy_all:
        src_pd = src / "ProjectData"
        if not src_pd.is_dir():
            print(f"[init] 源不存在: {src_pd}")
            return 1
        for sub in SUBDIRS:
            s, d = src_pd / sub, pd / sub
            if s.is_dir():
                for f in s.iterdir():
                    if f.is_file():
                        shutil.copy2(f, d / f.name)
        print(f"[init] 已复制 ProjectData 全部子目录 ← {src_pd}")
    elif args.copy_template:
        src_tpl = src / "ProjectData" / "Template"
        if not src_tpl.is_dir():
            print(f"[init] 源 Template 不存在: {src_tpl}")
            print("       请先确认 ZHGK_ROOT 中有 v4 Template/ 目录，或手动放入三个底表文件：")
            print("         入场评估标准表.xlsx / 工勘常见高风险库.xlsx / 新版项目工勘报告模板.docx")
            return 1
        for f in src_tpl.iterdir():
            if f.is_file():
                shutil.copy2(f, pd / "Template" / f.name)
        print(f"[init] 已复制 Template/ ← {src_tpl}")

    readme = dest / "README_HITL测试.md"
    readme.write_text(README.format(dest=str(dest)), encoding="utf-8")

    print(f"[init] v4 工作区就绪: {dest}")
    print(f"       ProjectData: {pd}")
    print(f"       说明: {readme}")
    print()
    print("下一步：在 agent/.env 设置 ZHGK_ROOT 后重启 Agent，再 POST /agent/zhgk/start")
    if not args.copy_template and not args.copy_all:
        print("       （当前 Template 为空 → 适合测「缺底表」HITL）")
    elif args.copy_template and not args.copy_all:
        print("       （已复制 Template，Input 无 BOQ → 适合测「缺 BOQ」HITL）")
    print()
    print("必须手动放置的三个模板文件（若未使用 --copy-template）：")
    print("  Template/入场评估标准表.xlsx")
    print("  Template/工勘常见高风险库.xlsx")
    print("  Template/新版项目工勘报告模板.docx（可选）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
