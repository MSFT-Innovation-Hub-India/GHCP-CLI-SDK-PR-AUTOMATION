"""
Fleet Compliance Agent - Agentic Loop with Custom Tools
========================================================

This implements a TRUE agentic workflow where:
1. The GitHub Copilot SDK acts as the agent's "brain"
2. Custom tools are registered with the SDK
3. The SDK autonomously decides which tools to call
4. Tool results are returned to the SDK for reasoning
5. The cycle continues until the task is complete

Key SDK Components:
- Tool: Defines a callable tool (name, description, handler, parameters)
- ToolHandler: Function signature (ToolInvocation) -> ToolResult
- ToolInvocation: Contains tool_name, arguments
- ToolResult: Contains textResultForLlm for the response
"""

from __future__ import annotations
import asyncio
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from nanoid import generate

from copilot import CopilotClient
from copilot.types import Tool, ToolInvocation, ToolResult

# Import existing modules for actual functionality
from fleet_agent.rag import search as rag_search_impl
from fleet_agent.mcp_clients import approval as mcp_approval, security_scan as mcp_security_scan
from fleet_agent.patcher_fastapi import detect as detect_drift_impl, apply as apply_patches_impl
from fleet_agent.github_ops import (
    gh_auth_status, clone_repo, checkout_branch,
    commit_all, push_branch, open_pr
)


ROOT = Path(__file__).resolve().parents[1]  # agent/
WORKSPACES = ROOT / "workspaces"
WORKSPACES.mkdir(parents=True, exist_ok=True)

# File-based PR tracking (more reliable than module-level state)
PR_LOG_FILE = ROOT / "created_prs.json"

# File-based modified files tracking (SDK events don't expose tool results)
MODIFIED_FILES_LOG = ROOT / "modified_files.json"

# Global state for tracking workspaces across tool calls
_workspace_registry: dict[str, Path] = {}

# Global state for tracking created PRs (accessible by UI backend)
created_prs: list[dict] = []  # [{"repo_url": ..., "pr_url": ...}, ...]

def log_created_pr(repo_url: str, pr_url: str, title: str):
    """Log a created PR to file for the UI backend to read."""
    import json
    prs = []
    if PR_LOG_FILE.exists():
        try:
            prs = json.loads(PR_LOG_FILE.read_text())
        except:
            prs = []
    prs.append({"repo_url": repo_url, "pr_url": pr_url, "title": title})
    PR_LOG_FILE.write_text(json.dumps(prs))
    print(f"[PR_LOGGED] Wrote PR to {PR_LOG_FILE}: {pr_url}", flush=True)

def get_created_prs() -> list[dict]:
    """Read created PRs from file."""
    import json
    if PR_LOG_FILE.exists():
        try:
            return json.loads(PR_LOG_FILE.read_text())
        except:
            return []
    return []

def clear_created_prs():
    """Clear the PR log file."""
    if PR_LOG_FILE.exists():
        PR_LOG_FILE.unlink()


def log_modified_files(repo_url: str, files: list[str]):
    """Log modified files for the UI backend to read."""
    import json
    data = {}
    if MODIFIED_FILES_LOG.exists():
        try:
            data = json.loads(MODIFIED_FILES_LOG.read_text())
        except:
            data = {}
    data[repo_url] = files
    MODIFIED_FILES_LOG.write_text(json.dumps(data))
    print(f"[MODIFIED_FILES] Logged {len(files)} files for {repo_url}", flush=True)


def get_modified_files(repo_url: str = None) -> dict | list:
    """Get modified files from log. If repo_url provided, return list for that repo."""
    import json
    if not MODIFIED_FILES_LOG.exists():
        return [] if repo_url else {}
    try:
        data = json.loads(MODIFIED_FILES_LOG.read_text())
        if repo_url:
            return data.get(repo_url, [])
        return data
    except:
        return [] if repo_url else {}


def clear_modified_files():
    """Clear the modified files log."""
    if MODIFIED_FILES_LOG.exists():
        MODIFIED_FILES_LOG.unlink()
    if PR_LOG_FILE.exists():
        PR_LOG_FILE.unlink()


