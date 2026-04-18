# Fleet Compliance Agent — Demo Talk Track

## The Problem: Compliance at Scale in the Enterprise

Imagine you're a platform engineer or an IT Pro at a large enterprise. Your organization has dozens — maybe hundreds — of microservices, each living in its own GitHub repository. These services power critical business functions: processing orders, handling payments, managing product catalogs.

Now here's the challenge. Your organization has **compliance policies** that every service must follow:

- **Health and readiness endpoints** so Kubernetes knows when a service is alive (OPS-2.1)
- **Structured logging** so your observability stack can ingest and query logs consistently (OBS-1.1)
- **Trace propagation headers** so distributed traces flow across service boundaries (OBS-3.2)
- **Dependency vulnerability scanning** so known CVEs don't ship to production (SEC-2.4)
- **Change management approvals** routed based on risk — who needs to sign off before a change goes live (CM-7)
- **PR quality gates** that enforce test coverage and review requirements (REL-1.0)

These policies aren't suggestions. They come from frameworks like **NIST 800-53**, **SOC 2**, **CIS Benchmarks**, and **SRE best practices**. They're the rules your auditors will ask about.

### The manual reality

Today, someone has to go into **every single repository**, manually inspect the code, figure out what's missing, write the patches, run the tests, and open a Pull Request. That's hours of tedious, repetitive grunt work — per repository.

And the information is scattered everywhere:
- The **source code** lives in GitHub repositories
- The **compliance policies** live in a knowledge base — markdown documents, wikis, internal portals
- **Vulnerability data** is published externally on a regular basis — new CVEs appear daily
- **Change management rules** live in an approval matrix maintained by your governance team

A human doing this work has to context-switch between all of these systems, cross-reference policies against code, and do this consistently across every repo. It doesn't scale.

---

## The Solution: An Autonomous Fleet Compliance Agent

What if an agent could do all of that — autonomously?

That's what this demo shows. We've built a **Fleet Compliance Agent** that:

1. Reads your compliance policies from a knowledge base
2. Clones each target repository
3. Detects what's missing or non-compliant
4. Scans dependencies for known vulnerabilities
5. Applies the necessary code patches
6. Runs the test suite to verify nothing breaks
7. Creates a Pull Request with a detailed description, policy references, and risk assessment

All of this happens **without human intervention**. The agent reasons about what to do, decides the order of operations, handles errors, and completes the workflow end to end.

---

## The Brain: GitHub Copilot SDK

At the heart of this agent is the **GitHub Copilot SDK** — the same engine that powers **Agent Mode in the VS Code Copilot panel**. But here, instead of a developer typing prompts in an editor, **code drives the conversation**.

The SDK acts as the agent's **reasoning brain**:
- It receives a system prompt describing the compliance workflow
- It has access to **13 custom tools** — clone a repo, scan for vulnerabilities, apply patches, create a PR, and more
- It **autonomously decides** which tool to call next, based on what it learns from each tool's result
- It continues this loop until the task is complete

This is a true agentic implementation — not a scripted pipeline. The SDK reasons, adapts, and orchestrates.

### Why this runs in the user's context

An important architectural point: this agent **cannot run as a headless workflow on github.com**. It requires the **authenticated GitHub context** of a logged-in user — someone who has permissions to clone repos, push branches, and create Pull Requests.

The Copilot SDK communicates with the Copilot API through the **Copilot CLI**, which authenticates using the developer's GitHub login session (`gh auth login`). This is by design — the agent operates under the user's identity, with their permissions and audit trail.

This means the automation runs either:
- Through a **visual UI** like the one I'll demonstrate today, or
- As a **headless process** on the user's machine, running under their GitHub session

Either way, it's the user's authenticated context that authorizes every action.

---

## The Demo Scenario

We have a fictional enterprise — **Contoso** — running an e-commerce platform built on three FastAPI microservices:

| Service | Repository | Purpose |
|---------|-----------|---------|
| **Contoso Orders API** | `contoso-orders-api` | Order creation, status tracking, fulfillment |
| **Contoso Payments API** | `contoso-payments-api` | Payment authorization, capture, refunds |
| **Contoso Catalog API** | `contoso-catalog-api` | Product catalog, categories, inventory |

These are real GitHub repositories with real Python code. Each one was written by a different team, at a different time, with different levels of compliance awareness. Some have structured logging. Some don't have health endpoints. Some have outdated dependencies with known CVEs.

Our agent's job: bring **all three** into compliance — automatically.

---

## The Architecture

The agent is composed of several coordinated components:

**Agent Core** — Python code that registers 13 custom tools with the Copilot SDK, sends the compliance task as a prompt, and handles the event-driven tool execution loop.

**Knowledge Base (FoundryIQ)** — Compliance policy documents are stored in Azure Blob Storage, indexed by an Azure AI Search Knowledge Source, and served through a Knowledge Base that returns **extractive results** — verbatim policy text, not synthesized answers. This is the agent's reference library.

**MCP Servers** — Two local microservices using the Model Context Protocol (MCP):
- A **Security Scanner** (port 4102) that checks `requirements.txt` for known CVEs
- A **Change Management Server** (port 4101) that evaluates risk and determines required approvals

