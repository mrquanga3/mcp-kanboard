<#
.SYNOPSIS
  Start mcp-kanboard HTTP transport + ngrok tunnel, print connector info
  for claude.ai. Auth is OAuth + passphrase (set via MCP_PASSPHRASE).

.DESCRIPTION
  Kills any previous mcp-kanboard / ngrok process, reads MCP_PASSPHRASE
  from .env if present, starts the MCP HTTP server on $Port, opens an
  ngrok tunnel to it, queries the ngrok local API for the public URL,
  and prints everything you need to paste into claude.ai -> Connectors
  -> Add custom connector. claude.ai will redirect you to a passphrase
  form once on connect.

  State (URL, PIDs) is written to .web-mcp-state.json (gitignored) for
  reuse / cleanup.

.PARAMETER Port
  Local port for the MCP HTTP server. Default 8765.

.PARAMETER Insecure
  Pass --insecure-no-auth to mcp-kanboard. No login required. Use ONLY
  for a quick test, then stop immediately.

.EXAMPLE
  .\scripts\start-web.ps1

.EXAMPLE
  .\scripts\start-web.ps1 -Insecure
#>
[CmdletBinding()]
param(
    [int]$Port = 8765,
    [switch]$Insecure
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$statePath = Join-Path $repoRoot ".web-mcp-state.json"
$envPath = Join-Path $repoRoot ".env"

# --- Prerequisite check ---
$missing = @()
foreach ($cmd in @("uv", "ngrok")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { $missing += $cmd }
}
if ($missing) {
    Write-Host "[!] Missing on PATH: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "    Run first:  .\scripts\setup.ps1" -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path (Join-Path $repoRoot ".venv"))) {
    Write-Host "[!] .venv not found. Run first:  .\scripts\setup.ps1" -ForegroundColor Yellow
    exit 1
}

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

function Read-DotenvValue {
    param([string]$Path, [string]$Key)
    if (-not (Test-Path $Path)) { return "" }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
        $eq = $trimmed.IndexOf("=")
        if ($eq -lt 1) { continue }
        $k = $trimmed.Substring(0, $eq).Trim()
        $v = $trimmed.Substring($eq + 1).Trim().Trim('"').Trim("'")
        if ($k -eq $Key) { return $v }
    }
    return ""
}

function Stop-NgrokOnPort {
    param([int]$LocalPort)
    # Only kill ngrok agents whose command line targets EXACTLY our port.
    # \b at the end prevents "8765" from matching "87650" or "87651" — so
    # ngrok agents tunneling other MCPs (different ports) are left alone.
    $pattern = "http\s+$LocalPort\b"
    try {
        $procs = Get-CimInstance Win32_Process -Filter "Name = 'ngrok.exe'" -ErrorAction SilentlyContinue
        foreach ($p in $procs) {
            if ($p.CommandLine -match $pattern) {
                Write-Host "  Stopping ngrok (PID $($p.ProcessId)) targeting port $LocalPort..."
                Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            } else {
                Write-Host "  Leaving ngrok (PID $($p.ProcessId)) alone — different port." -ForegroundColor Gray
            }
        }
    } catch {}
}

# Resolve port: use environment variable MCP_PORT if specified in .env and not explicitly overridden on command line
if (-not $PSBoundParameters.ContainsKey('Port')) {
    $envPort = Read-DotenvValue -Path $envPath -Key "MCP_PORT"
    if ($envPort) {
        $Port = [int]$envPort
        Write-Host "  Using port $Port configured in .env (MCP_PORT)..." -ForegroundColor Gray
    }
}
Write-Host "Resolved port: $Port" -ForegroundColor Cyan

# 1. Cleanup prior run
Write-Host "[1/5] Killing previous mcp-kanboard / ngrok processes on port $Port..." -ForegroundColor Cyan
if (Test-Path $statePath) {
    try {
        $prev = Get-Content $statePath -Raw | ConvertFrom-Json
        foreach ($oldPid in @($prev.mcp_pid, $prev.ngrok_pid)) {
            if ($oldPid) { Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue }
        }
    } catch {}
}
Stop-NgrokOnPort -LocalPort $Port
Stop-OnPort -LocalPort $Port
Start-Sleep -Milliseconds 800

