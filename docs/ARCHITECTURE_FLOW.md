# Fleet Compliance Agent - Architecture & Flow Diagrams

This document provides visual and technical documentation of the Fleet Compliance Agent's **agentic architecture** where the GitHub Copilot SDK acts as the autonomous decision-making brain.

---

## Core Concept: SDK as Agent Brain

The Fleet Compliance Agent is a **TRUE agentic implementation**:
- The **GitHub Copilot SDK** (via Copilot API) is the agent brain
- Custom tools are registered with the SDK and exposed via function calling
- The SDK reasons about tool results and decides next steps
- The agent loop continues until the task is complete

> **Important Distinction:**
> - **Copilot SDK** = Agent brain (LLM reasoning, tool orchestration)
> - **Azure OpenAI** = Vector Store ONLY (RAG search, no LLM reasoning)

```mermaid
flowchart TB
    subgraph AgentBrain["🧠 GitHub Copilot SDK - The Agent Brain"]
        LLM[Copilot API<br/>Autonomous Reasoning]
        PROMPT[System Prompt<br/>Compliance Workflow Instructions]
        DECIDE[/"Decides Which Tool to Call<br/>and With What Arguments"/]
    end

    subgraph CustomTools["🔧 13 Custom Tools"]
        T1[rag_search]
        T2[clone_repository]
        T3[detect_compliance_drift]
        T4[security_scan]
        T5[create_branch]
        T6[apply_compliance_patches]
        T7[get_required_approvals]
        T8[run_tests]
        T9[read_file]
        T10[fix_code]
        T11[commit_changes]
        T12[push_branch]
        T13[create_pull_request]
    end

    subgraph External["🌐 External Services"]
        AOAI[(Azure OpenAI<br/>Vector Store ONLY<br/>No LLM Reasoning)]
        MCP_SEC[MCP: Security Server]
        MCP_CM[MCP: Change Mgmt Server]
        GH[(GitHub)]
    end

    LLM --> DECIDE
    PROMPT --> LLM
    DECIDE -->|function call| T1 & T2 & T3 & T4 & T5 & T6 & T7 & T8 & T9 & T10 & T11
    
    T1 -->|results| LLM
    T2 -->|results| LLM
    T3 -->|results| LLM
    
    T1 --> AOAI
    T4 --> MCP_SEC
    T7 --> MCP_CM
    T2 & T9 & T10 & T11 --> GH
```

---

## Agent Loop Sequence

```mermaid
sequenceDiagram
    participant User
    participant AgentLoop as Agent Loop
    participant SDK as Copilot SDK
    participant Tools as Custom Tools
    participant External as External Services

    User->>AgentLoop: Process repositories
    AgentLoop->>SDK: Create session with 13 tools
    AgentLoop->>SDK: Send user prompt
    
    loop Until session.idle
        SDK->>SDK: Reason about task
        SDK-->>AgentLoop: tool.execution_start
        AgentLoop->>Tools: Invoke handler
        Tools->>External: (RAG/MCP/Git)
        External-->>Tools: Response
        Tools-->>AgentLoop: ToolResult
        AgentLoop-->>SDK: Tool result
        SDK->>SDK: Reason about result
        SDK-->>AgentLoop: assistant.message
    end
    
    SDK-->>AgentLoop: session.idle
    AgentLoop-->>User: Summary with PRs
```

---

## Simple Flow Diagram (Agentic Mode)

```mermaid
flowchart TB
    subgraph SDK["🧠 GitHub Copilot SDK - Agent Brain"]
        LLM[Copilot API decides<br/>which tools to call]
    end

    subgraph Tools["🔧 Custom Tool Flow"]
        A[rag_search] --> B[clone_repository]
        B --> C[detect_compliance_drift]
        C --> D[security_scan]
        D --> E[create_branch]
        E --> F[apply_compliance_patches]
        F --> G[get_required_approvals]
        G --> H[run_tests]
        H --> I[fix_code if needed]
        I --> J[commit_changes]
        J --> K[push_branch]
        K --> L[create_pull_request]
    end

    subgraph External["🌐 External Services"]
        RAG[(Azure OpenAI<br/>Vector Store)]
        MCP[(MCP Servers)]
        GH[(GitHub)]
    end

    LLM -->|function calling| Tools
    Tools -->|results| LLM
    
    A --> RAG
    D & G --> MCP
    B & I & J & K --> GH

    style SDK fill:#9944ff,color:white
    style LLM fill:#6633cc,color:white
    style A fill:#4a9eff,color:white
    style D fill:#ff9944,color:white
    style G fill:#ff9944,color:white
```

