"""
FastAPI Compliance Patcher Module (SDK-Powered)
===============================================
Detects and applies compliance patches to FastAPI microservices using
the GitHub Copilot SDK for intelligent code transformation.

This module implements the policy enforcement logic for:
- OPS-2.1: Health and readiness endpoints (/healthz, /readyz)
- OBS-1.1: Structured logging with structlog
- OBS-3.2: Trace propagation via RequestContextMiddleware

Smart Discovery:
----------------
Instead of assuming a fixed structure (e.g., app/main.py), this module
dynamically discovers the FastAPI application structure by scanning all
Python files for:
- FastAPI() instantiation (the main app)
- APIRouter() instances (route modules)
- Existing middleware configurations

The Copilot SDK then receives the full context of the discovered structure
and generates appropriate transformations that fit the actual codebase.

Usage:
    from fleet_agent.patcher_fastapi import detect, apply
    from pathlib import Path
    
    repo = Path("./contoso-orders-api")
    
    # Check for compliance drift (auto-discovers structure)
    drift = detect(repo)
    if drift.missing_healthz:
        print(f"Missing /healthz in {drift.app_entry_point}")
    
    # Apply patches using Copilot SDK
    import asyncio
    modified_files = asyncio.run(apply_async(repo, "contoso-orders-api", drift))
    print(f"Modified: {modified_files}")
"""

from __future__ import annotations
import ast
import asyncio
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from copilot import CopilotClient
from fleet_agent.rag import search as rag_search


# =============================================================================
# Code Validation
# =============================================================================

