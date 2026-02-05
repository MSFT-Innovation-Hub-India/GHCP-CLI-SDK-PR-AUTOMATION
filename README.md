# Fleet Compliance Agent Demo

**Demonstrating GitHub Copilot CLI/SDK Integration for Enterprise Fleet Management**

This demo showcases a Python-based compliance agent that automatically enforces organizational policies across a fleet of microservices using GitHub Copilot CLI SDK capabilities.

---

## 🎯 What This Demo Proves

| Capability | Description |
|------------|-------------|
| **Fleet-Wide Enforcement** | Automate compliance across multiple repos (vs single-repo manual reviews) |
| **Multi-Step Orchestration** | Clone → Detect Drift → RAG Evidence → MCP Calls → Patch → Test → PR |
| **Policy-as-Code** | Knowledge base searchable via RAG for evidence-backed PRs |
| **Risk-Aware Routing** | Change management determines approvals based on service tier and file patterns |
| **Security Integration** | Dependency vulnerability scanning with SLA-based response |
| **Copilot SDK Ready** | Single integration point for AI-powered PR descriptions |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FLEET COMPLIANCE AGENT                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │   GitHub    │    │  Knowledge  │    │   Copilot   │                     │
│  │   Repos     │    │    Base     │    │    SDK      │                     │
│  │  (Target)   │    │   (RAG)     │    │  (AI Assist)│                     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                     │
│         │                  │                   │                            │
│         ▼                  ▼                   ▼                            │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │                     AGENT CORE (Python)                      │           │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │           │
│  │  │  Clone  │→ │ Detect  │→ │  Patch  │→ │  Test   │→ PR    │           │
│  │  │  Repo   │  │  Drift  │  │  Code   │  │  Local  │        │           │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │           │
│  └───────────────────────────┬─────────────────────────────────┘           │
│                              │                                              │
│         ┌────────────────────┼────────────────────┐                        │
│         ▼                    ▼                    ▼                         │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐                 │
│  │ Change Mgmt │      │  Security   │      │   GitHub    │                 │
│  │ MCP Server  │      │ MCP Server  │      │     CLI     │                 │
│  │ (Approvals) │      │   (Scans)   │      │   (PRs)     │                 │
│  └─────────────┘      └─────────────┘      └─────────────┘                 │
│     :4101                :4102                 gh                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Details

| Component | Purpose |
|-----------|---------|
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
│   │   ├── run.py              # Main entry point
│   │   ├── github_ops.py       # Git/GitHub operations
│   │   ├── mcp_clients.py      # MCP server clients
│   │   ├── patcher_fastapi.py  # Code patching logic
│   │   ├── rag.py              # Knowledge base search
│   │   └── copilot_assist.py   # Copilot SDK integration
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
├── sample-repos/               # Demo target repos (contain compliance gaps)
│   ├── contoso-catalog-api/
│   ├── contoso-orders-api/
│   └── contoso-payments-api/
│
├── scripts/                    # Helper scripts
│   ├── setup.ps1               # Initial setup
│   ├── start-mcp-servers.ps1   # Start MCP servers
│   ├── stop-mcp-servers.ps1    # Stop MCP servers
│   ├── run-agent.ps1           # Run the agent
│   └── push-sample-repos.ps1   # Push samples to GitHub
│
├── DEMO_CHECKLIST.md           # Demo presentation guide
└── README.md                   # This file
```

---

## 🚀 Quick Start

### Prerequisites

#### Required Tools

| Tool | Purpose | Installation |
|------|---------|--------------|
| **Python 3.11+** | Agent runtime | [python.org](https://www.python.org/downloads/) |
| **Git** | Source control | [git-scm.com](https://git-scm.com/) |
| **GitHub CLI** | Repo operations & PRs | See below |
| **Node.js 18+** | Copilot CLI runtime | [nodejs.org](https://nodejs.org/) |
| **Azure CLI** | Azure authentication (for RAG) | See below |

#### Azure Resources (for RAG)

| Resource | Purpose |
|----------|---------|
| **Azure OpenAI Service** | Responses API with file_search |
| **Vector Store** | Native OpenAI vector store (not Azure AI Search) |

---

### Step-by-Step Installation

#### 1. Install GitHub CLI

**Windows (winget):**
```powershell
winget install GitHub.cli
```

**macOS (Homebrew):**
```bash
brew install gh
```

**Verify installation:**
```powershell
gh --version
```

#### 2. Authenticate GitHub CLI

```powershell
gh auth login
```

Follow the prompts to authenticate with GitHub. Select:
- GitHub.com
- HTTPS
- Login with a web browser (or paste token)

Verify authentication:
```powershell
gh auth status
```

#### 3. Install Node.js and Copilot CLI

**Windows (winget):**
```powershell
winget install OpenJS.NodeJS.LTS
```

**Install GitHub Copilot CLI globally:**
```powershell
npm install -g @anthropic-ai/copilot
```

**Verify installation:**
```powershell
copilot --version
```

> **Windows Note:** The Copilot CLI path is typically `C:\Users\<username>\AppData\Roaming\npm\copilot.cmd`. You may need to set `COPILOT_CLI_PATH` in your `.env` file (see configuration section).

#### 4. Install Azure CLI (for RAG with Azure OpenAI)

**Windows (winget):**
```powershell
winget install Microsoft.AzureCLI
```

**macOS (Homebrew):**
```bash
brew install azure-cli
```

**Login to Azure:**
```powershell
az login
```

This enables `DefaultAzureCredential` for authenticating with Azure OpenAI without API keys.

#### 5. Create Azure OpenAI Vector Store

The RAG component uses Azure OpenAI's Responses API with file_search. You need a **native OpenAI vector store** (not Azure AI Search/Foundry index).

**Create vector store via API:**
```powershell
# Get Azure AD token
$token = az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv

