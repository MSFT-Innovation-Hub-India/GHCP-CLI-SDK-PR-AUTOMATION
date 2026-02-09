"""
MCP (Model Context Protocol) Client Module
==========================================
Connects to MCP servers using the proper MCP protocol over SSE transport.

This module provides thin wrappers that call MCP tools on two remote servers:

1. **Change Management Server** (default port 4101)
   - evaluate_approval: required approvals based on CM-7 policy
   - assess_risk: risk level and SLA for changes

2. **Security Scan Server** (default port 4102)
   - scan_dependencies: CVE vulnerability scan
   - scan_detailed: detailed scan with filters
   - get_vulnerability: single CVE lookup

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
    Start them with: python mcp/change_mgmt/server.py  &  python mcp/security/server.py
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

# ---------------------------------------------------------------------------
# Server base URLs – the SSE endpoint is at  <base>/sse
# ---------------------------------------------------------------------------
_change_mgmt_base = os.getenv("CHANGE_MGMT_URL", "http://localhost:4101").rstrip("/")
_security_base = os.getenv("SECURITY_URL", "http://localhost:4102").rstrip("/")


# ---------------------------------------------------------------------------
# Low-level helper: call a single MCP tool on a remote server via SSE
# ---------------------------------------------------------------------------
async def _call_tool(base_url: str, tool_name: str, arguments: dict[str, Any]) -> dict:
    """
    Open an SSE connection to *base_url*, call *tool_name* with *arguments*,
    and return the parsed JSON result.
    """
    sse_url = f"{base_url}/sse"
    async with sse_client(sse_url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

            # result.content is a list of TextContent / ImageContent objects.
            # Our tools always return a single JSON text blob.
            text = result.content[0].text
            return json.loads(text)


def _call_tool_sync(base_url: str, tool_name: str, arguments: dict[str, Any]) -> dict:
    """
    Synchronous wrapper around ``_call_tool``.

    Because the agent's tool handlers run synchronously inside an outer
    async event loop, we cannot simply do ``asyncio.run()``.  Instead we
    spin up a *new* event loop on a worker thread – the same pattern the
    codebase already uses in ``_fix_code_with_sdk``.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, _call_tool(base_url, tool_name, arguments))
        return future.result(timeout=30.0)


# ---------------------------------------------------------------------------
# Public helpers – drop-in replacements for the old HTTP wrappers
# ---------------------------------------------------------------------------

def approval(service: str, touched_paths: list[str]) -> dict:
    """
    Request approval requirements from the Change Management MCP server.

    Evaluates which approvals are required based on:
    - Service criticality (high-impact services need SRE approval)
    - Files modified (security-sensitive files need Security team)
    - Infrastructure changes (need SRE review)
    - Database changes (need DBA review)

    Args:
        service: Service name (e.g. "contoso-payments-api")
        touched_paths: List of modified file paths

    Returns:
        dict with keys:
            - required_approvals: List of required approver roles
            - risk_level: "low", "medium", "high", or "critical"
            - rationale: Explanation of approval requirements
            - auto_merge_allowed: Whether auto-merge is permitted
            - sla_hours: Review SLA in hours
    """
    return _call_tool_sync(
        _change_mgmt_base,
        "evaluate_approval",
        {"service": service, "touched_paths": touched_paths},
    )


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
    """
    return _call_tool_sync(
        _security_base,
        "scan_dependencies",
        {"requirements": requirements_text},
    )
