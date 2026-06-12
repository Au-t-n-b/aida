# a3-csm-ip-workflow

离线 **计算参数面地址规划**（确定性，无 LLM）。自动识别 A2 / A3 场景，对齐：

- `src/manage_agent/sub_agents/LLD_IP/csm_ip_address.py`
- `src/manage_agent/sub_agents/LLD_IP/a3_csm_ip_address.py`

## Quick start

```bash
cd skill_staging/a3-csm-ip-workflow.code1
pip install -r requirements.txt
# 将「参数面端口互联」与「项目信息收集表」放在当前目录
python scripts/offline_csm_pipeline.py
```

输出：`output/run_*/` 下的网段规划、IP 地址规划、地址规划 Excel 及 `scenario_detection.txt`。

## 统一指令

**计算参数面地址规划**（无需区分 L2/L3 或 A2/A3）。

## 文档

详见 [SKILL.md](./SKILL.md)。
