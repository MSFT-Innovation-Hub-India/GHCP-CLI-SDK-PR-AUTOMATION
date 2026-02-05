#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start both MCP servers for the Fleet Compliance Agent Demo

.DESCRIPTION
    Starts both MCP servers (Change Management and Security) in background jobs.
    Use stop-mcp-servers.ps1 to stop them.

.EXAMPLE
    .\scripts\start-mcp-servers.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Starting MCP Servers                        " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Get project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Start Change Management MCP Server
Write-Host "Starting Change Management MCP Server on port 4101..." -ForegroundColor Yellow
$changeMgmtJob = Start-Job -Name "MCP-ChangeMgmt" -ScriptBlock {
    param($root)
    Set-Location "$root\mcp\change_mgmt"
    & ".venv\Scripts\uvicorn.exe" server:app --host 0.0.0.0 --port 4101
} -ArgumentList $ProjectRoot

# Start Security MCP Server
Write-Host "Starting Security MCP Server on port 4102..." -ForegroundColor Yellow
$securityJob = Start-Job -Name "MCP-Security" -ScriptBlock {
    param($root)
    Set-Location "$root\mcp\security"
    & ".venv\Scripts\uvicorn.exe" server:app --host 0.0.0.0 --port 4102
} -ArgumentList $ProjectRoot

# Wait a moment for servers to start
Start-Sleep -Seconds 3

# Check if servers are running
Write-Host ""
Write-Host "Checking server health..." -ForegroundColor Yellow

$changeMgmtStatus = $changeMgmtJob.State
$securityStatus = $securityJob.State

Write-Host "  Change Management MCP: $changeMgmtStatus" -ForegroundColor $(if($changeMgmtStatus -eq "Running"){"Green"}else{"Red"})
Write-Host "  Security MCP: $securityStatus" -ForegroundColor $(if($securityStatus -eq "Running"){"Green"}else{"Red"})

# Test endpoints
try {
    $null = Invoke-WebRequest -Uri "http://localhost:4101/healthz" -TimeoutSec 5
    Write-Host "  ✓ Change Management MCP healthz OK" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Change Management MCP not responding" -ForegroundColor Red
}

try {
    $null = Invoke-WebRequest -Uri "http://localhost:4102/healthz" -TimeoutSec 5
    Write-Host "  ✓ Security MCP healthz OK" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Security MCP not responding" -ForegroundColor Red
}

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  MCP Servers Started" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Endpoints:" -ForegroundColor White
Write-Host "  Change Management: http://localhost:4101" -ForegroundColor Gray
Write-Host "    - POST /approval"
Write-Host "    - POST /risk-assessment"
Write-Host "    - GET  /healthz"
Write-Host ""
Write-Host "  Security Scan:     http://localhost:4102" -ForegroundColor Gray
Write-Host "    - POST /scan"
Write-Host "    - POST /scan-detailed"
Write-Host "    - GET  /vulnerability/{cve_id}"
Write-Host "    - GET  /healthz"
Write-Host ""
Write-Host "To view logs: Get-Job | Receive-Job" -ForegroundColor Yellow
Write-Host "To stop servers: .\scripts\stop-mcp-servers.ps1" -ForegroundColor Yellow
Write-Host ""
