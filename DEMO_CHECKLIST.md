# Fleet Compliance Agent Demo - Presentation Guide

**Duration:** 5-8 minutes  
**Audience:** Developers, Platform Engineers, Engineering Leadership

---

## Demo Modes

| Mode | How to Run | Best For |
|------|------------|----------|
| **Visual UI** | Start MCP servers + UI backend + frontend (4 terminals) | Live demos, presentations |
| **Console** | Start MCP servers + `python -m fleet_agent.agent_loop` | Development, debugging |

---

## Pre-Demo Setup

Before the demo:
- [ ] GitHub repos created and pushed (`contoso-*-api`) — use `scripts/push-sample-repos.ps1`
- [ ] `agent/.env` configured (Azure OpenAI, Copilot CLI path, MCP URLs)
- [ ] Azure OpenAI vector store deployed — `python scripts/deploy-vector-store.py`
- [ ] Virtual environments set up (`agent/.venv`, `mcp/change_mgmt/.venv`, `mcp/security/.venv`)
- [ ] GitHub CLI authenticated — `gh auth login`
- [ ] Azure CLI authenticated — `az login`
- [ ] MCP servers running (2 terminals — see below)
- [ ] For UI mode: Node.js 18+ installed, `npm install` done in `ui/frontend/`
- [ ] Browser tabs open:
  - GitHub org/user page (to show PRs being created)
  - http://localhost:5173 (UI frontend — if using visual mode)

### Starting MCP Servers (Required for Both Modes)

**Terminal 1 — Change Management MCP (port 4101):**
```powershell
cd mcp\change_mgmt
.venv\Scripts\Activate.ps1
python server.py
```

**Terminal 2 — Security MCP (port 4102):**
```powershell
cd mcp\security
.venv\Scripts\Activate.ps1
python server.py
```

### Starting the UI (Visual Mode Only)

