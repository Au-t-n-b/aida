# Skill · 组合模型自动建模与 API 落位（auto_dragd）

## 用途

把 9 个 POD（超节点）对应的组合模型用 `batchCreateCombo` **一次性平铺创建**（POD1 在 x=150，
之后每个 POD x+100、y=60），创建阶段全部完成后**只需手动刷新 nVisual 一次**；
再用 `batchMoveNodes` **逐个机柜**（一次只移 1 个，从 401 A01 → 403 A18 串行）把机柜按
`cabinets.json` 的画布中心点坐标移动到目标机房目标列。

工作分两阶段、两子命令：
- `build`：把所有请求体（5 条批量创建 + 162 条逐机柜移动）预生成到 `requests.json`，可人工核对、可复用。
- `run`：读取 `requests.json` 按序发送 —— 创建阶段 → 暂停等刷新 → 逐个移动阶段（失败可续跑）。

与旧 `auto_drag` 的区别：旧方案用确定性鼠标拖拽（需标定 + 前台窗口），本方案**全程纯 API**，
不需要 `calibrate.py`、不依赖窗口前台，更快更稳可重复。

> **为何创建要分 5 次**：`batchCreateCombo` 的 `model` 与 `roomName` 是请求体顶层字段，
> 一次调用内所有 items 共用同一 `model`/`roomName`。9 个 POD 跨「-上/-下」两种 model、
> 401/402/403 三个 roomName，故最少按 `(roomName × model)` 分 5 次创建；但创建阶段全部跑完后只刷新一次。

---

## 输入

| 输入 | 路径（默认，相对 skill 根目录） | 提供的信息 |
|------|------|------|
| 建模仿真设备适配信息表 | `../api_adapt/output/建模仿真设备适配信息表.md` | 【超节点概述】首数据行「超节点组合」= 组合模型名 |
| 机房机柜信息表 | `../../auto_drag/机房机柜信息表.xlsx` | 每个 POD 的机房号(401/402/403) 与列字母(A/B/C/D) |
| 机柜画布坐标 | `../cad-analysis/cabinets.json` | 每个机柜的画布坐标（与软件画布同原点同比例） |

> 三个路径均可用 CLI 参数覆盖（`--adapt-md` / `--xlsx` / `--grid`）。

---

## 前提条件

- Python 3.9+；`pip install -r requirements.txt`（仅需 `requests`）。
- 可访问建模仿真 API（默认 `http://100.102.191.17:9091`），Bearer Token 已内置默认值，
  可用 `--token` 或环境变量 `$env:SIM_API_TOKEN` 覆盖；API 基址可用 `--api-base` 或 `$env:SIM_API_BASE`。
- 组合模型名为系统中**已存在**的组合模型(typeGroup=16)；目标视图(`--diagram`)已存在。

---

## 目录结构

```
auto_dragd/
├── SKILL.md
├── README.md
├── requirements.txt
├── requests.json          # build 生成（创建 + 移动请求体），run 读取
└── scripts/
    └── run_place_api.py   # 编排入口（build / run 子命令）
```

---

## 执行命令

```powershell
cd auto_dragd

# 1) 生成 requests.json（创建 5 条 + 移动 162 条），并打印分组与顺序供核对
python scripts/run_place_api.py build --diagram <视图名>

# 2) dry-run 核对发送计划（不发任何请求）
python scripts/run_place_api.py run --dry-run

# 3) 正式执行：创建阶段全跑完 → 暂停等你刷新 → 逐个机柜移动
python scripts/run_place_api.py run                 # 默认创建后交互式按回车继续
python scripts/run_place_api.py run --refresh-wait 10  # 改为自动等 10s 不按回车

# 4) 分段 / 续跑
python scripts/run_place_api.py run --only-create   # 只跑创建阶段
python scripts/run_place_api.py run --only-move     # 已创建并刷新过，只跑移动
python scripts/run_place_api.py run --skip-create   # 跳过创建，直接进入移动
python scripts/run_place_api.py run --start-move 37 # 移动失败后从第 37 条续跑
```

---

## 执行流程

```
[build] 生成 requests.json
  [1] parse_combo_model(适配信息表)
        取【超节点概述】首数据行「超节点组合」→ 组合模型名基准（A3 900 液冷384卡）。
        按列字母加朝向后缀：A/C 列 → 「-上」，B/D 列 → 「-下」。
  [2] parse_pod_layout(xlsx)
        sheet1：B=POD名 / C=机房号(401..) / D-H=机柜编号 → 每个 POD 的机房号 + 列字母。
  [3] build_create_requests
        x = 150 + (POD序号-1)*100，y = 60；按 (roomName × model) 分 5 组生成 batchCreateCombo 请求。
  [4] build_move_requests
        grid_room = ROOM_GRID_MAP[机房号]（401→F1-R1, 402→F1-R2, 403→F1-R3）；
        取该房间 code 匹配 ^{col}\d+$ 的机柜，节点名 f"{col}{编号:02d}"，坐标 (ctr_x, ctr_y)；
        每个机柜一条 batchMoveNodes 请求，顺序 POD1 A01 → POD9 A18（共 162 条）。

[run] 按序发送
  创建阶段：依次发 5 条 batchCreateCombo（任一失败即停）。
  → 暂停：提示手动刷新 nVisual 一次（回车继续，或 --refresh-wait N 自动等待）。
  移动阶段：逐条发 batchMoveNodes，前一条 code==200 才发下一条，失败即停（--start-move 续跑）。
```

---

## POD → 目标列映射（本数据集）

