# a3-compute-net-interconnect-l2-l3-workflow

**离线确定性** A3 计算侧五类平面 **Leaf–Spine 网络互联规划**：**只依赖「项目信息收集表」中的 `网络资源需求表`**（第一列网络平面 + **`网关位置*`**：`SPINE`→L2、`LEAF`→L3），配合 007 端口连线表，**每次运行输出一份** `output/run_*/A3网络互联规划.xlsx`。

> L2：接口/VLAN 对齐 `a3_l2_net_interconnection.py`，**ETH-TRUNK 恒为 2**  
> L3：对齐 `a3_ni_ip_address.py`

## 安装

```bash
python -m pip install -r requirements.txt
```

## 推荐用法（自动 L2/L3）

在含 **`项目信息收集表.xlsx`** 与 007 的 **cwd** 下：

```bash
python scripts/offline_net_interconnect_pipeline.py --plane 计算样本面
```

可选：`--007`、`--resource`（默认优先当前目录 **`项目信息收集表.xlsx`**）、`--merge-from`。

## 显式用法

```bash
python scripts/offline_net_interconnect_pipeline.py --mode l2 --sheet 计算管理面端口互联
```

详见 **`SKILL.md`**。

## 目录结构

- `SKILL.md`：契约与参数全文  
- `scripts/offline_net_interconnect_pipeline.py`：主入口  
- `scripts/net_interconnect_rules.py`：规则（含网关→模式、007 sheet 候选）  
- `scripts/validate_inputs.py`：可选校验（支持 `--plane`）
