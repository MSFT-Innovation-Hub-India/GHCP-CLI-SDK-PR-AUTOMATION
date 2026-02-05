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
        return _run(args, cwd=repo)
    except RuntimeError as e:
        # If label error, retry without labels
        if "not found" in str(e).lower() and "label" in str(e).lower():
            args = ["gh", "pr", "create", "--base", base, "--head", head, "--title", title, "--body", body]
            return _run(args, cwd=repo)
        raise
