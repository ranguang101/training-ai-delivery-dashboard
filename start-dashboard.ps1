<#
.SYNOPSIS
    一键启动辅导班提效系统交付看板（本地只读模式）
.DESCRIPTION
    绑定 127.0.0.1:8013，以 D:\培训机构AI提效项目 为项目根目录。
    如需指定其他端口或路径，可通过参数覆盖。
#>
[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8013,
    [string]$ProjectRoot = "D:\培训机构AI提效项目"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Error "未找到虚拟环境 Python: $PythonExe，请先配置 .venv。"
    exit 1
}

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " 启动辅导班提效系统交付看板 (只读监控)" -ForegroundColor Cyan
Write-Host " 地址: http://$HostAddress`:$Port/project-status" -ForegroundColor Green
Write-Host " 项目根路径: $ProjectRoot" -ForegroundColor Yellow
Write-Host " 按 Ctrl+C 退出进程" -ForegroundColor Gray
Write-Host "=========================================" -ForegroundColor Cyan

& $PythonExe -m tools.project_dashboard.run `
    --host $HostAddress `
    --port $Port `
    --project-root $ProjectRoot
