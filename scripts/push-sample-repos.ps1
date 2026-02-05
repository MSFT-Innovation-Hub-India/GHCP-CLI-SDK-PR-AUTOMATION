#!/usr/bin/env pwsh
param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubOrg,
    
    [switch]$CreateRepos
)

$ErrorActionPreference = "Stop"

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  Push Sample Repos to GitHub         " -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "GitHub Org/User: $GitHubOrg" -ForegroundColor White
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

$repos = @(
    "contoso-catalog-api",
    "contoso-orders-api",
    "contoso-payments-api"
)

if ($CreateRepos) {
    Write-Host "Creating GitHub repos..." -ForegroundColor Yellow
    foreach ($repo in $repos) {
        Write-Host "  Creating $repo..."
        try {
            gh repo create "$GitHubOrg/$repo" --private --description "Fleet Compliance Demo" --confirm 2>&1 | Out-Null
            Write-Host "    Created $repo" -ForegroundColor Green
        } catch {
            Write-Host "    $repo may already exist" -ForegroundColor Yellow
        }
    }
    Write-Host ""
}

foreach ($repo in $repos) {
    Write-Host "Processing $repo..." -ForegroundColor Yellow
    
    $repoPath = "$ProjectRoot\sample-repos\$repo"
    Set-Location $repoPath
    
    if (-not (Test-Path ".git")) {
        Write-Host "  Initializing git..."
        git init -q
        git add .
        git commit -m "Initial commit" -q
    }
    
    $remoteUrl = "https://github.com/$GitHubOrg/$repo.git"
    
    $existingRemote = git remote 2>&1
    if ($existingRemote -contains "origin") {
        git remote remove origin
    }
    git remote add origin $remoteUrl
    
    $currentBranch = git branch --show-current
    if ($currentBranch -ne "main") {
        git branch -M main
    }
    
    Write-Host "  Pushing to $remoteUrl..."
    try {
        git push -u origin main --force 2>&1 | Out-Null
        Write-Host "  Pushed $repo" -ForegroundColor Green
    } catch {
        Write-Host "  Failed to push $repo" -ForegroundColor Red
    }
    
    Write-Host ""
}

Write-Host "Updating agent/config/repos.json..." -ForegroundColor Yellow
$reposConfig = @{
    repos = @(
        "https://github.com/$GitHubOrg/contoso-orders-api.git",
        "https://github.com/$GitHubOrg/contoso-payments-api.git",
        "https://github.com/$GitHubOrg/contoso-catalog-api.git"
    )
}
$reposConfig | ConvertTo-Json | Set-Content "$ProjectRoot\agent\config\repos.json"
Write-Host "  Updated repos.json" -ForegroundColor Green

Write-Host ""
Write-Host "Done! Next steps:" -ForegroundColor Cyan
Write-Host "  1. Start MCP servers: .\scripts\start-mcp-servers.ps1"
Write-Host "  2. Run the agent: .\scripts\run-agent.ps1"
Write-Host ""

Set-Location $ProjectRoot
