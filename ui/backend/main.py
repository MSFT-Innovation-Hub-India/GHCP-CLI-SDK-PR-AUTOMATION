"""
Fleet Compliance Agent - FastAPI Backend
=========================================

This backend wraps the existing agent_loop.py and exposes it via WebSocket
for real-time streaming to the React frontend.

It does NOT modify agent_loop.py - it imports and wraps it.
"""

from __future__ import annotations
import asyncio
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
import subprocess

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Add agent directory to path for imports
AGENT_DIR = Path(__file__).resolve().parents[2] / "agent"
sys.path.insert(0, str(AGENT_DIR))

# Global WebSocket reference - can be updated when client reconnects
_active_websocket: Optional[WebSocket] = None
_active_emitter: Optional['AgentEventEmitter'] = None
_agent_running: bool = False

load_dotenv(AGENT_DIR / ".env")


# =============================================================================
# Event Types for WebSocket streaming
# =============================================================================

class EventType(str, Enum):
    # System events
    SYSTEM_STATUS = "system_status"
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    ERROR = "error"
    
    # Tool events
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_COMPLETE = "tool_call_complete"
    
    # Agent reasoning
    AGENT_REASONING = "agent_reasoning"
    AGENT_MESSAGE = "agent_message"
    
    # Progress tracking
    REPO_START = "repo_start"
    REPO_PROGRESS = "repo_progress"
    REPO_COMPLETE = "repo_complete"
    PR_CREATED = "pr_created"
    
    # Console logs
    CONSOLE_LOG = "console_log"
    
    # Checklist
    CHECKLIST_UPDATE = "checklist_update"


@dataclass
class WSEvent:
    """WebSocket event structure."""
    type: EventType
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data: dict = field(default_factory=dict)
    
    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "timestamp": self.timestamp,
            "data": self.data
        })


# =============================================================================
# System Status Checker
# =============================================================================

def check_system_status() -> dict:
    """Check if all required services are available."""
    status = {
        "github_cli": False,
        "github_user": None,
        "mcp_security": False,
        "mcp_change_mgmt": False,
        "vector_store": False,
    }
    
    # Check GitHub CLI and get username
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10
        )
        status["github_cli"] = result.returncode == 0
        
        # Extract username from output (format: "Logged in to github.com account USERNAME")
        if result.returncode == 0:
            import re
            match = re.search(r'Logged in to github\.com account ([^\s(]+)', result.stdout + result.stderr)
            if match:
                status["github_user"] = match.group(1)
    except:
        pass
    
    # Check MCP servers
    import socket
    for name, port in [("mcp_security", 4102), ("mcp_change_mgmt", 4101)]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', port))
            status[name] = result == 0
            sock.close()
        except:
            pass
    
    # Check Vector Store - verify connectivity
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    vector_store_id = os.getenv("AZURE_OPENAI_VECTOR_STORE_ID")
    if endpoint and vector_store_id:
        try:
            from openai import AzureOpenAI
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default"
            )
            client = AzureOpenAI(
                azure_endpoint=endpoint.replace("/openai/v1/", "").replace("/openai/v1", ""),
                azure_ad_token_provider=token_provider,
                api_version="2025-01-01-preview"
            )
            # Quick check - retrieve vector store info
            vs = client.vector_stores.retrieve(vector_store_id)
            status["vector_store"] = vs.status == "completed"
        except Exception as e:
            print(f"[STATUS] Vector store check failed: {e}")
            status["vector_store"] = False
    
    return status


def get_fleet_repos() -> list[dict]:
    """Load fleet repositories from config."""
    config_path = AGENT_DIR / "config" / "repos.json"
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        repos = data.get("repos", [])
        return [
            {
                "url": url,
                "name": url.rstrip("/").split("/")[-1].removesuffix(".git"),
                "status": "pending"
            }
            for url in repos
        ]
    return []


# =============================================================================
# Agent Wrapper with Event Streaming
# =============================================================================