---

## Tool Registration (agent_loop.py)

The agentic implementation registers 13 custom tools with the Copilot SDK:

```python
from copilot import CopilotClient
from copilot.types import Tool, ToolResult

# Create tool with handler and JSON Schema parameters
rag_search_tool = Tool(
    name="rag_search",
    description="Search the knowledge base for compliance policy documents.",
    handler=rag_search_handler,  # Function that returns ToolResult
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        },
        "required": ["query"]
    }
)

# Session with ONLY custom tools (available_tools whitelist)
session = await client.create_session({
    "model": "gpt-4o",
    "system_message": {"content": SYSTEM_PROMPT},
    "tools": [rag_search_tool, clone_tool, ..., read_file_tool, fix_code_tool],
    "available_tools": ["rag_search", "clone_repository", ..., "read_file", "fix_code"]  # Whitelist
})
```

**Key Pattern**: Use `available_tools` (not `excluded_tools`) to ensure the SDK only uses custom tools, not built-in ones.

---

## Key Architecture Points

### 1. Loop Structure: Sequential Per-Repository

```
┌─────────────────────────────────────────────────────────────────┐
│  OUTER LOOP: for url in repos (sequential)                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  INNER EXECUTION: All steps for ONE repo (synchronous)    │  │
│  │                                                           │  │
│  │  Clone → Detect → Scan → Patch → Test → Commit → PR       │  │
│  │                                                           │  │
│  │  NO inner loop per tool call - each step runs once        │  │
│  │  Agent controls flow, detects completion, moves to next   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**The agent uses a TRUE agentic approach** - the Copilot SDK autonomously decides tool order:
1. Each repository is processed **sequentially** (not in parallel)
2. The SDK reasons about the task and calls tools as needed
3. The agent loop (`agent_loop.py`) registers tools and handles events
4. The SDK decides "what to do next" based on system prompt and tool results
5. PR descriptions are generated by the SDK through the `create_pull_request` tool

### 2. Azure OpenAI: Vector Store Only (NOT LLM)

```
┌────────────────────────────────────────────────────────────────────┐
│                     Azure OpenAI Service                           │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │   ✅ USED: Vector Store                                  │     │
│  │   • Endpoint: Configured via AZURE_OPENAI_ENDPOINT       │      │
│  │   • Vector Store ID: AZURE_OPENAI_VECTOR_STORE_ID        |      │
│  │   • Embedding Model: text-embedding-3-small              │      │
│  │   • Responses API with file_search tool                  │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │   ❌ NOT USED: LLM Models (gpt-4o, etc.)                 │     │
│  │   • No chat completions from Azure OpenAI                │      │
│  │   • LLM capability comes from GitHub Copilot SDK         │      │
│  └──────────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────────┘
```

### 3. GitHub Copilot SDK Integration

```
┌────────────────────────────────────────────────────────────────────┐
│  GitHub Copilot SDK (github-copilot-sdk)                           │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Prerequisites:                                                    │
│  • COPILOT_CLI_PATH → C:\Users\...\npm\copilot.cmd (Windows)       │
│  • GitHub CLI authenticated (gh auth login)                        │
│  • Copilot CLI extension (gh extension install github/gh-copilot)  │
│                                                                    │
│  How it works:                                                     │
│  ┌──────────┐    JSON-RPC    ┌─────────────┐     API     ┌───────┐ │
│  │ Python   │ ──────────────▶│ Copilot CLI │ ──────────▶│GitHub │ │
│  │ SDK      │                │ (server     │             │Copilot│ │
│  │          │◀──────────────│  mode)      │◀──────────  │ API   │ │
│  └──────────┘   SSE Events   └─────────────┘             └───────┘ │
│                                                                    │
│  Streaming Implementation:                                         │
│  • CopilotClient.start() launches CLI in server mode               │
│  • create_session() initializes with model + system prompt         │
│  • session.on(handler) registers event callback                    │
│  • session.send(prompt) sends user message                         │
│  • Events: assistant.message.delta (tokens), assistant.message     │
│  • Chunks collected → joined → returned as CopilotDraft            │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 4. Event-Driven Streaming

