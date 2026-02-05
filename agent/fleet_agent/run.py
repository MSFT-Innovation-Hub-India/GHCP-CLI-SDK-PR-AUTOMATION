from __future__ import annotations
import os, json, time, subprocess
from pathlib import Path
from nanoid import generate
from dotenv import load_dotenv

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
    gh_auth_status()

    repos = json.loads((ROOT / "config" / "repos.json").read_text(encoding="utf-8"))["repos"]

    # Use Azure OpenAI vector search for knowledge retrieval
    hits = search("structured logging trace propagation health readiness approval vulnerability evidence", k=4)
    evidence = "\n".join([f"- **{h.doc_id}**: {h.excerpt}" for h in hits])

    pytest_enabled = os.getenv("PYTEST_ENABLED", "true").lower() == "true"
    use_copilot = os.getenv("USE_COPILOT_SDK", "false").lower() == "true"

    for url in repos:
        service = repo_name(url)
        print(f"\n=== Processing {service} ===")

        ws = WORKSPACES / f"{service}-{generate(size=6)}"
        clone_repo(url, ws)

        drift = detect(ws)
        if not drift.applicable:
            print("Skipping: not applicable")
            continue

        req_path = ws / "requirements.txt"
        req_text = req_path.read_text(encoding="utf-8") if req_path.exists() else ""
        sec = security_scan(req_text)

        needs_fix = drift.missing_healthz or drift.missing_readyz or drift.missing_structlog or drift.missing_middleware or bool(sec.get("findings"))
        if not needs_fix:
            print("No drift detected.")
            continue

        branch = f"chore/fleet-compliance-{time.time_ns()}"
        checkout_branch(ws, branch)

        touched = apply(ws, service)

        approvals = approval(service, touched)
        labels = []
        if "SRE-Prod" in approvals.get("required_approvals", []):
            labels.append("needs-sre-approval")
        if "Security" in approvals.get("required_approvals", []):
            labels.append("needs-security-approval")

        if pytest_enabled and (ws / "tests").exists():
            try:
                subprocess.run(["python", "-m", "pip", "install", "-r", "requirements.txt"], cwd=str(ws), check=False)
                r = subprocess.run(["python", "-m", "pytest", "-q"], cwd=str(ws), capture_output=True, text=True)
                if r.stdout.strip():
                    print(r.stdout)
                if r.returncode != 0:
                    print(r.stderr)
                    print("Local tests failed; still opening PR for review.")
            except Exception as e:
                print(f"pytest skipped: {e}")

        committed = commit_all(ws, "chore: enforce logging/tracing/health gates")
        if not committed:
            print("Nothing to commit.")
            continue

        push_branch(ws, branch)

        title = f"chore({service}): enforce logging/tracing/health gates"
        body = draft_pr_body(
            prompt="Write a PR description for a fleet compliance remediation PR. Include risk and rollout suggestions.",
            evidence=evidence,
            changes=touched,
            use_copilot=use_copilot
        ).text

        pr_url = open_pr(ws, "main", branch, title, body, labels)
        print(f"Opened PR: {pr_url}")

    print("\nDone.")

if __name__ == "__main__":
    main()
