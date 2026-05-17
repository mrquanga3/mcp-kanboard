<#
.SYNOPSIS
  Stop the mcp-kanboard HTTP server and ngrok tunnel started by start-web.ps1.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "SilentlyContinue"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$statePath = Join-Path $repoRoot ".web-mcp-state.json"

if (Test-Path $statePath) {
    $state = Get-Content $statePath -Raw | ConvertFrom-Json
    foreach ($name in @("mcp_pid", "ngrok_pid")) {
        $procId = $state.$name
        if ($procId) {
            $proc = Get-Process -Id $procId
            if ($proc) {
                Write-Host "Stopping $($proc.ProcessName) (PID $procId)"
                Stop-Process -Id $procId -Force
            }
        }
    }
    Remove-Item $statePath
} else {
    Write-Host "No .web-mcp-state.json — falling back to killing any ngrok processes."
    Get-Process -Name "ngrok" | Stop-Process -Force
}
Write-Host "Done."