def _validate_python_syntax(code: str, filename: str) -> tuple[bool, str]:
    """
    Validate Python code syntax using ast.parse().
    
    Args:
        code: Python source code to validate
        filename: Filename for error reporting
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax error in {filename} at line {e.lineno}: {e.msg}"


def _run_ruff_check(file_path: Path) -> tuple[bool, str]:
    """
    Run ruff linter on a file (if ruff is available).
    
    Args:
        file_path: Path to the Python file
    
    Returns:
        Tuple of (passed, output)
    """
    try:
        result = subprocess.run(
            ["ruff", "check", str(file_path), "--select=E,F"],  # Only errors and pyflakes
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stdout + result.stderr
    except FileNotFoundError:
        # ruff not installed, skip linting
        return True, ""
    except Exception as e:
        return True, f"Lint check skipped: {e}"


def _validate_and_write_file(
    repo: Path,
    rel_path: str,
    content: str,
    validate_syntax: bool = True,
    run_linter: bool = False
) -> tuple[bool, str]:
    """
    Validate and write a file to the repository.
    
    Args:
        repo: Repository root path
        rel_path: Relative file path
        content: File content to write
        validate_syntax: Whether to validate Python syntax
        run_linter: Whether to run ruff linter
    
    Returns:
        Tuple of (success, error_message)
    """
    # SAFETY: reject path-traversal attempts (e.g. "../../ui/backend/middleware.py")
    if ".." in rel_path:
        return False, f"Path traversal rejected: {rel_path}"
    
    full_path = (repo / rel_path).resolve()
    
    # SAFETY: ensure the resolved path is still inside the repo root
    try:
        full_path.relative_to(repo.resolve())
    except ValueError:
        return False, f"Path escapes repo root: {rel_path}"
    
    # Only validate Python files
    is_python = rel_path.endswith(".py")
    
    if is_python and validate_syntax:
        valid, error = _validate_python_syntax(content, rel_path)
        if not valid:
            return False, error
    
    # Write the file
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content + "\n", encoding="utf-8")
    
    # Optional: run linter after writing
    if is_python and run_linter:
        passed, lint_output = _run_ruff_check(full_path)
        if not passed:
            print(f"   [PATCHER] Lint warnings for {rel_path}: {lint_output[:200]}", flush=True)
            # Don't fail on lint warnings, just report
    
    return True, ""


# =============================================================================
# Smart FastAPI Discovery
# =============================================================================

@dataclass
class FastAPIStructure:
    """
    Discovered FastAPI application structure.
    
    Attributes:
        app_file: Path to the file containing FastAPI() instantiation (relative to repo)
        app_variable: Variable name of the FastAPI app (e.g., 'app', 'application')
        router_files: List of files containing APIRouter() instances
        requirements_file: Path to requirements.txt (or pyproject.toml)
        existing_middleware: List of middleware already configured
        is_factory_pattern: True if app is created via a factory function
    """
    app_file: Optional[str] = None
    app_variable: str = "app"
    router_files: list[str] = field(default_factory=list)
    requirements_file: Optional[str] = None
    existing_middleware: list[str] = field(default_factory=list)
    is_factory_pattern: bool = False


def discover_fastapi_structure(repo: Path) -> FastAPIStructure:
    """
    Discover the FastAPI application structure by scanning Python files.
    
    Scans all .py files in the repository for:
    - FastAPI() instantiation
    - APIRouter() instances
    - Existing middleware configurations
    - Requirements file location
    
    Args:
        repo: Path to the repository root directory
    
    Returns:
        FastAPIStructure describing the discovered application layout
    """
    structure = FastAPIStructure()
    
    # Find requirements file
    for req_name in ["requirements.txt", "pyproject.toml", "setup.py"]:
        req_path = repo / req_name
        if req_path.exists():
            structure.requirements_file = req_name
            break
    
    # Patterns to detect FastAPI components
    fastapi_app_pattern = re.compile(
        r'(\w+)\s*=\s*FastAPI\s*\(', re.MULTILINE
    )
    fastapi_factory_pattern = re.compile(
        r'def\s+(\w+)\s*\([^)]*\)\s*->\s*FastAPI|'
        r'def\s+(\w+)\s*\([^)]*\):[^}]*return\s+FastAPI\s*\(',
        re.MULTILINE | re.DOTALL
    )
    router_pattern = re.compile(
        r'(\w+)\s*=\s*APIRouter\s*\(', re.MULTILINE
    )
    middleware_pattern = re.compile(
        r'\.add_middleware\s*\(\s*(\w+)', re.MULTILINE
    )
    
    # Scan all Python files
    py_files = list(repo.rglob("*.py"))
    
    # Skip common non-source directories
    skip_dirs = {
        ".venv", "venv", "__pycache__", ".git", "node_modules",
        ".tox", "dist", "build",
    }
    # Filter using path parts RELATIVE to repo root (not absolute path)
    # to avoid false positives from parent directory names
    py_files = [
        f for f in py_files 
        if not any(skip in f.relative_to(repo).parts for skip in skip_dirs)
    ]
    
    for py_file in py_files:
        try:
            content = py_file.read_text(encoding="utf-8")
            rel_path = str(py_file.relative_to(repo))
            
            # Check for FastAPI app instantiation
            app_match = fastapi_app_pattern.search(content)
            if app_match and structure.app_file is None:
                structure.app_file = rel_path
                structure.app_variable = app_match.group(1)
                
                # Check for existing middleware
                for mw_match in middleware_pattern.finditer(content):
                    structure.existing_middleware.append(mw_match.group(1))
            
            # Check for factory pattern
            factory_match = fastapi_factory_pattern.search(content)
            if factory_match and structure.app_file is None:
                structure.app_file = rel_path
                structure.is_factory_pattern = True
                structure.app_variable = factory_match.group(1) or factory_match.group(2)
            
            # Check for routers
            if router_pattern.search(content):
                if rel_path not in structure.router_files:
                    structure.router_files.append(rel_path)
                    
        except Exception as e:
            # Skip files that can't be read
            continue
    
    return structure


@dataclass
class Drift:
    """
    Represents compliance drift detection results for a FastAPI app.
    
    Attributes:
        applicable: True if this is a FastAPI app (FastAPI() found somewhere)
        structure: Discovered FastAPI application structure
        missing_healthz: True if /healthz endpoint is missing
        missing_readyz: True if /readyz endpoint is missing
        missing_structlog: True if structlog is not configured
        missing_middleware: True if RequestContextMiddleware is missing
    """
    applicable: bool
    structure: FastAPIStructure = field(default_factory=FastAPIStructure)
    missing_healthz: bool = False
    missing_readyz: bool = False
    missing_structlog: bool = False
    missing_middleware: bool = False
    
    @property
    def app_entry_point(self) -> Optional[str]:
        """Convenience property to get the main app file path."""
        return self.structure.app_file


def detect(repo: Path) -> Drift:
    """
    Detect compliance drift in a FastAPI repository.
    
    Uses smart discovery to find the FastAPI application structure,
    then checks for compliance features across all relevant files.
    
    Checks for:
    - /healthz endpoint (OPS-2.1)
    - /readyz endpoint (OPS-2.1)
    - structlog configuration (OBS-1.1)
    - RequestContextMiddleware (OBS-3.2)
    
    Args:
        repo: Path to the repository root directory
    
    Returns:
        Drift object indicating which compliance features are missing
    """
    # Discover structure
    structure = discover_fastapi_structure(repo)
    
    if structure.app_file is None:
        return Drift(applicable=False, structure=structure)
    
    # Read all relevant files to check for compliance features
    all_code = ""
    files_to_check = [structure.app_file] + structure.router_files
    
    for rel_path in files_to_check:
        try:
            file_path = repo / rel_path
            if file_path.exists():
                all_code += file_path.read_text(encoding="utf-8") + "\n"
        except Exception:
            continue
    
    # Also check requirements
    req_content = ""
    if structure.requirements_file:
        try:
            req_content = (repo / structure.requirements_file).read_text(encoding="utf-8")
        except Exception:
            pass
    
    return Drift(
        applicable=True,
        structure=structure,
        missing_healthz="/healthz" not in all_code,
        missing_readyz="/readyz" not in all_code,
        missing_structlog="structlog" not in all_code and "structlog" not in req_content.lower(),
        missing_middleware="RequestContextMiddleware" not in all_code 
                          and "RequestContextMiddleware" not in structure.existing_middleware,
    )


# =============================================================================
# Copilot SDK-Powered Code Transformation
# =============================================================================

def _build_policy_context(drift: Drift) -> str:
    """
    Build policy context by searching RAG for relevant compliance requirements.
    
    Args:
        drift: The detected compliance drift
    
    Returns:
        String containing relevant policy excerpts from the knowledge base
    """
    queries = []
    if drift.missing_healthz or drift.missing_readyz:
        queries.append("health endpoints kubernetes readiness liveness")
    if drift.missing_structlog:
        queries.append("structured logging observability")
    if drift.missing_middleware:
        queries.append("trace propagation correlation request context")
    
    policy_context = []
    for query in queries:
        try:
            hits = rag_search(query, k=2)
            for hit in hits:
                policy_context.append(f"--- {hit.doc_id} (relevance: {hit.score:.2f}) ---\n{hit.excerpt}")
        except Exception as e:
            print(f"   [PATCHER] RAG search warning: {e}", flush=True)
    
    return "\n\n".join(policy_context) if policy_context else "No specific policy documents found."


def _read_repo_files(repo: Path, structure: FastAPIStructure) -> dict[str, str]:
    """
    Read all relevant files from the repository based on discovered structure.
    
    Args:
        repo: Path to the repository root
        structure: Discovered FastAPI structure
    
    Returns:
        Dictionary mapping relative file paths to their content
    """
    files = {}
    
    # Read the main app file
    if structure.app_file:
        app_path = repo / structure.app_file
        if app_path.exists():
            files[structure.app_file] = app_path.read_text(encoding="utf-8")
    
    # Read router files
    for router_file in structure.router_files:
        router_path = repo / router_file
        if router_path.exists():
            files[router_file] = router_path.read_text(encoding="utf-8")
    
    # Read requirements
    if structure.requirements_file:
        req_path = repo / structure.requirements_file
        if req_path.exists():
            files[structure.requirements_file] = req_path.read_text(encoding="utf-8")
    
    return files


def _build_transformation_prompt(
    repo_files: dict[str, str],
    service_name: str,
    drift: Drift,
    policy_context: str
) -> str:
    """
    Build the prompt for Copilot SDK to transform the code.
    
    Args:
        repo_files: Dictionary of file paths to content
        service_name: Name of the service
        drift: Detected compliance drift (includes structure info)
        policy_context: Policy excerpts from RAG
    
    Returns:
        Formatted prompt string for the SDK
    """
    structure = drift.structure
    
    missing_features = []
    if drift.missing_healthz:
        missing_features.append("- /healthz endpoint (liveness probe)")
    if drift.missing_readyz:
        missing_features.append("- /readyz endpoint (readiness probe)")
    if drift.missing_structlog:
        missing_features.append("- Structured logging with structlog")
    if drift.missing_middleware:
        missing_features.append("- RequestContextMiddleware for trace propagation (W3C traceparent)")
    
    # Build file listing
    file_sections = []
    for path, content in repo_files.items():
        file_sections.append(f"### File: {path}\n```python\n{content}\n```")
    
    # Determine where middleware.py and logging_config.py should go
    # Use the same directory as the app file, or 'app/' as fallback
    app_dir = str(Path(structure.app_file).parent) if structure.app_file else "app"
    if app_dir == ".":
        app_dir = ""  # Root level
    
    middleware_path = f"{app_dir}/middleware.py" if app_dir else "middleware.py"
    logging_path = f"{app_dir}/logging_config.py" if app_dir else "logging_config.py"
    
    return f"""You are a compliance engineer. Transform this FastAPI application to add missing compliance features.

