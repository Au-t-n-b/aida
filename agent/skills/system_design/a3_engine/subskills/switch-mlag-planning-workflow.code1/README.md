# 交换机 MLAG 规划 Skill

这是 `a3_switch_mlag.py` 的离线重构版本，只依赖本目录代码、`pandas` 和 `openpyxl`。业务分配逻辑对齐项目实现，项目里的数据库、EDM、日志、上传和对话展示链路改为本地 Excel 文件读写。

## 快速运行

```bash
python scripts/run_switch_mlag.py \
  --topology 建模仿真输出文档007-端口连线表.xlsx \
  --resource 项目信息收集表.xlsx \
  --user-id x00612310 \
  --project-id 00ffa4183d76bfed42996718460816e9 \
  --output-dir runs
```

常用参数：

| 参数 | 默认值 | 说明 |
|------|------|------|
| `--topology` | `建模仿真输出文档007-端口连线表.xlsx` | 端口连线表 |
| `--resource` | `项目信息收集表.xlsx` | 项目信息收集表 |
| `--out` | 自动 | 带合并区域的最终输出；传入 `--user-id/--project-id` 时默认 `{user_id}_{project_id}_A3交换机MLAG规划.xlsx`，否则默认 `A3交换机MLAG规划.xlsx` |
| `--temp` | 自动 | 未合并区域的中间输出；传入 `--user-id/--project-id` 时默认 `{user_id}_交换机MLAG规划.xlsx`，否则默认 `交换机MLAG规划.xlsx` |
| `--user-id` / `--project-id` | 无 | 按项目输出模式生成文件名 |
| `--output-dir` | `.` | 按项目输出模式生成文件名时的输出目录 |
| `--sheet` | 无 | 指定一个 007 sheet；可重复传入。支持项目配置名，也支持 `|` 组合配置中的实际 Excel 页签名 |
| `--merge-existing` | 关闭 | 读取已有未合并结果，删除本次网络平面后追加新结果 |
| `--existing` | 无 | `--merge-existing` 使用的已有结果文件；默认优先读取 `--temp`，缺失时读取 `--out` |
| `--list-sheets` | 关闭 | 只列出当前 007 文件中支持 MLAG 的 sheet |
| `--compat-composite-sheets` | 关闭 | 离线增强：自动扫描时兼容按 `|` 拆分组合 sheet；默认按项目入口只处理工作簿中与 `WEB_NETWORK_TYPE_CONFIG` 完全同名的 sheet |

## Python 调用

```python
from switch_mlag_planning import generate_switch_mlag

result = generate_switch_mlag(
    topology_file="建模仿真输出文档007-端口连线表.xlsx",
    resource_file="项目信息收集表.xlsx",
    user_id="x00612310",
    project_id="00ffa4183d76bfed42996718460816e9",
    output_dir="runs",
)

print(result.result_df)
```

## 输入契约

### 建模仿真输出文档007-端口连线表

- 找首个含「设备命名」的单元格行作为表头。
- 表头之后的数据行按项目逻辑取列：
  - 第 1 列：`本端交换机`
  - 第 2 列：`本端端口`
  - 第 3 列：`本端接口带宽`
  - 倒数第 4 列：`对端带宽`
  - 倒数第 3 列：`对端接口类型`
  - 倒数第 2 列：`对端端口`
  - 最后 1 列：`对端交换机`
- 只保留 `本端交换机` 含 `leaf|spine`，且两端同为 leaf 或同为 spine 的连线。
- 处理的 sheet 与项目 `WEB_NETWORK_TYPE_CONFIG` 保持一致；`超平面` 会按项目逻辑跳过。

### 项目信息收集表

- 优先读取 sheet `网络资源需求表`，找不到时尝试 `资源表` 及其他包含 `网络平面` 列的 sheet。
- 行定位：`网络平面 == MLAG`。
- 使用 `地址池*` / `地址池` 和 `最小规划掩码` / `掩码`。
- 从地址池中寻找第一对位于同一子网且不是 network/broadcast 的连续 IP，分别写入 DAD 的本端和对端 IP。

## 输出契约

