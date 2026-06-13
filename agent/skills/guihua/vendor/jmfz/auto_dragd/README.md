# auto_dragd

用 API（`batchCreateCombo` + `batchMoveNodes`）把 9 个 POD 的组合模型**一次性平铺创建**（只需刷新一次），
再**逐个机柜**按画布中心点坐标精确移动到目标列。替代旧 `auto_drag` 的鼠标拖拽方案：无需鼠标标定、
不依赖前台窗口，纯 HTTP 调用，更快更稳可重复。

分两阶段、两子命令：
- `build`：把所有请求体（5 条批量创建 + 162 条逐机柜移动）预生成到 `requests.json`，可人工核对、可复用。
- `run`：读取 `requests.json` 按序发送 —— 创建阶段 → 暂停等手动刷新一次 → 逐个机柜移动（失败可续跑）。

## 快速开始

```powershell
cd auto_dragd
pip install -r requirements.txt

# 1) 生成 requests.json
python scripts/run_place_api.py build --diagram <视图名>

# 2) dry-run 核对发送计划（不发请求）
python scripts/run_place_api.py run --dry-run

# 3) 正式执行：创建全跑完 → 暂停等你刷新 nVisual → 逐个机柜移动
python scripts/run_place_api.py run

# 4) 续跑（已创建并刷新过，从第 N 条移动续发）
python scripts/run_place_api.py run --only-move --start-move N
```

详见 [SKILL.md](SKILL.md)。
