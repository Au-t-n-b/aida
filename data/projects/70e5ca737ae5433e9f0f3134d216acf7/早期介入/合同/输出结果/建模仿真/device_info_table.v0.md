# 建模仿真设备信息表

说明：基于 BoQ 自洽分析结果与建模仿真 API 查询结果生成（device-centric-v1）。

【网络平面：参数面】

| 设备型号 | 设备角色 | 设备数量 | 板卡/插卡型号 | 板卡/插卡数量 | 模型校验 |
|---|---|---|---|---|---|
| 16800-CE16800-X16A-DH-B02-CE16800-X16 | 参数面汇聚交换机 | 64 | 36端口400GE，2端口100GE以太网光接口板(XL-J2,QSFP-DD,QSFP28)(CM)含3\*CE168-RTU-U6DQ-ISP | 256 | 模糊匹配 |
【网络平面：业务面】

| 设备型号 | 设备角色 | 设备数量 | 板卡/插卡型号 | 板卡/插卡数量 | 模型校验 |
|---|---|---|---|---|---|
| 待确认 | 业务面接入交换机（存储侧） | 待规则C确认 | - | - | 模糊匹配 |
| 待确认 | 业务面接入交换机（智算侧） | 待规则C确认 | - | - | 模糊匹配 |
| 待确认 | 业务面汇聚交换机 | 待规则C确认 | - | - | 模糊匹配 |
【智算服务器】

| 设备型号 | 设备角色 | 设备数量 | 板卡/插卡型号 | 板卡/插卡数量 | 模型校验 |
|---|---|---|---|---|---|
| AI计算规划设计与实施服务（训练） | 智算服务器 | 9 | - | - | 模糊匹配 |
| Atlas 900 A3 | 智算服务器 | 48 | - | - | 模糊匹配 |
| Atlas 900 A3 | 智算服务器 | 48 | - | - | 模糊匹配 |
| Atlas 900 A3 | 智算服务器 | 48 | - | - | 模糊匹配 |
| Atlas 900 A3 | 智算服务器 | 48 | - | - | 模糊匹配 |
| Atlas 900 A3 | 智算服务器 | 48 | - | - | 模糊匹配 |
| Atlas 900 A3 | 智算服务器 | 48 | - | - | 模糊匹配 |
| Atlas 900 A3 | 智算服务器 | 48 | - | - | 模糊匹配 |
| Atlas 900 A3 | 智算服务器 | 48 | - | - | 模糊匹配 |
| Atlas 900 A3 | 智算服务器 | 48 | - | - | 模糊匹配 |
【待项目组确认】

| 设备型号 | 设备角色 | 设备数量 | 板卡/插卡型号 | 板卡/插卡数量 | 模型校验 |
|---|---|---|---|---|---|
| CE9866-128DQ-B | 设备角色待项目组确认 | 76 | CE9866-128DQ交换机(128\*400GE QSFP112,2\*10GE SFP+,4\*交流电源,6\*风机盒,)-ISP | - | 模糊匹配 |

## API 查询摘要

- 交付项目：`JD项目（test-boq）`
- 设备模型总数：`0`
- 模型校验列：`通过`=API 精确命中；`模糊匹配`=模糊匹配或未调 API（skip-api）
- API 精确命中台数：`0/0`

## 自动计算说明

