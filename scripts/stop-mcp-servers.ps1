#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Stop MCP servers started by start-mcp-servers.ps1

.EXAMPLE
    .\scripts\stop-mcp-servers.ps1
#>

Write-Host "Stopping MCP Servers..." -ForegroundColor Yellow

# Stop background jobs
Get-Job -Name "MCP-*" | Stop-Job
Get-Job -Name "MCP-*" | Remove-Job

Write-Host "✓ MCP Servers stopped" -ForegroundColor Green
