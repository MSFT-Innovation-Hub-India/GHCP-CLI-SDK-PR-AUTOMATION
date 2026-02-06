"""
MCP (Model Context Protocol) Client Module
==========================================
HTTP clients for communicating with MCP servers in the Fleet Compliance Agent.

This module provides simple HTTP wrappers for the two MCP servers:

1. **Change Management Server** (default port 4101)
   - Evaluates required approvals based on CM-7 policy
   - Determines risk level and SLA for changes

2. **Security Scan Server** (default port 4102)
   - Scans dependencies for CVE vulnerabilities
   - Implements SEC-2.4 policy for vulnerability response

Environment Variables:
    CHANGE_MGMT_URL: Base URL for Change Management MCP (default: http://localhost:4101)
    SECURITY_URL: Base URL for Security MCP (default: http://localhost:4102)

Usage:
    from fleet_agent.mcp_clients import approval, security_scan
    
    # Get required approvals for a change
    result = approval("contoso-payments-api", ["app/main.py"])
    print(result["required_approvals"])  # ["SRE-Prod"]
    
    # Scan dependencies for vulnerabilities
    result = security_scan("requests==2.25.0\\nflask==2.3.0")
    print(result["findings"])  # List of CVEs

Note:
    MCP servers must be running before calling these functions.
    Start them with: scripts/start-mcp-servers.ps1
"""

from __future__ import annotations
import os
import requests

# MCP server endpoints - read base URL from environment, append endpoint path
# Env vars contain base URL (e.g., http://localhost:4101), we append the path
_change_mgmt_base = os.getenv("CHANGE_MGMT_URL", "http://localhost:4101").rstrip("/")
_security_base = os.getenv("SECURITY_URL", "http://localhost:4102").rstrip("/")

CHANGE_MGMT_URL = f"{_change_mgmt_base}/approval"
SECURITY_URL = f"{_security_base}/scan"


def approval(service: str, touched_paths: list[str]) -> dict:
    """
    Request approval requirements from the Change Management MCP server.
    
    Evaluates which approvals are required based on:
    - Service criticality (high-impact services need SRE approval)
    - Files modified (security-sensitive files need Security team)
    - Infrastructure changes (need SRE review)
    - Database changes (need DBA review)
    
    Args:
        service: Service name (e.g., "contoso-payments-api")
        touched_paths: List of modified file paths
    
    Returns:
        dict with keys:
            - required_approvals: List of required approver roles
            - risk_level: "low", "medium", "high", or "critical"
            - rationale: Explanation of approval requirements
            - auto_merge_allowed: Whether auto-merge is permitted
            - sla_hours: Review SLA in hours
    
    Raises:
        requests.RequestException: If MCP server is unavailable
    """
    r = requests.post(CHANGE_MGMT_URL, json={"service": service, "touched_paths": touched_paths}, timeout=20)
    r.raise_for_status()
    return r.json()

def security_scan(requirements_text: str) -> dict:
    """
    Scan dependencies for vulnerabilities via the Security MCP server.
    
    Parses requirements.txt format and checks each package against
    a vulnerability database (NVD/OSV/Snyk in production).
    
    Args:
        requirements_text: Contents of requirements.txt file
    
    Returns:
        dict with keys:
            - findings: List of vulnerability objects with CVE details
            - summary: Counts by severity (critical, high, medium, low)
            - policy_compliant: True if no critical/high vulnerabilities
            - recommendations: List of remediation suggestions
    
    Raises:
        requests.RequestException: If MCP server is unavailable
    """
    r = requests.post(SECURITY_URL, json={"requirements": requirements_text}, timeout=20)
    r.raise_for_status()
    return r.json()
