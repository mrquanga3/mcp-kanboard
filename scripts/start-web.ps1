<#
.SYNOPSIS
  Start mcp-kanboard HTTP transport + ngrok tunnel, print connector info for claude.ai.

.DESCRIPTION
  Kills any previous mcp-kanboard / ngrok process, generates (or reuses) a bearer
  token, starts the MCP HTTP server on $Port, opens an ngrok tunnel to it, queries
  the ngrok local API for the public URL, and prints everything you need to paste
  into claude.ai -> Connectors -> Add custom connector.

  State (URL, token, PIDs) is written to .web-mcp-state.json (gitignored) for
  reuse / cleanup.

.PARAMETER Port
  Local port for the MCP HTTP server. Default 8765.

.PARAMETER BearerToken
  Pre-existing bearer token to reuse. If omitted, a new 32-byte URL-safe token is
  generated.

.PARAMETER Insecure
  Pass through --insecure-no-auth to mcp-kanboard. Skips bearer check (use ONLY
  for a quick test).

.EXAMPLE
  .\scripts\start-web.ps1

.EXAMPLE
  .\scripts\start-web.ps1 -Port 9000 -BearerToken (Get-Content .bearer.txt)
#>
[CmdletBinding()]
param(
    [int]$Port = 8765,
    [string]$BearerToken = "",
    [switch]$Insecure
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$statePath = Join-Path $repoRoot ".web-mcp-state.json"

function Stop-OnPort {
    param([int]$LocalPort)
    $conns = Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        try {
            $proc = Get-Process -Id $c.OwningProcess -ErrorAction Stop
            Write-Host "  Killing $($proc.ProcessName) (PID $($proc.Id)) on port $LocalPort"
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        } catch {}
    }
}

# 1. Reuse prior state for cleanup
Write-Host "[1/5] Killing previous mcp-kanboard / ngrok processes..." -ForegroundColor Cyan
if (Test-Path $statePath) {
    try {
        $prev = Get-Content $statePath -Raw | ConvertFrom-Json
        foreach ($oldPid in @($prev.mcp_pid, $prev.ngrok_pid)) {
            if ($oldPid) {
                Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
}
Get-Process -Name "ngrok" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Stop-OnPort -LocalPort $Port
Start-Sleep -Milliseconds 800

# 2. Bearer token
if (-not $Insecure) {
    if (-not $BearerToken) {
        $bytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $BearerToken = [Convert]::ToBase64String($bytes).Replace("+","-").Replace("/","_").TrimEnd("=")
        Write-Host "[!] Generated new bearer token (will be required in claude.ai header)" -ForegroundColor Yellow
    }
    $env:MCP_BEARER_TOKEN = $BearerToken
} else {
    Remove-Item Env:\MCP_BEARER_TOKEN -ErrorAction SilentlyContinue
}

# 3. Start MCP HTTP
Write-Host "[2/5] Starting mcp-kanboard --http on port $Port..." -ForegroundColor Cyan
$mcpArgs = @("run", "mcp-kanboard", "--http", "--port", "$Port")
if ($Insecure) { $mcpArgs += "--insecure-no-auth" }
$mcpProc = Start-Process -FilePath "uv" -ArgumentList $mcpArgs `
    -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 3

if ($mcpProc.HasExited) {
    Write-Host "[!] mcp-kanboard exited immediately (exit $($mcpProc.ExitCode)). Check Kanboard env vars in .env." -ForegroundColor Red
    exit 1
}

# Confirm port is listening
$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    Write-Host "[!] Port $Port is not listening after 3s. mcp-kanboard may have failed silently." -ForegroundColor Red
    exit 1
}
Write-Host "  MCP listening on http://127.0.0.1:$Port/mcp (PID $($mcpProc.Id))"

# 4. Start ngrok
Write-Host "[3/5] Starting ngrok tunnel..." -ForegroundColor Cyan
$ngrokProc = Start-Process -FilePath "ngrok" -ArgumentList @("http", "$Port", "--log=stdout") `
    -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 3

# 5. Read public URL from ngrok's local API
Write-Host "[4/5] Reading public URL from http://127.0.0.1:4040/api/tunnels..." -ForegroundColor Cyan
$publicUrl = $null
for ($i = 0; $i -lt 12; $i++) {
    try {
        $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2 -ErrorAction Stop
        $https = $tunnels.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1
        if ($https) { $publicUrl = $https.public_url; break }
    } catch {}
    Start-Sleep -Seconds 1
}
if (-not $publicUrl) {
    Write-Host "[!] Could not read ngrok URL. Is ngrok authenticated? Try: ngrok config add-authtoken <YOUR_TOKEN>" -ForegroundColor Red
    Stop-Process -Id $mcpProc.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $ngrokProc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
$mcpUrl = "$publicUrl/mcp"

# 6. Save state
$state = [PSCustomObject]@{
    public_url   = $mcpUrl
    bearer_token = $BearerToken
    insecure     = [bool]$Insecure
    mcp_pid      = $mcpProc.Id
    ngrok_pid    = $ngrokProc.Id
    started_at   = (Get-Date).ToString("o")
}
$state | ConvertTo-Json | Set-Content -Encoding UTF8 $statePath

# 7. Print
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "[5/5] Ready. In claude.ai -> Settings -> Connectors -> Add custom connector:" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Name:        Kanboard"
Write-Host ("  Remote URL:  {0}" -f $mcpUrl) -ForegroundColor White
if (-not $Insecure) {
    Write-Host "  Advanced settings -> Custom headers:"
    Write-Host ("    Authorization: Bearer {0}" -f $BearerToken) -ForegroundColor White
} else {
    Write-Host "  Auth:        NONE (insecure mode)" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "MCP PID:    $($mcpProc.Id)"
Write-Host "ngrok PID:  $($ngrokProc.Id)"
Write-Host ""
Write-Host "To stop:    .\scripts\stop-web.ps1   (or kill PIDs above)"
Write-Host "State file: $statePath (gitignored)"
Write-Host ""