| POD | 组合模型(model) | roomName | grid 房间 | 列(rack_prefix) | sp_num | 创建坐标(x,y) | 移动机柜 |
|-----|---------|-----------|-----------|----|---------|---------|---------|
| POD1 | A3 900 液冷384卡-上 | 401 | F1-R1 | A | 1 | (150,60) | A01..A18 |
| POD2 | A3 900 液冷384卡-下 | 401 | F1-R1 | B | 2 | (250,60) | B01..B18 |
| POD3 | A3 900 液冷384卡-上 | 401 | F1-R1 | C | 3 | (350,60) | C01..C18 |
| POD4 | A3 900 液冷384卡-下 | 401 | F1-R1 | D | 4 | (450,60) | D01..D18 |
| POD5 | A3 900 液冷384卡-上 | 402 | F1-R2 | A | 5 | (550,60) | A01..A18 |
| POD6 | A3 900 液冷384卡-下 | 402 | F1-R2 | B | 6 | (650,60) | B01..B18 |
| POD7 | A3 900 液冷384卡-上 | 402 | F1-R2 | C | 7 | (750,60) | C01..C18 |
| POD8 | A3 900 液冷384卡-下 | 402 | F1-R2 | D | 8 | (850,60) | D01..D18 |
| POD9 | A3 900 液冷384卡-上 | 403 | F1-R3 | A | 9 | (950,60) | A01..A18 |

创建实际按 `(roomName × model)` 分 5 次调用（每次含同房间同 model 的 items）：

| 创建调用 | model | roomName | items (列/sp_num/x) |
|---|---|---|---|
| 1 | …-上 | 401 | A(1,150), C(3,350) |
| 2 | …-下 | 401 | B(2,250), D(4,450) |
| 3 | …-上 | 402 | A(5,550), C(7,750) |
| 4 | …-下 | 402 | B(6,650), D(8,850) |
| 5 | …-上 | 403 | A(9,950) |

> 同房间不同列名不冲突；跨房间 A 列重名靠 `roomName` 区分（batchMoveNodes 按 rack location 筛选）。

---

## CLI 参数

### `build` 子命令

| 参数 | 说明 | 默认 |
|------|------|------|
| `--diagram` | 目标视图名（必填，写入各请求体） | — |
| `--adapt-md` | 适配信息表路径 | `../api_adapt/output/建模仿真设备适配信息表.md` |
| `--xlsx` | 机房机柜信息表 | `../../auto_drag/机房机柜信息表.xlsx` |
| `--grid` | 机柜画布坐标 | `../cad-analysis/cabinets.json` |
| `--out` | 输出文件 | `requests.json` |
| `--api-base` | 仅写入 meta 供参考 | `http://100.102.191.17:9091` |

### `run` 子命令

| 参数 | 说明 | 默认 |
|------|------|------|
| `--file` | requests 文件 | `requests.json` |
| `--api-base` | 仿真 API 基址 | `http://100.102.191.17:9091` |
| `--token` | Bearer Token | 内置/`$env:SIM_API_TOKEN` |
| `--dry-run` | 只打印计划，不发请求 | 关 |
| `--refresh-wait` | 创建后等待刷新秒数；0=交互式按回车 | `0` |
| `--move-wait` | 每条移动成功后等待秒数再发下一条 | `0.5` |
| `--start-move` | 从第几条移动续跑（1 基） | `1` |
| `--skip-create` | 跳过创建阶段，直接移动 | 关 |
| `--only-create` | 只跑创建阶段 | 关 |
| `--only-move` | 只跑移动阶段 | 关 |

> 平铺坐标常量（`SPAWN_X0=150 / SPAWN_Y=60 / SPAWN_DX=100`）与朝向后缀映射在脚本顶部，可按需调整。

---

## 待实跑验证的假设（排错指引）

- **机柜命名**：假定组合模型创建后机柜名为 `A01..A18`（两位补零，前缀=A 基准，`rack_prefix` 直接传列字母即生效）。
  若实际命名不同（如不补零 `A1` 或基准前缀非 A），先 `run --only-create` 建模后看软件里真实机柜名，
  再改 `build_move_nodes` 里 `name` 的生成规则并重新 `build`。
- **设备随动**：只移动机柜，假定机柜内设备/Leaf 随机柜移动。若不随动，需补充移动设备节点。
- **roomName 筛选**：`roomName` 用 401/402/403 时，依赖创建组合模型时已把机柜 `rack location` 设为该值。
  batchMoveNodes 返回「未找到以下节点」即说明 roomName 或机柜名不匹配。

---

## 常见问题

**Q: batchCreateCombo 返回非 200**
检查 `--diagram` 视图名是否存在、组合模型名（含 `-上/-下` 后缀）是否为系统中存在的组合模型(typeGroup=16)、token 是否过期。
若部分创建已成功，修复后用 `run --skip-create` 跳过创建直接移动，或手动删掉 `requests.json` 里已成功的 create 项。

**Q: batchMoveNodes 返回「未找到以下节点: ...」**
说明该机柜名在该 roomName 下不存在。先 `run --only-create` 建模后到软件确认真实机柜名/rack location，
据此调整 `build_move_nodes` 的命名规则或 `roomName` 取值，再重新 `build`。

**Q: 机柜移动后位置整体偏移**
确认坐标语义：本脚本用机柜中心点 `ctr_x/ctr_y`。若软件 batchMoveNodes 期望左上角，
改用 cabinets.json 的 `tl_x/tl_y`。

**Q: 移动中途某条失败 / 想从中间续跑**
失败时日志会提示续跑命令。组合模型已创建并刷新过，续跑应跳过创建阶段：
`run --only-move --start-move N`（只跑移动、从第 N 条开始）。
注意：单用 `--start-move N` 默认仍会先重跑创建阶段+刷新暂停，故续跑请加 `--only-move`（或 `--skip-create`）。

**Q: 改了输入表/坐标后**
重新跑 `build` 覆盖 `requests.json`，再 `run`。