**Terminal 3 — FastAPI Backend (port 8000):**
```powershell
cd ui\backend
..\..\agent\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Terminal 4 — React Frontend (port 5173):**
```powershell
cd ui\frontend
npm run dev
```

### Running Console Mode

**Terminal 3 — Agent (after MCP servers are running):**
```powershell
cd agent
.venv\Scripts\Activate.ps1
python -m fleet_agent.agent_loop
```

---

## Demo Flow

### 1. Set the Scene (1 min)

**Say:** "Imagine you're managing 50+ microservices. You need to enforce:
- Health endpoints for K8s probes
- Structured logging for observability
- Correlation IDs for distributed tracing
- Security vulnerability SLAs

Doing this manually across 50 repos? Nightmare. Let me show you how we automate it."

---

### 2. Show the Problem (1 min)

Open one sample repo in VS Code or GitHub:
- `sample-repos/contoso-payments-api/app/main.py`

**Point out what's MISSING (not what's there):**
- No `/healthz` or `/readyz` endpoints anywhere
- Uses `print()` statements throughout (search for `print(`)
- No `structlog` import
- No `RequestContextMiddleware`

**Say:** "This service is missing critical compliance features. It has no health endpoints, no correlation middleware, and it's using `print()` instead of structured logging. This looks like typical tech debt - and it would fail our PR gates."

**Key point:** The violations aren't marked with comments - the agent discovers them through actual code analysis.

---

### 3. Show the Policies (1 min)

Open `knowledge/` folder:

```
knowledge/
├── OBS-1.1-structured-logging.md    # JSON logs required
├── OBS-3.2-trace-propagation.md     # Correlation IDs
├── OPS-2.1-health-readiness.md      # /healthz, /readyz
├── CM-7-approval-matrix.md          # Who approves what
├── SEC-2.4-dependency-vulnerability.md
└── REL-1.0-pr-gates.md              # Quality gates
```

**Say:** "We have policy documents that define what 'compliant' means. The agent uses these as evidence when opening PRs. This is policy-as-code that humans AND machines can read."

---

### 4. Show MCP Integration (1 min)

**Explain the MCP servers:**

**Say:** "We have two MCP servers — Model Context Protocol — that provide domain-specific intelligence. The Security server scans dependencies for CVEs, and the Change Management server evaluates who needs to approve changes based on service tier and files touched."

**Show `mcp.json` at the project root:**
```json
{
  "mcpServers": {
    "change_mgmt": {
      "url": "http://localhost:4101/sse",
      "transport": "sse",
      "tools": ["evaluate_approval", "assess_risk"]
    },
    "security": {
      "url": "http://localhost:4102/sse",
      "transport": "sse",
      "tools": ["scan_dependencies", "scan_detailed", "get_vulnerability"]
    }
  }
}
```

**Say:** "This `mcp.json` follows the emerging standard — the same format VS Code, Codex, and Claude Desktop use to discover MCP servers. Our agent reads URLs from this file at startup."

**Show `mcp/change_mgmt/server.py`** — highlight the `@mcp.tool()` decorators and the approval logic (high-impact services like payments require SRE approval).

**Say:** "The Change Management MCP evaluates who needs to approve based on service tier and what files were touched. Payments + auth files = SRE and Security approval required."

---

### 5. Run the Agent (2 min)

**Option A: Visual UI (Recommended for Demos)**

Start all 4 terminals as described in Pre-Demo Setup, then open http://localhost:5173.

**UI Highlights to show:**
- System status indicators (green checkmarks)
- Per-repo checklist cards updating in real-time
- Tool calls panel showing each invocation
- Agent reasoning with markdown tables
- Console logs with emoji indicators
- Progress heartbeat for long-running tools (⏳ [10s elapsed])

**Option B: Console Mode**

In terminal (with MCP servers already running):
```powershell
cd agent
.venv\Scripts\Activate.ps1
python -m fleet_agent.agent_loop
```

**Narrate as it runs:**
- \"Cloning contoso-orders-api...\"
- \"Detecting drift... missing healthz, missing structlog...\"
- \"Querying knowledge base for policy evidence...\"
- \"Applying fixes...\"
- \"Running tests...\"
- \"Opening PR...\"

---

### 6. Show the Results (2 min)

Open GitHub PRs page.

**Show a PR and highlight:**

1. **PR Title:** `chore(contoso-payments-api): enforce logging/tracing/health gates`

2. **Labels:** 
   - `needs-sre-approval` (because it's payments)
   - `compliance`

3. **PR Body:**
   - Summary of changes
   - Policy evidence excerpts
   - Files modified

4. **Changed Files:**
   - `app/main.py` - health endpoints added
   - `app/middleware.py` - correlation middleware
   - `app/logging_config.py` - structured logging
   - `tests/test_health.py` - compliance tests

**Say:** "The agent opened PRs across all three repos. Payments got extra labels because CM-7 says high-impact services need SRE approval. The PR body includes evidence from our policy documents so reviewers know WHY these changes are needed."

---

### 7. Copilot SDK Integration (30 sec)

Open `agent/fleet_agent/agent_loop.py`:

**Highlight the SDK session creation:**
```python
from copilot import CopilotClient
from copilot.types import Tool, ToolResult

# Create session with 13 custom tools
session = await client.create_session({
    "system_message": {"content": SYSTEM_PROMPT},
    "tools": tools,
    "available_tools": tool_names,
})
```

**Say:** "The Copilot SDK acts as the agent's brain. It decides which tools to call based on the system prompt. The `create_pull_request` tool generates PR descriptions - no separate copilot_assist module needed."

---

## Key Messages

1. **Fleet Scale:** "This works across 50 repos, not just one"
2. **Policy-Backed:** "Every change is backed by policy evidence"
3. **Risk-Aware:** "Approvals are routed based on risk, not guesswork"
4. **Human-in-Loop:** "Agent opens PRs; humans approve and merge"
5. **Copilot Ready:** "Single integration point for AI assistance"

---

## Q&A Prep

**Q: Does this auto-merge?**  
A: No. Policy CM-7 explicitly prohibits agent auto-merge. Humans review and merge.

**Q: What if the patch is wrong?**  
A: The agent runs tests locally before opening PRs. If tests fail, it still opens the PR but notes the failure.

**Q: How does it know what to fix?**  
A: The patcher has deterministic rules in `patcher_fastapi.py`. It detects missing patterns and applies known-good fixes.

**Q: Can we customize the policies?**  
A: Yes! Edit the markdown files in `knowledge/`. The RAG search will pick them up.

**Q: What about non-Python services?**  
A: You'd add patchers for other languages. The architecture is pluggable.

---

## Cleanup

After demo:
```powershell
# Stop MCP servers (Ctrl+C in their terminals)
# Optionally delete test PRs from GitHub:
#   gh pr close <PR_NUMBER> --repo <OWNER>/<REPO> --delete-branch
```

