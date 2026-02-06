<#
.SYNOPSIS
    Starts the Fleet Compliance Agent UI (Backend + Frontend)
.DESCRIPTION
    This script starts both the FastAPI backend and React frontend for the
    Fleet Compliance Agent UI. It reuses the existing agent code without modification.
.NOTES
    Prerequisites:
    - Python 3.10+ with venv in agent/.venv
    - Node.js 18+ with npm
    - MCP servers running (run scripts/start-mcp-servers.ps1 first)
#>

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Fleet Compliance Agent UI Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check MCP servers
Write-Host "Checking MCP servers..." -ForegroundColor Yellow
$securityPort = 4102
$changeMgmtPort = 4101

$securityRunning = (Test-NetConnection -ComputerName localhost -Port $securityPort -WarningAction SilentlyContinue).TcpTestSucceeded
$changeMgmtRunning = (Test-NetConnection -ComputerName localhost -Port $changeMgmtPort -WarningAction SilentlyContinue).TcpTestSucceeded

if (-not $securityRunning -or -not $changeMgmtRunning) {
    Write-Host "WARNING: MCP servers not running!" -ForegroundColor Yellow
    Write-Host "Run: .\scripts\start-mcp-servers.ps1" -ForegroundColor Yellow
    Write-Host ""
}

# Start Backend
if (-not $FrontendOnly) {
    Write-Host "Starting FastAPI backend..." -ForegroundColor Green
    
    $backendDir = Join-Path $root "ui\backend"
    $agentVenv = Join-Path $root "agent\.venv"
    
    # Install backend dependencies if needed
    $pip = Join-Path $agentVenv "Scripts\pip.exe"
    & $pip install -q -r (Join-Path $backendDir "requirements.txt")
    
    # Start backend in new terminal
    $python = Join-Path $agentVenv "Scripts\python.exe"
    $backendMain = Join-Path $backendDir "main.py"
    
    Start-Process -FilePath "powershell" -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$backendDir'; & '$python' -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
    ) -WindowStyle Normal
    
    Write-Host "Backend starting at http://localhost:8000" -ForegroundColor Cyan
    Start-Sleep -Seconds 2
}

# Start Frontend
if (-not $BackendOnly) {
    Write-Host "Starting React frontend..." -ForegroundColor Green
    
    $frontendDir = Join-Path $root "ui\frontend"
    
    # Install dependencies if node_modules doesn't exist
    if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
        Push-Location $frontendDir
        npm install
        Pop-Location
    }
    
    # Start frontend in new terminal
    Start-Process -FilePath "powershell" -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$frontendDir'; npm run dev"
    ) -WindowStyle Normal
    
    Write-Host "Frontend starting at http://localhost:3000" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  UI is starting!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "Frontend: http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C in each terminal to stop" -ForegroundColor Yellow
