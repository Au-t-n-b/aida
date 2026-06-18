---
name: system_design
version: 1.0.0
enabled: true
ui:
  label: 系统设计
  group: design
  order: 10
  icon: design
  route_key: design
runtime:
  workspace_env: SYSTEM_DESIGN_ROOT
description: 系统设计（A3 智能网络开局）· 规划设计第二段：意图识别→输入检查→平面规划→LLD 融合→ZTP→命名替换→发布。串联在建模仿真（guihua）之后，消费其产出的 001/004/007 仿真输出件。
---

# 系统设计（A3 智能网络开局）

「规划设计」业务 = **建模仿真**（`guihua`，线性 5 段）+ **系统设计**（本 skill）。
本 skill 由 Raw Skill《系统设计模块》转换而来，落为**线性 DAG**，串联在建模仿真之后：
第一步 `input_check` 消费建模仿真产出的 007/001/004 仿真输出件，形成「建模仿真 → 系统设计」链路。

## 串联关系

```
规划设计
├─ 建模仿真（guihua）：BOQ提取 → 设备确认 → 创建设备 → 拓扑确认 → 拓扑连接
└─ 系统设计（system_design）：意图识别 → 输入检查 → 平面规划 → LLD 融合 → ZTP → 命名替换 → 发布
                                   ▲ 消费建模仿真产出的 001/004/007
```

工作区默认复用建模仿真（jmfz）工作区（`SYSTEM_DESIGN_ROOT` 可覆盖），使产物天然衔接。

## 后端节点（steps[] 顺序即 DAG）

| 后端节点 | 名称 | 业务 | LLM | HITL |
|---|---|---|---|---|
| `input_check` | 输入件检查 | 校验 4 必需件（007/001/004/项目信息收集表） | 否 | 缺件软中断 |
| `intent_recognition` | 意图识别 | NL → 标准命令归一化 | 是（仅语义近似） | 否 |
| `plane_planning` | 平面规划 | 各平面确定性地址/互联/接入规划 | 否 | 缺 007/资源表软中断 |
| `lld_integrate` | LLD 融合 | 平面表去重融合为完整 LLD | 否 | 否 |
| `naming_replace` | 设备名称替换 | 替换为现网命名（可选） | 否 | 否 |
| `ztp_generate` | 生成 ZTP 设计文件 | 灵衢带外管理+超平面+004 → ZTP_LLD | 否 | 缺 004 软中断 |
| `publish` | 发布完成 | 汇总产物 + 执行摘要 + 回写进度 | 否 | 否 |

## 工具能力

- `doc_read_xlsx`（内置）：读 007 端口连线表等输入件。
- **`doc_write_xlsx`（需新增工具）**：9 个内置工具中无写 Excel 工具（仅 `doc_write_docx`）。
  系统设计的正式产物（平面表 / LLD / ZTP_LLD）需此工具。当前缺失时，按运行时契约
  «工具失败返回 'Error:' 不抛异常» 优雅降级为 JSON manifest，并在执行摘要中标注 warning。
- 无对外通知（不使用 send_mail / send_welink）。

## 运行时对齐

- 节点返回 state 差量；`steps`/`logs` 走 reducer 累加。
- HITL = 软中断：`check_inputs` 返 `missing` → 框架写 `state['hitl']` → router → END → resume（非 `interrupt()`）。
- LLM 无原生结构化输出：意图识别在 prompt 注入 JSON Schema + `json.loads` 解析 + 失败降级。

## 假设引用

平面/输入/分支判断的模糊点见 Raw Skill《系统设计模块》假设清单（A001 必需件 4 件、
A008 规划无 LLM、A009 ZTP 自动补齐、A010 LLD 同平面取最新、A013 命名替换可选、A015 平面只读 007+资源表、A016 防火墙/知识问答不支持）。
