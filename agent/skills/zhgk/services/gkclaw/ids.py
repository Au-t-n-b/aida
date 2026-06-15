"""
gkclaw ids · 标识符生成与校验（契约 §6）

task_id:    task-{YYYYMMDDHHMMSSmmm}-{净化 project_code}，同毫秒冲突时追加 -001
            registry 目录下 task_id_clock.txt 持久化最近时间戳/冲突序号
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


def _timestamp_ms() -> str:
    now = datetime.now().astimezone()
    return f"{now:%Y%m%d%H%M%S}{now.microsecond // 1000:03d}"


def new_task_id(project_code: str, registry_root: Path | str) -> str:
    """生成全局唯一 task_id。ID 与生成时间绑定，精确到毫秒。"""
    root = Path(registry_root)
    root.mkdir(parents=True, exist_ok=True)
    clock_file = root / "task_id_clock.txt"
    stamp = _timestamp_ms()
    last_stamp = ""
    last_seq = -1
    if clock_file.exists():
        try:
            parts = clock_file.read_text(encoding="utf-8").strip().split(" ", 1)
            last_stamp = parts[0]
            last_seq = int(parts[1]) if len(parts) > 1 else 0
        except (IndexError, ValueError):
            last_stamp = ""
            last_seq = -1

    seq = 0
    if stamp <= last_stamp:
        stamp = last_stamp
        seq = last_seq + 1
    clock_file.write_text(f"{stamp} {seq}", encoding="utf-8")

    suffix = "" if seq == 0 else f"-{seq:03d}"
    tid = f"task-{stamp}-{sanitize_code(project_code)}{suffix}"
    if not TASK_ID_RE.match(tid):  # project_code 极端超长时兜底
        tid = f"task-{stamp}-ZHGK{suffix}"
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
