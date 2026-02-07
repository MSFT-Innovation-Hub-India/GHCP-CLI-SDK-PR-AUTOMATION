# Fleet Compliance Agent UI

React + FastAPI visual frontend for demonstrating the Fleet Compliance Agent.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ React Frontend (localhost:3000)                                 │
│ • Multi-panel layout with Tailwind CSS                          │
│ • Real-time streaming via WebSocket                             │
│ • Single repo dropdown selector for demos                       │
│ • Markdown rendering with remark-gfm                            │
│ • Clickable PR URLs when created                                │
└─────────────────────────────────────────────────────────────────┘
                    │ WebSocket
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI Backend (localhost:8000)                                │
│ • Wraps existing agent_loop.py                                  │
│ • Real-time event streaming via asyncio.run_coroutine_threadsafe│
│ • Tool call tracking by call_id                                 │
│ • PR URL capture from gh pr create output                       │
│ • Heartbeat emitter for long-running tools                      │
└─────────────────────────────────────────────────────────────────┘
                    │ imports
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ agent/fleet_agent/agent_loop.py                                 │
│ • Core agent logic with 11 custom tools                         │
│ • File-based PR tracking for reliable URL capture               │
│ • Event callbacks invoked by Copilot SDK                        │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **MCP Servers running** (ports 4101, 4102)
   ```powershell
   # Terminal 1
   cd mcp\change_mgmt
   .venv\Scripts\Activate.ps1
   uvicorn server:app --host 0.0.0.0 --port 4101
   
   # Terminal 2
   cd mcp\security
   .venv\Scripts\Activate.ps1
   uvicorn server:app --host 0.0.0.0 --port 4102
   ```

2. **Python environment** with agent dependencies
   ```powershell
   cd agent
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Node.js 18+** for React frontend

4. **GitHub CLI authenticated**
   ```bash
   gh auth status
   ```

## Quick Start

**Terminal 1 - Backend:**
```powershell
cd ui\backend
..\..\agent\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```powershell
cd ui\frontend
npm run dev
```

Open http://localhost:3000 (or port shown by Vite) and click **"Run Fleet Agent"**.

## Manual Start

### Backend
```powershell
cd ui/backend
..\..\agent\.venv\Scripts\pip.exe install -r requirements.txt
..\..\agent\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

### Frontend
```powershell
cd ui/frontend
npm install
npm run dev
```

## UI Layout

The UI features a **three-panel layout** optimized for demos:

| Panel | Location | Description |
|-------|----------|-------------|
| **Control + Tool Calls** | Left | Repo selector dropdown, run button, checklist, tool call history |
| **Agent Reasoning** | Center | Streaming agent messages with markdown tables |
| **Console Logs** | Right | Real-time timestamped logs with emoji indicators |

### Key Features

- **Single Repo Selector**: Dropdown to select one repository at a time (ideal for demos)
- **Initialization Overlay**: Shows "Initializing..." state on startup instead of red indicators
- **Real-time Streaming**: Events appear in UI as they happen (not batched)
- **PR URL Display**: Clickable links to created PRs appear in the left panel

## WebSocket Events

The backend emits these events to the frontend:

| Event | Description |
|-------|-------------|
| `system_status` | GitHub CLI, MCP, Vector Store status |
| `agent_start` | Agent execution begins |
| `agent_complete` | Agent finished with summary |
| `tool_call_start` | Tool invocation started |
| `tool_call_complete` | Tool finished execution |
| `agent_message` | Agent reasoning/message |
| `repo_start` | Processing new repository |
| `repo_complete` | Repository finished |
| `console_log` | Streaming log entry |
| `checklist_update` | Step completion update |

## Development

### Backend changes
Edit `ui/backend/main.py` - auto-reloads with uvicorn

### Frontend changes
Edit `ui/frontend/src/App.tsx` - auto-reloads with Vite

## Note

This UI layer **does not modify** the console-based agent in `agent/fleet_agent/agent_loop.py`. It wraps and imports the existing code to provide a visual interface.

---

## Implementation Details

### Real-time Event Streaming

Events stream to the UI **immediately** as they occur using `asyncio.run_coroutine_threadsafe`:

```python
# Capture the event loop at session start
loop = asyncio.get_running_loop()

# Helper to emit from sync SDK callback
def emit_now(coro):
    """Schedule async emit to run immediately on event loop."""
    asyncio.run_coroutine_threadsafe(coro, loop)

# SDK callback (synchronous) emits directly
def on_event(event):
    if event.type.value == "tool.execution_start":
        emit_now(self.emit(WSEvent(type=EventType.TOOL_CALL_START, data={...})))
        emit_now(self.log("🔎 Starting tool...", "info"))
```

This bypasses any queue and ensures events appear in the UI within milliseconds of occurring.

### Tool Call Tracking

Tool calls are matched by `call_id` to ensure reliable completion:

```python
# SDK emits tool.execution_start with call_id
on_event("tool_start", {"tool": name, "call_id": call_id})

# SDK emits tool.execution_completed with same call_id
on_event("tool_end", {"tool": name, "call_id": call_id, "result": result})
```

The frontend tracks in-progress tools and matches completions by `call_id`.

### Heartbeat for Long-Running Tools

Some tools (e.g., `clone_repository`, `run_tests`) can take 30+ seconds. A heartbeat emitter keeps the UI responsive:

```python
async def heartbeat_emitter():
    start_time = time.time()
    while not agent_done.is_set():
        elapsed = int(time.time() - start_time)
        await websocket.send_json({
            "type": "heartbeat",
            "message": f"⏳ [{elapsed}s elapsed] Still working..."
        })
        await asyncio.sleep(10)  # Every 10 seconds
```

### PR URL Capture

PR URLs are captured from `gh pr create` output and emitted to the UI:

```python
# github_ops.py returns the PR URL
pr_url = _run(["gh", "pr", "create", ...])  # Returns: https://github.com/.../pull/123

# Backend emits to UI via WebSocket
emit_now(self.emit(WSEvent(type=EventType.PR_CREATED, data={"pr_url": pr_url})))
```

The UI displays clickable PR links in the "Pull Requests Created" section.

### Per-Repository Checklist

Each repo gets its own checklist card with step-by-step progress tracking:

| Step | Tool | Status |
|------|------|--------|
| Policy Knowledge Search | `rag_search` | ✓ |
| Clone Repository | `clone_repository` | ✓ |
| Detect Compliance Drift | `detect_compliance_drift` | ✓ |
| Security Vulnerability Scan | `security_scan` | ⏳ |
| Apply Compliance Patches | `apply_compliance_patches` | ○ |
| Run Tests | `run_tests` | ○ |
| Create Pull Request | `create_pull_request` | ○ |