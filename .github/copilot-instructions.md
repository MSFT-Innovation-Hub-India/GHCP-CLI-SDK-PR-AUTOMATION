# Fleet Compliance Agent — Copilot Custom Instructions

## Project Overview

This is an **autonomous fleet compliance agent** that enforces organizational policies across multiple FastAPI microservices. The GitHub Copilot SDK acts as the agent's reasoning engine ("brain"), orchestrating 13 custom tools to scan repos, detect compliance drift, apply patches, and create Pull Requests — all without human intervention.

**Key distinction:** The Copilot SDK is embedded as an **infrastructure service**, not used interactively. Code drives the conversation — the SDK receives structured prompts, invokes registered tools autonomously, and completes multi-step workflows.

## Architecture

```
Entry Points
├── Console:  agent/fleet_agent/agent_loop.py  (main → run_agent)
└── UI:       ui/backend/main.py  (FastAPI + WebSocket → AgentEventEmitter.run_agent)
                ui/frontend/       (React + Vite + Tailwind)

Agent Core (agent/fleet_agent/)
├── agent_loop.py       — 13 custom tools registered with Copilot SDK, system prompt, agentic loop
├── patcher_fastapi.py  — Compliance drift detection + SDK-powered code patching
├── rag.py              — Azure OpenAI Responses API with file_search (vector store only, NOT LLM)
├── mcp_clients.py      — MCP protocol clients (SSE transport) for security + change-mgmt servers
└── github_ops.py       — Git/GitHub CLI wrappers (clone, branch, commit, push, PR)

MCP Servers (mcp/)
├── change_mgmt/server.py  — FastMCP server on port 4101 (approval matrix, CM-7 policy)
└── security/server.py     — FastMCP server on port 4102 (CVE vulnerability scanning, SEC-2.4)

Configuration
├── mcp.json               — MCP server manifest (standard convention)
├── agent/config/repos.json — Target repository URLs
├── agent/.env              — Environment variables (Azure OpenAI, Copilot CLI path, MCP URLs)
└── knowledge/*.md          — Policy documents uploaded to Azure OpenAI vector store for RAG
```

## Critical Design Decisions

### Copilot SDK Sessions

- **Always set `available_tools`** to a whitelist of custom tool names. Never rely on `excluded_tools`. This prevents the SDK's built-in tools (file write, terminal) from executing and writing files to the process CWD.
- For **text-only SDK sessions** (e.g., `fix_code` which transforms code), set `available_tools: []` — zero tools. The SDK should only return text, not take actions.
- The SDK communicates with the Copilot CLI via **JSON-RPC**. The CLI runs in server mode (spawned by `CopilotClient.start()`).
- Sessions are event-driven: register `session.on(handler)` and wait for `session.idle`.

### MCP Server Connections

- MCP servers use **FastMCP with SSE transport** (not stdio, not HTTP REST).
- Client URL resolution follows priority: `mcp.json` → environment variables → hardcoded defaults.
- The `_call_tool_sync` wrapper runs MCP calls in a `ThreadPoolExecutor` with `asyncio.run()` because tool handlers execute synchronously inside the SDK's async event loop.
- SSE endpoint is always `{base_url}/sse` — the base URL in `mcp.json` already includes `/sse`.

### Patcher Safety

- **Path traversal protection:** `_validate_and_write_file()` rejects paths containing `..` and validates the resolved path stays inside the repo root.
- **Workspaces-only guard:** Both `apply_async()` and `_apply_fallback_templates()` verify the repo path is inside `agent/workspaces/` before writing any files.
- **Relative path filtering:** `discover_fastapi_structure()` uses `f.relative_to(repo).parts` (not `f.parts`) when checking `skip_dirs` to avoid false positives from parent directory names in absolute paths.
- **skip_dirs:** `[".venv", "venv", ".git", "__pycache__", "node_modules", ".tox", "site-packages"]` — only virtual env and build artifacts. Do NOT add project-level directories like `agent`, `ui`, `mcp` here.

### RAG (Knowledge Base Search)

- Uses **Azure OpenAI Responses API** with the `file_search` tool and a native vector store.
- Azure OpenAI is used **only for vector search** — NOT for LLM reasoning. All LLM capability comes from the Copilot SDK.
- The deployment model name (e.g., `gpt-4o`) is required by the Responses API even though it's used for search, not generation. Read from `AZURE_OPENAI_DEPLOYMENT` env var.
- Authentication uses `DefaultAzureCredential` (Azure AD token), not API keys.

### Two Entry Points — Keep in Sync

Both the console and UI paths must stay synchronized:

| Aspect | Console (`agent_loop.py → main()`) | UI (`ui/backend/main.py → AgentEventEmitter.run_agent()`) |
|--------|--------------------------------------|-----------------------------------------------------------|
| Tools | `create_tools()` from agent_loop.py | Same — imports `create_tools()` |
| System prompt | `SYSTEM_PROMPT` from agent_loop.py | Same — imports `SYSTEM_PROMPT` |
| State cleanup | `clear_created_prs()` + `clear_modified_files()` | Same |
| Timeout | 600 seconds | 600 seconds |
| available_tools | Custom tool names only | Custom tool names only |

