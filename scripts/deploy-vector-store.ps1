#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy Azure OpenAI Vector Store for Fleet Compliance Agent

.DESCRIPTION
    This script creates a vector store in Azure OpenAI and uploads all 
    markdown files from the knowledge/ folder. Uses Azure DefaultAzureCredential
    for authentication (Azure CLI, Managed Identity, etc.)

.EXAMPLE
    .\scripts\deploy-vector-store.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Deploy Azure OpenAI Vector Store            " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Run the Python deployment script using the agent's venv
$AgentVenv = Join-Path $ProjectRoot "agent\.venv\Scripts\python.exe"
$DeployScript = Join-Path $ScriptDir "deploy-vector-store.py"

if (-not (Test-Path $AgentVenv)) {
    Write-Host "Error: Agent virtual environment not found." -ForegroundColor Red
    Write-Host "Run .\scripts\setup.ps1 first." -ForegroundColor Yellow
    exit 1
}

Write-Host "Using Python: $AgentVenv" -ForegroundColor Gray
Write-Host ""

& $AgentVenv $DeployScript

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Deployment failed!" -ForegroundColor Red
    exit 1
}
