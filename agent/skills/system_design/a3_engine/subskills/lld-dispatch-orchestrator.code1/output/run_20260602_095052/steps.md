# Dispatch plan: 地址规划

- anchor_level: `L1`
- phases: 8

## L2: 带外管理地址规划 (ready)
### 1. 计算带外管理地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-dw-manage-ip-workflow.code1\scripts\offline_dw_manage_pipeline.py --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`
### 2. 网络带外管理地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-net-dw-manage-ip-workflow.code1\scripts\offline_net_dw_manage_pipeline.py --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`
### 3. 存储带外管理地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-storage-dw-manage-ip-workflow.code1\scripts\offline_storage_dw_manage_pipeline.py --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`
### 4. 灵衢带外管理地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-lq-dw-manage-ip-workflow.code1\scripts\offline_lq_dw_manage_pipeline.py --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`

## L2: 管理面地址规划 (ready)
### 1. 计算管理面地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-l2-l3-ip-workflow.code1\scripts\offline_l2_l3_ip_pipeline.py --sheet 计算管理面端口互联 --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`
### 2. 存储管理面地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-cc-glm-ip-workflow.code1\scripts\offline_cc_glm_pipeline.py --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`

## L2: 管存面地址规划 (ready)
### 1. 计算管存面地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-gcm-ip-workflow.code1\scripts\offline_gcm_pipeline.py --topology i3 --network-plane 计算管存面 --skip-prompt-check --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`

## L2: 业务面地址规划 (ready)
### 1. 计算业务面地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-ywm-ip-workflow.code1\scripts\offline_ywm_pipeline.py --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`
### 2. 存储业务面地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-cc-ywm-ip-workflow.code1\scripts\offline_cc_ywm_pipeline.py --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`

## L2: 样本面地址规划 (ready)
### 1. 计算样本面地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-ybm-ip-workflow.code1\scripts\ybm_offline_pipeline.py --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`
### 2. 存储样本面地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-cc-ybm-ip-workflow.code1\scripts\offline_cc_ybm_pipeline.py --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`

## L2: 参数面地址规划 (ready)
### 1. 计算参数面地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-csm-ip-workflow.code1\scripts\offline_csm_pipeline.py --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`

## L2: 超平面地址规划 (ready)
### 1. 计算超平面地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-cpm-lq-ip-workflow.code1\scripts\offline_cpm_lq_ip_pipeline.py --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`

## L2: 网络业务地址规划 (ready)
### 1. 网络业务地址规划 (ready)
- cli: `C:\Program Files\Python311\python.exe D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\a3-gcm-ip-workflow.code1\scripts\offline_gcm_pipeline.py --topology i3 --network-plane 其它 --skip-prompt-check --out-dir D:\OCCproject\终版skill对齐\a3-intelligent-network-opening\subskills\lld-dispatch-orchestrator.code1\output`
