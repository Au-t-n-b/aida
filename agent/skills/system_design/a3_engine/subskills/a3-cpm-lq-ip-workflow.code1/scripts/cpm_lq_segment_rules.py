"""DEPRECATED: 这是上一轮 i2/i3 路线的产物，已废弃。
本 skill 现按 a3_cpm_L1_ip_prompt.py / a3_cpm_L2_ip_prompt.py 实现 LoopBack 规划，
全部业务逻辑迁移到 cpm_lq_loopback_rules.py。

请在把 skill 移动到 D:\\project\\system\\ 之前手动删除本文件：
    Remove-Item "D:\\project\\system\\a3-cpm-lq-ip-workflow.code1\\scripts\\cpm_lq_segment_rules.py"
"""

raise ImportError(
    "cpm_lq_segment_rules.py is deprecated; use cpm_lq_loopback_rules.py instead."
)
