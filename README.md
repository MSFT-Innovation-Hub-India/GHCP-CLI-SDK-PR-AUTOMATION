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

## � From POC to Production

This demo implements a pattern that is **directly applicable to enterprise production environments**. The underlying use case - automated compliance enforcement via AI agents - is increasingly common in platform engineering and DevSecOps.

### The Use Case: AI-Powered Platform Engineering

Organizations managing hundreds of microservices face a common challenge: **enforcing consistency at scale**. Manual code reviews can't keep pace with the need to ensure every service has:
- Proper health endpoints for Kubernetes
- Structured logging for observability platforms
- Security vulnerability remediation
- Compliance with internal standards

**This agent demonstrates automated enforcement**: an AI agent that understands policies, detects drift, and proposes fixes via Pull Requests - keeping humans in the approval loop.

### How This POC Implements It

| Component | POC Implementation | Purpose |
|-----------|-------------------|---------|
| **Agent Runtime** | Single Python process | Orchestrates compliance workflow |
| **AI Brain** | GitHub Copilot SDK | Autonomous decision-making for tool selection |
| **Policy Knowledge** | Azure OpenAI Vector Store + RAG | Grounds agent decisions in organizational policies |
| **Integration Layer** | MCP Servers (HTTP) | Connects to approval workflows and security scanners |
| **Execution** | GitHub CLI | Git operations and PR creation |
| **UI** | React + WebSocket | Real-time visibility for single user |
| **State** | JSON files | PR tracking during execution |

**Limitations of the POC:**
- Single-user, single-machine execution
- No persistent state between runs
- No authentication/authorization
- No job queuing or scheduling
- No audit trail or compliance reporting

### Production Architecture

In a production scenario, this pattern scales to support **multi-tenant, enterprise-grade operations**:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                          PRODUCTION ARCHITECTURE                                         │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                         FRONTEND LAYER                                           │   │
│   │   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │   │
│   │   │   Web Portal    │    │  CLI Tool       │    │  GitHub App     │             │   │
│   │   │  (React/Vue)    │    │  (Developer)    │    │  (Webhook)      │             │   │
│   │   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘             │   │
│   └────────────┼─────────────────────┼─────────────────────┼────────────────────────┘   │
│                │                      │                     │                            │
│                ▼                      ▼                     ▼                            │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                          API GATEWAY                                             │   │
│   │   • OAuth/OIDC Authentication (Azure AD, GitHub)                                 │   │
│   │   • RBAC: Who can run agents on which repos/orgs                                 │   │
│   │   • Rate limiting, request validation                                            │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                                 │
│                                        ▼                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                        JOB ORCHESTRATION                                         │   │
│   │   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │   │
│   │   │   Job Queue     │    │   Scheduler     │    │  Job Manager    │             │   │
│   │   │ (Redis/RabbitMQ)│    │   (Cron/Event)  │    │  (Status/Retry) │             │   │
│   │   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘             │   │
│   └────────────┼─────────────────────┼─────────────────────┼────────────────────────┘   │
│                │                      │                     │                            │
│                ▼                      ▼                     ▼                            │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                      WORKER POOL (Scalable)                                      │   │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │   │
│   │   │   Worker 1   │  │   Worker 2   │  │   Worker 3   │  │   Worker N   │        │   │
│   │   │ (Agent Core) │  │ (Agent Core) │  │ (Agent Core) │  │ (Agent Core) │        │   │
│   │   │  + SDK       │  │  + SDK       │  │  + SDK       │  │  + SDK       │        │   │
│   │   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                │                                                                         │
│                ▼                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                      DATA & INTEGRATION LAYER                                    │   │
│   │                                                                                  │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │   │
│   │   │ PostgreSQL  │  │   Redis     │  │  Vector DB  │  │   Blob      │            │   │
│   │   │ (Jobs, PRs, │  │  (Cache,    │  │  (Policy    │  │  Storage    │            │   │
│   │   │  Audit)     │  │   Sessions) │  │   RAG)      │  │  (Logs)     │            │   │
│   │   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │   │
│   │                                                                                  │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │   │
│   │   │ ServiceNow  │  │   Snyk/     │  │   GitHub    │  │  Slack/     │            │   │
│   │   │ (Change     │  │   Dependabot│  │   (Repos,   │  │  Teams      │            │   │
│   │   │  Mgmt)      │  │   (Security)│  │   PRs)      │  │  (Notify)   │            │   │
│   │   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                       OBSERVABILITY                                              │   │
│   │   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │   │
│   │   │  OpenTelemetry  │    │   Prometheus    │    │   Grafana       │             │   │
│   │   │  (Distributed   │    │   (Metrics)     │    │  (Dashboards)   │             │   │
│   │   │   Tracing)      │    │                 │    │                 │             │   │
│   │   └─────────────────┘    └─────────────────┘    └─────────────────┘             │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Production Components Explained