# =============================================================================
# System Prompt - Agent Instructions
# =============================================================================

SYSTEM_PROMPT = """You are the Fleet Compliance Agent. Your job is to enforce compliance policies across FastAPI microservices.

## Your Mission
Given repository URLs, you must:
1. Search the knowledge base for policy requirements
2. Clone and analyze each repository
3. Detect compliance drift (missing health endpoints, logging, tracing)
4. Scan for security vulnerabilities
5. Apply compliance patches
6. Run tests to validate changes
7. **If tests fail, debug and fix the code**
8. Create Pull Requests with evidence-backed descriptions

## Workflow
For EACH repository, follow this sequence:
1. rag_search - Get policy evidence about health endpoints, logging, security
2. clone_repository - Clone the repo
3. detect_compliance_drift - Check what's missing
4. security_scan - Check for CVEs
5. create_branch - Create feature branch
6. apply_compliance_patches - Fix compliance issues
7. get_required_approvals - Determine who must approve
8. run_tests - Validate the changes work
9. **IF TESTS FAIL**: Use read_file and fix_code tools to debug and fix
10. **Re-run tests** until they pass (max 3 attempts)
11. commit_changes - Commit the fixes
12. push_branch - Push to remote
13. create_pull_request - Open PR with detailed description

## Test Failure Handling (IMPORTANT!)
When run_tests returns passed=false:
1. Read the error output carefully
2. Use read_file to examine the failing file
3. Use fix_code with the error message to apply a fix
4. Run tests again
5. Repeat up to 3 times before giving up

Example fix workflow:
- run_tests → failed with "ImportError: cannot import name 'app' from 'main'"
- read_file("app/main.py") → see the actual code
- fix_code(file_path="tests/test_health.py", error_message="ImportError: ...") → fix the import
- run_tests → passed!

## Important Rules
- Process repositories ONE AT A TIME to completion
- Always search RAG FIRST to understand policy requirements
- **Never skip test failures - always attempt to fix them**
- Include policy evidence in PR descriptions
- Add approval labels based on MCP response
- Report progress after each major step

Begin by searching the knowledge base, then process each repository."""


# =============================================================================
# Tool Definitions - Custom Functions for the SDK
# =============================================================================

def _repo_name(url: str) -> str:
    """Extract repository name from URL."""
    return url.rstrip("/").split("/")[-1].removesuffix(".git")


def _get_args(invocation) -> dict:
    """Extract arguments from invocation - handles both dict and ToolInvocation."""
    if isinstance(invocation, dict):
        # SDK passes dict with {session_id, tool_call_id, tool_name, arguments}
        return invocation.get("arguments", {}) or {}
    elif hasattr(invocation, 'arguments'):
        # ToolInvocation object
        return invocation.arguments or {}
    else:
        return {}