The agent uses event callbacks to stream tool results to the UI:

```python
# Event handler in agent_loop.py

def on_event(event):
    event_type = event.type.value
    
    if event_type == "tool.execution_start":
        tool_name = event.data.tool_name
        args = event.data.arguments
        # Emit to UI via WebSocket
    
    elif event_type == "tool.execution_complete":
        # Tool finished, SDK will reason about result
    
    elif event_type == "assistant.message":
        # Agent reasoning/message - extract PR URLs
    
    elif event_type == "session.idle":
        done.set()  # Agent completed task
```

### 5. MCP Server Integration

```
┌─────────────────────────────────────────────────────────────────┐
│  MCP Servers (Model Context Protocol)                           │
│  Local FastAPI services providing domain-specific tools         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Security Scanner (Port 4102)                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  POST /scan                                                │ │
│  │  Input:  { "requirements": "fastapi==0.100.0\n..." }       │ │
│  │  Output: { "findings": [ { "package": "pyjwt",             │ │
│  │                           "cve": "CVE-2024-...",           │ │
│  │                           "severity": "high" } ] }         │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Change Management (Port 4101)                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  POST /approval                                           │  │
│  │  Input:  { "service": "contoso-payments-api",             │  │
│  │            "touched_paths": ["app/auth.py"] }             │  │
│  │  Output: { "required_approvals": ["SRE-Prod","Security"], │  │
│  │            "risk_level": "high",                          │  │
│  │            "rationale": "High-impact + sensitive files" } │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6. PR Generation Instruction

The prompt sent to Copilot SDK includes:

```markdown
## Instruction
Write a PR description for a fleet compliance remediation PR. 
Include risk and rollout suggestions.

## Policy Evidence (from knowledge base)
- **OPS-2.1-health-readiness.md**: Health and readiness endpoints 
  are required for all HTTP services deployed on Kubernetes...
- **SEC-2.4-dependency-vulnerability-response.md**: All dependencies 
  must be scanned for CVEs. Critical vulnerabilities must be...
[... 2 more documents ...]

## Changes Made
- app/main.py
- app/middleware.py
- app/logging_config.py
- requirements.txt
- tests/test_health.py

## Output Format
Please provide a professional PR description with:
1. **Summary** - Brief overview of the changes
2. **Changes** - Bullet list of specific modifications
3. **Policy Compliance** - How this addresses fleet policies
4. **Risk Assessment** - Any deployment considerations
5. **Testing** - Verification steps performed
```

### 7. Test Execution & Error Handling

```
┌─────────────────────────────────────────────────────────────────┐
│  Unit Test Execution (per-repository)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Prerequisites:                                                 │
│  • PYTEST_ENABLED=true in .env                                  │
│  • tests/ directory exists in repository                        │
│                                                                 │
│  Execution Flow:                                                │
│  1. pip install -r requirements.txt (install dependencies)      │
│  2. python -m pytest -q (run tests quietly)                     │
│                                                                 │
│  Error Handling:                                                │
│  • Tests PASS  → Continue to commit/push/PR                     │
│  • Tests FAIL  → Log failure, STILL create PR (human review)    │
│  • Tests ERROR → Catch exception, continue with PR              │
│                                                                 │
│  Why not block on failures?                                     │
│  • Agent patches are deterministic and tested                   │
│  • Existing repo tests may fail for unrelated reasons           │
│  • Human reviewers see test status and decide                   │
│  • Better to surface issue in PR than silently skip             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Complete Data Flow