## Service Name
{service_name}

## Discovered Application Structure
- **Main App File**: {structure.app_file or 'Not found'}
- **App Variable Name**: {structure.app_variable}
- **Router Files**: {', '.join(structure.router_files) or 'None'}
- **Requirements File**: {structure.requirements_file or 'Not found'}
- **Existing Middleware**: {', '.join(structure.existing_middleware) or 'None'}
- **Factory Pattern**: {'Yes' if structure.is_factory_pattern else 'No'}

## Missing Compliance Features
{chr(10).join(missing_features)}

## Policy Requirements (from knowledge base)
{policy_context}

## Current Repository Files
{chr(10).join(file_sections)}

## Your Task
Generate the COMPLETE updated/new files. Output these sections:

### UPDATED {structure.app_file}
(Complete updated file with all compliance features. Preserve ALL existing code and style. Add imports at top, configure_logging() call early, middleware after app creation, health endpoints.)

### UPDATED {structure.requirements_file or 'requirements.txt'}
(Complete updated requirements with structlog==24.2.0 added if missing)

### NEW {middleware_path}
(RequestContextMiddleware implementation. Must:
- Use contextvars for trace_id and request_id
- Extract trace_id from W3C traceparent header: 00-<trace_id>-<span_id>-<flags>
- Generate request_id from x-request-id header or uuid
- Export get_trace_id() and get_request_id() functions
- Add x-trace-id and x-request-id response headers)

