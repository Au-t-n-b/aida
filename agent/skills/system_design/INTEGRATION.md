# A3 子 Skill 集成清单 · system_design

> 原始工程：`D:\h00503675\code\AIDA_test\new\a3-intelligent-network-opening`  
> AIDA 集成目录：`aida/agent/skills/system_design/`  
> **子 skill 全部 vendoring 进 AIDA 仓库**：`system_design/a3_engine/`（subskills + runtime + path_config，181 个 py）。
> 通过 `pipelines/a3_bridge.py` 进程内 runpy 执行（无 subprocess）。

## 代码根 / 数据根解耦（a3_paths.py）

| 根 | 位置 | 内容 |
|----|------|------|
| 代码根 `get_a3_code_root()` | `system_design/a3_engine/` | vendored subskills + runtime（随 AIDA 仓库走，离线自包含） |
| 数据根 `get_a3_data_root()` | `a3-intelligent-network-opening/` | `ProjectData/Input` 输入件 + `Output` 产物 |

环境变量：

| 变量 | 作用 |
|------|------|
| `SYSTEM_DESIGN_ROOT` / `A3_ROOT` | 数据根（默认样例工程） |
| `A3_CODE_ROOT` | 代码根覆盖（一般无需，默认 vendored a3_engine） |

## 集成架构

```
LangGraph system_design steps
    ├─ 单命令：a3_bridge.run_command(L3命令)         （② 菜单式 dispatch 基元）
    └─ 批次/完整：a3_bridge.run_dispatch(L1/L2锚点)   （① 整包接入 offline_dispatch_pipeline）
            → vendored dispatch_runner.plan_dispatch（L2 策略 / pass_prior / 007 裁剪）
            → 逐 phase/task 进程内 run_command（runpy，无 subprocess）
    → ProjectData/Output 产物 → state.files / metrics → sdui.py 投影
```

## ① L1/L2 dispatch 编排器整包接入

`a3_bridge.build_dispatch_plan(anchor, work_root)` 复用 vendored `dispatch_runner.plan_dispatch`
（= a3 `offline_dispatch_pipeline` 的 plan 逻辑：`dispatch_expander` + `skill_registry.yaml` L2 策略 +
`dispatch_tree.yaml` + entrypoint 存在性裁剪）。`run_dispatch()` 按 plan 的 phase/task 顺序、
带 `pass_prior` 进程内执行，保留编排器的 skipped/errors 结构供 SDUI 投影。

## ② intent_command 驱动的单命令 dispatch 模式

`a3_bridge.resolve_execution_mode(intent_command)` → 三态：

| 模式 | 触发意图 | plane_planning 行为 | 下游 lld/ztp/naming |
|------|----------|---------------------|---------------------|
| `full` | 生成/融合完整LLD设计、空 | run_dispatch(地址规划) | 全部执行（一条龙交付） |
| `batch` | 地址规划 / 互联规划 / 接入规划 / 网管规划 / 路由规划 | run_dispatch(该 L1) | 自跳过（跑完即发布） |
| `single` | 任一 l3_skill_index 单条命令 | run_command(该命令) | 自跳过（菜单式触发） |

下游 step 读 `metrics["sd_mode"]`，在 single/batch 时返回 `*_status="skipped"`，不做无谓执行。

## 线性 DAG step → A3 命令映射

| AIDA step | A3 子 skill / 命令 |
|-----------|-------------------|
| `intent_recognition` | 会话侧归一化（AIDA 内置 LLM，对齐 `lld-intent-recognition` 语义） |
| `input_check` | 关键词扫描（对齐 `a3-input-components-workflow`） |
| `plane_planning` | **全部 L3 地址批次** 或 intent 指定的单条 L3（`resolve_plan_commands`） |
| `lld_integrate` | `融合完整LLD设计` → `a3_LLD_generate_code1` |
| `ztp_generate` | `生成ZTP设计文件` → `a3-generate-ztp-lld-workflow` |
| `naming_replace` | `替换设备名称` → `a3-device-naming-workflow`（可选跳过） |
| `publish` | 扫描 `ProjectData/Output`（AIDA 自有） |

