# a3-generate-ztp-lld-workflow

离线 A3「**生成ZTP设计文件**」：`超平面规划 + 灵衢带外管理地址 + 设备位置` → `ZTP_LLD.xlsx`。

> 业务来源：`generate_ztp_lld.generate_ztp_lld_file`

## 前置依赖

需先具备（或由其它 address-planning skill 生成）：

- `A3超平面网络规划.xlsx`（或文件名含「超平面」「规划」）
- `A3灵衢带外管理地址规划.xlsx`（含「灵衢」「带外」「地址」，非网关规划）
- `建模仿真输出文档004-设备位置表.xlsx`（sheet：`设备位置信息`）

## 安装

```bash
cd _skill_staging/a3-generate-ztp-lld-workflow.code1
python -m pip install -r requirements.txt
```

## 运行

将 **007、项目信息收集表、004 设备位置表** 放在 skill 根目录即可；若缺少两份「规划结果」表，会自动运行前置 skill 生成（无需手动拷贝）：

```bash
python scripts/offline_generate_ztp_lld_pipeline.py --out-dir output
```

| 你只需放置（示例） | 作用 |
|-------------------|------|
| 建模仿真输出文档007-端口连线表.xlsx | 前置 skill 输入 |
| 项目信息收集表.xlsx | 前置 skill 输入 |
| 建模仿真输出文档004-设备位置表.xlsx | 本 skill 直接使用 |

若已有 `超平面网络规划.xlsx` / `A3灵衢带外管理地址规划.xlsx`，则跳过对应前置 skill。

前置 skill 运行失败（如数据校验不通过）时，会回退使用 `_skill_staging` 内同名的**最新已有**产出。

禁用自动前置：`--no-auto-prereq`

显式指定路径：

```bash
python scripts/offline_generate_ztp_lld_pipeline.py \
  --cpm A3超平面网络规划.xlsx \
  --manage A3灵衢带外管理地址规划.xlsx \
  --location 建模仿真输出文档004-设备位置表.xlsx \
  --out-dir output
```

## 输出

- `output/run_*/ZTP_LLD.xlsx`（sheet：`网络IP规划`）

## 下一步

将生成的 `ZTP_LLD.xlsx` 与 `项目信息收集表.xlsx` 放入 **`a3-generate-ztp-cfg-workflow`** 目录，执行「生成ZTP配置文件」。
