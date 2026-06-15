param(
    [switch]$NoStart,
    [switch]$NoFrontend,
    [switch]$NoMailgw,
    [switch]$NoMockDatacenter,
    [switch]$KeepMailgwData
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $Root ".codex-start-logs"
$AgentPython = Join-Path $Root "agent\.venv\Scripts\python.exe"
$AgentEnv = Join-Path $Root "agent\.env"

function Write-Step($Message) {
    Write-Host "[reset-local] $Message"
}

function Get-DotEnvValue($Path, $Name) {
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.+?)\s*$") {
            return $Matches[1].Trim('"').Trim("'")
        }
    }
    return $null
}

function Stop-ProcessTreeById {
    param(
        [int]$ProcessId,
        [string]$Reason = ""
    )
    if ($ProcessId -le 0 -or $ProcessId -eq $PID) { return }

    $children = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ParentProcessId -eq $ProcessId }
    foreach ($child in $children) {
        Stop-ProcessTreeById -ProcessId ([int]$child.ProcessId) -Reason $Reason
    }

    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($proc) {
        $suffix = if ($Reason) { " $Reason" } else { "" }
        Write-Step "stop pid=$ProcessId $($proc.ProcessName)$suffix"
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Stop-DevCommandLines {
    $patterns = @(
        "agent\.main:app",
        "agent.main:app",
        "manager\.main:app",
        "manager.main:app",
        "mock_datacenter\.py",
        "-m\s+mailgw"
    )
    $processes = @()
    foreach ($proc in (Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)) {
        if ($proc.ProcessId -eq $PID) { continue }
        if ($proc.Name -notin @("python.exe", "node.exe", "npm.cmd")) { continue }
        if (-not $proc.CommandLine) { continue }
        foreach ($pattern in $patterns) {
            if ($proc.CommandLine -match $pattern) {
                $processes += $proc
                break
            }
        }
    }

    foreach ($proc in $processes) {
        Stop-ProcessTreeById -ProcessId ([int]$proc.ProcessId) -Reason "matching dev command"
    }
}

function Stop-DevPorts {
    param([int[]]$Ports)
    $connections = Get-NetTCPConnection -State Listen -LocalPort $Ports -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -notin @("python", "node")) { continue }
        if ($proc) {
            Stop-ProcessTreeById -ProcessId ([int]$conn.OwningProcess) -Reason ":$($conn.LocalPort)"
            continue
        }

        $children = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.ParentProcessId -eq $conn.OwningProcess }
        foreach ($child in $children) {
            Stop-ProcessTreeById -ProcessId ([int]$child.ProcessId) -Reason ":$($conn.LocalPort) orphaned listener parent=$($conn.OwningProcess)"
        }
    }
}

function Wait-DevPortsReleased {
    param(
        [int[]]$Ports,
        [int]$TimeoutSeconds = 12
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $open = Get-NetTCPConnection -State Listen -LocalPort $Ports -ErrorAction SilentlyContinue
        if (-not $open) { return $true }
        Start-Sleep -Milliseconds 500
    }

    $remaining = Get-NetTCPConnection -State Listen -LocalPort $Ports -ErrorAction SilentlyContinue
    foreach ($conn in $remaining) {
        Write-Step "port still busy :$($conn.LocalPort) owner=$($conn.OwningProcess)"
    }
    return $false
}

function Stop-LocalDevServices {
    param([int[]]$Ports)
    Stop-DevPorts -Ports $Ports
    Stop-DevCommandLines
    Start-Sleep -Seconds 2
    Stop-DevPorts -Ports $Ports
    if (-not (Wait-DevPortsReleased -Ports $Ports)) {
        throw "Local dev ports were not released; aborting restart to avoid serving stale code."
    }
}

function Clear-DirectoryContents {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
        return
    }
    $resolved = Resolve-Path $Path
    $driveRoot = [System.IO.Path]::GetPathRoot($resolved.Path)
    if ($resolved.Path -eq $driveRoot) {
        throw "Refusing to clear drive root: $($resolved.Path)"
    }
    Get-ChildItem -LiteralPath $resolved.Path -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

function Start-HiddenProcess {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [string]$LogName
    )
    $out = Join-Path $LogDir "$LogName.out.log"
    $err = Join-Path $LogDir "$LogName.err.log"
    Write-Step "start $LogName"
    Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $out `
        -RedirectStandardError $err `
        -WindowStyle Hidden | Out-Null
}

function Test-Http {
    param(
        [string]$Name,
        [string]$Url,
        [int[]]$OkStatus = @(200)
    )
    try {
        $response = Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 8
        $code = [int]$response.StatusCode
    } catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $code = [int]$_.Exception.Response.StatusCode
        } else {
            Write-Step "$Name FAIL: $($_.Exception.Message)"
            return $false
        }
    }
    if ($OkStatus -contains $code) {
        Write-Step "$Name OK: HTTP $code"
        return $true
    }
    Write-Step "$Name FAIL: HTTP $code"
    return $false
}