def create_tools() -> list[Tool]:
    """Create all tools for the agent."""

    # --- RAG Search Tool ---
    def rag_search_handler(invocation) -> ToolResult:
        """Search knowledge base for policy documents."""
        args = _get_args(invocation)
        query = args.get("query", "compliance policies")
        k = args.get("k", 4)
        
        print(f"\n   [TOOL] rag_search executing: query='{query}', k={k}", flush=True)
        
        try:
            hits = rag_search_impl(query, k)
            results = [{"doc_id": h.doc_id, "score": h.score, "excerpt": h.excerpt[:200]} for h in hits]
            print(f"   [TOOL] rag_search found {len(results)} documents", flush=True)
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "count": len(results),
                "documents": results
            }, indent=2))
        except Exception as e:
            print(f"   [TOOL] rag_search ERROR: {e}", flush=True)
            return ToolResult(error=str(e))

    rag_search_tool = Tool(
        name="rag_search",
        description="Search the knowledge base for compliance policy documents. Use this FIRST to understand what policies apply.",
        handler=rag_search_handler,
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for policy documents (e.g., 'health endpoints kubernetes', 'structured logging', 'security vulnerabilities')"
                },
                "k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 4)",
                    "default": 4
                }
            },
            "required": ["query"]
        }
    )

    # --- Clone Repository Tool ---
    def clone_repository_handler(invocation) -> ToolResult:
        """Clone a GitHub repository."""
        args = _get_args(invocation)
        url = args.get("url", "")
        
        print(f"\n   [TOOL] clone_repository executing: url='{url}'", flush=True)
        
        if not url:
            return ToolResult(error="Missing required parameter: url")
        
        try:
            repo_name = _repo_name(url)
            ws = WORKSPACES / f"{repo_name}-{generate(size=6)}"
            print(f"   [TOOL] Cloning to {ws}...", flush=True)
            clone_repo(url, ws)
            _workspace_registry[url] = ws
            print(f"   [TOOL] Clone successful", flush=True)
            
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "repo_name": repo_name,
                "workspace": str(ws),
                "message": f"Cloned {repo_name} to {ws}"
            }))
        except Exception as e:
            print(f"   [TOOL] clone ERROR: {e}", flush=True)
            return ToolResult(error=str(e))

    clone_tool = Tool(
        name="clone_repository",
        description="Clone a GitHub repository to local workspace for analysis.",
        handler=clone_repository_handler,
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "GitHub repository URL (e.g., https://github.com/org/repo)"
                }
            },
            "required": ["url"]
        }
    )

    # --- Detect Compliance Drift Tool ---
    def detect_drift_handler(invocation) -> ToolResult:
        """Detect missing compliance features."""
        args = _get_args(invocation)
        repo_url = args.get("repo_url", "")
        
        ws = _workspace_registry.get(repo_url)
        if not ws:
            return ToolResult(error="Repository not cloned. Call clone_repository first.")
        
        try:
            drift = detect_drift_impl(ws)
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "applicable": drift.applicable,
                "missing_healthz": drift.missing_healthz,
                "missing_readyz": drift.missing_readyz,
                "missing_structlog": drift.missing_structlog,
                "missing_middleware": drift.missing_middleware,
                "has_drift": drift.missing_healthz or drift.missing_readyz or drift.missing_structlog or drift.missing_middleware,
                "summary": "Compliance drift detected" if (drift.missing_healthz or drift.missing_readyz or drift.missing_structlog or drift.missing_middleware) else "No drift detected"
            }, indent=2))
        except Exception as e:
            return ToolResult(error=str(e))

    detect_drift_tool = Tool(
        name="detect_compliance_drift",
        description="Analyze a cloned repository for compliance drift (missing health endpoints, structured logging, middleware).",
        handler=detect_drift_handler,
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL (must have been cloned first)"
                }
            },
            "required": ["repo_url"]
        }
    )

    # --- Security Scan Tool (MCP) ---
    def security_scan_handler(invocation) -> ToolResult:
        """Scan for security vulnerabilities."""
        args = _get_args(invocation)
        repo_url = args.get("repo_url", "")
        
        ws = _workspace_registry.get(repo_url)
        if not ws:
            return ToolResult(error="Repository not cloned. Call clone_repository first.")
        
        try:
            req_path = ws / "requirements.txt"
            req_text = req_path.read_text(encoding="utf-8") if req_path.exists() else ""
            result = mcp_security_scan(req_text)
            findings = result.get("findings", [])
            
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "vulnerabilities_found": len(findings),
                "findings": findings,
                "summary": f"Found {len(findings)} vulnerabilities" if findings else "No vulnerabilities found"
            }, indent=2))
        except Exception as e:
            return ToolResult(error=str(e))

    security_scan_tool = Tool(
        name="security_scan",
        description="Scan repository dependencies for CVE vulnerabilities using the Security MCP server.",
        handler=security_scan_handler,
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL (must have been cloned first)"
                }
            },
            "required": ["repo_url"]
        }
    )

    # --- Apply Compliance Patches Tool ---
    def apply_patches_handler(invocation) -> ToolResult:
        """Apply compliance fixes."""
        args = _get_args(invocation)
        repo_url = args.get("repo_url", "")
        
        ws = _workspace_registry.get(repo_url)
        if not ws:
            return ToolResult(error="Repository not cloned. Call clone_repository first.")
        
        try:
            repo_name = _repo_name(repo_url)
            touched = apply_patches_impl(ws, repo_name)
            
            # Log modified files for UI to read (SDK events don't expose tool results)
            log_modified_files(repo_url, touched)
            
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "modified_files": touched,
                "count": len(touched),
                "summary": f"Modified {len(touched)} files: {', '.join(touched)}"
            }))
        except Exception as e:
            return ToolResult(error=str(e))

    apply_patches_tool = Tool(
        name="apply_compliance_patches",
        description="Apply compliance patches to fix detected drift (adds health endpoints, structured logging, middleware).",
        handler=apply_patches_handler,
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL (must have been cloned first)"
                }
            },
            "required": ["repo_url"]
        }
    )

    # --- Get Required Approvals Tool (MCP) ---
    def get_approvals_handler(invocation) -> ToolResult:
        """Determine required approvals."""
        args = _get_args(invocation)
        repo_url = args.get("repo_url", "")
        touched_paths = args.get("touched_paths", [])
        
        try:
            repo_name = _repo_name(repo_url)
            result = mcp_approval(repo_name, touched_paths)
            
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "required_approvals": result.get("required_approvals", []),
                "risk_level": result.get("risk_level", "unknown"),
                "rationale": result.get("rationale", ""),
                "summary": f"Requires approval from: {', '.join(result.get('required_approvals', ['none']))}"
            }, indent=2))
        except Exception as e:
            return ToolResult(error=str(e))

    get_approvals_tool = Tool(
        name="get_required_approvals",
        description="Determine who must approve changes based on service tier and files modified. Uses Change Management MCP server.",
        handler=get_approvals_handler,
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL"
                },
                "touched_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of modified file paths"
                }
            },
            "required": ["repo_url", "touched_paths"]
        }
    )

    # --- Create Branch Tool ---
    def create_branch_handler(invocation) -> ToolResult:
        """Create a feature branch."""
        args = _get_args(invocation)
        repo_url = args.get("repo_url", "")
        
        # Always generate unique branch name with timestamp to avoid conflicts
        # Even if agent provides a name, we append uniqueness to prevent "PR already exists"
        base_name = args.get("branch_name", "chore/fleet-compliance")
        # Strip any existing timestamp suffix to normalize
        if base_name.startswith("chore/fleet-compliance"):
            base_name = "chore/fleet-compliance"
        # Add unique suffix (nanoseconds ensures uniqueness even in rapid succession)
        branch_name = f"{base_name}-{time.time_ns()}"
        
        ws = _workspace_registry.get(repo_url)
        if not ws:
            return ToolResult(error="Repository not cloned. Call clone_repository first.")
        
        try:
            checkout_branch(ws, branch_name)
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "branch": branch_name,
                "message": f"Created and checked out branch: {branch_name}"
            }))
        except Exception as e:
            return ToolResult(error=str(e))

    create_branch_tool = Tool(
        name="create_branch",
        description="Create and checkout a new feature branch for compliance fixes.",
        handler=create_branch_handler,
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL (must have been cloned first)"
                },
                "branch_name": {
                    "type": "string",
                    "description": "Branch name (e.g., 'chore/fleet-compliance-123')"
                }
            },
            "required": ["repo_url"]
        }
    )

    # --- Run Tests Tool ---
    def run_tests_handler(invocation) -> ToolResult:
        """Run pytest in repository."""
        args = _get_args(invocation)
        repo_url = args.get("repo_url", "")
        
        ws = _workspace_registry.get(repo_url)
        if not ws:
            return ToolResult(error="Repository not cloned. Call clone_repository first.")
        
        try:
            if not (ws / "tests").exists():
                return ToolResult(textResultForLlm=json.dumps({
                    "success": True,
                    "passed": True,
                    "skipped": True,
                    "message": "No tests directory found - skipping"
                }))
            
            # Install dependencies
            subprocess.run(
                ["python", "-m", "pip", "install", "-r", "requirements.txt"],
                cwd=str(ws), check=False, capture_output=True
            )
            
            # Run tests
            result = subprocess.run(
                ["python", "-m", "pytest", "-q"],
                cwd=str(ws), capture_output=True, text=True, timeout=120
            )
            
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "passed": result.returncode == 0,
                "skipped": False,
                "output": (result.stdout + result.stderr)[:500],
                "message": "All tests passed" if result.returncode == 0 else "Some tests failed"
            }))
        except Exception as e:
            return ToolResult(error=str(e))

    run_tests_tool = Tool(
        name="run_tests",
        description="Run pytest to validate that compliance patches don't break existing functionality.",
        handler=run_tests_handler,
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL (must have been cloned first)"
                }
            },
            "required": ["repo_url"]
        }
    )

    # --- Commit Changes Tool ---
    def commit_changes_handler(invocation) -> ToolResult:
        """Commit all changes."""
        args = _get_args(invocation)
        repo_url = args.get("repo_url", "")
        message = args.get("message", "chore: enforce compliance policies")
        
        ws = _workspace_registry.get(repo_url)
        if not ws:
            return ToolResult(error="Repository not cloned. Call clone_repository first.")
        
        try:
            committed = commit_all(ws, message)
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "committed": committed,
                "message": f"Committed changes: {message}" if committed else "Nothing to commit"
            }))
        except Exception as e:
            return ToolResult(error=str(e))

    commit_changes_tool = Tool(
        name="commit_changes",
        description="Commit all staged changes with a descriptive message.",
        handler=commit_changes_handler,
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL (must have been cloned first)"
                },
                "message": {
                    "type": "string",
                    "description": "Commit message"
                }
            },
            "required": ["repo_url", "message"]
        }
    )

    # --- Push Branch Tool ---
    def push_branch_handler(invocation) -> ToolResult:
        """Push branch to remote."""
        args = _get_args(invocation)
        repo_url = args.get("repo_url", "")
        branch_name = args.get("branch_name", "")
        
        ws = _workspace_registry.get(repo_url)
        if not ws:
            return ToolResult(error="Repository not cloned. Call clone_repository first.")
        
        try:
            push_branch(ws, branch_name)
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "pushed": True,
                "branch": branch_name,
                "message": f"Pushed branch {branch_name} to remote"
            }))
        except Exception as e:
            return ToolResult(error=str(e))

    push_branch_tool = Tool(
        name="push_branch",
        description="Push the feature branch to the remote repository.",
        handler=push_branch_handler,
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL"
                },
                "branch_name": {
                    "type": "string",
                    "description": "Branch name to push"
                }
            },
            "required": ["repo_url", "branch_name"]
        }
    )

    # --- Create Pull Request Tool ---
    def create_pr_handler(invocation) -> ToolResult:
        """Create a pull request."""
        print(f"[CREATE_PR_HANDLER] Called!", flush=True)
        args = _get_args(invocation)
        print(f"[CREATE_PR_HANDLER] Args: {args}", flush=True)
        repo_url = args.get("repo_url", "")
        base = args.get("base", "main")
        head = args.get("head", "")
        title = args.get("title", "")
        body = args.get("body", "")
        labels = args.get("labels", [])
        
        ws = _workspace_registry.get(repo_url)
        print(f"[CREATE_PR_HANDLER] Workspace for {repo_url}: {ws}", flush=True)
        if not ws:
            return ToolResult(error="Repository not cloned. Call clone_repository first.")
        
        try:
            pr_url = open_pr(ws, base, head, title, body, labels)
            print(f"[CREATE_PR_HANDLER] open_pr returned: {pr_url}", flush=True)
            # Track PR for UI backend to access (both in-memory and file-based)
            created_prs.append({"repo_url": repo_url, "pr_url": pr_url, "title": title})
            log_created_pr(repo_url, pr_url, title)  # File-based for cross-module access
            print(f"[PR_CREATED] {pr_url}", flush=True)  # Marker for backend to capture
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "pr_url": pr_url,
                "title": title,
                "message": f"Created PR: {pr_url}"
            }))
        except Exception as e:
            print(f"[CREATE_PR_HANDLER] Exception: {e}", flush=True)
            return ToolResult(error=str(e))

    create_pr_tool = Tool(
        name="create_pull_request",
        description="Create a Pull Request with a detailed description citing policy evidence. Include risk assessment and rollout suggestions.",
        handler=create_pr_handler,
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL"
                },
                "base": {
                    "type": "string",
                    "description": "Base branch (usually 'main')"
                },
                "head": {
                    "type": "string",
                    "description": "Head branch (the feature branch)"
                },
                "title": {
                    "type": "string",
                    "description": "PR title"
                },
                "body": {
                    "type": "string",
                    "description": "PR description with policy evidence, changes summary, and risk assessment"
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels to add (e.g., ['needs-sre-approval', 'compliance'])"
                }
            },
            "required": ["repo_url", "base", "head", "title", "body"]
        }
    )

    # --- Read File Tool ---
    def read_file_handler(invocation) -> ToolResult:
        """Read a file from the cloned repository."""
        args = _get_args(invocation)
        repo_url = args.get("repo_url", "")
        file_path = args.get("file_path", "")
        
        ws = _workspace_registry.get(repo_url)
        if not ws:
            return ToolResult(error="Repository not cloned. Call clone_repository first.")
        
        try:
            full_path = ws / file_path
            if not full_path.exists():
                return ToolResult(textResultForLlm=json.dumps({
                    "success": False,
                    "error": f"File not found: {file_path}"
                }))
            
            content = full_path.read_text(encoding="utf-8")
            return ToolResult(textResultForLlm=json.dumps({
                "success": True,
                "file_path": file_path,
                "content": content[:10000],  # Limit to 10k chars
                "truncated": len(content) > 10000
            }))
        except Exception as e:
            return ToolResult(error=str(e))

    read_file_tool = Tool(
        name="read_file",
        description="Read the contents of a file from the cloned repository. Use this to examine code before fixing errors.",
        handler=read_file_handler,
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL (must have been cloned first)"
                },
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file (e.g., 'app/main.py', 'tests/test_health.py')"
                }
            },
            "required": ["repo_url", "file_path"]
        }
    )

    # --- Fix Code Tool (SDK-Powered) ---
    def fix_code_handler(invocation) -> ToolResult:
        """Fix code using the Copilot SDK based on error messages."""
        args = _get_args(invocation)
        repo_url = args.get("repo_url", "")
        file_path = args.get("file_path", "")
        error_message = args.get("error_message", "")
        
        ws = _workspace_registry.get(repo_url)
        if not ws:
            return ToolResult(error="Repository not cloned. Call clone_repository first.")
        
        try:
            full_path = ws / file_path
            if not full_path.exists():
                return ToolResult(error=f"File not found: {file_path}")
            
            original_content = full_path.read_text(encoding="utf-8")
            
            # Use sync helper to call SDK (we're in a sync handler)
            fixed_content = _fix_code_with_sdk(original_content, file_path, error_message)
            
            if fixed_content and fixed_content != original_content:
                # Validate syntax before writing
                import ast
                try:
                    if file_path.endswith(".py"):
                        ast.parse(fixed_content)
                except SyntaxError as e:
                    return ToolResult(textResultForLlm=json.dumps({
                        "success": False,
                        "error": f"SDK generated invalid syntax: {e.msg} at line {e.lineno}",
                        "file_path": file_path
                    }))
                
                # Write the fixed content
                full_path.write_text(fixed_content, encoding="utf-8")
                return ToolResult(textResultForLlm=json.dumps({
                    "success": True,
                    "file_path": file_path,
                    "message": f"Fixed {file_path} based on error",
                    "changes_made": True
                }))
            else:
                return ToolResult(textResultForLlm=json.dumps({
                    "success": False,
                    "file_path": file_path,
                    "message": "SDK could not determine a fix",
                    "changes_made": False
                }))
        except Exception as e:
            return ToolResult(error=str(e))

    fix_code_tool = Tool(
        name="fix_code",
        description="Fix code errors in a file using AI. Provide the file path and the error message (e.g., from test failures or syntax errors). The SDK will analyze the code and apply a fix.",
        handler=fix_code_handler,
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "The repository URL (must have been cloned first)"
                },
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file to fix (e.g., 'app/main.py')"
                },
                "error_message": {
                    "type": "string",
                    "description": "The error message or test failure output that needs to be fixed"
                }
            },
            "required": ["repo_url", "file_path", "error_message"]
        }
    )

    return [
        rag_search_tool,
        clone_tool,
        detect_drift_tool,
        security_scan_tool,
        create_branch_tool,
        apply_patches_tool,
        get_approvals_tool,
        run_tests_tool,
        read_file_tool,
        fix_code_tool,
        commit_changes_tool,
        push_branch_tool,
        create_pr_tool,
    ]