| Component | Production Implementation | vs POC |
|-----------|--------------------------|--------|
| **Authentication** | OAuth/OIDC with Azure AD or GitHub | None (local user) |
| **Authorization** | RBAC database: user → org → repos permissions | None |
| **Job Queue** | Redis/RabbitMQ with Celery workers | Direct execution |
| **State Management** | PostgreSQL with jobs, PRs, audit tables | JSON file |
| **Scalability** | Kubernetes pods with auto-scaling | Single process |
| **Observability** | OpenTelemetry traces, Prometheus metrics | Console logs |
| **Notifications** | WebSocket hub + Slack/Teams integration | WebSocket to single client |
| **Scheduling** | Cron jobs or GitHub webhook triggers | Manual invocation |
| **Audit Trail** | Full event log with user, timestamp, action | None |

### Key Production Considerations

**1. Multi-Tenancy**
```sql
-- Every job is scoped to an organization
CREATE TABLE compliance_jobs (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL,          -- Tenant isolation
    user_id UUID NOT NULL,         -- Who triggered it
    repo_url TEXT NOT NULL,
    status VARCHAR(20),
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

**2. Credential Management**
- GitHub App installation tokens (per-org) instead of user PAT
- Azure Managed Identity for OpenAI access
- HashiCorp Vault or Azure Key Vault for secrets

**3. Rate Limiting & Quotas**
- Per-org limits on concurrent jobs
- GitHub API rate limit handling with backoff
- Cost tracking for LLM usage

**4. Compliance & Audit**
```sql
-- Full audit trail for compliance reporting
CREATE TABLE audit_events (
    id UUID PRIMARY KEY,
    job_id UUID REFERENCES compliance_jobs(id),
    event_type VARCHAR(50),        -- 'tool_called', 'pr_created', etc.
    payload JSONB,
    created_at TIMESTAMP
);
```

**5. Error Handling & Retry**
- Transient failure retry with exponential backoff
- Dead letter queue for failed jobs
- Manual intervention workflow for blocked PRs

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
│   │   ├── agent_loop.py       # Main agentic entry point (SDK-driven)
│   │   ├── github_ops.py       # Git/GitHub operations
│   │   ├── mcp_clients.py      # MCP server clients
│   │   ├── patcher_fastapi.py  # Code patching logic
│   │   └── rag.py              # Knowledge base search (Azure OpenAI)
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
│   ├── setup.ps1               # Initial setup
│   ├── start-mcp-servers.ps1   # Start MCP servers
│   ├── stop-mcp-servers.ps1    # Stop MCP servers
│   ├── run-agent-agentic.ps1   # Run the agent (console mode)
│   ├── start-ui.ps1            # Run the agent (visual UI mode)
│   ├── deploy-vector-store.ps1 # Deploy Azure OpenAI vector store
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

## �🚀 Quick Start

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
.\scripts\run-agent-agentic.ps1
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

# GitHub Copilot SDK Configuration (agent uses SDK as brain)
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

## �️ Visual UI Mode (React + FastAPI)

For demos and presentations, a visual UI provides real-time streaming of agent activity.
> **⚠️ Important: Single-User Local Application**
>
> This React-based web app is designed for **single-user, local execution only**. It is NOT intended to be hosted on a web server for concurrent multi-user access.
>
> **Prerequisites for the logged-in user:**
> - Authenticated with GitHub CLI: `gh auth login`
> - Authenticated with Azure: `az login`
> - GitHub Copilot CLI installed and SDK dependencies met
>
> The agent uses the **local user's credentials** for GitHub operations and Azure OpenAI access.
### Quick Start

```powershell
# Prerequisites: MCP servers running
.\scripts\start-mcp-servers.ps1

# Start both frontend and backend
.\scripts\start-ui.ps1

# Open http://localhost:3000 in browser
```

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
3. Restart servers:
   ```powershell
   .\scripts\stop-mcp-servers.ps1
   .\scripts\start-mcp-servers.ps1
   ```

---

## 📄 License

This demo is provided for educational purposes. See LICENSE for details.
