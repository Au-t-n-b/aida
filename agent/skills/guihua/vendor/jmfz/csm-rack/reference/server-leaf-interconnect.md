# 参数面 server→leaf 拓扑连线规则

> 裁剪自 csm-analysis/reference/parameter-plane-interconnect.md，仅保留 §1 服务器上行部分。
> 本 skill 不建 spine，不生成 leaf→spine CLOS 连线。

## 1. Server → Leaf（connection_type=服务器上行）

### 1.1 A3 系列双轨

- 单台 `8×400GE` 上联端口（PIC8 槽）。
- dual-rail（默认）：
  - 奇数口（1/3/5/7）4×400GE → 奇编号 Leaf（001,003,005,...）
  - 偶数口（2/4/6/8）4×400GE → 偶编号 Leaf（002,004,006,...）

### 1.2 成对 Leaf 分块与 leaves_used 推导

- 块大小动态计算：`block_size = floor(leaf_downlink_pool / ports_per_server_on_one_leaf)`。
  - CE9866 下联池 = 64 口（128口，contiguous_half 前半）。
  - A3 双轨每轨 4 口 → `block_size = 64 / 4 = 16`。
- **实际使用 Leaf 数** = `ceil(432 / 16) × 2 = 27 × 2 = 54 台`。
- 奇偶 Leaf 分组：`odd_leaves = active_leaves[0::2]`，`even_leaves = active_leaves[1::2]`。

### 1.3 Leaf 下联端口分池（contiguous_half）

- Leaf 数据口按**连续半区**分为下联池与上联池：
  - 下联（→Server）：`1/0/1 ~ 1/0/64`（前半 64 口）
  - 上联（→Spine，本 skill 不使用）：`1/0/65 ~ 1/0/128`
- 策略由 `config.plane.leaf_port_split_policy` 控制（`contiguous_half` 或 `panel_split`）。

### 1.4 payload 组装（batchCreateLink，连线视图=机房）

连线在**上架完成后**进行，此时 leaf 已进入「机房」、server 也在「机房」（嵌套在
组合模型内）。统一用 `batchCreateLink`（递归查找所有层级 type_group=7 设备），
而非 `createTopoLink`（仅查直接子节点，会因 server/leaf 嵌套而报「源设备或目标设备不存在」）。
两者 payload 结构一致。

双轨各生成 1 个 payload，共 2 条：

**奇轨 payload：**
```json
{
  "diagram": "机房",
  "connection_type": "服务器上行",
  "link_type": "MPO-MPO-OM4-16 水蓝",
  "source_device_range": ["SP01-AT900A3-01", "SP01-AT900A3-02", "...（全部432台）"],
  "target_device_range": ["CSM-LEAF-CE9866-001", "CSM-LEAF-CE9866-003", "...（奇编号27台）"],
  "source_port_range": [{"slot_name": "PIC8", "port_name": "1,3,5,7", "actual_port_standard": "400GE"}],
  "target_port_range": [{"slot_name": "", "port_name": "1/0/1,...,1/0/64", "actual_port_standard": "400GE"}],
  "source_start_port": [{"slot_name": "PIC8", "port_name": "1", "actual_port_standard": "400GE"}],
  "target_start_port": [{"slot_name": "", "port_name": "1/0/1", "actual_port_standard": "400GE"}]
}
```

**偶轨 payload：** 同理，偶口（2,4,6,8）+ 偶编号 Leaf（002,004,...,054）。

### 1.5 容量守卫

- 校验：`server_count × src_ports_per_rail == leaf_count_per_rail × leaf_downlink_pool`
- 本项目：432 × 4 = 1728 == 27 × 64 = 1728 ✓（平衡，无规则C）

### 1.6 端口来源

- Server 侧：固定 `PIC8` 槽，端口 `1..8`（不依赖 queryPort）。
- Leaf 侧：优先 `queryPort(CE9866)` 实时取；不可用时兜底 `1/0/1..1/0/128`，并追加 warnings。

## 2. Server 设备名来源

server 为预建设备（由组合模型创建），名称从 `DataGrid.xlsx` 读取：

| 字段 | 说明 |
|-----|------|
| 名称 | 设备名，如 `SP01-AT900A3-01`，按 SP01→SP09 有序 |
| 型号 | `Atlas 900 A3` |
| 机柜名称 | 所在机柜，如 `A08` |
| 机房名称 | 所在机房，如 `401` |

全部 432 台 server，SP01..SP09 各 48 台，对应 leaf 001..054 顺序完全吻合。
