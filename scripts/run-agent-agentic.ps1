#!/usr/bin/env pwsh
# Run the Fleet Compliance Agent in Agentic Mode
# Uses GitHub Copilot CLI SDK for autonomous tool calling

$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot\..\agent"

try {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Fleet Compliance Agent (Agentic Mode)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "This runs the agent using the GitHub Copilot CLI SDK."
    Write-Host "The SDK acts as the agent's 'brain' - deciding what tools"
    Write-Host "to call and when based on the system instructions."
    Write-Host ""
    
    # Check virtual environment
    if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
        Write-Host "Error: Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
        exit 1
    }
    
    # Check MCP servers
    Write-Host "Checking MCP servers..." -ForegroundColor Yellow
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:4101/docs" -TimeoutSec 2 -ErrorAction Stop
        Write-Host "  Change Management MCP (4101): OK" -ForegroundColor Green
    } catch {
        Write-Host "  Change Management MCP (4101): NOT RUNNING" -ForegroundColor Red
        Write-Host "  Run: .\scripts\start-mcp-servers.ps1" -ForegroundColor Yellow
        exit 1
    }
    
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:4102/docs" -TimeoutSec 2 -ErrorAction Stop
        Write-Host "  Security MCP (4102): OK" -ForegroundColor Green
    } catch {
        Write-Host "  Security MCP (4102): NOT RUNNING" -ForegroundColor Red
        Write-Host "  Run: .\scripts\start-mcp-servers.ps1" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host ""
    Write-Host "Starting agent..." -ForegroundColor Cyan
    Write-Host ""
    
    # Clear workspaces
    if (Test-Path ".\workspaces") {
        Remove-Item -Recurse -Force ".\workspaces\*" -ErrorAction SilentlyContinue
    }
    
    # Run the agentic loop
    .\.venv\Scripts\python.exe -m fleet_agent.agent_loop
    
} finally {
    Pop-Location
}
