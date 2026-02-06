from __future__ import annotations
import subprocess
from pathlib import Path

def _run(args: list[str], cwd: Path | None = None) -> str:
    p = subprocess.run(args, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{p.stderr or p.stdout}")
    return (p.stdout or "").strip()

def gh_auth_status() -> str:
    return _run(["gh", "auth", "status"])

def clone_repo(url: str, dest: Path) -> None:
    _run(["git", "clone", "--depth", "1", url, str(dest)])

def checkout_branch(repo: Path, branch: str) -> None:
    _run(["git", "checkout", "-b", branch], cwd=repo)

def commit_all(repo: Path, msg: str) -> bool:
    _run(["git", "add", "-A"], cwd=repo)
    try:
        _run(["git", "commit", "-m", msg], cwd=repo)
        return True
    except RuntimeError as e:
        if "nothing to commit" in str(e).lower():
            return False
        raise

def push_branch(repo: Path, branch: str) -> None:
    _run(["git", "push", "-u", "origin", branch], cwd=repo)

def open_pr(repo: Path, base: str, head: str, title: str, body: str, labels: list[str]) -> str:
    import re
    print(f"[GITHUB_OPS] open_pr called: repo={repo}, head={head}", flush=True)
    # Try to create labels if they don't exist (ignore errors)
    for label in labels:
        try:
            _run(["gh", "label", "create", label, "--color", "fbca04", "--force"], cwd=repo)
        except RuntimeError:
            pass  # Label may already exist or creation failed - ignore
    
    args = ["gh", "pr", "create", "--base", base, "--head", head, "--title", title, "--body", body]
    if labels:
        args += ["--label", ",".join(labels)]
    
    try:
        result = _run(args, cwd=repo)
        print(f"[GITHUB_OPS] gh pr create returned: {result}", flush=True)
        return result
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[GITHUB_OPS] gh pr create error: {error_msg}", flush=True)
        
        # Check if PR already exists - extract URL from error message
        if "already exists" in error_msg.lower():
            pr_match = re.search(r'https://github\.com/[^/]+/[^/]+/pull/\d+', error_msg)
            if pr_match:
                pr_url = pr_match.group(0)
                print(f"[GITHUB_OPS] PR already exists, extracted URL: {pr_url}", flush=True)
                return pr_url
        
        # If label error, retry without labels
        if "not found" in error_msg.lower() and "label" in error_msg.lower():
            args = ["gh", "pr", "create", "--base", base, "--head", head, "--title", title, "--body", body]
            try:
                result = _run(args, cwd=repo)
                print(f"[GITHUB_OPS] gh pr create (retry) returned: {result}", flush=True)
                return result
            except RuntimeError as retry_e:
                retry_msg = str(retry_e)
                # Also check for "already exists" on retry
                if "already exists" in retry_msg.lower():
                    pr_match = re.search(r'https://github\.com/[^/]+/[^/]+/pull/\d+', retry_msg)
                    if pr_match:
                        return pr_match.group(0)
                raise
        raise