class AgentEventEmitter:
    """Wraps agent execution and emits events to WebSocket."""
    
    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.current_repo: Optional[str] = None
        self.checklist = {
            "rag_search": {"label": "Policy Knowledge Search", "status": "pending"},
            "clone": {"label": "Clone Repository", "status": "pending"},
            "detect_drift": {"label": "Detect Compliance Drift", "status": "pending"},
            "security_scan": {"label": "Security Vulnerability Scan", "status": "pending"},
            "apply_patches": {"label": "Apply Compliance Patches", "status": "pending"},
            "run_tests": {"label": "Run Tests", "status": "pending"},
            "create_pr": {"label": "Create Pull Request", "status": "pending"},
        }
    
    def update_websocket(self, websocket: WebSocket):
        """Update the WebSocket reference (called on reconnection)."""
        self.ws = websocket
        print("[EMITTER] WebSocket reference updated", flush=True)
    
    async def emit(self, event: WSEvent):
        """Send event to WebSocket."""
        # Use global reference in case it was updated
        global _active_websocket
        ws = _active_websocket or self.ws
        try:
            json_data = event.to_json()
            await ws.send_text(json_data)
            print(f"[EMIT] Sent: {event.type.value}", flush=True)
        except Exception as e:
            print(f"[EMIT] FAILED to send {event.type.value}: {e}", flush=True)
    
    async def log(self, message: str, level: str = "info"):
        """Emit console log event."""
        await self.emit(WSEvent(
            type=EventType.CONSOLE_LOG,
            data={"message": message, "level": level, "repo": self.current_repo}
        ))
    
    async def update_checklist(self, item: str, status: str, repo: str | None = None):
        """Update checklist item status."""
        # Use provided repo or fall back to current_repo
        target_repo = repo if repo is not None else self.current_repo
        if item in self.checklist:
            self.checklist[item]["status"] = status
            await self.emit(WSEvent(
                type=EventType.CHECKLIST_UPDATE,
                data={"item": item, "status": status, "checklist": self.checklist, "repo": target_repo}
            ))
    
    async def run_agent(self, repos: list[str]):
        """Run the agent with event streaming."""
        from fleet_agent.agent_loop import create_tools, SYSTEM_PROMPT, WORKSPACES, _workspace_registry, get_created_prs, clear_created_prs
        from fleet_agent.github_ops import gh_auth_status
        from copilot import CopilotClient
        from copilot.types import Tool, ToolResult
        import re
        
        # Clear any previous PR tracking (file-based)
        clear_created_prs()
        
        # Emit start
        await self.emit(WSEvent(
            type=EventType.AGENT_START,
            data={"repos": repos, "total": len(repos)}
        ))
        
        await self.log("Verifying GitHub authentication...")
        gh_auth_status()
        await self.log("GitHub CLI authenticated", "success")
        
        # Get tools
        tools = create_tools()
        tool_names = [t.name for t in tools]
        
        await self.log(f"Registered {len(tools)} custom tools")
        
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

