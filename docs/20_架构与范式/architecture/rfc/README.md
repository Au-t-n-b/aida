# rfc/ · 跨模块接口申请

开发者跑 [Workflow D2](../00_DEVELOPER_SOP.md#workflow-d2--阻碍处理缺跨模块接口--rfc) 遇到「缺一个别的模块/底座没提供的接口」时，生成 `RFC_<日期>_<接口名>.md` 放本目录，用 Mock 占位继续开发。

- 模板见 [00_DEVELOPER_SOP.md · RFC 模板](../00_DEVELOPER_SOP.md#rfc-模板rfcrfc_日期_接口md)。
- 架构师走 [RFC 审批](../00_ARCHITECT_SOP.md#rfc-审批开发者申请跨模块接口--底座能力)：批准 → 更新 [02 边界图](../02_module_boundaries.md) + 若动底座写一条 [`decisions/`](../../../90_决策ADR/README.md) ADR。

> **RFC ↔ ADR**：RFC 是开工前的**阻塞申请**（未决）；ADR 是**已决定的记录**（入库）。RFC 批准并改了底座 → 产出一条 ADR。
