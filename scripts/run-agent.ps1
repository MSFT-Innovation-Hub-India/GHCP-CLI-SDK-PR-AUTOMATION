#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run the Fleet Compliance Agent

.DESCRIPTION
    Runs the fleet compliance agent to detect drift and open PRs.
    Make sure MCP servers are running first: .\scripts\start-mcp-servers.ps1

.PARAMETER DryRun
    If specified, detect drift but don't open PRs

.PARAMETER NoPytest
    If specified, skip running pytest before opening PRs

.PARAMETER UseCopilot
    If specified, enable Copilot SDK for PR descriptions

.EXAMPLE
    .\scripts\run-agent.ps1
    .\scripts\run-agent.ps1 -DryRun
    .\scripts\run-agent.ps1 -UseCopilot
#>

param(
    [switch]$DryRun,
    [switch]$NoPytest,
    [switch]$UseCopilot
)

$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Fleet Compliance Agent                      " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Get project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Check MCP servers are running
Write-Host "Checking MCP servers..." -ForegroundColor Yellow
try {
    $null = Invoke-WebRequest -Uri "http://localhost:4101/healthz" -TimeoutSec 3
    Write-Host "  ✓ Change Management MCP OK" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Change Management MCP not running!" -ForegroundColor Red
    Write-Host "    Run: .\scripts\start-mcp-servers.ps1" -ForegroundColor Yellow
    exit 1
}

try {
    $null = Invoke-WebRequest -Uri "http://localhost:4102/healthz" -TimeoutSec 3
    Write-Host "  ✓ Security MCP OK" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Security MCP not running!" -ForegroundColor Red
    Write-Host "    Run: .\scripts\start-mcp-servers.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Set environment variables based on parameters
$env:DRY_RUN = if($DryRun) { "true" } else { "false" }
$env:PYTEST_ENABLED = if($NoPytest) { "false" } else { "true" }
$env:USE_COPILOT_SDK = if($UseCopilot) { "true" } else { "false" }

if ($DryRun) {
    Write-Host "Mode: DRY RUN (no PRs will be opened)" -ForegroundColor Yellow
}
if ($NoPytest) {
    Write-Host "Mode: Skipping pytest" -ForegroundColor Yellow
}
if ($UseCopilot) {
    Write-Host "Mode: Copilot SDK enabled" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Running fleet compliance agent..." -ForegroundColor Yellow
Write-Host ""

# Run the agent
Set-Location "$ProjectRoot\agent"
& ".venv\Scripts\python.exe" -m fleet_agent.run

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Agent run complete!" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Check your GitHub repos for new PRs." -ForegroundColor White
Write-Host "Workspaces created in: agent\workspaces\" -ForegroundColor Gray
Write-Host ""

Set-Location $ProjectRoot
