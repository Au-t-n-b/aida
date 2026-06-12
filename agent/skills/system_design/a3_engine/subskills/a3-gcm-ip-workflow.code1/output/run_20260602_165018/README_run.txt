topology=i3
network_plane=计算管存面
sheet007=计算管存面端口互联
sheet_res_index=网络资源需求表
server_substring='AT900'
i3_split_spine_leaf=False

语义说明：
  i2 — 等价于离线化 a3_l2_ip_address：全项目节点共用同一IPv4子网顺序分配（二层汇聚场景）。
  i3 — 等价于离线化 a3_ywm_ip_address 网段诉求：每台接入交换机（末列）独立子网，与 a3_i3_network_segment_tools_prompt 的规则一致（LEAF 一机一网段）。