### NEW {logging_path}
(Structured logging configuration. Must:
- Use structlog with JSON output
- Inject trace_id, request_id, and service name "{service_name}" into all log entries
- Provide configure_logging() function to call at startup)

### NEW tests/test_health.py
(Pytest tests. Must test:
- GET /healthz returns 200
- GET /readyz returns 200
- Response includes x-request-id and x-trace-id headers
- Import the correct app variable from the correct module)

## Critical Requirements:
1. **Preserve existing functionality** - don't remove any existing routes, imports, or logic
2. **Match existing code style** - indentation, quotes, naming conventions
3. **Correct imports** - adjust import paths based on the actual app structure
4. **Handle factory pattern** - if using create_app(), apply middleware inside the factory

Output ONLY the code sections with the exact headers shown. No explanations."""


def _extract_code_blocks(response_text: str, drift: Drift) -> dict[str, str]:
    """
    Extract code blocks from the SDK response.
    
    Args:
        response_text: Raw response from Copilot SDK
        drift: Drift info to determine expected file paths
    
    Returns:
        Dictionary mapping file names to their content
    """
    files = {}
    structure = drift.structure
    
    # Determine paths
    app_dir = str(Path(structure.app_file).parent) if structure.app_file else "app"
    if app_dir == ".":
        app_dir = ""
    
    middleware_path = f"{app_dir}/middleware.py" if app_dir else "middleware.py"
    logging_path = f"{app_dir}/logging_config.py" if app_dir else "logging_config.py"
    
    # Normalize response text: convert Windows paths to forward slashes
    normalized_text = response_text.replace("\\", "/")
    
    # Build patterns dynamically - made more flexible to handle format variations
    # Patterns now handle: "### UPDATED file", "### Updated: file", "**file**", etc.
    file_patterns = []
    
    if structure.app_file:
        # Normalize the app file path too
        norm_app = structure.app_file.replace("\\", "/")
        file_patterns.append((norm_app, ["UPDATED", "UPDATE", "Modified"]))
    
    req_file = (structure.requirements_file or "requirements.txt").replace("\\", "/")
    file_patterns.append((req_file, ["UPDATED", "UPDATE", "Modified"]))
    
    norm_mw = middleware_path.replace("\\", "/")
    file_patterns.append((norm_mw, ["NEW", "CREATE", "CREATED", "Add"]))
    
    norm_log = logging_path.replace("\\", "/")
    file_patterns.append((norm_log, ["NEW", "CREATE", "CREATED", "Add"]))
    
    file_patterns.append(("tests/test_health.py", ["NEW", "CREATE", "CREATED", "Add"]))
    
    for filename, keywords in file_patterns:
        # Try multiple pattern variations
        escaped_file = re.escape(filename)
        
        for keyword in keywords:
            # Pattern 1: ### KEYWORD filename\n```python\n...\n```
            pattern = rf"###?\s*{keyword}[:\s]+{escaped_file}\s*\n```(?:python)?\n(.*?)```"
            match = re.search(pattern, normalized_text, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                if content and len(content) > 10:
                    # Use original filename (with backslashes if on Windows)
                    files[filename] = content
                    print(f"   [PATCHER] Extracted: {filename} ({len(content)} chars)", flush=True)
                    break
        
        # If still not found, try a more generic pattern: **filename** or `filename` followed by code block
        if filename not in files:
            # Pattern: filename (any format) followed by code block
            simple_pattern = rf"(?:\*\*|`)?{escaped_file}(?:\*\*|`)?[:\s]*\n```(?:python)?\n(.*?)```"
            match = re.search(simple_pattern, normalized_text, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                if content and len(content) > 10:
                    files[filename] = content
                    print(f"   [PATCHER] Extracted (simple): {filename} ({len(content)} chars)", flush=True)
    
    return files


async def apply_async(repo: Path, service_name: str, drift: Optional[Drift] = None) -> list[str]:
    """
    Apply compliance patches using the Copilot SDK for intelligent code transformation.
    
    This function uses smart discovery to find the FastAPI structure, then
    leverages the Copilot SDK to transform the code. The SDK considers:
    - Actual application structure (not assumed app/main.py)
    - Existing code patterns and style
    - Policy requirements from the RAG knowledge base
    - Factory patterns, routers, existing middleware
    
    Args:
        repo: Path to the repository root directory
        service_name: Name of the service (used in logs and health responses)
        drift: Optional pre-computed drift (will be computed if not provided)
    
    Returns:
        List of file paths that were modified (relative to repo root)
    
    Raises:
        ValueError: If repo path is outside the allowed workspaces directory
    """
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    
    # SAFETY CHECK: Only allow patching within agent/workspaces directory
    # This prevents accidental patching of the project's own code (ui/, mcp/, etc.)
    agent_dir = Path(__file__).resolve().parents[1]
    workspaces_dir = agent_dir / "workspaces"
    repo_resolved = repo.resolve()
    
    # Check if repo is within workspaces directory
    try:
        repo_resolved.relative_to(workspaces_dir)
    except ValueError:
        # repo is NOT inside workspaces - this is a safety violation
        error_msg = (
            f"SAFETY: Refusing to patch '{repo_resolved}' - "
            f"only repositories cloned to '{workspaces_dir}' can be patched. "
            f"This prevents accidental modification of the project's own code."
        )
        print(f"   [PATCHER] ❌ {error_msg}", flush=True)
        raise ValueError(error_msg)
    
    # Detect drift if not provided (this also discovers structure)
    if drift is None:
        drift = detect(repo)
    
    structure = drift.structure
    
    if not drift.applicable:
        print(f"   [PATCHER] Not a FastAPI app (no FastAPI() found in any .py file)", flush=True)
        return []
    
    print(f"   [PATCHER] Discovered structure:", flush=True)
    print(f"      App file: {structure.app_file}", flush=True)
    print(f"      App variable: {structure.app_variable}", flush=True)
    print(f"      Routers: {structure.router_files}", flush=True)
    print(f"      Existing middleware: {structure.existing_middleware}", flush=True)
    
    # Check if there's anything to fix
    has_drift = drift.missing_healthz or drift.missing_readyz or drift.missing_structlog or drift.missing_middleware
    if not has_drift:
        print(f"   [PATCHER] No compliance drift detected", flush=True)
        return []
    
    print(f"   [PATCHER] Using Copilot SDK for code transformation...", flush=True)
    
    # Read all relevant files
    repo_files = _read_repo_files(repo, structure)
    
    if not repo_files:
        print(f"   [PATCHER] Could not read any source files", flush=True)
        return []
    
    # Get policy context from RAG
    print(f"   [PATCHER] Searching knowledge base for policy requirements...", flush=True)
    policy_context = _build_policy_context(drift)
    
    # Build transformation prompt
    prompt = _build_transformation_prompt(repo_files, service_name, drift, policy_context)
    
    # Call Copilot SDK
    print(f"   [PATCHER] Calling Copilot SDK for transformation...", flush=True)
    
    client = CopilotClient()
    await client.start()
    
    touched: list[str] = []
    
    try:
        model = os.getenv("COPILOT_MODEL", "gpt-4o")
        
        session = await client.create_session({
            "model": model,
            "system_message": {"content": "You are a code transformation assistant. Output only code, no explanations."},
            "available_tools": [],  # Prevent SDK built-in tools from writing files to CWD
        })
        
        # Collect response
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
                print(f"   [PATCHER] SDK Error: {event.data}", flush=True)
                done_event.set()
        
        session.on(on_event)
        await session.send({"prompt": prompt})
        
        try:
            await asyncio.wait_for(done_event.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            print(f"   [PATCHER] SDK timeout (60s)", flush=True)
        
        await session.destroy()
        
        # Extract and write files with validation
        if response_text:
            print(f"   [PATCHER] Parsing SDK response ({len(response_text)} chars)...", flush=True)
            # Debug: print first 500 chars to see format
            print(f"   [PATCHER] SDK response preview:\n{response_text[:800]}...", flush=True)
            files = _extract_code_blocks(response_text, drift)
            
            # Check if we got any parseable files
            if not files:
                print(f"   [PATCHER] ⚠️  Could not parse code blocks from SDK response, falling back to templates...", flush=True)
                touched = _apply_fallback_templates(repo, service_name, drift)
            else:
                # Backup original files for rollback
                backups: dict[str, str] = {}
                for rel_path in files:
                    original_path = repo / rel_path
                    if original_path.exists():
                        backups[rel_path] = original_path.read_text(encoding="utf-8")
                
                # Validate all files BEFORE writing any
                validation_errors = []
                for rel_path, content in files.items():
                    if rel_path.endswith(".py"):
                        valid, error = _validate_python_syntax(content, rel_path)
                        if not valid:
                            validation_errors.append(error)
                
                if validation_errors:
                    print(f"   [PATCHER] ⚠️  SDK generated invalid code:", flush=True)
                    for err in validation_errors:
                        print(f"      {err}", flush=True)
                    print(f"   [PATCHER] Falling back to templates...", flush=True)
                    touched = _apply_fallback_templates(repo, service_name, drift)
                else:
                    # All files valid - write them
                    for rel_path, content in files.items():
                        success, error = _validate_and_write_file(repo, rel_path, content, validate_syntax=False)
                        if success:
                            touched.append(rel_path)
                            print(f"   [PATCHER] ✓ Wrote: {rel_path}", flush=True)
                        else:
                            print(f"   [PATCHER] ✗ Failed to write {rel_path}: {error}", flush=True)
        else:
            print(f"   [PATCHER] No response from SDK, falling back to templates", flush=True)
            touched = _apply_fallback_templates(repo, service_name, drift)
        
    finally:
        await client.stop()
    
    return sorted(set(touched))


def apply(repo: Path, service_name: str) -> list[str]:
    """
    Synchronous wrapper for apply_async.
    
    This function is provided for backwards compatibility with code that
    expects a synchronous interface. It handles being called from within
    an existing event loop (e.g., from agent_loop.py tool handlers).
    
    Args:
        repo: Path to the repository root directory
        service_name: Name of the service
    
    Returns:
        List of file paths that were modified (relative to repo root)
    """
    import concurrent.futures
    
    try:
        # Check if we're already in an async context
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - safe to use asyncio.run()
        return asyncio.run(apply_async(repo, service_name))
    
    # Already in an async context - run in a thread pool to avoid blocking
    # and to get a fresh event loop
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, apply_async(repo, service_name))
        return future.result(timeout=180.0)  # 3 minute timeout


# =============================================================================
# Fallback Templates (used if SDK fails)
# =============================================================================

def _apply_fallback_templates(repo: Path, service_name: str, drift: Drift) -> list[str]:
    """
    Apply hardcoded templates as a fallback if SDK transformation fails.
    
    This preserves the original behavior as a safety net, but now uses
    the discovered structure to determine file paths.
    """
    # SAFETY CHECK: Only allow patching within agent/workspaces directory
    agent_dir = Path(__file__).resolve().parents[1]
    workspaces_dir = agent_dir / "workspaces"
    repo_resolved = repo.resolve()
    try:
        repo_resolved.relative_to(workspaces_dir)
    except ValueError:
        print(f"   [PATCHER FALLBACK] SAFETY: Refusing to patch '{repo_resolved}' - outside workspaces", flush=True)
        return []
    
    touched: list[str] = []
    structure = drift.structure
    
    if not structure.app_file:
        print(f"   [PATCHER FALLBACK] No app file discovered, cannot apply templates", flush=True)
        return touched
    
    # Determine paths based on discovered structure
    app_dir = Path(structure.app_file).parent
    app_dir_str = str(app_dir) if str(app_dir) != "." else ""
    
    middleware_rel = f"{app_dir_str}/middleware.py" if app_dir_str else "middleware.py"
    logging_rel = f"{app_dir_str}/logging_config.py" if app_dir_str else "logging_config.py"
    
    # Update requirements
    req_file = structure.requirements_file or "requirements.txt"
    req = repo / req_file
    if req.exists() and drift.missing_structlog:
        r = req.read_text(encoding="utf-8")
        if "structlog" not in r.lower():
            req.write_text(r.rstrip() + "\nstructlog==24.2.0\n", encoding="utf-8")
            touched.append(req_file)

    # Ensure app directory exists
    (repo / app_dir).mkdir(parents=True, exist_ok=True)

    # Create middleware
    if drift.missing_middleware:
        mw = repo / middleware_rel
        if not mw.exists():
            mw.write_text(_middleware_py(), encoding="utf-8")
            touched.append(middleware_rel)

    # Create logging config
    if drift.missing_structlog:
        lc = repo / logging_rel
        if not lc.exists():
            # Compute middleware import path based on app structure
            middleware_import_path = f"{app_dir_str.replace('/', '.')}.middleware" if app_dir_str else "middleware"
            lc.write_text(_logging_py(service_name, middleware_import_path), encoding="utf-8")
            touched.append(logging_rel)

    # Update main app file
    main_py = repo / structure.app_file
    m = main_py.read_text(encoding="utf-8")
    original_m = m
    
    # Build correct import paths based on app location
    if app_dir_str:
        logging_import = f"from {app_dir_str.replace('/', '.')}.logging_config import configure_logging"
        middleware_import = f"from {app_dir_str.replace('/', '.')}.middleware import RequestContextMiddleware"
    else:
        logging_import = "from logging_config import configure_logging"
        middleware_import = "from middleware import RequestContextMiddleware"

    if drift.missing_structlog and logging_import not in m:
        m = logging_import + "\n" + m
    if drift.missing_middleware and middleware_import not in m:
        m = middleware_import + "\n" + m

    if drift.missing_structlog and "configure_logging()" not in m:
        lines = m.splitlines()
        insert_at = 0
        for i, line in enumerate(lines):
            if line.strip() and not (line.startswith("import ") or line.startswith("from ")):
                insert_at = i
                break
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, "configure_logging()")
        lines.insert(insert_at + 2, "")
        m = "\n".join(lines)

    if drift.missing_middleware and f"{structure.app_variable}.add_middleware(RequestContextMiddleware" not in m:
        out = []
        added = False
        in_fastapi_def = False
        paren_depth = 0
        app_pattern = f"{structure.app_variable} = FastAPI"
        for line in m.splitlines():
            out.append(line)
            if not added:
                if line.strip().startswith(app_pattern):
                    in_fastapi_def = True
                    paren_depth = line.count("(") - line.count(")")
                    if paren_depth == 0:
                        out.append("")
                        out.append("# Correlation middleware (trace_id/request_id)")
                        out.append(f'{structure.app_variable}.add_middleware(RequestContextMiddleware, service_name="{service_name}")')
                        added = True
                elif in_fastapi_def:
                    paren_depth += line.count("(") - line.count(")")
                    if paren_depth <= 0:
                        out.append("")
                        out.append("# Correlation middleware (trace_id/request_id)")
                        out.append(f'{structure.app_variable}.add_middleware(RequestContextMiddleware, service_name="{service_name}")')
                        added = True
                        in_fastapi_def = False
        m = "\n".join(out)

    if drift.missing_healthz:
        m += (
            f'\n\n@{structure.app_variable}.get("/healthz")\n'
            f'def healthz():\n'
            f'    return {{"status":"ok","service":"{service_name}","version":"dev","timestamp":"now"}}\n'
        )

    if drift.missing_readyz:
        m += (
            f'\n\n@{structure.app_variable}.get("/readyz")\n'
            f'def readyz():\n'
            f'    return {{"status":"ready","service":"{service_name}","version":"dev","timestamp":"now"}}\n'
        )

    if m != original_m:
        main_py.write_text(m + ("\n" if not m.endswith("\n") else ""), encoding="utf-8")
        touched.append(structure.app_file)

    # Create tests
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    th = tests_dir / "test_health.py"
    if not th.exists():
        th.write_text(_tests_py(structure), encoding="utf-8")
        touched.append("tests/test_health.py")

    return touched


def _middleware_py() -> str:
    """Generate the RequestContextMiddleware source code (fallback template)."""
    return '''import contextvars
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

trace_id_var = contextvars.ContextVar("trace_id", default="")
request_id_var = contextvars.ContextVar("request_id", default="")

def get_trace_id() -> str:
    return trace_id_var.get() or ""

def get_request_id() -> str:
    return request_id_var.get() or ""

def _extract_trace_id(traceparent: str) -> str:
    # W3C traceparent: 00-<trace_id>-<span_id>-<flags>
    try:
        parts = traceparent.split("-")
        if len(parts) >= 4 and len(parts[1]) == 32:
            return parts[1]
    except Exception:
        pass
    return ""

class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        tp = request.headers.get("traceparent", "")
        trace_id = _extract_trace_id(tp) or uuid.uuid4().hex
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        trace_id_var.set(trace_id)
        request_id_var.set(req_id)

        response: Response = await call_next(request)
        response.headers["x-trace-id"] = trace_id
        response.headers["x-request-id"] = req_id
        return response
'''


def _logging_py(service_name: str, middleware_import_path: str = "app.middleware") -> str:
    """Generate the logging configuration source code (fallback template)."""
    return f'''import logging
import structlog
from {middleware_import_path} import get_trace_id, get_request_id

class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        record.request_id = get_request_id()
        record.service = "{service_name}"
        return True

def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    root = logging.getLogger()
    root.addFilter(_ContextFilter())

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
'''


def _tests_py(structure: FastAPIStructure) -> str:
    """Generate the health endpoint test source code (fallback template)."""
    # Build correct import based on app location
    app_file = structure.app_file or "app/main.py"
    module_path = app_file.replace("/", ".").replace("\\", ".").removesuffix(".py")
    app_var = structure.app_variable
    
    return f'''from fastapi.testclient import TestClient
from {module_path} import {app_var}

client = TestClient({app_var})

def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200

def test_readyz_ok():
    r = client.get("/readyz")
    assert r.status_code == 200

def test_headers_present():
    r = client.get("/healthz")
    assert "x-request-id" in {{k.lower(): v for k, v in r.headers.items()}}
    assert "x-trace-id" in {{k.lower(): v for k, v in r.headers.items()}}
'''