**GitHub** — The agent uses `git` and the `gh` CLI to clone repos, create branches, commit changes, push, and open Pull Requests — all through the authenticated user's session.

---

## The Agent Lifecycle: What Happens When You Click "Run"

When you click **"Run Compliance Check"** in the UI, here's what unfolds — step by step:

### Step 1: Policy Knowledge Search

The agent's first action is to **search the knowledge base**. It queries FoundryIQ for compliance policies relevant to the task — health endpoints, structured logging, trace propagation, vulnerability response, and change management rules.

This gives the agent the **policy context** it needs to know what "compliant" looks like. The results are extractive — verbatim excerpts from the actual policy documents, with references back to the source.

### Step 2: Clone the Repository

The agent clones the target repository into a temporary workspace. Each clone gets a unique directory name (with a nanoid suffix) to avoid collisions when processing multiple repos.

### Step 3: Detect Compliance Drift

The agent scans the repository's FastAPI application structure and compares it against the policies it retrieved. It detects **what's missing**:

- No `/healthz` or `/ready` endpoint? → Flag it
- No structured logging configuration? → Flag it
- No trace propagation middleware? → Flag it
- Missing `tests/` for health endpoints? → Flag it

This produces a structured drift report that tells the agent exactly what needs to be fixed.

### Step 4: Security Vulnerability Scan

The agent sends the repository's `requirements.txt` to the **Security MCP Server**, which scans every dependency against a vulnerability database. It returns any findings — CVE identifiers, severity levels, affected packages, and recommended fixes.

### Step 5: Apply Compliance Patches

This is where the agent writes code. Based on the drift report and vulnerability findings, the agent applies patches:

- Adds `/healthz` and `/ready` endpoints to the FastAPI app
- Adds structured logging configuration with `structlog`
- Adds trace propagation middleware for `X-Request-ID` and `traceparent` headers
- Updates `requirements.txt` to fix vulnerable dependency versions
- Adds test files to cover the new endpoints

The patching is done by the **Copilot SDK itself** — it generates context-aware code that fits the existing application structure. If the SDK's output isn't usable, deterministic fallback templates are applied instead.

### Step 6: Evaluate Change Management Approvals

The agent consults the **Change Management MCP Server** with the service name and the list of files that were modified. The server evaluates the change against an approval matrix and returns:

- The **risk level** (low, medium, high)
- The **required approvers** (e.g., Service Owner, SRE-Prod, Security Team)
- The **rationale** for why those approvals are needed

This information is included in the PR description so reviewers know what's expected.

### Step 7: Run Tests

The agent installs the repository's dependencies and runs `pytest` to verify the patches don't break anything. If tests pass, great. If they fail, the agent notes the failure but **still creates the PR** — because it's better to surface the issue for human review than to silently skip the repository.

### Step 8: Commit, Push, and Create the Pull Request

The agent commits all changes to a uniquely named branch, pushes it to GitHub, and opens a Pull Request. The PR includes:

- A **summary** of all changes made
- **Policy references** — which compliance policies drove each change
- A **risk assessment** from the change management evaluation
- **Required approvers** based on the risk level
- **Test results** so reviewers know the verification status

The PR is a self-contained, reviewable artifact that a human can approve with full context.

### Repeat for Every Repository

The agent then moves to the next repository and repeats the entire lifecycle. In this demo, it processes all three Contoso APIs sequentially — Orders, Payments, and Catalog — each getting its own compliance PR.

---

## Scaling to the Enterprise

In this demo, we process **3 repositories** sequentially in a single SDK session. That's intentional — it keeps the flow predictable and easy to follow on screen.

But in a real enterprise with **50, 100, or 500 repositories**, the architecture shifts:

- **One SDK session per repository** — avoids context window overflow and enables independent timeouts
- **Parallel worker pool** — multiple repos processed concurrently with controlled concurrency
- **Per-repo state tracking** — a persistent store for retry and resume after failures
- **Scheduled or event-driven triggers** — run nightly, on policy updates, or when new CVEs are published

The fundamental workflow stays the same. The agent still clones, detects, scans, patches, tests, and creates PRs. But now it does it across the entire fleet, continuously, keeping every repository in compliance as policies evolve and new vulnerabilities emerge.

---

## Key Takeaways

1. **The GitHub Copilot SDK is an infrastructure service here** — not an interactive assistant. Code drives the conversation, and the SDK orchestrates the workflow autonomously.

2. **The same engine that powers VS Code Agent Mode** is what reasons about compliance, decides which tools to call, and generates the code patches and PR descriptions.

3. **Compliance knowledge, vulnerability data, and source code** are all stitched together by the agent — eliminating the manual cross-referencing that makes this work so painful.

4. **Every action runs under the user's authenticated GitHub context** — maintaining the audit trail and permission boundaries that enterprises require.

5. **The output is a Pull Request** — not an automated commit. Humans stay in the loop for review and approval, but the grunt work of detection, patching, and documentation is handled by the agent.

6. **This scales from 3 repos to 300** — the architecture supports parallel processing, per-repo isolation, and continuous execution for true fleet-wide compliance enforcement.
