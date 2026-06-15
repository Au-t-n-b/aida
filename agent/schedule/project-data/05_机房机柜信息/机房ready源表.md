# 机房ready源表表头

## 一、文档作用

本文档描述 `机房ready源表.xlsx` 的表头结构。该表是一行一机房的 ready 日期源表，用于导入器填充契约 `Room.cabling_ready_date`、`Room.install_ready_date`、`Room.liquid_ready_date`。三段日期均可为空；空值表示待定，排期引擎可按上电/上线目标倒推建议。

## 二、表头字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| 机房id | string | Y | 机房唯一标识，需与 `机房机柜信息表.xlsx` 的 `机房名称` 对齐。 |
| 可布线 | date | N | 可布线 ready 日期，格式 `YYYY-MM-DD`；空=待定。 |
| 可装设备 | date | N | 可装设备 ready 日期，格式 `YYYY-MM-DD`；空=待定。 |
| 可通液 | date | N | 可通液 ready 日期，格式 `YYYY-MM-DD`；空=待定。 |

## 三、md 表头与 Excel 变量映射

| md字段 | Excel变量 | Excel文件 | Sheet | 表头行 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 机房id | 机房id | `机房ready源表.xlsx` | `Sheet1` | 1 | 直接对应 `Room.room_id`。 |
| 可布线 | 可布线 | `机房ready源表.xlsx` | `Sheet1` | 1 | 直接对应 `Room.cabling_ready_date`。 |
| 可装设备 | 可装设备 | `机房ready源表.xlsx` | `Sheet1` | 1 | 直接对应 `Room.install_ready_date`。 |
| 可通液 | 可通液 | `机房ready源表.xlsx` | `Sheet1` | 1 | 直接对应 `Room.liquid_ready_date`。 |