When adding or modifying tools, update `create_tools()` in `agent_loop.py` — both paths use it.

### Demo vs. Production Execution

The current implementation processes repos **sequentially in a single SDK session**. This is intentional for the demo (3 repos, predictable flow).

For production fleet scale (50+ repos), the architecture shifts to:
- **One SDK session per repo** — avoids context window overflow and enables independent timeouts
- **Parallel worker pool** — `asyncio.Semaphore`-controlled concurrency
- **Per-repo state tracking** — persistent store for retry/resume after failures
- **Scheduled or event-driven triggers** — not manual invocation

See `docs/ARCHITECTURE_FLOW.md` § "Production Architecture" for the full diagram and design decisions.

## Coding Conventions

### Python

- **Python 3.11+** required. The codebase uses `match` statements, `removeprefix()`/`removesuffix()`, and `Path` throughout.
- **Type hints** on all function signatures. Use `from __future__ import annotations` for forward references.
- **Docstrings:** Module-level docstrings explain purpose, tools, and usage. Function docstrings include Args/Returns sections.
- **Async pattern:** The agent loop is async (`async def run_agent`), but tool handlers are synchronous. When calling async code from sync handlers, use `ThreadPoolExecutor` + `asyncio.run()`.
- **No global mutable state for cross-run data.** Use file-based logs (`created_prs.json`, `modified_files.json`) that are cleared at the start of each run.
- **Error handling in tools:** Return `ToolResult(error=str(e))` — never raise from a tool handler. The SDK handles error results gracefully.

### JavaScript/TypeScript (Frontend)

- React 18 with TypeScript, Vite bundler, Tailwind CSS.
- Single-page app communicating via WebSocket to the FastAPI backend.
- No state management library — `useState`/`useEffect` hooks only.

### MCP Servers

- Use `FastMCP` from `mcp` package with `transport="sse"`.
- Each tool is a decorated function: `@mcp.tool()`.
- Tools return plain dicts — FastMCP handles JSON serialization.
- Each server runs in its own venv with `mcp[cli]>=1.2.0`, `pydantic`, `structlog`.

## File Naming & Policy IDs

| Prefix | Category | Source |
|--------|----------|--------|
| CM- | Configuration Management | NIST 800-53 |
| OBS- | Observability | SRE/DevOps |
| OPS- | Operations | Platform engineering |
| REL- | Reliability | Google SRE |
| SEC- | Security | NIST, SOC 2, CIS |

Knowledge documents follow the pattern: `{PREFIX}-{number}-{slug}.md` (e.g., `OPS-2.1-health-readiness.md`).

## Environment & Dependencies

### Three Separate Virtual Environments

| venv | Location | Key Packages | Purpose |
|------|----------|--------------|---------|
| Agent | `agent/.venv` | `github-copilot-sdk`, `openai`, `azure-identity`, `mcp`, `fastapi`, `nanoid` | Agent core + UI backend |
| Change Mgmt MCP | `mcp/change_mgmt/.venv` | `mcp[cli]`, `pydantic`, `structlog` | Approval matrix server |
| Security MCP | `mcp/security/.venv` | `mcp[cli]`, `pydantic`, `structlog` | Vulnerability scan server |

The UI backend runs using the **agent venv's Python** (not its own venv): `..\..\agent\.venv\Scripts\python.exe -m uvicorn main:app`

### Required External Tools

- `gh` (GitHub CLI) — authenticated via `gh auth login`
- `git` — for clone/branch/commit/push
- `az` (Azure CLI) — for `DefaultAzureCredential` token
- `copilot` (Copilot CLI) — path set via `COPILOT_CLI_PATH` env var

## Common Pitfalls

1. **Never remove `available_tools` from SDK sessions.** Without it, the SDK may use built-in file-write tools that write to the process CWD, creating rogue files in irrelevant directories.
2. **Never add project directories (agent, ui, mcp) to `skip_dirs` in the patcher.** This causes all files in `agent/workspaces/{repo}/` to be skipped because the absolute path contains "agent".
3. **MCP servers must be running before the agent starts.** The agent does not start them automatically. Ports 4101 and 4102 must be listening.
4. **`agent/workspaces/` is ephemeral.** Repos are cloned here with a nanoid suffix for uniqueness. Do not rely on workspace paths persisting across runs.
5. **`created_prs.json` and `modified_files.json` are runtime artifacts.** They are cleared at the start of each run and should not be committed (listed in `.gitignore`).
6. **The patcher has both an SDK path and a fallback template path.** `apply_async()` tries Copilot SDK first; if the SDK response is empty or invalid, `_apply_fallback_templates()` writes deterministic template files. Both paths have the workspaces-only safety guard.
7. **Branch names include `time.time_ns()`** to guarantee uniqueness and avoid "PR already exists" errors when re-running against the same repo.
