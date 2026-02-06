# Fleet Compliance Agent UI

React + FastAPI visual frontend for demonstrating the Fleet Compliance Agent.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ React Frontend (localhost:3001)                                 │
│ • Multi-panel layout with Tailwind CSS                         │
│ • Real-time streaming via WebSocket                             │
│ • Per-repo progress tracking                                    │
│ • Markdown rendering with remark-gfm                            │
└─────────────────────────────────────────────────────────────────┘
                    │ WebSocket
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI Backend (localhost:8000)                                │
│ • Wraps existing agent_loop.py                                  │
│ • Queue-based event streaming architecture                      │
│ • Tool call tracking by call_id                                 │
│ • Heartbeat emitter for long-running tools                      │
└─────────────────────────────────────────────────────────────────┘
                    │ imports
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ agent/fleet_agent/agent_loop.py                                 │
│ • Unchanged - same code used for console mode                   │
│ • Event emitter callback injected at runtime                    │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **MCP Servers running** (ports 4101, 4102)
   ```powershell
   .\scripts\start-mcp-servers.ps1
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

```powershell
# From project root
.\scripts\start-ui.ps1
```

This will:
1. Start FastAPI backend on http://localhost:8000
2. Start React frontend on http://localhost:3001

Open http://localhost:3001 and click **"Run Fleet Agent"**.

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
npm run dev -- --port 3001
```

## UI Panels

| Panel | Description |
|-------|-------------|
| **Control Panel** | Start/stop agent, system status |
| **Fleet Repositories** | Per-repo cards with progress checklist |
| **Agent Reasoning** | Streaming agent messages/decisions |
| **Tool Calls** | Real-time tool execution status |
| **Console Logs** | Streaming execution logs |

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

### Event Streaming Pattern

The key challenge is emitting events from **synchronous tool handlers** to an **async WebSocket**. We solve this with a queue:

```python
# 1. Agent tool emits event (sync context)
def emit(event_type: str, data: dict):
    event_emitter(event_type, data)  # Callback from FastAPI

# 2. FastAPI puts event on queue (thread-safe)
def on_event(event_type: str, data: dict):
    event_queue.put_nowait({"type": event_type, **data})

# 3. Queue processor forwards to WebSocket (async context)
async def process_queue():
    while True:
        event = await event_queue.get()
        await websocket.send_json(event)
```

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

### Per-Repository Checklist

Each repo gets its own checklist card. The key is capturing the repo name **at queue time**, not processing time:

```python
# WRONG: Reads self.current_repo later (may have changed)
event_queue.put_nowait({"repo": self.current_repo, ...})

# RIGHT: Capture repo at emit time
repo = self.current_repo  # Capture now
event_queue.put_nowait({"repo": repo, ...})
```