"""guihua services · 建模仿真业务逻辑（线下移植自 Desktop/skill/jmfz）。

- sim_api      —— 统一仿真 API 出口（唯一对外副作用通道，dry-run + 留痕）
- compat_table —— 设备信息表 → 调 sim API 匹配 → 设备适配信息表（移植 build_compat_table.py）
- place_api    —— 适配表 + 机柜坐标 → batchCreateCombo/batchMoveNodes 编排（移植 run_place_api.py）
- subproc      —— subprocess 真跑 vendored jmfz 脚本（combo_create/cabinet_move/handoff 使用）
- sentinel     —— run_id 绑定的磁盘留痕，防跨 run 假跳过副作用步

fixtures/ 内置离线样本（拷自 Desktop/skill/jmfz），保证无内网时骨架可端到端跑：
  device_info.md          —— 设备信息表（adapt_build 输入兜底）
  compat_table.md         —— 设备适配信息表（adapt_build 离线产物兜底）
  requests_fixture.json   —— 预建创建/落位请求（5 创建 + 162 移动，combo_create/cabinet_move 兜底）
  cabinets.json           —— 机柜几何中心点（现建 move 请求用）
"""
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

FIXTURE_DEVICE_INFO = FIXTURES_DIR / "device_info.md"
FIXTURE_COMPAT_TABLE = FIXTURES_DIR / "compat_table.md"
FIXTURE_REQUESTS = FIXTURES_DIR / "requests_fixture.json"
FIXTURE_CABINETS = FIXTURES_DIR / "cabinets.json"

# ── 移植自 jmfz 的原始脚本（subprocess 真跑目标；见 plan「Vendoring」）──────────────
VENDOR_DIR = Path(__file__).resolve().parents[1] / "vendor" / "jmfz"
VENDOR_AUTODRAGD = VENDOR_DIR / "auto_dragd"          # run_place_api.py + requests.json
VENDOR_CSMRACK = VENDOR_DIR / "csm-rack"              # run_device_install.py + config.json + DataGrid
VENDOR_ADAPT_MD = VENDOR_DIR / "api_adapt" / "output" / "建模仿真设备适配信息表.md"