def _fix_code_with_sdk(original_code: str, file_path: str, error_message: str) -> Optional[str]:
    """
    Call Copilot SDK to fix code based on an error message.
    
    This is a sync wrapper that runs the async SDK call in a thread pool
    to avoid blocking the event loop.
    """
    import concurrent.futures
    
    async def _async_fix():
        from copilot import CopilotClient
        
        client = CopilotClient()
        await client.start()
        
        try:
            model = os.getenv("COPILOT_MODEL", "gpt-4o")
            
            session = await client.create_session({
                "model": model,
                "system_message": {"content": "You are a code fixer. Output ONLY the complete fixed code, no explanations."},
                "available_tools": [],  # Prevent SDK built-in tools from writing files to CWD
            })
            
            prompt = f"""Fix this Python code based on the error.

## File: {file_path}

## Error Message
```
{error_message}
```

## Current Code
```python
{original_code}
```

## Instructions
1. Analyze the error message carefully
2. Identify the root cause
3. Output the COMPLETE fixed file (not just the changed parts)
4. Do not include any explanations, only the code

Output the fixed code:
```python
"""
            
            response_text = ""
            done_event = asyncio.Event()
            
            def on_event(event):
                nonlocal response_text
                event_type = event.type.value if hasattr(event.type, 'value') else str(event.type)
                
                if event_type == "assistant.message":
                    if hasattr(event.data, 'content') and event.data.content:
                        response_text += event.data.content
                elif event_type == "session.idle":
                    done_event.set()
                elif event_type in ("error", "session.error"):
                    done_event.set()
            
            session.on(on_event)
            await session.send({"prompt": prompt})
            
            try:
                await asyncio.wait_for(done_event.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                pass
            
            await session.destroy()
            
            # Extract code from response
            if response_text:
                # Look for code block
                match = re.search(r'```(?:python)?\n(.*?)```', response_text, re.DOTALL)
                if match:
                    return match.group(1).strip()
                # Or just return raw if it looks like code
                if "def " in response_text or "import " in response_text:
                    return response_text.strip()
            
            return None
            
        finally:
            await client.stop()
    
    # Run in thread pool to get fresh event loop
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, _async_fix())
        return future.result(timeout=90.0)


