# a3-switch-asn-workflow

离线 **网络设备 ASN 规划**（确定性，无 LLM）。统一指令、按端口表与资源表**自动识别待规划平面**，对齐：

- `src/manage_agent/sub_agents/LLD_IP/a3_switch_loopback_ip_address.py`（BGP AS 分配）
- `src/manage_agent/sub_agents/LLD_IP/a3_switch_asn.py`（ASN 汇总导出）

## Quick start

```bash
cd skill_staging/a3-switch-asn-workflow.code1
pip install -r requirements.txt
# 将「端口连线表 007」与「项目信息收集表」放在当前目录
python scripts/offline_switch_asn_pipeline.py
```

输出：`output/run_*/A3交换机ASN规划.xlsx`（并复制到 skill 根目录），及 `plane_detection.txt`。

若资源表 `EBGP AS规划` 为空，需在表中填写 `65001-65099` 等形式，或使用：

```bash
python scripts/offline_switch_asn_pipeline.py --as-range "存储管理面=65001-65099"
```

## 统一指令

**网络设备ASN规划**（无需区分 L2/L3；线上 `_L2` / `_L3` 均调用同一函数）。

## 文档

详见 [SKILL.md](./SKILL.md)。
