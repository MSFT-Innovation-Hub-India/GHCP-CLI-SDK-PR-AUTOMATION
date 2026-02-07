# Fleet Compliance Agent Demo

**Demonstrating GitHub Copilot CLI/SDK Integration for Enterprise Fleet Management**

This demo showcases a Python-based compliance agent that automatically enforces organizational policies across a fleet of microservices using GitHub Copilot [CLI SDK](https://github.com/github/copilot-sdk) capabilities.

---

## 💡 From Interactive CLI to Programmable Agent

**GitHub Copilot CLI** is typically used for interactive, natural language conversations - a developer types a question and gets a response. But what if you could harness that same AI capability **programmatically**?

The **GitHub Copilot CLI SDK** unlocks exactly this. By exposing the Copilot CLI through a Python SDK, it transforms from a conversational tool into a **programmable agent brain**.

**The Key Insight:** Instead of a human typing prompts, this demo shows how **code can drive the conversation** - sending structured prompts to the SDK, registering custom tools, and letting the SDK autonomously decide the execution path.

```python
# The SDK becomes the "brain" - you register tools, it decides when to call them
session = await client.create_session({
    "system_message": {"content": SYSTEM_PROMPT},
    "tools": [clone_tool, detect_drift_tool, apply_patches_tool, ...],
})
await session.send({"prompt": "Enforce compliance on contoso-payments-api"})
# SDK autonomously calls tools, reasons over results, and completes the workflow
```

This pattern enables **enterprise automation scenarios** that would be impossible with interactive CLI usage alone.

---

## 🎯 What This Demo Demonstrates

### SDK & AI Capabilities

| Capability | How It's Used | Implementation |
|------------|---------------|----------------|
| **SDK as Orchestrating Agent** | Copilot SDK is the "brain" that drives the entire compliance workflow end-to-end | SDK receives a single prompt, then autonomously executes all steps |
| **Autonomous Tool Calling** | SDK decides which tools to invoke based on the task | 11 custom tools registered with the SDK |
| **Function Calling** | Tools return structured JSON that the SDK reasons over | Each tool returns `ToolResult` with JSON payload |
| **MCP Server Integration** | External services for approvals and security scans | Change Mgmt (port 4101), Security (port 4102) |
| **RAG (Retrieval-Augmented Generation)** | Policy evidence grounded in organizational knowledge | Azure OpenAI Vector Store with file_search |
| **Multi-Step Reasoning** | SDK chains tools: clone → analyze → patch → test → PR | Event-driven workflow with state tracking |
| **Real-Time Event Streaming** | Live UI updates as agent executes | WebSocket events via `asyncio.run_coroutine_threadsafe` |

### Compliance Domain Features

| Feature | Description | Policy Reference |
|---------|-------------|------------------|
| **Fleet-Wide Enforcement** | Automate compliance across multiple repos | - |
| **Health Endpoint Detection** | Identify missing `/healthz` and `/readyz` endpoints | OPS-2.1 |
| **Structured Logging** | Detect and add structlog configuration | OBS-1.1 |
| **Trace Propagation** | Add middleware for W3C traceparent correlation | OBS-3.2 |
| **Security Vulnerability Scanning** | Scan dependencies for CVEs (Common Vulnerabilities and Exposures) via MCP server | SEC-2.4 |
| **Risk-Aware Approvals** | Route PRs to appropriate approvers based on service tier | CM-7 |
| **Evidence-Backed PRs** | Include policy citations in PR descriptions | REL-1.0 |

---

## 🔄 How the Agent Works (Complete Workflow)

Understanding when each step happens is critical. The agent works in **three phases**:

### Phase 1: Discovery & Analysis (BEFORE any code changes)

| Step | Tool | What Happens |
|------|------|--------------|
| 1 | `rag_search` | Search knowledge base for policy requirements (health endpoints, logging, security) |
| 2 | `clone_repository` | Clone the target repo to local workspace |
| 3 | `detect_compliance_drift` | **Scan ORIGINAL code** - check if `/healthz`, `/readyz`, structlog, middleware exist |
| 4 | `security_scan` | **Scan ORIGINAL requirements.txt** via Security MCP server for CVE vulnerabilities |

**At this point: No code has been changed. We've only analyzed what's wrong.**

### Phase 2: Code Modification (MAKING changes)

| Step | Tool | What Happens |
|------|------|--------------|
| 5 | `create_branch` | Create feature branch `chore/fleet-compliance-{timestamp}` |
| 6 | `apply_compliance_patches` | **NOW code is modified** using Copilot SDK |
| | | → Creates: `middleware.py`, `logging_config.py`, `tests/test_health.py` |
| | | → Modifies: `main.py` (adds endpoints), `requirements.txt` (adds structlog) |
| | | → Returns list of modified files |

### Phase 3: Validation & Approval (AFTER code changes)

| Step | Tool | What Happens |
|------|------|--------------|
| 7 | `get_required_approvals` | **Send MODIFIED file list** to Change Mgmt MCP to determine approvers |
| 8 | `run_tests` | **Run pytest on MODIFIED code** to validate changes |
| 8a | `read_file` + `fix_code` | If tests fail → examine code, apply fix, retry (max 3 times) |
| 9 | `commit_changes` | Commit all modifications |
| 10 | `push_branch` | Push branch to GitHub |
| 11 | `create_pull_request` | Open PR with policy evidence, vulnerability report, approval labels |

### Visual Timeline

```
ORIGINAL CODE                              MODIFIED CODE
     │                                          │
     ▼                                          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  clone → detect_drift → security_scan    │   apply_patches → run_tests  │
│         (analyze original)               │   (modify & validate)        │
│                                          │                              │
│  ◄────── BEFORE changes ──────►          │  ◄────── AFTER changes ─────►│
└──────────────────────────────────────────────────────────────────────────┘
                                       ▲
                                       │
                                 Branch created
                                 Code modified here
```

### Concrete Example: contoso-payments-api

```
Steps 1-2: Clone repo
           Original state: basic FastAPI, no /healthz, no structlog, requests==2.19.0

Step 3:    detect_compliance_drift on ORIGINAL code
           → "Missing: /healthz, /readyz, structlog, middleware"

Step 4:    security_scan on ORIGINAL requirements.txt
           → "Found CVE-2018-18074 in requests==2.19.0" (vulnerability reported, NOT auto-fixed)

Step 5:    create_branch "chore/fleet-compliance-xxx"

Step 6:    apply_compliance_patches MODIFIES the code
           → Creates middleware.py, logging_config.py
           → Adds endpoints to main.py
           → Adds structlog to requirements.txt
           → Returns: ["app/main.py", "app/middleware.py", "app/logging_config.py", 
                       "requirements.txt", "tests/test_health.py"]

Step 7:    get_required_approvals with THOSE MODIFIED FILES
           → "payments" in service name → requires SRE-Prod approval
           → Returns: required_approvals=["SRE-Prod"], risk_level="high"

Step 8:    run_tests on MODIFIED code
           → pytest validates /healthz, /readyz endpoints work

Steps 9-11: commit → push → create PR
           PR description includes:
           - Compliance drift that was detected (from step 3)
           - Vulnerabilities found (from step 4) - reported but NOT auto-fixed
           - Files changed (from step 6)
           - Required approvers as labels (from step 7)
           - Test results (from step 8)
```

---

## ⚡ Getting Started (Windows)

> **Important:** These instructions are for **Windows** machines. Commands use PowerShell syntax.

### Prerequisites Checklist

Before you begin, ensure you have the following:

| Requirement | Purpose | Verification |
|-------------|---------|--------------|
| **Python 3.11+** | Agent and MCP server runtime | `python --version` |
| **Node.js 18+** | Frontend and Copilot CLI | `node --version` |
| **Git** | Repository operations | `git --version` |
| **GitHub CLI** | PR creation, repo management | `gh --version` |
| **Azure CLI** | Azure authentication (for RAG) | `az --version` |
| **GitHub Copilot License** | Required for Copilot SDK | Check GitHub account |
| **GitHub Copilot CLI** | SDK dependency | `npm list -g @anthropic-ai/copilot` |

### Azure Requirements

This project uses **Azure OpenAI's native Vector Store** (via the OpenAI-compatible API), **NOT** Azure AI Search or Azure AI Foundry indexes. Search is not accessible directly by API (which OpenAI API supports), but only through Responses API, hence an LLM is required 

| Resource | Purpose |
|----------|---------|
| **Azure OpenAI Service** | Hosts the model and vector store |
| **Model Deployment** (e.g., `gpt-4o`) | Required for Responses API with `file_search`. |
| **Vector Store** | Stores policy documents for RAG search |

**RBAC Requirements:** The user running this demo must have:
- `Cognitive Services OpenAI User` role on the Azure OpenAI resource
- Permissions to create vector stores and upload files (refer to [Azure OpenAI documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/))

---

### Step-by-Step Setup

#### Step 0: Clone This Repository

```powershell
git clone https://github.com/MSFT-Innovation-Hub-India/GHCP-CLI-SDK-PR-AUTOMATION.git
cd ghcp-cli-sdk-sample1
```

#### Step 1: Create Target Repositories

The agent operates on **external GitHub repositories**. Create 3 repos from the sample code:

> **Note:** These sample APIs intentionally contain compliance gaps that the agent will detect and remediate:
> - Missing `/healthz` and `/readyz` health endpoints
> - No structured logging (uses `print()` statements)
> - No request correlation middleware for tracing
> - Outdated dependencies with known vulnerabilities (payments API)
>
> The agent will audit these repositories, detect the issues, apply fixes, and create Pull Requests.

```powershell
# For each API in sample-repos/, create a GitHub repo and push:
cd sample-repos\contoso-orders-api
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/contoso-orders-api.git
git push -u origin main
cd ..\..

# Repeat for contoso-payments-api and contoso-catalog-api
```

Then update `agent/config/repos.json`:
```json
{
  "repos": [
    "https://github.com/YOUR_USERNAME/contoso-orders-api.git",
    "https://github.com/YOUR_USERNAME/contoso-payments-api.git",
    "https://github.com/YOUR_USERNAME/contoso-catalog-api.git"
  ]
}
```

#### Step 2: Authenticate with Azure and GitHub

```powershell
# Azure - must be logged into the subscription with your Azure OpenAI resource
az login
az account set --subscription "YOUR_SUBSCRIPTION_NAME"

# GitHub CLI - must have Copilot access
gh auth login
```

#### Step 3: Configure Environment

```powershell
# Copy the example environment file
cd agent
copy .env.example .env
```

Edit `agent/.env` with your Azure OpenAI details:
```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://YOUR_RESOURCE.openai.azure.com/openai/v1/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_VECTOR_STORE_ID=   # Will be set by deploy script

# Copilot CLI path (find with: where.exe copilot)
COPILOT_CLI_PATH=C:\Users\YOUR_USERNAME\AppData\Roaming\npm\copilot.cmd

# MCP Server URLs (defaults)
CHANGE_MGMT_URL=http://localhost:4101
SECURITY_URL=http://localhost:4102
```

#### Step 4: Create Python Virtual Environments

Create a virtual environment in **each** of these folders:

```powershell
# MCP Change Management Server
cd mcp\change_mgmt
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
deactivate
cd ..\..

# MCP Security Server
cd mcp\security
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
deactivate
cd ..\..

# Agent (includes github-copilot-sdk)
cd agent
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
deactivate
cd ..
```

**Key Dependency:** The agent requires `github-copilot-sdk>=0.1.21` which is the core of this project.

#### Step 5: Deploy Vector Store with Policy Documents

Upload the knowledge base files to Azure OpenAI:

```powershell
# Activate agent venv (has required dependencies)
cd agent
.venv\Scripts\Activate.ps1

# Run the deployment script
python ..\scripts\deploy-vector-store.py

# This will:
# 1. Create a vector store named "fleet-compliance-knowledge"
# 2. Upload all .md files from knowledge/ folder
# 3. Update agent/.env with the AZURE_OPENAI_VECTOR_STORE_ID

deactivate
cd ..
```

#### Step 6: Install Frontend Dependencies

```powershell
cd ui\frontend
npm install
cd ..\..
```

---

### Running the Demo

Open **4 separate PowerShell terminals**:

**Terminal 1 - Change Management MCP Server:**
```powershell
cd mcp\change_mgmt
.venv\Scripts\Activate.ps1
uvicorn server:app --host 0.0.0.0 --port 4101
```

**Terminal 2 - Security MCP Server:**
```powershell
cd mcp\security
.venv\Scripts\Activate.ps1
uvicorn server:app --host 0.0.0.0 --port 4102
```

**Terminal 3 - FastAPI Backend:**
```powershell
cd ui\backend
..\..\agent\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Terminal 4 - React Frontend:**
```powershell
cd ui\frontend
npm run dev
```

**Open in browser:** http://localhost:3000 (or the port shown by Vite)

---

### What Happens on Each Run

- A **new workspace directory** is created for each repository: `agent/workspaces/contoso-orders-api-Xa7kM2/`
- All code analysis, patching, and testing happens in this isolated workspace
- Workspaces persist after the run for debugging (manually delete to clean up)
- Workspaces are in `.gitignore` and not committed

---

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `copilot: command not found` | Set `COPILOT_CLI_PATH` in `.env` to full path |
| `DefaultAzureCredential failed` | Run `az login` and ensure correct subscription |
| `Vector store not found` | Run `deploy-vector-store.py` script |
| `Connection refused :4101/:4102` | Ensure MCP servers are running |
| `gh: not logged in` | Run `gh auth login` |

---

## 🏢 From POC to Production

This demo implements a pattern that is **directly applicable to enterprise production environments**. The underlying use case - automated compliance enforcement via AI agents - is increasingly common in platform engineering and DevSecOps.

**Limitations of the Solution:**
- Single-user, single-machine execution
- No persistent state between runs
- No authentication/authorization
- No job queuing or scheduling
- No audit trail or compliance reporting

### Related Industry Patterns

This demo aligns with established patterns in platform engineering:

| Pattern/Tool | Description |
|--------------|-------------|
| **Backstage (Spotify OSS)** | Open-source developer portal with plugin ecosystem for automation |
| **Dependabot / Renovate** | Automated dependency update PRs at scale |
| **GitHub Advanced Security** | Automated security alerts and remediation suggestions |
| **Policy-as-Code (OPA, Kyverno)** | Declarative policy enforcement in CI/CD |
| **Internal Developer Platforms** | Self-service portals with guardrails (industry trend) |

The approach of **"automation proposes, human approves"** is an established GitOps pattern - maintaining human oversight while scaling operations. AI-powered agents extend this pattern by adding reasoning capabilities for complex, context-dependent decisions.

> **Note:** This demo is a proof-of-concept. The specific implementation of AI agents for compliance is an emerging practice; references to industry patterns above are to related (not identical) automation approaches.

---

## �🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         FLEET COMPLIANCE AGENT                               │
├──────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │              🖥️ Visual UI Mode (React + FastAPI)                     │   │
│  │  ┌─────────────────┐    WebSocket    ┌─────────────────┐             │    │
│  │  │  React Frontend │◄───────────────►│ FastAPI Backend │             │    │
│  │  │  localhost:3001 │   (streaming)   │  localhost:8000 │             │    │
│  │  └─────────────────┘                 └────────┬────────┘             │    │
│  └───────────────────────────────────────────────┼──────────────────────┘    │
│                                                  │ imports                   │
│                                                  ▼                           │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │              🧠 Agent Core (agent_loop.py)                            │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │  │
│  │  │   GitHub    │    │  Knowledge  │    │   Copilot   │                 │  │
│  │  │   Repos     │    │    Base     │    │    SDK      │                 │  │
│  │  │  (Target)   │    │   (RAG)     │    │ (Agent Brain)│                │  │
│  │  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                 │  │
│  │         │                  │                  │                        │  │
│  │         ▼                  ▼                  ▼                        │  │
│  │  ┌─────────────────────────────────────────────────────────────┐       │  │
│  │  │          11 CUSTOM TOOLS (Registered with SDK)              │       │  │
│  │  │  rag_search → clone → detect_drift → security_scan →        │       │  │
│  │  │  create_branch → apply_patches → get_approvals →            │       │  │
│  │  │  run_tests → commit → push → create_pull_request            │       │  │
│  │  └───────────────────────────┬─────────────────────────────────┘       │  │
│  └──────────────────────────────┼─────────────────────────────────────────┘  │
│                                 │                                            │
│         ┌───────────────────────┼────────────────────┐                       │
│         ▼                       ▼                    ▼                       │
│  ┌─────────────┐          ┌─────────────┐      ┌─────────────┐               │
│  │ Change Mgmt │          │  Security   │      │   GitHub    │               │
│  │ MCP Server  │          │ MCP Server  │      │     CLI     │               │
│  │ (Approvals) │          │   (Scans)   │      │   (PRs)     │               │
│  └─────────────┘          └─────────────┘      └─────────────┘               │
│     :4101                    :4102                 gh                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Component Details

| Component | Purpose |
|-----------|---------|
| **React UI** | Visual dashboard with real-time streaming, per-repo checklists |
| **FastAPI Backend** | WebSocket server wrapping agent_loop.py for event streaming |
| **Agent Core** | Orchestrates the compliance workflow |
| **Knowledge Base** | Markdown policy documents searchable via RAG |
| **Change Mgmt MCP** | Evaluates approval requirements per CM-7 matrix |
| **Security MCP** | Scans dependencies for CVE vulnerabilities |
| **GitHub CLI** | Clones repos, creates branches, opens PRs |
| **Copilot SDK** | AI-powered PR descriptions (optional) |

---

## 📁 Project Structure

```
ghcp-cli-sdk-sample1/
├── agent/                      # Fleet compliance agent
│   ├── config/
│   │   └── repos.json          # Target repositories
│   ├── fleet_agent/
│   │   ├── __init__.py         
│   │   ├── agent_loop.py       # Main agentic entry point (SDK-driven)
│   │   ├── github_ops.py       # Git/GitHub operations
│   │   ├── mcp_clients.py      # MCP server clients
│   │   ├── patcher_fastapi.py  # Code patching logic
│   │   └── rag.py              # Knowledge base search (Azure OpenAI)
│   ├── test_sdk_response.py    # SDK response parsing tests
│   ├── requirements.txt
│   └── .env.example
│
├── knowledge/                  # Policy documents (RAG source)
│   ├── OBS-1.1-structured-logging.md
│   ├── OBS-3.2-trace-propagation.md
│   ├── OPS-2.1-health-readiness.md
│   ├── CM-7-approval-matrix.md
│   ├── SEC-2.4-dependency-vulnerability-response.md
│   └── REL-1.0-pr-gates.md
│
├── mcp/                        # MCP servers
│   ├── change_mgmt/            # Approval matrix evaluation
│   │   ├── server.py
│   │   └── requirements.txt
│   └── security/               # Vulnerability scanning
│       ├── server.py
│       └── requirements.txt
│
├── sample-repos/               # Demo target repos (hosted separately - see below)
│   ├── contoso-catalog-api/
│   ├── contoso-orders-api/
│   └── contoso-payments-api/
│
├── scripts/                    # Helper scripts
│   ├── deploy-vector-store.py  # Deploy Azure OpenAI vector store
│   └── push-sample-repos.ps1   # Push samples to GitHub
│
├── ui/                         # Visual UI (React + FastAPI)
│   ├── frontend/               # React app with Vite + Tailwind
│   │   ├── src/App.tsx         # Main UI component
│   │   └── package.json
│   ├── backend/                # FastAPI WebSocket server
│   │   └── main.py             # Event streaming wrapper
│   └── README.md               # UI-specific documentation
│
├── docs/                       # Architecture documentation
│   └── ARCHITECTURE_FLOW.md    # Detailed flow diagrams
│
├── DEMO_CHECKLIST.md           # Demo presentation guide
└── README.md                   # This file
```

---

## 📜 Policy ID Naming Conventions

The knowledge base policy documents use IDs inspired by real compliance frameworks:

| Prefix | Category | Inspired By |
|--------|----------|-------------|
| **CM** | Configuration Management | NIST 800-53 (CM controls) |
| **OBS** | Observability | SRE/DevOps practices |
| **OPS** | Operations | SRE/Platform operations |
| **REL** | Reliability | Google SRE, AWS Well-Architected |
| **SEC** | Security | NIST, SOC 2, CIS Controls |

The numbering follows a `Category.Control` pattern (e.g., `OBS-1.1`, `SEC-2.4`) common in enterprise GRC (Governance, Risk, Compliance) tools.

---

## 🎯 Sample Target Repositories

The sample FastAPI microservices used as compliance targets are hosted in separate GitHub repositories:

| Repository | Description | GitHub |
|------------|-------------|--------|
| **contoso-orders-api** | Order management service | [ssrikantan/contoso-orders-api](https://github.com/ssrikantan/contoso-orders-api) |
| **contoso-payments-api** | Payment processing service (high-impact) | [ssrikantan/contoso-payments-api](https://github.com/ssrikantan/contoso-payments-api) |
| **contoso-catalog-api** | Product catalog service | [ssrikantan/contoso-catalog-api](https://github.com/ssrikantan/contoso-catalog-api) |

> **Note:** These repos are excluded from this repository via `.gitignore`. Clone them separately or use the `push-sample-repos.ps1` script to create your own copies.

---


### UI Layout

The UI features a **three-panel layout** optimized for demos:

| Panel | Location | Description |
|-------|----------|-------------|
| **Control + Tool Calls** | Left | Repo selector dropdown, run button, checklist, tool call history |
| **Agent Reasoning** | Center | Streaming agent messages with markdown tables |
| **Console Logs** | Right | Real-time timestamped logs with emoji indicators |

### Key UI Features

- **Single Repo Selector**: Dropdown to select one repository at a time (ideal for focused demos)
- **Initialization Overlay**: Shows "Initializing..." state on startup instead of red error indicators
- **Real-time Streaming**: Events appear in UI immediately as they happen (no batching)
- **PR URL Display**: Clickable links to created PRs appear in a dedicated section
- **Per-Repo Checklist**: Step-by-step progress tracking with visual indicators

### WebSocket Event Types

The backend streams these events via WebSocket (`ws://localhost:8000/ws/agent`):

| Event | Description |
|-------|-------------|
| `agent_start` | Agent execution begins |
| `tool_call_start` | Tool invocation with name and arguments |
| `tool_call_complete` | Tool finished with call_number for tracking |
| `agent_message` | Agent reasoning/message (supports markdown) |
| `checklist_update` | Per-repo step completion |
| `repo_start` / `repo_complete` | Repository processing boundaries |
| `pr_created` | PR URL captured (clickable in UI) |
| `console_log` | Streaming log with level (info/success/warning/error) |

---

## ⚙️ Implementation Details

### True Agentic Architecture

The agent uses the **GitHub Copilot SDK as the autonomous decision-making brain**:

```python
from copilot import CopilotClient
from copilot.types import Tool, ToolResult

# Tools are registered with the SDK
tools = [rag_search_tool, clone_tool, detect_drift_tool, ...]

# SDK creates session with custom tools (model is Copilot's backend, not specified)
session = await client.create_session({
    "system_message": {"content": SYSTEM_PROMPT},
    "tools": tools,
    "available_tools": [t.name for t in tools],  # Whitelist
})

# SDK autonomously decides which tools to call
session.on(event_handler)  # Receive tool calls and messages
await session.send({"prompt": user_input})
```

**Key Design Decisions:**
- **SDK as Brain**: The Copilot SDK (not hardcoded workflow) decides tool order
- **11 Custom Tools**: Each tool returns `ToolResult` with JSON for LLM reasoning
- **Event-Based**: Tool execution events stream to UI via queue
- **Whitelist Approach**: `available_tools` ensures only custom tools are used

### Event Streaming Architecture

The UI uses **direct event emission** for real-time streaming without queue delays:

```
┌─────────────────────────────────────────────────────────────────┐
│  SDK Event Callback (on_event)                                  │
│  └─► Synchronous, called from SDK thread                        │
│      └─► emit_now(coro)  # Uses asyncio.run_coroutine_threadsafe│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (immediate, no queue)
┌─────────────────────────────────────────────────────────────────┐
│  WebSocket Emit                                                 │
│  └─► await websocket.send_json(event)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  React Frontend                                                 │
│  └─► useEffect WebSocket listener                               │
│      └─► setState updates → UI re-render                        │
└─────────────────────────────────────────────────────────────────┘
```

**Key insight:** Using `asyncio.run_coroutine_threadsafe(coro, loop)` allows synchronous SDK callbacks to emit events directly to the async WebSocket, ensuring real-time updates without buffering.

### Tool Call Tracking

Tool calls are tracked by `call_id` for reliable completion matching:

```python
# On tool.execution_start
call_id = getattr(event.data, 'call_id', None)
active_tool_calls[call_id] = tool_name
tool_call_count += 1

# On tool.execution_complete
tool_name = active_tool_calls.pop(call_id, None)
emit_now(self.emit(WSEvent(type=EventType.TOOL_CALL_COMPLETE, data={"tool": tool_name})))
```

### PR URL Capture

When a PR is created, the URL is captured from `gh pr create` output:

```python
# github_ops.py - open_pr returns the PR URL
pr_url = _run(["gh", "pr", "create", "--base", base, "--head", head, ...])
# Returns: https://github.com/org/repo/pull/123

# agent_loop.py - PR URL is logged and tracked
log_created_pr(repo_url, pr_url, title)  # File-based tracking
print(f"[PR_CREATED] {pr_url}")  # Console marker

# main.py - Backend emits to UI
emit_now(self.emit(WSEvent(type=EventType.PR_CREATED, data={"pr_url": pr_url})))
```

The UI displays clickable PR links in the left panel after the agent completes.

### Heartbeat for Long-Running Tools

Long-running operations (tests, patches, scans) emit periodic elapsed time:

```python
long_running_tools = {"run_tests", "apply_compliance_patches", "security_scan"}

async def heartbeat_emitter():
    while not done_event.is_set():
        await asyncio.sleep(5)
        for tool_name in long_running_tools:
            if tool_name in long_running_start_times:
                elapsed = int(time.time() - long_running_start_times[tool_name])
                if elapsed % 10 == 0:  # Every 10 seconds
                    event_queue.put(("log", (f"  ⏳ [{elapsed}s elapsed]", "info")))
```

### Checklist Per-Repository

Each repository has independent checklist state, captured at queue time:

```python
# Checklist update captures repo at queue time (not processing time)
if tool_name in tool_checklist_map:
    event_queue.put(("checklist", (
        tool_checklist_map[tool_name],  # e.g., "clone"
        "running",
        self.current_repo  # Captured NOW, not later
    )))
```

---

## �🔧 Customization Points

| What to Customize | Location |
|-------------------|----------|
| Target repos | `agent/config/repos.json` |
| Policy documents | `knowledge/*.md` |
| Approval rules | `mcp/change_mgmt/server.py` |
| Vulnerability DB | `mcp/security/server.py` |
| Patching logic | `agent/fleet_agent/patcher_fastapi.py` |
| Agent tools | `agent/fleet_agent/agent_loop.py` |

---

## 🤖 Copilot SDK Integration

The agent integrates with the official [GitHub Copilot SDK](https://github.com/github/copilot-sdk) for AI-generated PR descriptions.

> **⚠️ Preview SDK Notice**
>
> The GitHub Copilot SDK is currently in **preview**. This demo uses version `github-copilot-sdk>=0.1.21` (see `agent/requirements.txt`).
>
> **SDK Dependencies:**
> - The SDK depends on the **GitHub Copilot CLI** (`gh copilot` extension)
> - The user must be signed in via `gh auth login` with Copilot access
> - The SDK communicates with Copilot CLI via JSON-RPC over stdio
> - Authentication uses the **local user's GitHub credentials** (not API keys)

### Installation

```powershell
# Install the Python SDK
pip install github-copilot-sdk

# The SDK requires the Copilot CLI (already installed via npm)
npm install -g @anthropic-ai/copilot
```

### How It Works

The SDK communicates with the Copilot CLI via JSON-RPC over stdio. Here's how it's used in `agent_loop.py`:

```python
# agent/fleet_agent/agent_loop.py

import asyncio
from copilot import CopilotClient
from copilot.types import Tool, ToolResult

async def run_agent(user_input: str):
    """Run the agent with custom tools - SDK is the brain."""
    client = CopilotClient()
    await client.start()
    
    # Create session with 11 custom tools
    tools = create_tools()  # rag_search, clone, detect_drift, etc.
    session = await client.create_session({
        "system_message": {"content": SYSTEM_PROMPT},
        "tools": tools,
        "available_tools": [t.name for t in tools],
    })
    
    done = asyncio.Event()
    
    def on_event(event):
        if event.type.value == 'tool.execution_start':
            # SDK decided to call a tool
            tool_name = event.data.tool_name
        elif event.type.value == 'assistant.message':
            # SDK reasoning/response (includes PR descriptions)
            content = event.data.content
        elif event.type.value == 'session.idle':
            done.set()
    
    session.on(on_event)
    await session.send({'prompt': user_input})
    await asyncio.wait_for(done.wait(), timeout=600)
    
    await session.destroy()
    await client.stop()
```

### Configuration

| Environment Variable | Purpose | Default |
|---------------------|---------|---------|
| `COPILOT_CLI_PATH` | Path to CLI binary (Windows) | Auto-detect |
| `COPILOT_MODEL` | Model to use | `gpt-4o` |

### Windows Path Configuration

On Windows, you may need to explicitly set the CLI path:

```env
# In agent/.env
COPILOT_CLI_PATH=C:\Users\YOUR_USERNAME\AppData\Roaming\npm\copilot.cmd
```

Find your path:
```powershell
(Get-Command copilot).Source
# Or check: %APPDATA%\npm\copilot.cmd
```

### Agentic Architecture

The agent uses a **TRUE agentic approach** where the Copilot SDK is always the brain:
- The SDK autonomously decides which tools to call
- PR descriptions are generated by the SDK through the `create_pull_request` tool
- No separate mode switching needed - the SDK is integral to the architecture

---

## 📊 MCP Server APIs

### Change Management (Port 4101)

```bash
# Evaluate approvals
curl -X POST http://localhost:4101/approval \
  -H "Content-Type: application/json" \
  -d '{"service": "contoso-payments-api", "touched_paths": ["app/auth.py"]}'

# Response
{
  "required_approvals": ["SRE-Prod", "Security"],
  "rationale": "High-impact service; Security-sensitive files modified",
  "risk_level": "high",
  "sla_hours": 4
}
```

### Security Scan (Port 4102)

```bash
# Scan dependencies
curl -X POST http://localhost:4102/scan \
  -H "Content-Type: application/json" \
  -d '{"requirements": "requests==2.19.0\npyyaml==5.1"}'

# Response
{
  "findings": [
    {"name": "requests", "cve": "CVE-2018-18074", "severity": "HIGH", "fixed_version": "2.20.0"},
    {"name": "pyyaml", "cve": "CVE-2020-14343", "severity": "CRITICAL", "fixed_version": "6.0.1"}
  ],
  "policy_compliant": false
}
```

---

## 📝 Demo Script (5-8 minutes)

See [DEMO_CHECKLIST.md](./DEMO_CHECKLIST.md) for the presentation guide.

**Key talking points:**
1. Show a sample repo **before** (missing compliance features)
2. Show the knowledge base policies
3. Run the agent
4. Show PRs created with evidence and labels
5. Highlight the Copilot SDK integration point

---

## 🔗 Related Resources

- [GitHub Copilot CLI Documentation](https://docs.github.com/en/copilot/github-copilot-in-the-cli)
- [GitHub Copilot SDK (Python)](https://github.com/github/copilot-sdk)
- [MCP (Model Context Protocol) Specification](https://modelcontextprotocol.io/)
- [Azure OpenAI Responses API](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/responses)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## 🐛 Troubleshooting

### Copilot CLI Not Found

**Error:** `FileNotFoundError: copilot` or SDK fails to start

**Solution (Windows):**
1. Find the CLI path:
   ```powershell
   where.exe copilot
   # Or: C:\Users\<username>\AppData\Roaming\npm\copilot.cmd
   ```
2. Add to `.env`:
   ```env
   COPILOT_CLI_PATH=C:\Users\YOUR_USERNAME\AppData\Roaming\npm\copilot.cmd
   ```

### Vector Store Not Found

**Error:** `Could not find vector store with id vs_xxxx`

**Causes:**
- Using a Foundry/AI Search index instead of native OpenAI vector store
- Wrong vector store ID

**Solution:**
Create a native vector store via the OpenAI API (not Azure AI Foundry):
```powershell
# Use POST /openai/v1/vector_stores endpoint
# NOT the Foundry index management
```

### Azure Authentication Failed

**Error:** `DefaultAzureCredential failed to retrieve a token`

**Solution:**
```powershell
# Login to Azure
az login

# Verify account
az account show
```

### GitHub Label Not Found

**Error:** `Error adding label: compliance`

**Solution:** The agent now auto-creates missing labels. If issues persist:
```powershell
gh label create compliance --description "Compliance-related PR" --color "0E8A16"
gh label create needs-sre-approval --description "Requires SRE approval" --color "D93F0B"
gh label create needs-security-approval --description "Requires Security approval" --color "B60205"
```

### MCP Server Connection Refused

**Error:** `Connection refused localhost:4101`

**Solution:**
1. Verify servers are running:
   ```powershell
   Get-Process | Where-Object { $_.ProcessName -eq "python" }
   ```
2. Check ports:
   ```powershell
   netstat -an | findstr "4101 4102"
   ```
3. Restart servers manually (see Running the Demo section above)

---

## 📄 License

This demo is provided for educational purposes. See LICENSE for details.