Process all repositories completely."""
        
        # Start client
        client = CopilotClient()
        await client.start()
        
        try:
            session = await client.create_session({
                "system_message": {"content": SYSTEM_PROMPT},
                "tools": tools,
                "available_tools": tool_names,
            })
            
            await self.log("Copilot SDK session created (powered by GitHub Copilot)")
            
            # Track state
            done_event = asyncio.Event()
            prs_created = []
            tool_call_count = 0
            
            # Capture running loop for thread-safe callback
            loop = asyncio.get_running_loop()
            
            # Helper to emit WebSocket events directly from sync callback
            # This bypasses the queue and emits immediately
            def emit_now(coro):
                """Schedule async emit to run immediately on event loop."""
                asyncio.run_coroutine_threadsafe(coro, loop)
            
            # Tool to checklist mapping
            tool_checklist_map = {
                "rag_search": "rag_search",
                "clone_repository": "clone",
                "detect_compliance_drift": "detect_drift",
                "security_scan": "security_scan",
                "apply_compliance_patches": "apply_patches",
                "run_tests": "run_tests",
                "create_pull_request": "create_pr",
            }
            
            # Track tool calls by ID for completion lookup
            active_tool_calls = {}  # call_id -> tool_name
            rag_search_queries = {}  # call_id -> query (for showing in completion)
            rag_search_counter = [0]  # Using list for nonlocal mutation
            thinking_logged = False
            
            # Track long-running tools for heartbeat messages
            long_running_tools = set()  # Set of tool names currently running that need heartbeats
            long_running_start_times = {}  # tool_name -> start_time
            
            def on_event(event):
                nonlocal tool_call_count, thinking_logged
                event_type = event.type.value if hasattr(event.type, 'value') else str(event.type)
                print(f"[SDK EVENT] {event_type}", flush=True)
                
                # Show "thinking" status for intermediate events
                if event_type in ("pending_messages.modified", "session.info", "user.message"):
                    if not thinking_logged:
                        emit_now(self.log("Agent analyzing task and planning approach...", "info"))
                        thinking_logged = True
                    return
                
                if event_type == "assistant.message":
                    if hasattr(event.data, 'content') and event.data.content:
                        content = event.data.content
                        print(f"[SDK] Assistant message: {content[:100]}...", flush=True)
                        
                        # Emit directly
                        emit_now(self.emit(WSEvent(type=EventType.AGENT_MESSAGE, data={"content": content[:1000]})))
                        
                        # Extract PR URLs from assistant message and emit them
                        pr_urls = re.findall(r'https://github\.com/[^/]+/[^/]+/pull/\d+', content)
                        for url in pr_urls:
                            if url not in prs_created:
                                prs_created.append(url)
                                print(f"[SDK] Found PR URL in assistant message: {url}", flush=True)
                                emit_now(self.emit(WSEvent(type=EventType.PR_CREATED, data={"repo": self.current_repo, "pr_url": url})))
                                emit_now(self.log(f"🔗 PR created: {url}", "success"))
                
                elif event_type == "tool.execution_start":
                    tool_name = getattr(event.data, 'tool_name', 'unknown')
                    args = getattr(event.data, 'arguments', {})
                    # Track by call_id for completion lookup
                    call_id = getattr(event.data, 'call_id', None) or getattr(event.data, 'id', None) or getattr(event.data, 'tool_call_id', None)
                    if call_id:
                        active_tool_calls[call_id] = tool_name
                    tool_call_count += 1
                    print(f"[SDK] Tool start: {tool_name} (call_id={call_id})", flush=True)
                    
                    # Detect repo from clone
                    if tool_name == "clone_repository" and args.get("url"):
                        repo_name = args["url"].rstrip("/").split("/")[-1]
                        # Remove .git suffix if present
                        if repo_name.endswith(".git"):
                            repo_name = repo_name[:-4]
                        self.current_repo = repo_name
                        emit_now(self.emit(WSEvent(type=EventType.REPO_START, data={"repo": repo_name, "url": args["url"]})))
                    
                    # Emit tool call event directly
                    emit_now(self.emit(WSEvent(type=EventType.TOOL_CALL_START, data={
                        "tool": tool_name,
                        "args": args,
                        "repo": self.current_repo,
                        "call_number": tool_call_count
                    })))
                    
                    # Emit checklist update
                    if tool_name in tool_checklist_map:
                        emit_now(self.update_checklist(tool_checklist_map[tool_name], "running", self.current_repo))
                    
                    # Emit descriptive log based on tool type
                    # For rag_search, add a counter and store query for completion
                    if tool_name == "rag_search":
                        rag_search_counter[0] += 1
                        query_short = args.get('query', '')[:40]
                        if call_id:
                            rag_search_queries[call_id] = query_short
                    
                    tool_descriptions = {
                        "rag_search": f"🔎 RAG #{rag_search_counter[0]}: {args.get('query', '')[:40]}...",
                        "clone_repository": f"📥 Cloning repository: {args.get('url', '').split('/')[-1]}",
                        "detect_compliance_drift": "🔍 Analyzing code for compliance drift...",
                        "security_scan": "🛡️ Starting security scan for CVE vulnerabilities...",
                        "create_branch": f"🌿 Creating branch: {args.get('branch_name', 'compliance-fix')}",
                        "apply_compliance_patches": "🔧 Applying compliance patches...",
                        "get_required_approvals": "📋 Checking approval requirements (MCP)...",
                        "run_tests": "🧪 Starting pytest (this may take 30-60 seconds)...",
                        "commit_changes": f"💾 Committing: {args.get('message', 'compliance fix')[:50]}",
                        "push_branch": f"⬆️ Pushing branch to remote...",
                        "create_pull_request": f"📝 Creating PR: {args.get('title', '')[:40]}...",
                    }
                    log_msg = tool_descriptions.get(tool_name, f"Tool: {tool_name}")
                    emit_now(self.log(log_msg, "info"))
                    
                    # Track long-running tools for heartbeat progress
                    if tool_name in ("run_tests", "apply_compliance_patches", "security_scan"):
                        long_running_tools.add(tool_name)
                        long_running_start_times[tool_name] = time.time()
                
                elif event_type == "tool.execution_complete":
                    # Look up tool name by call_id first, then try direct attributes
                    call_id = getattr(event.data, 'call_id', None) or getattr(event.data, 'id', None) or getattr(event.data, 'tool_call_id', None)
                    tool_name = None
                    if call_id and call_id in active_tool_calls:
                        tool_name = active_tool_calls.pop(call_id)
                    if not tool_name:
                        tool_name = (
                            getattr(event.data, 'tool_name', None) or
                            getattr(event.data, 'name', None) or
                            getattr(event.data, 'tool', None) or
                            'unknown'
                        )
                    print(f"[SDK] Tool complete: {tool_name} (call_id={call_id})", flush=True)
                    
                    emit_now(self.emit(WSEvent(type=EventType.TOOL_CALL_COMPLETE, data={"tool": tool_name, "repo": self.current_repo})))
                    
                    # Remove from long-running tracking
                    long_running_tools.discard(tool_name)
                    long_running_start_times.pop(tool_name, None)
                    
                    # Emit checklist update
                    if tool_name in tool_checklist_map:
                        emit_now(self.update_checklist(tool_checklist_map[tool_name], "complete", self.current_repo))
                    
                    # Emit descriptive completion log
                    # For rag_search, include the query it searched for
                    if tool_name == "rag_search":
                        query_info = rag_search_queries.pop(call_id, "") if call_id else ""
                        short_query = query_info[:30] + "..." if len(query_info) > 30 else query_info
                        emit_now(self.log(f"✅ Found: {short_query}", "success"))
                    
                    complete_descriptions = {
                        "clone_repository": "✅ Repository cloned",
                        "detect_compliance_drift": "✅ Compliance analysis complete",
                        "security_scan": "✅ Security scan complete",
                        "create_branch": "✅ Feature branch created",
                        "apply_compliance_patches": "✅ Compliance patches applied",
                        "get_required_approvals": "✅ Approval requirements retrieved",
                        "run_tests": "✅ Tests completed!",
                        "commit_changes": "✅ Changes committed",
                        "push_branch": "✅ Branch pushed to remote",
                        "create_pull_request": "🎉 Pull request created!",
                    }
                    # Only log completion for tools that have a description (skips rag_search)
                    log_msg = complete_descriptions.get(tool_name)
                    if log_msg:
                        emit_now(self.log(log_msg, "success"))
                    
                    # If PR created, mark repo complete and capture PR URL
                    if tool_name == "create_pull_request":
                        # Debug: dump ALL attributes and values
                        print(f"[SDK] create_pull_request event.data type: {type(event.data)}", flush=True)
                        print(f"[SDK] create_pull_request event.data attributes: {dir(event.data)}", flush=True)
                        for attr in dir(event.data):
                            if not attr.startswith('_'):
                                try:
                                    val = getattr(event.data, attr)
                                    if not callable(val):
                                        print(f"[SDK]   {attr} = {val}", flush=True)
                                except:
                                    pass
                        
                        # Try multiple possible attribute names
                        tool_content = None
                        for attr_name in ['content', 'result', 'tool_result', 'text_result', 'output', 
                                          'textResultForLlm', 'text_result_for_llm', 'response', 'data']:
                            val = getattr(event.data, attr_name, None)
                            if val:
                                tool_content = val
                                print(f"[SDK] Found content in '{attr_name}': {val}", flush=True)
                                break
                        
                        pr_url = None
                        if tool_content:
                            try:
                                import json as json_mod
                                if isinstance(tool_content, str):
                                    data = json_mod.loads(tool_content)
                                else:
                                    data = tool_content
                                if isinstance(data, dict):
                                    pr_url = data.get("pr_url") or data.get("url") or data.get("html_url")
                                    print(f"[SDK] Extracted PR URL from JSON: {pr_url}", flush=True)
                            except Exception as e:
                                print(f"[SDK] JSON parse failed: {e}, trying regex", flush=True)
                                # Try regex extraction as fallback
                                pr_match = re.search(r'https://github\.com/[^/]+/[^/]+/pull/\d+', str(tool_content))
                                if pr_match:
                                    pr_url = pr_match.group(0)
                                    print(f"[SDK] Extracted PR URL from regex: {pr_url}", flush=True)
                        
                        if pr_url and pr_url not in prs_created:
                            prs_created.append(pr_url)
                            emit_now(self.emit(WSEvent(type=EventType.PR_CREATED, data={"repo": self.current_repo, "pr_url": pr_url})))
                            emit_now(self.log(f"🔗 PR created: {pr_url}", "success"))
                        else:
                            print(f"[SDK] No PR URL found in tool result", flush=True)
                        
                        emit_now(self.emit(WSEvent(type=EventType.REPO_COMPLETE, data={"repo": self.current_repo})))
                
                elif event_type == "session.idle":
                    print("[SDK] Session idle - done", flush=True)
                    done_event.set()
                
                elif event_type in ("error", "session.error"):
                    print(f"[SDK] Error: {event.data}", flush=True)
                    emit_now(self.log(f"Error: {event.data}", "error"))
                    done_event.set()
            
            # Heartbeat task for long-running tools (emits directly)
            async def heartbeat_emitter():
                """Emit periodic elapsed time updates for long-running operations."""
                last_emit_time = {}  # tool_name -> last emit timestamp
                
                while not done_event.is_set():
                    await asyncio.sleep(5)  # Check every 5 seconds
                    
                    for tool_name in list(long_running_tools):
                        if tool_name not in long_running_start_times:
                            continue
                        
                        elapsed = int(time.time() - long_running_start_times[tool_name])
                        last = last_emit_time.get(tool_name, 0)
                        
                        # Only emit every 10 seconds
                        if elapsed - last >= 10:
                            await self.log(f"  ⏳ [{elapsed}s elapsed]", "info")
                            last_emit_time[tool_name] = elapsed
            
            heartbeat_task = asyncio.create_task(heartbeat_emitter())
            
            session.on(on_event)
            
            await self.log("Sending prompt to Copilot SDK...")
            await self.log("Agent is thinking... (this may take 10-30 seconds)", "info")
            
            # Run session.send() as a task while heartbeat runs in parallel
            # Events are emitted directly via emit_now() from the on_event callback
            send_task = asyncio.create_task(session.send({"prompt": user_input}))
            
            # Wait for completion (done_event is set when SDK sends "done" event)
            try:
                await asyncio.wait_for(done_event.wait(), timeout=600.0)
            except asyncio.TimeoutError:
                await self.log("Agent timeout (10 minutes)", "warning")
            
            # Wait for send to complete
            try:
                await send_task
            except Exception as e:
                print(f"[SDK] Send task error: {e}", flush=True)
            
            # Cancel heartbeat
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            
            await session.destroy()
            
            # Check created_prs from file (tool handler writes PRs there)
            file_prs = get_created_prs()
            print(f"[SDK] Checking created_prs from file: {file_prs}", flush=True)
            for pr_info in file_prs:
                pr_url = pr_info.get("pr_url")
                print(f"[SDK] Found PR in file: {pr_url}", flush=True)
                if pr_url and pr_url not in prs_created:
                    prs_created.append(pr_url)
                    await self.emit(WSEvent(type=EventType.PR_CREATED, data={"repo": self.current_repo, "pr_url": pr_url}))
                    await self.log(f"🔗 PR created: {pr_url}", "success")
            
            # Emit completion
            await self.emit(WSEvent(
                type=EventType.AGENT_COMPLETE,
                data={
                    "tool_calls": tool_call_count,
                    "prs_created": prs_created,
                    "repos_processed": len(repos)
                }
            ))
            
            await self.log(f"Agent complete: {tool_call_count} tool calls, {len(prs_created)} PRs created", "success")
            
        finally:
            await client.stop()


# =============================================================================
# FastAPI App
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    print("Fleet Compliance Agent Backend starting...")
    yield
    print("Backend shutting down...")


app = FastAPI(
    title="Fleet Compliance Agent",
    description="Backend for Fleet Compliance Agent UI",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
async def get_status():
    """Get system status."""
    return check_system_status()


@app.get("/api/repos")
async def get_repos():
    """Get fleet repositories."""
    return get_fleet_repos()


@app.websocket("/ws/agent")
async def websocket_agent(websocket: WebSocket):
    """WebSocket endpoint for agent execution with streaming."""
    global _active_websocket, _active_emitter, _agent_running
    
    await websocket.accept()
    print("[WS] WebSocket connection accepted", flush=True)
    
    # Update global reference
    _active_websocket = websocket
    
    # If agent is already running, update the emitter's websocket reference
    if _agent_running and _active_emitter:
        print("[WS] Agent already running - updating WebSocket reference", flush=True)
        _active_emitter.update_websocket(websocket)
        emitter = _active_emitter
    else:
        emitter = AgentEventEmitter(websocket)
        _active_emitter = emitter
    
    try:
        # Send initial status
        status = check_system_status()
        await emitter.emit(WSEvent(
            type=EventType.SYSTEM_STATUS,
            data=status
        ))
        
        # Wait for start command
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            print(f"[WS] Received message: {message}", flush=True)
            
            if message.get("action") == "start":
                repos = message.get("repos", [])
                print(f"[WS] Start requested with repos: {repos}", flush=True)
                if _agent_running:
                    await emitter.emit(WSEvent(
                        type=EventType.ERROR,
                        data={"message": "Agent is already running"}
                    ))
                elif repos:
                    try:
                        print(f"[WS] Calling run_agent...", flush=True)
                        _agent_running = True
                        await emitter.run_agent(repos)
                        print(f"[WS] run_agent completed", flush=True)
                    except Exception as e:
                        import traceback
                        error_msg = f"Agent error: {e}\\n{traceback.format_exc()}"
                        print(f"[WS] ERROR: {error_msg}", flush=True)
                        await emitter.emit(WSEvent(
                            type=EventType.ERROR,
                            data={"message": str(e)}
                        ))
                    finally:
                        _agent_running = False
                else:
                    await emitter.emit(WSEvent(
                        type=EventType.ERROR,
                        data={"message": "No repositories specified"}
                    ))
            
            elif message.get("action") == "status":
                status = check_system_status()
                await emitter.emit(WSEvent(
                    type=EventType.SYSTEM_STATUS,
                    data=status
                ))
    
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        await emitter.emit(WSEvent(
            type=EventType.ERROR,
            data={"message": str(e)}
        ))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
