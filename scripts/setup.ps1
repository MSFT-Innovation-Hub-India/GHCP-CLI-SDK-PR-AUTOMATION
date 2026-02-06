#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Setup script for the Fleet Compliance Agent Demo

.DESCRIPTION
    This script sets up the demo environment by:
    1. Creating Python virtual environments
    2. Installing dependencies
    3. Copying .env.example to .env
    4. Validating prerequisites

.EXAMPLE
    .\scripts\setup.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Fleet Compliance Agent Demo - Setup Script  " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

# -----------------------------------------------------------------------------
# Prerequisites Check
# -----------------------------------------------------------------------------
Write-Host "[1/5] Checking prerequisites..." -ForegroundColor Yellow

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found. Please install Python 3.11+" -ForegroundColor Red
    exit 1
}

# Check Git
try {
    $gitVersion = git --version 2>&1
    Write-Host "  ✓ Git: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Git not found. Please install Git." -ForegroundColor Red
    exit 1
}

# Check GitHub CLI
try {
    $ghVersion = gh --version 2>&1 | Select-Object -First 1
    Write-Host "  ✓ GitHub CLI: $ghVersion" -ForegroundColor Green
    
    # Check auth status
    $authStatus = gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ⚠ GitHub CLI not authenticated. Run: gh auth login" -ForegroundColor Yellow
    } else {
        Write-Host "  ✓ GitHub CLI authenticated" -ForegroundColor Green
    }
} catch {
    Write-Host "  ⚠ GitHub CLI not found. Install with: winget install GitHub.cli" -ForegroundColor Yellow
}

Write-Host ""

# -----------------------------------------------------------------------------
# Setup MCP Servers
# -----------------------------------------------------------------------------
Write-Host "[2/5] Setting up MCP servers..." -ForegroundColor Yellow

# Change Management MCP
Write-Host "  Setting up mcp/change_mgmt..."
Set-Location "$ProjectRoot\mcp\change_mgmt"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".venv\Scripts\pip.exe" install -r requirements.txt -q
Write-Host "  ✓ mcp/change_mgmt ready" -ForegroundColor Green

# Security MCP
Write-Host "  Setting up mcp/security..."
Set-Location "$ProjectRoot\mcp\security"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".venv\Scripts\pip.exe" install -r requirements.txt -q
Write-Host "  ✓ mcp/security ready" -ForegroundColor Green

Write-Host ""

# -----------------------------------------------------------------------------
# Setup Agent
# -----------------------------------------------------------------------------
Write-Host "[3/5] Setting up Fleet Agent..." -ForegroundColor Yellow
Set-Location "$ProjectRoot\agent"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".venv\Scripts\pip.exe" install -r requirements.txt -q
Write-Host "  ✓ agent ready" -ForegroundColor Green

# Copy .env.example to .env if not exists
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  ✓ Created .env from .env.example" -ForegroundColor Green
} else {
    Write-Host "  ✓ .env already exists" -ForegroundColor Green
}

Write-Host ""

# -----------------------------------------------------------------------------
# Setup Sample Repos (Local Testing)
# -----------------------------------------------------------------------------
Write-Host "[4/5] Setting up sample repos for local testing..." -ForegroundColor Yellow
$sampleRepos = @("contoso-catalog-api", "contoso-orders-api", "contoso-payments-api")

foreach ($repo in $sampleRepos) {
    $repoPath = "$ProjectRoot\sample-repos\$repo"
    Set-Location $repoPath
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }
    & ".venv\Scripts\pip.exe" install -r requirements.txt -q
    Write-Host "  ✓ $repo dependencies installed" -ForegroundColor Green
}

Write-Host ""

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
Write-Host "[5/5] Setup complete!" -ForegroundColor Yellow
Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Next Steps:" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Create GitHub repos and push sample-repos:" -ForegroundColor White
Write-Host "   - contoso-catalog-api"
Write-Host "   - contoso-orders-api"  
Write-Host "   - contoso-payments-api"
Write-Host ""
Write-Host "2. Update agent/config/repos.json with your repo URLs" -ForegroundColor White
Write-Host ""
Write-Host "3. Deploy the Azure OpenAI vector store (requires Azure CLI auth):" -ForegroundColor White
Write-Host "   .\scripts\deploy-vector-store.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Start MCP servers (in separate terminals):" -ForegroundColor White
Write-Host "   Terminal 1: .\scripts\start-mcp-servers.ps1" -ForegroundColor Gray
Write-Host "   Or manually:"
Write-Host "     cd mcp\change_mgmt; .\.venv\Scripts\uvicorn server:app --port 4101"
Write-Host "     cd mcp\security; .\.venv\Scripts\uvicorn server:app --port 4102"
Write-Host ""
Write-Host "5. Run the fleet agent:" -ForegroundColor White
Write-Host "   .\scripts\run-agent.ps1" -ForegroundColor Gray
Write-Host "   Or manually:"
Write-Host "     cd agent; .\.venv\Scripts\python -m fleet_agent.run"
Write-Host ""

Set-Location $ProjectRoot
