param(
    [string]$Source = "$env:USERPROFILE\Desktop\通道\通道1.sog",
    [string]$DestRoot = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "data\sog-assets\channel1")
)

$ErrorActionPreference = 'Stop'

if (!(Test-Path $Source)) {
    throw "SOG 源文件不存在: $Source`n请用 -Source 指定通道1.sog 路径。"
}

New-Item -ItemType Directory -Force -Path $DestRoot | Out-Null
Copy-Item -Force -Path $Source -Destination (Join-Path $DestRoot 'scene.sog')

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Join-Path $DestRoot 'hotspots.json'), "[]`n", $utf8NoBom)
$metaJson = (@{
    id = 'channel1'
    originalName = '通道1.sog'
    fileName = 'scene.sog'
    importedAt = (Get-Date).ToString('o')
} | ConvertTo-Json)
[System.IO.File]::WriteAllText((Join-Path $DestRoot 'meta.json'), $metaJson, $utf8NoBom)

Write-Host "已部署工勘孪生通道1:"
Get-ChildItem $DestRoot | Select-Object Name, Length | Format-Table -AutoSize