输出工作簿 sheet 名固定为 `交换机MLAG规划`。

固定列顺序：

`网络平面, 本端设备, 本端接口, 本端接口IP地址, 本端接口掩码, 本端ETH-TRUNK, 本端VLAN, 对端设备, 对端接口, 对端接口IP地址, 对端接口掩码, 对端ETH-TRUNK, 对端VLAN, PVID, 端口类型, 标签`

## 分配规则

- 端口带宽有两种时：数值更高的带宽标记为 `PEER-LINK`、`ETH-TRUNK=1`；其余标记为 `DAD`、`ETH-TRUNK=0`。
- 端口带宽只有一种时：按本端交换机统计端口数和端口序号；端口数为奇数时第 1 条为 `DAD`，端口数为偶数时前 2 条为 `DAD`，其余为 `PEER-LINK`。
- 所有 `DAD` 行填入同一对 MLAG IP 和掩码；`PEER-LINK` IP 和掩码为空。
- `本端VLAN`、`对端VLAN`、`PVID`、`端口类型` 按项目输出为 `NA`。
- 网络平面名称由 007 sheet 映射得到；带外管理面会过滤掉本端设备包含 `LEAF` 的记录。
- 输出模式与项目一致：逐 sheet 更新未合并临时文件 `{user_id}_交换机MLAG规划.xlsx`，全部 sheet 处理后再读取临时文件生成最终合并版 `{user_id}_{project_id}_A3交换机MLAG规划.xlsx`。
- 最终输出按 `网络平面, 本端设备, 本端ETH-TRUNK, 标签` 稳定排序，并对 IP、掩码、ETH-TRUNK 列做与项目一致的连续行合并。

## 与项目实现对比

项目侧相关实现集中在 `a3_switch_mlag.py`：

- `main_flow.py` 只把“交换机MLAG规划”指令路由到 `a3_switch_mlag.a3_switch_connect`，不包含具体分配逻辑。
- `a3_switch_connect` 读取 007 工作簿所有 sheet，筛选与 `WEB_NETWORK_TYPE_CONFIG` 完全同名的 sheet，逐个调用 `switch_connect`。
- `switch_connect` 负责 sheet 到网络平面的映射、跳过 `超平面`、生成单平面 MLAG 结果、带外 LEAF 过滤、写入临时总表。
- `allocate_connection` 是 DAD/PEER-LINK 分配核心，本工具保持同样规则。
- `merge_excel_regions` / `standard_merge_df` 负责最终表排序、空值规范化和单元格合并，本工具保持同样输出结构。

本 skill 的离线差异：

- 读取方式：项目通过 `get_excel_file_by_path`、`get_sheet_from_excel_or_db`、`get_df_from_excel_by_path` 读取项目文件；本工具直接读取本地路径。
- 输出方式：项目上传到 EDM 并调用 `display_file` / `display_message`；本工具只生成本地 Excel。
- 文件名：传入 `--user-id/--project-id` 时，本工具默认生成 `{user_id}_交换机MLAG规划.xlsx` 和 `{user_id}_{project_id}_A3交换机MLAG规划.xlsx`，与项目一致；不传时使用离线默认名。
- 合并策略：本工具按项目方式逐 sheet 更新未合并临时文件，并移除同网络平面的历史行后追加；全部 sheet 处理完成后再读取临时文件生成合并版。
- 资源表：项目固定读取 `网络资源需求表`；本工具优先读取该 sheet，同时兼容扫描其他包含 `网络平面` 列的 sheet，便于离线样例运行。
- 组合 sheet：项目 MLAG 入口默认只处理工作簿中与配置完全同名的 sheet；本工具默认保持一致。需要离线兼容 `|` 拆分候选 sheet 时，可加 `--compat-composite-sheets` 或直接用 `--sheet` 指定。
- 未迁移项：`a3_switch_mlag.py` 中 `_get_all_switch_mlag_data` 当前没有被 `a3_switch_connect` / `switch_connect` 调用，本工具没有迁移这段未使用辅助逻辑。

## 依赖

```bash
pip install -r requirements.txt
```