# Create vector store
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
    "api-version" = "2025-03-01-preview"
}

$body = @{
    name = "fleet-compliance-knowledge"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://YOUR_ENDPOINT.openai.azure.com/openai/v1/vector_stores" `
    -Method POST -Headers $headers -Body $body
```

**Upload knowledge files:**
```powershell
# Upload each file from knowledge/ folder
$files = Get-ChildItem .\knowledge\*.md
foreach ($file in $files) {
    # Upload file and add to vector store
    # See Azure OpenAI documentation for file upload API
}
```

Note the **vector_store_id** (format: `vs_xxxxxxxxxxxx`) for configuration.

---

### Option 1: Automated Setup (Recommended)

```powershell
# 1. Clone the demo
cd ghcp-cli-sdk-sample1

# 2. Run setup script
.\scripts\setup.ps1

# 3. Create and push sample repos
.\scripts\push-sample-repos.ps1 -GitHubOrg YOUR_USERNAME -CreateRepos

# 4. Start MCP servers (leave running)
.\scripts\start-mcp-servers.ps1

# 5. Run the agent (in new terminal)
.\scripts\run-agent.ps1
```

### Option 2: Manual Setup

#### Step 1: Create GitHub Repos

Create 3 empty repos (private is fine):
- `contoso-catalog-api`
- `contoso-orders-api`
- `contoso-payments-api`

#### Step 2: Push Sample Repos

```bash
cd sample-repos/contoso-orders-api
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_ORG/contoso-orders-api.git
git push -u origin main
```
Repeat for payments and catalog.

#### Step 3: Configure Agent

**Edit `agent/config/repos.json`:**
```json
{
  "repos": [
    "https://github.com/YOUR_ORG/contoso-orders-api.git",
    "https://github.com/YOUR_ORG/contoso-payments-api.git",
    "https://github.com/YOUR_ORG/contoso-catalog-api.git"
  ]
}
```

**Create `agent/.env` from template:**
```powershell
cd agent
copy .env.example .env
```

**Configure environment variables in `agent/.env`:**
```env
# Azure OpenAI RAG Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2025-03-01-preview
AZURE_OPENAI_VECTOR_STORE_ID=vs_xxxxxxxxxxxx

# GitHub Copilot SDK Configuration
USE_COPILOT_SDK=true
COPILOT_MODEL=gpt-4o

# Windows: Path to Copilot CLI (required on Windows)
COPILOT_CLI_PATH=C:\Users\YOUR_USERNAME\AppData\Roaming\npm\copilot.cmd

# MCP Server Ports (optional, defaults shown)
CHANGE_MGMT_URL=http://localhost:4101
SECURITY_URL=http://localhost:4102
```

> **Important:** On Windows, the Copilot SDK requires `COPILOT_CLI_PATH` to locate the CLI binary. Find your path with: `npm list -g @anthropic-ai/copilot`

#### Step 4: Start MCP Servers

Terminal 1:
```bash
cd mcp/change_mgmt
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
uvicorn server:app --port 4101
```

Terminal 2:
```bash
cd mcp/security
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn server:app --port 4102
```

#### Step 5: Run the Agent

Terminal 3:
```bash
cd agent
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
python -m fleet_agent.run
```

---

## 🔍 What Happens During the Demo

1. **Agent starts** and reads target repos from `config/repos.json`

2. **For each repository:**
   - Clones the repo to `agent/workspaces/`
   - Detects compliance drift (missing health endpoints, logging, etc.)
   - Searches knowledge base for policy evidence
   - Calls Security MCP to scan dependencies
   - Calls Change Mgmt MCP to determine approvals

3. **If drift detected:**
   - Creates a feature branch
   - Applies fixes (adds endpoints, middleware, logging)
   - Runs local tests
   - Commits changes
   - Opens PR with policy evidence and appropriate labels

4. **PR labels based on CM-7:**
   - `needs-sre-approval` for high-impact services (payments)
   - `needs-security-approval` for auth/secret file changes
   - Standard PRs get `ready-for-review`

---

## � Compliance Gaps in Sample Repos

The sample repos contain realistic "tech debt" that the agent will detect and remediate:

| Violation | Policy | All Repos | Payments Only |
|-----------|--------|:---------:|:-------------:|
| Missing `/healthz` endpoint | OPS-2.1 | ✓ | |
| Missing `/readyz` endpoint | OPS-2.1 | ✓ | |
| No structured logging (uses `print()`) | OBS-1.1 | ✓ | |
| No correlation middleware | OBS-3.2 | ✓ | |
| Vulnerable `requests==2.19.0` | SEC-2.4 | | ✓ |

**Detection method:** The agent uses string pattern matching (not comments or hints):
- Checks if `"/healthz"` appears in code
- Checks if `structlog` is imported
- Checks if `RequestContextMiddleware` exists
- Security MCP scans `requirements.txt` versions against CVE database

**Payments is "high-impact":** The word "payments" in the service name triggers CM-7.2, requiring SRE-Prod approval.

---

## �📋 Sample PR Output

The agent creates PRs like this:

```markdown
## Summary
This PR enforces fleet compliance policies across the service.

## Changes
- app/main.py (health endpoints, middleware)
- app/middleware.py (correlation ID handling)
- app/logging_config.py (structured logging)
- requirements.txt (structlog dependency)
- tests/test_health.py (compliance tests)

## Policy Compliance
- OPS-2.1: Added /healthz and /readyz endpoints
- OBS-1.1: Configured structlog for JSON logging
- OBS-3.2: Added RequestContextMiddleware for trace correlation

## Evidence (Policies Referenced)
- **OPS-2.1**: Health endpoints MUST return JSON with status, service, version...
- **OBS-1.1**: Logs MUST be structured JSON in production...
- **OBS-3.2**: Accept inbound W3C traceparent header...

[Labels: needs-sre-approval, compliance]
```

---

## 🔧 Customization Points

| What to Customize | Location |
|-------------------|----------|
| Target repos | `agent/config/repos.json` |
| Policy documents | `knowledge/*.md` |
| Approval rules | `mcp/change_mgmt/server.py` |
| Vulnerability DB | `mcp/security/server.py` |
| Patching logic | `agent/fleet_agent/patcher_fastapi.py` |
| Copilot integration | `agent/fleet_agent/copilot_assist.py` |

---

## 🤖 Copilot SDK Integration

The agent integrates with the official [GitHub Copilot SDK](https://github.com/github/copilot-sdk) for AI-generated PR descriptions.

### Installation

```powershell
# Install the Python SDK
pip install github-copilot-sdk

# The SDK requires the Copilot CLI (already installed via npm)
npm install -g @anthropic-ai/copilot
```

### How It Works

The SDK communicates with the Copilot CLI via JSON-RPC over stdio. Here's the integration in `copilot_assist.py`:

```python
# agent/fleet_agent/copilot_assist.py

import asyncio
from copilot import CopilotClient

async def draft_with_copilot_sdk(prompt: str) -> str:
    """Generate PR description using GitHub Copilot SDK."""
    client = CopilotClient()
    await client.start()
    
    session = await client.create_session({'model': 'gpt-4o'})
    
    done = asyncio.Event()
    response_text = ''
    
    def on_event(event):
        nonlocal response_text
        if event.type.value == 'assistant.message':
            response_text = event.data.content
        elif event.type.value == 'session.idle':
            done.set()
    
    session.on(on_event)
    await session.send({'prompt': prompt})
    await asyncio.wait_for(done.wait(), timeout=60)
    
    await session.destroy()
    await client.stop()
    
    return response_text
```

### Configuration

| Environment Variable | Purpose | Default |
|---------------------|---------|---------|
| `USE_COPILOT_SDK` | Enable AI-generated PR descriptions | `false` |
| `COPILOT_MODEL` | Model to use | `gpt-4o` |
| `COPILOT_CLI_PATH` | Path to CLI binary (Windows) | Auto-detect |

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

### Dynamic vs Deterministic Mode

| Mode | Setting | Behavior |
|------|---------|----------|
| **Dynamic (AI)** | `USE_COPILOT_SDK=true` | PR descriptions generated by Copilot |
| **Deterministic** | `USE_COPILOT_SDK=false` | Template-based PR descriptions |

When `USE_COPILOT_SDK=true`, the agent sends a prompt with policy evidence and file changes to Copilot, which generates a contextual PR description.

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
3. Restart servers:
   ```powershell
   .\scripts\stop-mcp-servers.ps1
   .\scripts\start-mcp-servers.ps1
   ```

---

## 📄 License

This demo is provided for educational purposes. See LICENSE for details.
