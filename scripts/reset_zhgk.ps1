param(
    [switch]$ClearInput,
    [switch]$ClearTemplate,
    [switch]$ClearCheckpoints,
    [switch]$Full,
    [switch]$DryRun,
    [string]$ZhgkRoot = ""
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$AgentPython = Join-Path $Root "agent\.venv\Scripts\python.exe"
$Script = Join-Path $Root "agent\scripts\reset_zhgk_workspace.py"

if (-not (Test-Path $AgentPython)) {
    throw "agent venv not found: $AgentPython"
}

$argsList = @($Script)
if ($ZhgkRoot) { $argsList += @("--zhgk-root", $ZhgkRoot) }
if ($ClearInput) { $argsList += "--clear-input" }
if ($ClearTemplate) { $argsList += "--clear-template" }
if ($ClearCheckpoints) { $argsList += "--clear-checkpoints" }
if ($Full) { $argsList += "--full" }
if ($DryRun) { $argsList += "--dry-run" }

& $AgentPython @argsList
exit $LASTEXITCODE