任意 `l3_skill_index.yaml` 注册命令均可通过 `a3_bridge.run_command()` 直执。

## l3_skill_index 子 skill 全覆盖（30+ 包）

### 编排 / 输入

| 标准命令 | 子包 | entrypoint | 集成方式 |
|----------|------|------------|----------|
| 检查输入件是否妥当 | a3-input-components-workflow | offline_input_components_pipeline.py | `run_command` 可直执 |
| （L1 地址规划） | lld-dispatch-orchestrator | offline_dispatch_pipeline.py | `expand_dispatch("地址规划")` 展开后逐条 L3 |

### 地址规划（13 包）

| 标准命令 | 子包 |
|----------|------|
| 计算带外管理地址规划 | a3-dw-manage-ip-workflow |
| 存储带外管理地址规划 | a3-storage-dw-manage-ip-workflow |
| 网络带外管理地址规划 | a3-net-dw-manage-ip-workflow |
| 灵衢带外管理地址规划 | a3-lq-dw-manage-ip-workflow |
| 计算管理面地址规划 | a3-l2-l3-ip-workflow |
| 存储管理面地址规划 | a3-cc-glm-ip-workflow |
| 计算管存面地址规划 | a3-gcm-ip-workflow |
| 计算业务面地址规划 | a3-ywm-ip-workflow |
| 存储业务面地址规划 | a3-cc-ywm-ip-workflow |
| 计算参数面地址规划 | a3-csm-ip-workflow |
| 计算超平面地址规划 | a3-cpm-lq-ip-workflow |
| 计算样本面地址规划 | a3-ybm-ip-workflow |
| 存储样本面地址规划 | a3-cc-ybm-ip-workflow |
| 网络业务地址规划 | a3-gcm-ip-workflow |

### 互联规划（1 包覆盖全部 *互联规划）

| 标准命令 | 子包 |
|----------|------|
| 全部 *互联规划 | oob-interconnect-workflow · run_oob_interconnect.py |

### 接入规划

| 标准命令 | 子包 |
|----------|------|
| 全部 *接入规划 | net-dw-access-ip-workflow · run_network_access_plan.py |

### 网管 / 路由

| 标准命令 | 子包 |
|----------|------|
| CCAE规划 | ccae-planner |
| DME规划 | dme-planning |
| NCE规划 | nce-planner |
| 交换机MLAG规划 | switch-mlag-planning-workflow |
| 网络设备ASN规划 | a3-switch-asn-workflow |

### LLD / ZTP / 命名

| 标准命令 | 子包 |
|----------|------|
| 生成完整LLD设计 | a3_LLD_generate_code1 |
| 融合完整LLD设计 | a3_LLD_generate_code1 |
| 生成ZTP设计文件 | a3-generate-ztp-lld-workflow |
| 生成ZTP配置文件 | a3-generate-ztp-cfg-workflow |
| 生成灵衢开局文件 | a3-generate-lq-open-workflow |
| 生成设备清单 / 替换设备名称 / ZTP名称替换* | a3-device-naming-workflow |

### 不支持（l3 index 标记 unsupported）

- 网络地址规划知识
- 防火墙互联规划

## 依赖

- A3 工程完整 checkout（含 `subskills/` + `runtime/`）
- Python 包：`pandas`, `openpyxl`, `pyyaml`（A3 pipeline 通用依赖）
- 输入件：`ProjectData/Input/` 下 007 / 001 / 004 / 项目信息收集表

## 验证

```python
from agent.skills.system_design.pipelines.a3_registry import list_integrated_commands
from agent.skills.system_design.pipelines.a3_bridge import run_command
print(len(list_integrated_commands()), "commands")
# run_command("检查输入件是否妥当", r"D:\...\a3-intelligent-network-opening")
```