# =============================================================================
# Agent Runner
# =============================================================================

@dataclass
class AgentRunResult:
    """Result of an agent run."""
    tool_calls: list[dict] = field(default_factory=list)
    prs_created: list[str] = field(default_factory=list)
    repos_processed: int = 0
    messages: list[str] = field(default_factory=list)


async def run_agent(user_input: str) -> AgentRunResult:
    """
    Run the Fleet Compliance Agent with custom tools.
    
    The Copilot SDK will:
    1. Receive the user input and system prompt
    2. Decide which tools to call based on the task
    3. Execute tools and receive results
    4. Continue until the task is complete
    """
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    
    # Set up environment
    cli_path = os.getenv("COPILOT_CLI_PATH", "")
    if cli_path:
        os.environ["COPILOT_CLI_PATH"] = cli_path
    
    result = AgentRunResult()
    
    # Verify GitHub auth
    print("🔐 Verifying GitHub authentication...")
    gh_auth_status()
    
    # Create tools
    tools = create_tools()
    print(f"🔧 Registered {len(tools)} custom tools:")
    for t in tools:
        print(f"   • {t.name}")
    
    # Start client
    client = CopilotClient()
    await client.start()
    
    try:
        model = os.getenv("COPILOT_MODEL", "gpt-4o")
        
        # Get tool names for whitelisting
        tool_names = [t.name for t in tools]
        
        # Create session with ONLY custom tools (whitelist approach)
        session = await client.create_session({
            "model": model,
            "system_message": {"content": SYSTEM_PROMPT},
            "tools": tools,
            "available_tools": tool_names,  # ONLY allow our custom tools
        })
        
        print(f"\n{'='*60}")
        print("  Fleet Compliance Agent (Agentic Mode)")
        print(f"  Model: {model}")
        print(f"  Tools: {len(tools)} custom tools registered")
        print(f"{'='*60}\n")
        
        print(f"📝 User Input:\n{user_input}\n")
        print("-" * 60)
        
        # Track events
        done_event = asyncio.Event()
        
        def on_event(event):
            event_type = event.type.value if hasattr(event.type, 'value') else str(event.type)
            
            if event_type == "assistant.message":
                if hasattr(event.data, 'content') and event.data.content:
                    content = event.data.content
                    print(f"\n💬 Agent: {content[:500]}", flush=True)
                    result.messages.append(content)
                    
                    # Extract PR URLs from agent messages (backup detection)
                    pr_urls = re.findall(r'https://github\.com/[^/]+/[^/]+/pull/\d+', content)
                    for url in pr_urls:
                        if url not in result.prs_created:
                            result.prs_created.append(url)
                            result.repos_processed += 1
            
            elif event_type == "tool.execution_start":
                tool_name = getattr(event.data, 'tool_name', 'unknown')
                args = getattr(event.data, 'arguments', {})
                print(f"\n🔧 Calling: {tool_name}", flush=True)
                if args:
                    print(f"   Args: {json.dumps(args, indent=2)[:200]}", flush=True)
                result.tool_calls.append({"tool": tool_name, "args": args})
            
            elif event_type == "tool.execution_complete":
                tool_name = getattr(event.data, 'tool_name', 'unknown')
                tool_result = getattr(event.data, 'result', None)
                if tool_result:
                    content = getattr(tool_result, 'content', str(tool_result))
                    print(f"   ✓ Result: {str(content)[:150]}...", flush=True)
                    
                    # Track PRs
                    if tool_name == "create_pull_request" and "pr_url" in str(content):
                        try:
                            data = json.loads(content) if isinstance(content, str) else content
                            if isinstance(data, dict) and data.get("pr_url"):
                                result.prs_created.append(data["pr_url"])
                                result.repos_processed += 1
                        except:
                            pass
            
            elif event_type == "session.idle":
                print("\n✅ Agent session idle - work complete", flush=True)
                done_event.set()
            
            elif event_type in ("error", "session.error"):
                print(f"\n❌ Error: {event.data}", flush=True)
                done_event.set()
        
        session.on(on_event)
        
        # Send user message and wait
        await session.send({"prompt": user_input})
        
        try:
            await asyncio.wait_for(done_event.wait(), timeout=600.0)  # 10 minute timeout
        except asyncio.TimeoutError:
            print("\n⏱️ Agent timeout (10 minutes)")
        
        await session.destroy()
        
    finally:
        await client.stop()
    
    # Summary
    print(f"\n{'='*60}")
    print("  Agent Run Summary")
    print(f"{'='*60}")
    print(f"  Tool Calls: {len(result.tool_calls)}")
    print(f"  PRs Created: {len(result.prs_created)}")
    for pr in result.prs_created:
        print(f"    • {pr}")
    print(f"{'='*60}\n")
    
    return result


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Run the agent with repository URLs from config."""
    # Load repos
    repos_config = ROOT / "config" / "repos.json"
    repos = json.loads(repos_config.read_text(encoding="utf-8"))["repos"]
    
    # Build user input
    user_input = f"""Analyze and enforce compliance on these FastAPI repositories:

{chr(10).join(f'• {url}' for url in repos)}

For each repository:
1. Search knowledge base for compliance policies (health endpoints, logging, security)
2. Clone the repository
3. Detect compliance drift
4. Scan for security vulnerabilities
5. Create a feature branch
6. Apply compliance patches
7. Get required approvals
8. Run tests
9. Commit and push changes
10. Create a Pull Request with policy evidence in the description

Start now."""

    # Run agent
    result = asyncio.run(run_agent(user_input))
    return result


if __name__ == "__main__":
    main()
