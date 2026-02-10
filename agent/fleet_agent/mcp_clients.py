"""
MCP (Model Context Protocol) Client Module
==========================================
Connects to MCP servers using the proper MCP protocol over SSE transport.

Server URLs are resolved in priority order:
1. **mcp.json** — project-level MCP server manifest (standard convention)
2. **Environment variables** — CHANGE_MGMT_URL / SECURITY_URL overrides
3. **Defaults** — http://localhost:4101 / http://localhost:4102

This module provides thin wrappers that call MCP tools on two remote servers:

1. **Change Management Server** (default port 4101)
   - evaluate_approval: required approvals based on CM-7 policy
   - assess_risk: risk level and SLA for changes

2. **Security Scan Server** (default port 4102)
   - scan_dependencies: CVE vulnerability scan
   - scan_detailed: detailed scan with filters
   - get_vulnerability: single CVE lookup

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
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

# ---------------------------------------------------------------------------
# Server URL resolution: mcp.json → env vars → defaults
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "change_mgmt": "http://localhost:4101",
    "security": "http://localhost:4102",
}


def _load_mcp_config() -> dict[str, str]:
    """
    Load MCP server base URLs from the project-root ``mcp.json``.

    Returns a dict mapping server name → base URL (without /sse suffix).
    Falls back to empty dict if the file is missing or unparseable.
    """
    # Walk upward from this file to find mcp.json at the project root
    # mcp_clients.py  →  fleet_agent/  →  agent/  →  project root
    project_root = Path(__file__).resolve().parents[2]
    mcp_json = project_root / "mcp.json"

    if not mcp_json.exists():
        return {}

    try:
        config = json.loads(mcp_json.read_text(encoding="utf-8"))
        servers = config.get("mcpServers", {})
        urls: dict[str, str] = {}
        for name, spec in servers.items():
            url = spec.get("url", "")
            # Strip /sse suffix so callers can append it themselves
            urls[name] = url.removesuffix("/sse").rstrip("/")
        return urls
    except Exception as exc:
        print(f"[MCP] Warning: could not parse mcp.json: {exc}")
        return {}


def _resolve_url(server_name: str, env_var: str) -> str:
    """Resolve a server URL: mcp.json → env var → built-in default."""
    mcp_urls = _load_mcp_config()

    # 1. mcp.json
    if server_name in mcp_urls:
        return mcp_urls[server_name]

    # 2. Environment variable override
    env_val = os.getenv(env_var)
    if env_val:
        return env_val.rstrip("/")

    # 3. Hardcoded default
    return _DEFAULTS[server_name]


_change_mgmt_base = _resolve_url("change_mgmt", "CHANGE_MGMT_URL")
_security_base = _resolve_url("security", "SECURITY_URL")


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
