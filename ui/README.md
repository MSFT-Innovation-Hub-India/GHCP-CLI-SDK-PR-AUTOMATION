# Fleet Compliance Agent UI

React + FastAPI frontend for the Fleet Compliance Agent.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ React Frontend (localhost:3000)                                 │
│ • Multi-panel layout                                            │
│ • Real-time streaming via WebSocket                             │
│ • Per-repo progress tracking                                    │
└─────────────────────────────────────────────────────────────────┘
                    │ WebSocket
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI Backend (localhost:8000)                                │
│ • Wraps existing agent_loop.py                                  │
│ • Emits events for tool calls, reasoning, progress              │
│ • Does NOT modify console-based agent                           │
└─────────────────────────────────────────────────────────────────┘
                    │ imports
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ agent/fleet_agent/agent_loop.py                                 │
│ • Unchanged - same code used for console mode                   │
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
2. Start React frontend on http://localhost:3000

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
