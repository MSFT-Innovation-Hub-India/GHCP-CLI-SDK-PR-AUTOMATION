from __future__ import annotations
import os, json, time, subprocess
from pathlib import Path
from nanoid import generate
from dotenv import load_dotenv

from fleet_agent.tracker import tracker, step, track_call
from fleet_agent.rag import search
from fleet_agent.github_ops import gh_auth_status, clone_repo, checkout_branch, commit_all, push_branch, open_pr
from fleet_agent.mcp_clients import approval, security_scan
from fleet_agent.patcher_fastapi import detect, apply
from fleet_agent.copilot_assist import draft_pr_body

ROOT = Path(__file__).resolve().parents[1]  # agent/
WORKSPACES = ROOT / "workspaces"
WORKSPACES.mkdir(parents=True, exist_ok=True)

def repo_name(url: str) -> str:
    return url.rstrip("/").split("/")[-1].removesuffix(".git")

def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    
    # Start progress tracking
    tracker.start_run("Fleet Compliance Agent")
    
    with step("Authenticate GitHub CLI"):
        gh_auth_status()

    repos = json.loads((ROOT / "config" / "repos.json").read_text(encoding="utf-8"))["repos"]
    tracker.info(f"Loaded {len(repos)} repositories from config")

    # RAG search for policy evidence
    with step("Search knowledge base (RAG)"):
        with track_call("RAG", "vector_search", "policy evidence query") as call:
            hits = search("structured logging trace propagation health readiness approval vulnerability evidence", k=4)
            call.response_summary = f"{len(hits)} policy documents found"
        evidence = "\n".join([f"- **{h.doc_id}**: {h.excerpt}" for h in hits])

    pytest_enabled = os.getenv("PYTEST_ENABLED", "true").lower() == "true"
    use_copilot = os.getenv("USE_COPILOT_SDK", "false").lower() == "true"

    for url in repos:
        service = repo_name(url)
        tracker.set_repo(service)

        ws = WORKSPACES / f"{service}-{generate(size=6)}"
        
        with step("Clone repository", url):
            clone_repo(url, ws)

        with step("Detect compliance drift"):
            drift = detect(ws)
            if not drift.applicable:
                tracker.skip_step("Apply patches", "not applicable")
                continue

        req_path = ws / "requirements.txt"
        req_text = req_path.read_text(encoding="utf-8") if req_path.exists() else ""
        
        with step("Security vulnerability scan"):
            with track_call("MCP", "security_scan", f"{len(req_text)} bytes") as call:
                sec = security_scan(req_text)
                findings_count = len(sec.get("findings", []))
                call.response_summary = f"{findings_count} vulnerabilities found"

        needs_fix = drift.missing_healthz or drift.missing_readyz or drift.missing_structlog or drift.missing_middleware or bool(sec.get("findings"))
        if not needs_fix:
            tracker.skip_step("Apply patches", "no drift detected")
            continue

        branch = f"chore/fleet-compliance-{time.time_ns()}"
        
        with step("Create feature branch", branch):
            checkout_branch(ws, branch)

        with step("Apply compliance patches"):
            touched = apply(ws, service)
            tracker.info(f"Modified {len(touched)} files")

        with step("Evaluate approvals (MCP)"):
            with track_call("MCP", "change_mgmt/approval", service) as call:
                approvals = approval(service, touched)
                required = approvals.get("required_approvals", [])
                call.response_summary = f"requires: {', '.join(required) or 'none'}"
        
        labels = []
        if "SRE-Prod" in approvals.get("required_approvals", []):
            labels.append("needs-sre-approval")
        if "Security" in approvals.get("required_approvals", []):
            labels.append("needs-security-approval")

        if pytest_enabled and (ws / "tests").exists():
            with step("Run local tests"):
                try:
                    subprocess.run(["python", "-m", "pip", "install", "-r", "requirements.txt"], cwd=str(ws), check=False, capture_output=True)
                    r = subprocess.run(["python", "-m", "pytest", "-q"], cwd=str(ws), capture_output=True, text=True)
                    if r.returncode == 0:
                        tracker.info("All tests passed")
                    else:
                        tracker.info("Tests failed - will continue with PR")
                        if r.stdout.strip():
                            print(r.stdout)
                except Exception as e:
                    tracker.info(f"pytest skipped: {e}")
        else:
            tracker.skip_step("Run local tests", "disabled or no tests")

        with step("Commit changes"):
            committed = commit_all(ws, "chore: enforce logging/tracing/health gates")
            if not committed:
                tracker.skip_step("Push & open PR", "nothing to commit")
                continue

        with step("Push branch to remote"):
            push_branch(ws, branch)

        with step("Generate PR description"):
            if use_copilot:
                with track_call("Copilot", "draft_pr_body", "SDK enabled") as call:
                    body = draft_pr_body(
                        prompt="Write a PR description for a fleet compliance remediation PR. Include risk and rollout suggestions.",
                        evidence=evidence,
                        changes=touched,
                        use_copilot=use_copilot
                    ).text
                    call.response_summary = f"{len(body)} chars generated"
            else:
                body = draft_pr_body(
                    prompt="Write a PR description for a fleet compliance remediation PR.",
                    evidence=evidence,
                    changes=touched,
                    use_copilot=False
                ).text
                tracker.info("Using deterministic template (Copilot SDK disabled)")

        with step("Open Pull Request"):
            with track_call("GitHub", "create_pr", f"main ← {branch}") as call:
                title = f"chore({service}): enforce logging/tracing/health gates"
                pr_url = open_pr(ws, "main", branch, title, body, labels)
                call.response_summary = pr_url
        
        tracker.info(f"PR opened: {pr_url}")

    # End tracking and print summary
    tracker.end_run()

if __name__ == "__main__":
    main()