if (-not (Test-Path $AgentPython)) {
    throw "agent venv not found: $AgentPython"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Write-Step "stop local dev services"
Stop-LocalDevServices -Ports @(8080, 7401, 8081, 8025, 9000)

$zhgkRoot = Get-DotEnvValue $AgentEnv "ZHGK_ROOT"
if (-not $zhgkRoot) {
    $zhgkRoot = Join-Path $env:USERPROFILE ".nanobot\workspace\skills\zhgk"
}
$projectData = Join-Path $zhgkRoot "ProjectData"

Write-Step "clear zhgk runtime data: $projectData"
foreach ($sub in @("Input", "Output", "RunTime", "Images")) {
    Clear-DirectoryContents (Join-Path $projectData $sub)
}
foreach ($sub in @("Start", "Template")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $projectData $sub) | Out-Null
}

$mockReportDest = Join-Path $projectData "Input\本地工勘报告.pdf"
$mockReportProject = Join-Path $Root "data\projects\70e5ca737ae5433e9f0f3134d216acf7\交付作业\智慧工勘\输入文件\本地工勘报告.pdf"
$mockReportFixture = Join-Path $Root "agent\skills\zhgk\fixtures\本地工勘报告.pdf"
$mockReportSrc = $null
if (Test-Path $mockReportProject) { $mockReportSrc = $mockReportProject }
elseif (Test-Path $mockReportFixture) { $mockReportSrc = $mockReportFixture }
if ($mockReportSrc) {
    New-Item -ItemType Directory -Force -Path (Join-Path $projectData "Input") | Out-Null
    Copy-Item -LiteralPath $mockReportSrc -Destination $mockReportDest -Force
    Write-Step "seed demo report from project: $mockReportDest"
} else {
    Write-Step "skip demo report seed: project asset and legacy fixture both missing"
}

if (-not $KeepMailgwData) {
    $mailgwData = Join-Path $Root "mailgw\data"
    Write-Step "clear mailgw local data: $mailgwData"
    Clear-DirectoryContents $mailgwData
}

Clear-DirectoryContents $LogDir

if ($NoStart) {
    Write-Step "skip start because -NoStart was set"
    exit 0
}

$env:NO_PROXY = "127.0.0.1,localhost"
$env:no_proxy = "127.0.0.1,localhost"

if (-not $NoMockDatacenter) {
    Start-HiddenProcess `
        -FilePath $AgentPython `
        -ArgumentList @("agent/.local/mock_datacenter.py") `
        -WorkingDirectory $Root `
        -LogName "mock-datacenter"
}

Start-HiddenProcess `
    -FilePath $AgentPython `
    -ArgumentList @("-m", "uvicorn", "agent.main:app", "--host", "127.0.0.1", "--port", "7401", "--workers", "1") `
    -WorkingDirectory $Root `
    -LogName "agent"

Start-HiddenProcess `
    -FilePath $AgentPython `
    -ArgumentList @("-m", "uvicorn", "manager.main:app", "--host", "127.0.0.1", "--port", "8081", "--workers", "1") `
    -WorkingDirectory $Root `
    -LogName "manager"

if (-not $NoMailgw) {
    $mailgwConfig = Join-Path $Root "mailgw\config.yaml"
    if (Test-Path $mailgwConfig) {
        $mailgwPython = Join-Path $Root "mailgw\.venv\Scripts\python.exe"
        if (-not (Test-Path $mailgwPython)) { $mailgwPython = $AgentPython }
        Start-HiddenProcess `
            -FilePath $mailgwPython `
            -ArgumentList @("-m", "mailgw", "--config", "config.yaml", "--env", ".env", "--host", "127.0.0.1", "--port", "8025") `
            -WorkingDirectory (Join-Path $Root "mailgw") `
            -LogName "mailgw"
    } else {
        Write-Step "skip mailgw: mailgw\config.yaml not found"
    }
}

if (-not $NoFrontend) {
    Start-HiddenProcess `
        -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
        -WorkingDirectory (Join-Path $Root "frontend") `
        -LogName "frontend"
}

Start-Sleep -Seconds 7

$ok = $true
if (-not $NoMockDatacenter) { $ok = (Test-Http "mock-datacenter" "http://127.0.0.1:9000/health") -and $ok }
$ok = (Test-Http "agent" "http://127.0.0.1:7401/healthz") -and $ok
$ok = (Test-Http "manager" "http://127.0.0.1:8081/health") -and $ok
if (-not $NoMailgw -and (Test-Path (Join-Path $Root "mailgw\config.yaml"))) {
    $ok = (Test-Http "mailgw" "http://127.0.0.1:8025/admin" @(200, 401)) -and $ok
}
if (-not $NoFrontend) { $ok = (Test-Http "frontend" "http://127.0.0.1:8080") -and $ok }

if (-not $ok) {
    Write-Step "one or more services failed health checks; see $LogDir"
    exit 1
}

Write-Step "reset complete"
