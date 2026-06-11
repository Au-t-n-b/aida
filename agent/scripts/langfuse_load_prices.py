"""
把 langfuse_models.json 里的智谱 GLM 定价灌进 Langfuse。

用法：
    cd D:/code/aida
    ./agent/.venv/Scripts/python.exe agent/scripts/langfuse_load_prices.py [--force]

行为：
    - 默认：已存在的 model_name 跳过（推荐 · 不影响历史 trace）
    - --force：先 delete 再 create（如果想改价；注意 Langfuse 历史 trace 的 cost 会重新计算）

需要环境变量（从 agent/.env 加载）：
    LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# Windows GBK 终端友好：用 utf-8 写
def _w(s: str) -> None:
    try:
        sys.stdout.buffer.write(s.encode("utf-8"))
    except Exception:
        sys.stdout.write(s)


ROOT = Path(__file__).resolve().parents[1]   # agent/
load_dotenv(ROOT / ".env")

from langfuse import Langfuse


def main() -> int:
    force = "--force" in sys.argv

    cfg_path = ROOT / "scripts" / "langfuse_models.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    models = cfg["models"]

    lf = Langfuse()
    _w(f"已认证：{lf.auth_check()}  · 模式：{'force-replace' if force else 'skip-if-exists'}\n")

    # 拉所有现有 models（带分页）
    existing: dict = {}
    page = 1
    while True:
        resp = lf.api.models.list(page=page, limit=50)
        for m in resp.data:
            existing[m.model_name] = m
        if len(resp.data) < 50:
            break
        page += 1

    created = 0
    skipped = 0
    for spec in models:
        name = spec["model_name"]
        pattern = spec["match_pattern"]
        in_price = float(spec["input_price_per_1k"]) / 1000.0
        out_price = float(spec["output_price_per_1k"]) / 1000.0
        note = spec.get("note", "")

        if name in existing:
            if not force:
                _w(f"  [skip ] {name:18s}  已存在（用 --force 覆盖）\n")
                skipped += 1
                continue
            _w(f"  [delete] {name} (id={existing[name].id})\n")
            try:
                lf.api.models.delete(existing[name].id)
            except Exception as e:
                _w(f"    ⚠ 删除失败：{e}\n")
                continue

        try:
            lf.api.models.create(
                model_name=name,
                match_pattern=pattern,
                unit="TOKENS",
                input_price=in_price,
                output_price=out_price,
            )
            line = f"  [create] {name:18s}  in={in_price * 1e6:7.3f}/M  out={out_price * 1e6:7.3f}/M  pattern={pattern}"
            if note:
                line += f"  · {note}"
            _w(line + "\n")
            created += 1
        except Exception as e:
            _w(f"  X {name} 创建失败：{e}\n")

    _w(f"\n完成 · created={created}  skipped={skipped}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