# 2. Resolve passphrase from env / .env
if (-not $Insecure) {
    $resolved = $env:MCP_PASSPHRASE
    if (-not $resolved) { $resolved = Read-DotenvValue -Path $envPath -Key "MCP_PASSPHRASE" }
    if (-not $resolved) {
        Write-Host ""
        Write-Host "[!] MCP_PASSPHRASE not found in environment or .env." -ForegroundColor Red
        Write-Host "    Add a line to .env:    MCP_PASSPHRASE=<any string you'll remember>"
        Write-Host "    Then re-run this script. Or pass -Insecure for a no-auth test."
        exit 1
    }
    $env:MCP_PASSPHRASE = $resolved
} else {
    Remove-Item Env:\MCP_PASSPHRASE -ErrorAction SilentlyContinue
}

# 3. Start MCP HTTP
Write-Host "[2/5] Starting mcp-kanboard --http on port $Port..." -ForegroundColor Cyan
$mcpArgs = @("run", "mcp-kanboard", "--http", "--port", "$Port")
if ($Insecure) { $mcpArgs += "--insecure-no-auth" }

$logPath = Join-Path $repoRoot "mcp-server.log"
$errPath = Join-Path $repoRoot "mcp-server-err.log"
Remove-Item $logPath -ErrorAction SilentlyContinue
Remove-Item $errPath -ErrorAction SilentlyContinue

$mcpProc = Start-Process -FilePath "uv" -ArgumentList $mcpArgs `
    -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $logPath -RedirectStandardError $errPath

Write-Host "  Waiting up to 12s for port $Port to start listening..." -ForegroundColor Gray
$listening = $false
for ($i = 0; $i -lt 12; $i++) {
    if ($mcpProc.HasExited) {
        break
    }
    $listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($listening) {
        break
    }
    Start-Sleep -Seconds 1
}

if ($mcpProc.HasExited -or -not $listening) {
    if ($mcpProc.HasExited) {
        Write-Host "[!] mcp-kanboard exited immediately (exit $($mcpProc.ExitCode))." -ForegroundColor Red
    } else {
        Write-Host "[!] Port $Port is not listening after 12s. mcp-kanboard may have failed silently." -ForegroundColor Red
        Stop-Process -Id $mcpProc.Id -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $logPath) {
        Write-Host ""
        Write-Host "--- Server Log Output (from mcp-server.log) ---" -ForegroundColor Yellow
        Get-Content $logPath
        Write-Host "------------------------------------------------" -ForegroundColor Yellow
    }
    if (Test-Path $errPath) {
        Write-Host ""
        Write-Host "--- Server Error Output (from mcp-server-err.log) ---" -ForegroundColor Red
        Get-Content $errPath
        Write-Host "----------------------------------------------------" -ForegroundColor Red
    }
    exit 1
}
Write-Host "  MCP listening on http://127.0.0.1:$Port/mcp (PID $($mcpProc.Id))"

# 4. Start ngrok (capture stdout/stderr so we can show why it died if it dies)
# Resolve dedicated authtoken from env / .env so this MCP uses its own ngrok
# account, independent of any other agent (e.g. mcp-gitlab) using a different
# token. ngrok reads NGROK_AUTHTOKEN natively when launched.
Write-Host "[3/5] Starting ngrok tunnel..." -ForegroundColor Cyan
$ngrokToken = $env:KANBOARD_NGROK_AUTHTOKEN
if (-not $ngrokToken) { $ngrokToken = Read-DotenvValue -Path $envPath -Key "KANBOARD_NGROK_AUTHTOKEN" }
if (-not $ngrokToken) { $ngrokToken = Read-DotenvValue -Path $envPath -Key "NGROK_AUTHTOKEN" }
if ($ngrokToken) {
    $env:NGROK_AUTHTOKEN = $ngrokToken
    Write-Host "  Using NGROK_AUTHTOKEN from .env (dedicated kanboard token)." -ForegroundColor Gray
} else {
    Write-Host "  No KANBOARD_NGROK_AUTHTOKEN in .env; falling back to ngrok global config." -ForegroundColor Gray
}

$ngrokLog = Join-Path $repoRoot "ngrok.log"
$ngrokErr = Join-Path $repoRoot "ngrok-err.log"
Remove-Item $ngrokLog -ErrorAction SilentlyContinue
Remove-Item $ngrokErr -ErrorAction SilentlyContinue
$ngrokProc = Start-Process -FilePath "ngrok" -ArgumentList @("http", "$Port", "--log=stdout") `
    -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $ngrokLog -RedirectStandardError $ngrokErr