- row_policy: `device-centric-v1`
- row_count: `12`
- rules_schema: `stage2-device-rows.rules.v1`
- rules_file: `C:/Users/z00486208/clone-boq/tools/demos/stage2-device-rows.rules.yaml`
- knowledge_refs: `{'knowledge_catalog': 'knowledge/taxonomy/knowledge-catalog.v0.yaml', 'bond_modes': 'knowledge/network-design-rules/bond-modes.v0.yaml', 'storage_chassis_management_ports': 'knowledge/product-knowledge/storage-chassis-management-ports.v0.yaml', 'compute_server_oob': 'knowledge/product-knowledge/compute-server-oob.v0.yaml', 'project_delivery': 'knowledge/project-knowledge-map.md', 'interconnect_map': 'knowledge/interconnect-knowledge-map.md', 'network_topology': '.cursor/skills/boq-analysis/knowledge/network-topology.md', 'compute_server_spec': '.cursor/skills/boq-analysis/knowledge/compute-server-spec.yaml', 'superpod_topology': '.cursor/skills/boq-analysis/knowledge/superpod-topology.md', 'optics_plane_rules': 'tools/core/optics_plane_rules.yaml', 'network_interconnect_design': 'knowledge/network-interconnect-design.md', 'plane_fabric_self_consistency': 'knowledge/plane-fabric-self-consistency.v0.md', 'parameter_plane_fabric': 'knowledge/parameter-plane-boq-fabric-derivation.v0.md', 'sample_plane_fabric': 'knowledge/sample-plane-boq-fabric-derivation.v0.md', 'management_plane_fabric': 'knowledge/management-plane-boq-fabric-derivation.v0.md', 'business_plane_fabric': 'knowledge/business-plane-boq-fabric-derivation.v0.md', 'stage12_outputs': 'knowledge/stage1-stage2-outputs-for-stage3.v0.md', 'rule_c_workflow': '.cursor/skills/project-delivery-workflow/SKILL.md', 'generalization_doc': 'knowledge/generalization-knowledge-and-rules.v0.md'}`
- design_knowledge_applied: `{'schema_version': 'design-knowledge-applied.v0', 'stage': 'stage2', 'generalization_doc': 'knowledge/generalization-knowledge-and-rules.v0.md', 'catalog': 'knowledge/taxonomy/knowledge-catalog.v0.yaml', 'catalog_schema_version': 'knowledge-catalog.v0', 'project_instance': None, 'project_bindings': None, 'design_rules_consolidated': None, 'manifest_design_knowledge_refs': {}, 'categories': {'network_design_rule': [{'id': 'bond_modes', 'path': 'knowledge/network-design-rules/bond-modes.v0.yaml', 'summary': 'bond1/bond4 定义与平面典型用法'}, {'id': 'cable_color_protocol', 'path': 'knowledge/network-design-rules/cable-color-protocol.v0.yaml', 'summary': '存储区三平面线缆颜色与协议'}, {'id': 'plane_fabric_self_consistency', 'path': 'knowledge/plane-fabric-self-consistency.v0.md', 'summary': 'BoQ 线卡端口池自洽优先'}, {'id': 'parameter_plane_fabric', 'path': 'knowledge/parameter-plane-boq-fabric-derivation.v0.md', 'summary': None}, {'id': 'sample_plane_fabric', 'path': 'knowledge/sample-plane-boq-fabric-derivation.v0.md', 'summary': None}, {'id': 'management_plane_fabric', 'path': 'knowledge/management-plane-boq-fabric-derivation.v0.md', 'summary': None}, {'id': 'business_plane_fabric', 'path': 'knowledge/business-plane-boq-fabric-derivation.v0.md', 'summary': None}], 'product_knowledge': [{'id': 'storage_chassis_management_ports', 'path': 'knowledge/product-knowledge/storage-chassis-management-ports.v0.yaml', 'summary': '9950/9550 带外 GE、IP/框、节点带外'}, {'id': 'compute_server_oob', 'path': 'knowledge/product-knowledge/compute-server-oob.v0.yaml', 'summary': None}, {'id': 'storage_io_card_labels', 'path': 'knowledge/product-knowledge/storage-io-card-labels.v0.yaml', 'summary': '适配表仿真定稿名；设备信息表 card_model 用 BoQ 原文（见 device_info_vs_compat_card_naming）'}, {'id': 'compute_server_spec', 'path': '.cursor/skills/boq-analysis/knowledge/compute-server-spec.yaml', 'summary': None}], 'process_rule': [{'id': 'device_info_vs_compat_card_naming', 'path': 'knowledge/device-info-vs-compat-card-naming.v0.md', 'summary': '设备信息表 card_model=BoQ 描述；适配表 sim_card_model=建模仿真匹配型号'}, {'id': 'datacenter_plane_derivation', 'path': 'knowledge/datacenter-plane-derivation.v0.md', 'summary': None}, {'id': 'compat_table_simulation_api', 'path': 'knowledge/compat-table-requires-simulation-api.v0.md', 'summary': None}, {'id': 'manifest_datacenter_placement', 'path': 'knowledge/manifest-datacenter-placement.v0.md', 'summary': None}, {'id': 'project_plane_confirmations', 'path': 'knowledge/project-plane-confirmations.v0.md', 'summary': None}, {'id': 'generalization_knowledge_and_rules', 'path': 'knowledge/generalization-knowledge-and-rules.v0.md', 'summary': '通用/模板/实例三层；禁止仓库内硬编码项目名'}]}, 'entry_count': 17, 'bindings_highlights': {}}`
- server_count_source: `unresolved`
- normalized_roles: `['server_gpu_eqv', 'switch_eqv']`
- xx4_overlay: `disabled`
- boq_coverage_notes: `['本 BoQ 信息缺少样本面、业务面、管理面的交换机信息；如需对智算网络进行建模仿真，请联系项目组补全相关交换机 BoQ。']`
- row_count_final: `15`
- numeric_qty_rows: `12`
