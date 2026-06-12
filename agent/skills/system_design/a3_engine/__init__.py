"""a3_engine · a3-intelligent-network-opening 子 skill 源码 vendoring 包。

包含从 a3 工程复制进 AIDA 的全部代码：
  - subskills/  ：30+ 子 skill（地址/互联/接入/网管/LLD/ZTP/命名 offline pipeline）
  - runtime/    ：argv_builder / registry_loader / dispatch_runner / subprocess_runner 等
  - path_config.py

代码根（本目录）与数据根（a3 工程 ProjectData/）解耦：
  - 代码：随 AIDA 仓库走，离线自包含（见 a3_paths.get_a3_code_root）
  - 数据：输入件 / 产物仍在 a3 工程 ProjectData（见 a3_paths.get_a3_data_root）

⚠️ 子 skill 之间用 `../` 相对路径与 sys.path 互引，调用经 pipelines/a3_bridge 统一 bootstrap。
"""