```mermaid
sequenceDiagram
    autonumber
    participant Agent as Fleet Agent<br/>(agent_loop.py)
    participant RAG as Azure OpenAI<br/>Vector Store
    participant MCP_Sec as MCP Security<br/>:4102
    participant MCP_CM as MCP Change Mgmt<br/>:4101
    participant Copilot as GitHub Copilot<br/>SDK
    participant GH as GitHub API

    Note over Agent: 🚀 Initialization (once)
    Agent->>Agent: Load repos.json (3 repos)
    Agent->>GH: gh auth status
    GH-->>Agent: Authenticated ✓
    
    Agent->>RAG: search("structured logging health...")
    RAG-->>Agent: 4 policy documents (evidence)
    
    Note over Agent: 🔄 Loop: contoso-orders-api
    Agent->>GH: git clone
    Agent->>Agent: detect() → missing_healthz=true
    Agent->>MCP_Sec: POST /scan (requirements.txt)
    MCP_Sec-->>Agent: {findings: []}
    Agent->>Agent: apply() → 5 files patched
    Agent->>MCP_CM: POST /approval (service, paths)
    MCP_CM-->>Agent: {required: [ServiceOwner]}
    Agent->>Agent: pytest → PASS ✓
    Agent->>GH: git push branch
    
    Agent->>Copilot: session.send(prompt + evidence)
    loop Streaming Events
        Copilot-->>Agent: assistant.message.delta (token)
        Agent->>Agent: print(token, flush=True)
    end
    Copilot-->>Agent: session.idle
    Agent->>Agent: join chunks → PR body
    
    Agent->>GH: gh pr create (title, body, labels)
    GH-->>Agent: PR #9 created ✓
    
    Note over Agent: 🔄 Loop: contoso-payments-api
    Agent->>GH: git clone
    Agent->>Agent: detect() → missing_healthz=true
    Agent->>MCP_Sec: POST /scan
    MCP_Sec-->>Agent: {findings: [2 CVEs]}
    Agent->>Agent: apply() → 5 files patched
    Agent->>MCP_CM: POST /approval
    MCP_CM-->>Agent: {required: [SRE-Prod,Security]}
    Agent->>Agent: pytest → PASS ✓
    Agent->>GH: git push branch
    Agent->>Copilot: session.send(prompt)
    Copilot-->>Agent: 2385 chars generated
    Agent->>GH: gh pr create + labels
    GH-->>Agent: PR #8 created ✓
    
    Note over Agent: 🔄 Loop: contoso-catalog-api
    Agent->>GH: git clone ... (same pattern)
    
    Note over Agent: ✅ Summary
    Agent->>Agent: Print run stats
```

---

## Production Architecture (Headless / Fleet Scale)

The demo runs a single SDK session processing repos sequentially — sufficient for 3-5 repos. For production fleet enforcement (50+ repos), the architecture shifts to **parallel workers with per-repo isolation**.

### Demo vs. Production

| Aspect | Demo (Current) | Production (Target) |
|--------|---------------|---------------------|
| **Execution** | Single SDK session, all repos in one prompt | One SDK session per repo, parallel workers |
| **Concurrency** | Sequential — repo 2 waits for repo 1 | Parallel — configurable worker pool |
| **Trigger** | Manual (UI button or `python -m fleet_agent.agent_loop`) | Scheduled (cron, Azure Timer Function) or event-driven (webhook) |
| **State** | In-memory + ephemeral JSON files | Persistent store (DB or blob) for retry/resume |
| **Failure handling** | Entire run fails if one repo errors | Per-repo retry with exponential backoff |
| **Reporting** | Console stdout or WebSocket stream | Structured results to dashboard/Slack/ITSM |
| **Infrastructure** | Developer laptop | Container (ACA, AKS) or Azure Functions |

### Production Architecture Diagram

