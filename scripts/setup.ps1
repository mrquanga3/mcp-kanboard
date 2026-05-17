<#
.SYNOPSIS
  One-time setup for mcp-kanboard on a fresh Windows machine.

.DESCRIPTION
  Idempotent. Re-running on a configured machine reports "already installed"
  for each step and only acts on what's missing. Installs:
    - Python 3.13 (via winget if missing)
    - uv (via winget or astral install script)
    - ngrok (via winget, only when -SkipNgrok is NOT set)
  Then runs `uv sync` to materialize the .venv and copies .env.example to
  .env if no .env exists yet.

.PARAMETER SkipNgrok
  Don't install or check ngrok. Use when you only need the stdio transport
  (Claude Code) and don't plan to expose the MCP to claude.ai web.

.PARAMETER NonInteractive
  Default-yes for install prompts; skip the ngrok authtoken prompt.

.EXAMPLE
  .\scripts\setup.ps1

.EXAMPLE
  .\scripts\setup.ps1 -SkipNgrok -NonInteractive
#>
[CmdletBinding()]
param(
    [switch]$SkipNgrok,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

function Test-Cmd { param([string]$Name) [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

function Refresh-Path {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = ($machine, $user, $env:Path) -join ";"
}

function Confirm {
    param([string]$Question, [string]$Default = "Y")
    if ($NonInteractive) { return $true }
    $ans = Read-Host "  $Question [$Default/n]"
    if (-not $ans) { $ans = $Default }
    return $ans -notmatch '^[nN]'
}

Write-Host "=== mcp-kanboard setup ===" -ForegroundColor Cyan
Write-Host "Repo: $repoRoot"
Write-Host ""

$hasWinget = Test-Cmd "winget"

# ----- 1. Python -----
Write-Host "[1/5] Python..." -ForegroundColor Cyan
$pyOk = $false
foreach ($cmd in @("python", "py")) {
    if (Test-Cmd $cmd) {
        $v = & $cmd --version 2>&1
        if ($v -match "Python 3\.(1[1-9]|[2-9]\d)") {
            Write-Host "  $v"
            $pyOk = $true
            break
        }
    }
}
if (-not $pyOk) {
    Write-Host "  Need Python 3.11+." -ForegroundColor Yellow
    if ($hasWinget -and (Confirm "Install Python 3.13 via winget?")) {
        winget install -e --id Python.Python.3.13 --silent --accept-source-agreements --accept-package-agreements
        Refresh-Path
    } else {
        Write-Host "  Install manually from https://www.python.org/downloads/, then re-run this script." -ForegroundColor Red
        exit 1
    }
}

# ----- 2. uv -----
Write-Host "[2/5] uv..." -ForegroundColor Cyan
if (Test-Cmd "uv") {
    Write-Host "  $(uv --version)"
} else {
    Write-Host "  uv not found."
    $installed = $false
    if ($hasWinget -and (Confirm "Install uv via winget?")) {
        try {
            winget install -e --id astral-sh.uv --silent --accept-source-agreements --accept-package-agreements
            Refresh-Path
            $installed = Test-Cmd "uv"
        } catch {
            Write-Host "  winget install failed: $_" -ForegroundColor Yellow
        }
    }
    if (-not $installed) {
        if (Confirm "Install uv via the official PowerShell installer (irm | iex)?") {
            powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
            Refresh-Path
            $installed = Test-Cmd "uv"
        }
    }
    if (-not $installed) {
        Write-Host "  uv install failed. See https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Installed: $(uv --version)"
}

# ----- 3. ngrok -----
if (-not $SkipNgrok) {
    Write-Host "[3/5] ngrok..." -ForegroundColor Cyan
    if (Test-Cmd "ngrok") {
        $first = (ngrok version) -split [Environment]::NewLine | Select-Object -First 1
        Write-Host "  $first"
    } else {
        Write-Host "  ngrok not found."
        if ($hasWinget -and (Confirm "Install ngrok via winget?")) {
            winget install -e --id Ngrok.Ngrok --silent --accept-source-agreements --accept-package-agreements
            Refresh-Path
        }
        if (-not (Test-Cmd "ngrok")) {
            Write-Host "  Install manually from https://ngrok.com/download, then re-run." -ForegroundColor Red
            exit 1
        }
    }

    $ngrokYml = Join-Path $env:LOCALAPPDATA "ngrok\ngrok.yml"
    $tokenSet = $false
    if (Test-Path $ngrokYml) {
        $tokenSet = (Select-String -Path $ngrokYml -Pattern "^\s*authtoken:" -Quiet)
    }
    if ($tokenSet) {
        Write-Host "  authtoken configured"
    } else {
        Write-Host "  authtoken not configured. Get yours at https://dashboard.ngrok.com/get-started/your-authtoken" -ForegroundColor Yellow
        if (-not $NonInteractive) {
            $token = Read-Host "  Paste ngrok authtoken (or Enter to skip)"
            if ($token) {
                ngrok config add-authtoken $token
                Write-Host "  Saved."
            } else {
                Write-Host "  Skipped. Run 'ngrok config add-authtoken <TOKEN>' before start-web.ps1." -ForegroundColor Yellow
            }
        }
    }
} else {
    Write-Host "[3/5] Skipping ngrok (-SkipNgrok)" -ForegroundColor Cyan
}

# ----- 4. uv sync -----
Write-Host "[4/5] Installing Python dependencies (uv sync)..." -ForegroundColor Cyan
Push-Location $repoRoot
try {
    uv sync
} finally {
    Pop-Location
}

# ----- 5. .env -----
Write-Host "[5/5] .env..." -ForegroundColor Cyan
$envPath = Join-Path $repoRoot ".env"
$envExample = Join-Path $repoRoot ".env.example"
if (-not (Test-Path $envPath)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envPath
        Write-Host "  Created .env from .env.example"
    } else {
        Write-Host "  WARNING: .env.example missing in repo." -ForegroundColor Yellow
    }
} else {
    Write-Host "  .env already exists"
}

$envContent = if (Test-Path $envPath) { Get-Content $envPath -Raw } else { "" }
$needed = @()
$placeholders = "(?m)^(KANBOARD_URL|KANBOARD_API_TOKEN|MCP_PASSPHRASE)=(PASTE_TOKEN_HERE|change-me-pick-a-real-passphrase|type_anything_secret_here|any_string_youll_remember)"
foreach ($k in @("KANBOARD_URL", "KANBOARD_API_TOKEN", "MCP_PASSPHRASE")) {
    if ($envContent -notmatch "(?m)^$k=.+") { $needed += "$k (missing)" }
}
if ($envContent -match $placeholders) {
    $matches = [regex]::Matches($envContent, $placeholders)
    foreach ($m in $matches) { $needed += "$($m.Groups[1].Value) (placeholder)" }
}
if ($needed) {
    Write-Host ""
    Write-Host "  .env needs real values for:" -ForegroundColor Yellow
    foreach ($k in ($needed | Select-Object -Unique)) { Write-Host "    - $k" }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next:"
Write-Host "  1. Edit .env, fill: KANBOARD_URL, KANBOARD_API_TOKEN, MCP_PASSPHRASE"
Write-Host "  2. Verify Kanboard connectivity:    uv run mcp-kanboard-smoke"
if (-not $SkipNgrok) {
    Write-Host "  3. Start for claude.ai web:         .\scripts\start-web.ps1"
}
Write-Host "  4. Register with Claude Code (CLI): see README -> 'Claude Code integration'"
Write-Host ""