Start-Sleep -Seconds 2

if ($ngrokProc.HasExited) {
    Write-Host "[!] ngrok exited immediately (exit $($ngrokProc.ExitCode))." -ForegroundColor Red
    if (Test-Path $ngrokLog) {
        Write-Host "--- ngrok stdout ---" -ForegroundColor Yellow
        Get-Content $ngrokLog
    }
    if (Test-Path $ngrokErr) {
        Write-Host "--- ngrok stderr ---" -ForegroundColor Yellow
        Get-Content $ngrokErr
    }
    Write-Host "Common causes:" -ForegroundColor Yellow
    Write-Host "  - Another ngrok agent already running (free plan = 1 agent only)" -ForegroundColor Yellow
    Write-Host "  - Missing authtoken: ngrok config add-authtoken <TOKEN>" -ForegroundColor Yellow
    Stop-Process -Id $mcpProc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

# 5. Read public URL
# Probe each ngrok agent's local API (4040, 4041, ...) and pick the tunnel
# whose config.addr points at OUR $Port. Without this filter, when another
# ngrok agent (e.g. for mcp-gitlab) is already running, we'd grab its URL
# and claude.ai would land on the wrong server's OAuth form.
Write-Host "[4/5] Reading public URL for port $Port (probing ngrok APIs 4040-4044)..." -ForegroundColor Cyan
$publicUrl = $null
$portPattern = ":$Port(`$|/|`?)"
# Total budget ~24s: 12 outer attempts × (5 ports × 0.4s timeout) + 1s sleep
for ($i = 0; $i -lt 12; $i++) {
    foreach ($apiPort in 4040..4044) {
        try {
            $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:$apiPort/api/tunnels" -TimeoutSec 1 -ErrorAction Stop
            $https = $tunnels.tunnels | Where-Object {
                $_.proto -eq "https" -and $_.config.addr -match $portPattern
            } | Select-Object -First 1
            if ($https) { $publicUrl = $https.public_url; break }
        } catch {}
    }
    if ($publicUrl) { break }
    if ($ngrokProc.HasExited) {
        Write-Host "[!] ngrok died while we were waiting for its tunnel." -ForegroundColor Red
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $publicUrl) {
    Write-Host "[!] Could not find an ngrok tunnel for port $Port." -ForegroundColor Red
    if (Test-Path $ngrokLog) {
        Write-Host "--- ngrok stdout (last 20 lines) ---" -ForegroundColor Yellow
        Get-Content $ngrokLog -Tail 20
    }
    if (Test-Path $ngrokErr) {
        Write-Host "--- ngrok stderr (last 20 lines) ---" -ForegroundColor Yellow
        Get-Content $ngrokErr -Tail 20
    }
    Write-Host "If another ngrok agent is already running (e.g. for mcp-gitlab)," -ForegroundColor Yellow
    Write-Host "the free plan only allows one agent. Stop that one first, or use" -ForegroundColor Yellow
    Write-Host "a paid plan with multiple tunnels under one agent (ngrok.yml)." -ForegroundColor Yellow
    Stop-Process -Id $mcpProc.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $ngrokProc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
$mcpUrl = "$publicUrl/kanboard-mcp"

# 6. Save state
$state = [PSCustomObject]@{
    public_url = $mcpUrl
    insecure   = [bool]$Insecure
    mcp_pid    = $mcpProc.Id
    ngrok_pid  = $ngrokProc.Id
    started_at = (Get-Date).ToString("o")
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
Write-Host ""
if (-not $Insecure) {
    Write-Host "  Auth:        OAuth + passphrase" -ForegroundColor Green
    Write-Host "  On connect:  claude.ai will pop a browser window."
    Write-Host "               Type your MCP_PASSPHRASE there, click Authorize."
} else {
    Write-Host "  Auth:        NONE (insecure mode)" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "MCP PID:    $($mcpProc.Id)"
Write-Host "ngrok PID:  $($ngrokProc.Id)"
Write-Host ""
Write-Host "To stop:    .\scripts\stop-web.ps1"
Write-Host "State file: $statePath (gitignored)"
Write-Host ""
