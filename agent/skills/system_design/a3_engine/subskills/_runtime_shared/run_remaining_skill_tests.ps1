# Remaining subskill smoke tests (cwd = subskills)
$ErrorActionPreference = "Continue"
$base = Split-Path -Parent $PSScriptRoot
Set-Location $base

$connect = "建模仿真输出文档007-端口连线表for all4.xlsx"
$res = "项目信息收集表模板-20260130 (1).xlsx"
$accessPlan = "a3-dw-manage-ip-workflow.code1\output\run_20260602_163823\A3网络设备接入规划.xlsx"

$tests = @(
  @{ cat = "输入检查"; cmd = "python a3-input-components-workflow.code1\scripts\offline_input_components_pipeline.py --out-dir a3-input-components-workflow.code1\output" },
  @{ cat = "互联-OOB计算带外L2"; cmd = "python oob-interconnect-workflow.code1\scripts\run_oob_interconnect.py --layer l2 --topology `"$connect`" --resource `"$res`" --plan 计算带外管理互联规划 --out oob-interconnect-workflow.code1\output\A3网络互联规划_oob_dw.xlsx" },
  @{ cat = "互联-计算五平面"; cmd = "python a3-compute-net-interconnect-l2-l3-workflow.code1\scripts\offline_net_interconnect_pipeline.py --plane 计算样本面 --007 `"$connect`" --resource `"$res`" --out-dir a3-compute-net-interconnect-l2-l3-workflow.code1\output" },
  @{ cat = "互联-网络LEAF-SPINE"; cmd = "python a3-net-interconnection-workflow.code1\scripts\offline_ni_pipeline.py --intent 计算业务面互联规划 --connect `"$connect`" --resource `"$res`" --out-dir a3-net-interconnection-workflow.code1\output" },
  @{ cat = "接入-计算带外"; cmd = "python net-dw-access-ip-workflow.code1\scripts\run_network_access_plan.py --access-plan `"$accessPlan`" --plan 计算带外管理接入规划 --out net-dw-access-ip-workflow.code1\output\access_dw.xlsx" },
  @{ cat = "ASN规划"; cmd = "python a3-switch-asn-workflow.code1\scripts\offline_switch_asn_pipeline.py --connect `"$connect`" --resource `"$res`" --out-dir a3-switch-asn-workflow.code1\output" },
  @{ cat = "CCAE规划"; cmd = "python ccae-planner.code1\scripts\run_ccae_planner.py --topology `"$connect`" --resource `"$res`" --out ccae-planner.code1\output\A3CCAE部署规划_test.xlsx" },
  @{ cat = "DME规划"; cmd = "python dme-planning.code1\scripts\generate_dme_plan.py --trigger DME规划 --port-file `"$connect`" --resource-file `"$res`" --output-dir dme-planning.code1\output" },
  @{ cat = "NCE规划"; cmd = "python nce-planner.code1\scripts\run_nce_planner.py --topology `"$connect`" --resource `"$res`" --out nce-planner.code1\output\A3NCE部署规划_test.xlsx" },
  @{ cat = "MLAG规划"; cmd = "python switch-mlag-planning-workflow.code1\scripts\run_switch_mlag.py --topology `"$connect`" --resource `"$res`" --out-dir switch-mlag-planning-workflow.code1\runs" },
  @{ cat = "设备命名-清单"; cmd = "python a3-device-naming-workflow.code1\scripts\offline_device_naming_pipeline.py generate-list --connect `"$connect`" --resource `"$res`" --out-dir a3-device-naming-workflow.code1\output" },
  @{ cat = "ZTP-LLD"; cmd = "python a3-generate-ztp-lld-workflow.code1\scripts\offline_generate_ztp_lld_pipeline.py --scan-dir . --out-dir a3-generate-ztp-lld-workflow.code1\output" },
  @{ cat = "ZTP-CFG"; cmd = "python a3-generate-ztp-cfg-workflow.code1\scripts\offline_generate_ztp_cfg_pipeline.py --scan-dir . --out-dir a3-generate-ztp-cfg-workflow.code1\output" },
  @{ cat = "灵衢开局"; cmd = "python a3-generate-lq-open-workflow.code1\scripts\offline_generate_lq_open_pipeline.py --scan-dir . --out-dir a3-generate-lq-open-workflow.code1\output" },
  @{ cat = "LLD-plan"; cmd = "python a3_LLD_generate_code1\scripts\offline_lld_generate_pipeline.py --mode plan --topology `"$connect`" --resource `"$res`" --out-dir a3_LLD_generate_code1\output" }
)

$results = @()
foreach ($t in $tests) {
  Write-Host "`n======== $($t.cat) ========"
  Invoke-Expression $t.cmd
  $code = $LASTEXITCODE
  $results += [pscustomobject]@{ category = $t.cat; exit = $code }
}
Write-Host "`n======== SUMMARY ========"
$results | Format-Table -AutoSize