```mermaid
flowchart TB
    subgraph Trigger["⏰ Trigger"]
        CRON[Scheduled<br/>cron / Timer Function]
        WEBHOOK[Event-Driven<br/>repo push / webhook]
        CLI[Manual<br/>CLI invocation]
    end

    subgraph Orchestrator["🎯 Orchestrator"]
        DISPATCH[Dispatcher<br/>Reads repos.json or registry<br/>Enqueues one job per repo]
        QUEUE[(Job Queue<br/>Azure Queue / Redis)]
    end

    subgraph Workers["⚙️ Worker Pool (N parallel)"]
        W1[Worker 1<br/>SDK Session<br/>contoso-orders-api]
        W2[Worker 2<br/>SDK Session<br/>contoso-payments-api]
        W3[Worker 3<br/>SDK Session<br/>contoso-catalog-api]
        WN[Worker N<br/>SDK Session<br/>...]
    end

    subgraph PerWorker["Per-Worker Flow (same 13 tools)"]
        direction LR
        RAG[RAG Search] --> CLONE[Clone]
        CLONE --> DETECT[Detect Drift]
        DETECT --> SCAN[Security Scan]
        SCAN --> PATCH[Apply Patches]
        PATCH --> TEST[Run Tests]
        TEST --> PR[Create PR]
    end

    subgraph SharedServices["🌐 Shared Services"]
        AOAI[(Azure OpenAI<br/>Vector Store)]
        MCP_SEC[MCP Security<br/>:4102]
        MCP_CM[MCP Change Mgmt<br/>:4101]
        GH[(GitHub)]
    end

    subgraph Results["📊 Results"]
        STATE[(State Store<br/>per-repo status<br/>retry tracking)]
        REPORT[Reporting<br/>Dashboard / Slack<br/>/ ITSM ticket]
    end

    CRON & WEBHOOK & CLI --> DISPATCH
    DISPATCH --> QUEUE
    QUEUE --> W1 & W2 & W3 & WN

    W1 & W2 & W3 & WN --> PerWorker
    PerWorker --> AOAI & MCP_SEC & MCP_CM & GH

    W1 & W2 & W3 & WN --> STATE
    STATE --> REPORT

    style Trigger fill:#f0f0f0,stroke:#999
    style Workers fill:#e8f4fd,stroke:#4a9eff
    style SharedServices fill:#fff3e0,stroke:#ff9944
    style Results fill:#e8f5e9,stroke:#4caf50
```

### Key Production Design Decisions

1. **One SDK session per repo** — Each worker creates its own `CopilotClient` and session. This avoids context window overflow and enables independent timeouts/retries per repo.

2. **Worker pool sizing** — Limited by Copilot API rate limits and MCP server capacity. Start with 3-5 concurrent workers and tune based on throughput.

3. **Idempotent re-runs** — Before cloning, check if a compliance PR already exists for the target branch. Skip repos that already have an open PR.

4. **State store** — Track per-repo status (`queued`, `in_progress`, `completed`, `failed`, `retrying`). Enables resume-after-failure without re-processing successful repos.

5. **MCP server scaling** — The current single-instance MCP servers become a bottleneck at scale. Deploy behind a load balancer or use the MCP `stdio` transport with per-worker server instances.

6. **Secrets management** — Move from `.env` file to Azure Key Vault or GitHub Actions secrets. Each worker authenticates independently.

### Console Entry Point — Current vs. Parallel

The current `main()` in `agent_loop.py` sends all repos in one prompt:

```python
# Current: sequential, single session
def main():
    repos = load_repos()
    user_input = build_prompt(repos)       # All repos in one prompt
    result = asyncio.run(run_agent(user_input))  # One session
```

A production version would dispatch per-repo:

```python
# Production: parallel, one session per repo
async def main_parallel():
    repos = load_repos()
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent

    async def process_one(url: str):
        async with semaphore:
            prompt = build_prompt([url])   # Single repo
            return await run_agent(prompt) # Own session

    results = await asyncio.gather(
        *[process_one(url) for url in repos],
        return_exceptions=True
    )
```

---

## Summary Table

| Aspect | Demo | Production |
|--------|------|------------|
| **Loop Structure** | Sequential per-repo, single SDK session | Parallel workers, one SDK session per repo |
| **Tool Autonomy** | Yes - SDK decides tool order based on reasoning | Same |
| **State Persistence** | Ephemeral JSON files, cleared each run | Persistent store with retry tracking |
| **Memory** | No long-term memory; fresh workspace each run | Same — stateless per-repo |
| **Azure OpenAI** | Vector Store ONLY (file_search), NOT LLM | Same |
| **LLM Provider** | GitHub Copilot SDK via Copilot CLI | Same |
| **Streaming** | Event-based: tool calls and messages stream to UI | Structured logs to observability platform |
| **Error Handling** | Tests can fail, PR still created (human decides) | Same + per-repo retry with backoff |
| **Completion Detection** | SDK signals session.idle when task complete | Same + state store updated |
| **Trigger** | Manual (button click or CLI) | Scheduled or event-driven |
| **Concurrency** | 1 (sequential) | N (configurable worker pool) |

