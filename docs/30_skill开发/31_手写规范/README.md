# Agent 开发文档索引

> 本目录是《[团队 Agent 开发范式](../../20_架构与范式/03_团队Agent开发范式.md)》的**工程落地手册**。范式写铁律与清单；此处写「怎么做」。  
> 本目录（`docs/30_skill开发/31_手写规范/`）即工程手册唯一真相，直接改源。

> 🚀 **新业务场景 Skill 开发，从这里起手** → [START_HERE.md](../../10_快速开始/START_HERE.md)

| 文档 | 读者 | 内容 |
|------|------|------|
| [START_HERE.md](../../10_快速开始/START_HERE.md) ⭐ | 新模块作者（第一站） | 起手式：架构图 → zhgk 模块图 → AI 规则 → 清单 → 模板 |
| [AGENT_QUICKSTART.md](../../10_快速开始/AGENT_QUICKSTART.md) 🤖 | coding agent / 赶时间 | 一页最小操作集：加 skill 改哪些文件 + step 骨架 + 守门 |
| [SKILL-DEVELOPMENT.md](SKILL-DEVELOPMENT.md) | 后端 / Skill 作者 | A+B 双层、BaseStep、HITL、HTTP、skill-as-tool |
| [TOOL-DEVELOPMENT.md](TOOL-DEVELOPMENT.md) | 后端 / 工具作者 | Tool 契约、注册、trace、评测挂钩 |
| [SDUI.md](SDUI.md) | 全栈 / 界面作者 | 投影器模式：后端吐 UI 树 → 前端通用渲染，新模块零前端 |
| [接入/接入-Skill与LangGraph接入规范.md](接入/接入-Skill与LangGraph接入规范.md) 📐 | 后端 / 合入既有模块 | **执行面接入规范**（正式契约）：SkillState/BaseStep/路由/HITL/意图识别/子脚本 vendoring + 四大保真红线①② |
| [接入/接入-SDUI接入规范.md](接入/接入-SDUI接入规范.md) 📐 | 全栈 / 合入既有模块 | **界面面接入规范**（正式契约）：投影器/节点白名单/SSE/上行/phase 渐进投影 + 四大保真红线③④ |
| [../evals/METRICS.md](../../40_评测/METRICS.md) | 全员 | 测评指标定义（[03 范式](../../20_架构与范式/03_团队Agent开发范式.md) §6 权威子规范） |
| [../evals/README.md](../../40_评测/README.md) | 测试 / 开发 | 如何跑评测、看 `/evals` |
| [../../AGENTS.md](../../../AGENTS.md) | 提交代码者 | lint 守门、命令速查 |
| [../../decisions/README.md](../../90_决策ADR/README.md) | 架构 / 复盘 | ADR 与非显然定制 |

> **接入规范 vs 手册**：上面 `SKILL-DEVELOPMENT`/`SDUI` 是「怎么做」的手册（偏路径 A 从零新建）；`接入/` 下两份是「契约 + 四大保真红线」的正式接入规范，重点覆盖**既有模块合入（路径 B · skill2langgraph）**。二者互补、勿互抄。两份规范所派生的 `接入对接元范式.md` 与所引 `接入2/MODULE-INTEGRATION-PLAYBOOK.md` **尚未入仓**（外部/待补），相应链接暂悬。

**样板工程**：`aida` + 智慧工勘 `zhgk`（`agent/skills/zhgk/`）。
