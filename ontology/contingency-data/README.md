# 预案（delivery-contingency-plan）本体 · 设计输入与数据来源

本目录是 **预案本体**（ontology id：`delivery-contingency-plan`）的**开发依据**，从
`D:\Code\test\backend\bak`（原 `预案 excel数据`、设计/来源 docs）与 `D:\Code\test\docs\plan`
搬入，作为后续在 **aida 内**（不再回老仓库）继续建模的起点。

## 目录内容

| 路径 | 作用 |
|------|------|
| `预案 excel数据/`（22 张信息表 `.xlsx`） | 预案本体的**数据来源**：项目基础/背景、设备/部件/软件/网络配置、机房机柜、服务/维护/SLA、责任矩阵、验收/测试、合同、风险、假设等 |
| `预案 excel数据/本体对齐分析与重构建议.md` | 信息表 ↔ 本体对象的对齐分析与重构建议 |
| `预案 excel数据/README_缺失与AI构造说明.md` | 信息表的缺失项与 AI 构造说明 |
| `预案本体数据方案.md` | 预案本体的数据方案（总纲） |
| `预案数据来源分类与缺失清单.md` | 数据来源分类 + 缺失清单 |
| `预案的初步的来源信息.md` | 初步来源信息 |
| `03-预案章节目录与子决策点映射(初版）.md` | 预案章节目录 ↔ 子决策点映射 |
| `JD三期项目交付预案_DRB-决策评审.md` | 真实预案样例（DRB 决策评审） |

## 与 schema 的关系

本体 schema 在 [`../contingency-schema/`](../contingency-schema/)（`object-types.json` 等，
共 29 个对象类型）。其 `datasource-bindings.yaml` 现状为 **metadata-only**
（`datasources: []`，各对象 `reader: metadata_only`，无运行时数据）——即「只有 schema、没有数据」。
注释已写明设计意图：资产类对象「由「预案 excel数据」18+ 输出表扩展，Excel→Dolt 加载后经映射读取」。

## 升级为「有数据」运行时本体的步骤（后续）

1. 选定信息表 → 对象/字段映射（参考 `本体对齐分析与重构建议.md`）。
2. 把 `预案 excel数据/` 各表加载进 **Dolt**（需起一个 Dolt SQL server）。
3. 在 `../contingency-schema/datasource-bindings.yaml` 把对应对象的 `sources` 接上、`reader` 改为实际读取器。
4. 放开 `../backend_app.py` 中 `_ensure_default_runtime_ontology` 对非 `default` 本体的 metadata-only 限制。

> 提示：在 aida 内开发即可，`D:\Code\test` 作只读参考存档；本目录的 xlsx 为二进制设计输入。
