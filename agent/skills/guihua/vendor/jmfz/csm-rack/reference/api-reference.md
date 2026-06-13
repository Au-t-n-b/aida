# csm-rack skill · API 速查（新 wapi 网关）

> 基址：`http://100.102.191.17:9091`，端点为完整 `/wapi/v1/...` 路径。  
> 鉴权：请求头 `Authorization: Bearer <token>`（config.auth.token）。

## 用到的接口

| 用途 | endpoint | 接口名 |
|------|---------|-------|
| 重置参数面-删除 | `POST /wapi/v1/ai/topology/deleteTopology` | `deleteTopology` |
| 重置参数面-重建 | `POST /wapi/v1/ai/shape/createShape` | `createShape` |
| 设备端口 query | `POST /wapi/v1/ai/model/queryPort` | `queryPort` |
| 建 Leaf 设备 | `POST /wapi/v1/ai/device/createDevice` | `createDevice` |
| 跨视图批量上架 | `POST /wapi/v1/ai/device/batchRackDevices` | `batchRackDevices` |
| 建 server→leaf 拓扑（递归） | `POST /wapi/v1/ai/link/batchCreateLink` | `batchCreateLink` |
| 上架后校验（可选） | `POST /wapi/v1/search` | `search` |

视图角色：`参数面`(leaf_diagram，建 leaf + 重置) / `机房`(room_diagram，机柜/server + 上架目标 + 连线) / `顶层`(parent_diagram，createShape 父视图)。

---

## deleteTopology + createShape（重置「参数面」视图）

```json
// 1) 删除整个参数面（设备 + 连线 + 视图节点）—— 绝不对「机房」调用
POST /wapi/v1/ai/topology/deleteTopology
{ "diagram": "参数面" }

// 2) 在「顶层」下重建「参数面」空视图
POST /wapi/v1/ai/shape/createShape
{ "diagram": "顶层", "shape_name": "参数面" }
```

- **硬约束**：`deleteTopology.diagram` 必须 == `参数面`，编排层断言其 != `机房`，否则中止。
- 参数面不存在时 deleteTopology 报 `entity not found`(800005)，视为无需清理、可继续。

---

## createDevice（批量建 Leaf，建在「参数面」）

```json
{
  "diagram": "参数面",
  "device_model": "CE9866",
  "device_role": "参数面接入交换机",
  "first_device_name": "CSM-LEAF-CE9866-001",
  "device_group": 1,
  "per_group_quantity": 54,
  "topo_level": 2,
  "slot_config": []
}
```

- `diagram`：视图名 = `参数面`（必须已由 createShape 建好）。
- `first_device_name`：第一台设备名，后续按命名规则自动递增（CE9866-001→054）。
- `slot_config`：CE9866 盒式无可插线卡，传空数组。

---

## batchRackDevices（跨视图批量上架，每柜一次共 18 次）

```json
{
  "device_range": ["CSM-LEAF-CE9866-001", "CSM-LEAF-CE9866-003", "CSM-LEAF-CE9866-005"],
  "device_diagram": "参数面",
  "cabinet_range": ["A17"],
  "cabinet_diagram": "机房",
  "roomName": "401",
  "startU": 41,
  "interval": 3,
  "installationDirection": "F",
  "allocationDirection": 1
}
```

| 字段 | 说明 |
|-----|------|
| `device_range` | 本柜要上架的 3 台 leaf（必须在 device_diagram 下） |
| `device_diagram` | 设备所在视图名（= "参数面"） |
| `cabinet_range` | 目标机柜（单柜，= 该柜对应的 1 个机柜） |
| `cabinet_diagram` | 机柜所在视图名（= "机房"） |
| `roomName` | 机房名称（401/402/403），通过 rack location 属性筛选机柜 |
| `startU` | 起始 U 位（41，从上向下第一台位置） |
| `interval` | 设备间隔 U 数（3U） |
| `installationDirection` | 安装面：`F`=正面，`B`=背面 |
| `allocationDirection` | U 位分配方向：`0`=由下向上，`1`=由上向下 |

> 跨视图：设备(参数面)与机柜(机房)分属不同视图，上架后 leaf 落入「机房」机柜内。
> 落位明细见 `rack-mounting-rules.md` / `leaf-cabinet-allocation.md`。

---

## batchCreateLink（server→leaf 拓扑互联，递归）

```json
{
  "diagram": "机房",
  "connection_type": "服务器上行",
  "link_type": "MPO-MPO-OM4-16 水蓝",
  "source_device_range": ["SP01-AT900A3-01", "..."],
  "target_device_range": ["CSM-LEAF-CE9866-001", "CSM-LEAF-CE9866-003", "..."],
  "source_port_range": [{"slot_name": "PIC8", "port_name": "1,3,5,7", "actual_port_standard": "400GE"}],
  "target_port_range": [{"slot_name": "", "port_name": "1/0/1,...,1/0/64", "actual_port_standard": "400GE"}],
  "source_start_port": [{"slot_name": "PIC8", "port_name": "1", "actual_port_standard": "400GE"}],
  "target_start_port": [{"slot_name": "", "port_name": "1/0/1", "actual_port_standard": "400GE"}]
}
```

- **为何用 `batchCreateLink` 而非 `createTopoLink`**：`batchCreateLink` **递归查找**业务面下
  所有层级的 type_group=7 设备；server 嵌套在组合模型内、leaf 上架后嵌套在机柜内，
  `createTopoLink` 只查直接子节点会报 800300「源设备或目标设备不存在」。两者 payload 一致。
- `diagram`：连线视图 = `机房`（上架后 leaf 与 server 同处机房）。
- `connection_type`：`服务器上行`（Server→Leaf）。
- `source_device_range`：全部 432 台 server（来自 DataGrid.xlsx）。
- `target_device_range`：27 台奇/偶编号 leaf。
- 端口名 `port_name` 为完整 CSV 列表，不使用 `...` 占位。

---

## search（上架后校验，可选）

```json
POST /wapi/v1/search
{ "keywords": "CSM-LEAF-CE9866-001", "exactMatch": true }
```

- 上架后用某台 leaf 名精确搜索，确认其已落入「机房」（响应 `result_list[].parentname` 为机柜名）。
- best-effort：失败仅告警，不阻断流程。

---

## queryPort（设备端口查询）

```json
POST /wapi/v1/ai/model/queryPort
{"model": "CE9866"}
```

响应 `data` 为端口行列表，每行含 `slot_name`、`port_name`（CSV）、`default_port_standard`。
用于取 Leaf 业务端口目录；不可用时按 `1/0/1..1/0/128` 合成并告警。
