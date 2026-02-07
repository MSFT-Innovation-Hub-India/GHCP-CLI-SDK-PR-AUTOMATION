"""
GitHub Operations Module
========================
Provides Git and GitHub CLI operations for the Fleet Compliance Agent.

This module wraps common Git and GitHub CLI commands used during the
compliance enforcement workflow:
- Repository cloning
- Branch management
- Committing and pushing changes
- Creating Pull Requests via `gh pr create`

Requirements:
    - Git CLI installed and in PATH
    - GitHub CLI (`gh`) installed and authenticated
      (run `gh auth login` to authenticate)

Usage:
    from fleet_agent.github_ops import clone_repo, checkout_branch, open_pr
    
    clone_repo("https://github.com/org/repo", Path("./workspace"))
    checkout_branch(Path("./workspace"), "feature/compliance")
    pr_url = open_pr(Path("./workspace"), "main", "feature/compliance", "Title", "Body", [])
"""

from __future__ import annotations
import subprocess
from pathlib import Path


def _run(args: list[str], cwd: Path | None = None) -> str:
    """
    Execute a shell command and return stdout.
    
    Args:
        args: Command and arguments as list (e.g., ["git", "status"])
        cwd: Working directory for the command (optional)
    
    Returns:
        Stripped stdout from the command
    
    Raises:
        RuntimeError: If the command exits with non-zero status
    """
    p = subprocess.run(args, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{p.stderr or p.stdout}")
    return (p.stdout or "").strip()

def gh_auth_status() -> str:
    """
    Check GitHub CLI authentication status.
    
    Returns:
        Authentication status message from `gh auth status`
    
    Raises:
        RuntimeError: If not authenticated with GitHub CLI
    """
    return _run(["gh", "auth", "status"])

def clone_repo(url: str, dest: Path) -> None:
    """
    Clone a GitHub repository (shallow clone, depth=1).
    
    Args:
        url: Repository URL (e.g., https://github.com/org/repo)
        dest: Local directory path to clone into
    
    Raises:
        RuntimeError: If clone fails (invalid URL, no access, etc.)
    """
    _run(["git", "clone", "--depth", "1", url, str(dest)])

def checkout_branch(repo: Path, branch: str) -> None:
    """
    Create and checkout a new branch.
    
    Args:
        repo: Path to the repository working directory
        branch: Name of the new branch to create
    
    Raises:
        RuntimeError: If branch creation fails (e.g., branch exists)
    """
    _run(["git", "checkout", "-b", branch], cwd=repo)

# Standard Python gitignore patterns to exclude from commits
PYTHON_GITIGNORE_PATTERNS = """
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.env
.venv
env/
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# pytest
.pytest_cache/
.coverage
htmlcov/

# mypy
.mypy_cache/
"""


def ensure_gitignore(repo: Path) -> bool:
    """
    Ensure the repository has a .gitignore with Python patterns.
    
    If .gitignore doesn't exist, creates one with standard Python patterns.
    If it exists but lacks key patterns, appends them.
    
    Args:
        repo: Path to the repository working directory
    
    Returns:
        True if .gitignore was created or modified, False if already sufficient
    """
    gitignore_path = repo / ".gitignore"
    existing_content = ""
    
    if gitignore_path.exists():
        existing_content = gitignore_path.read_text(encoding="utf-8")
        # Check if essential patterns already exist
        if "__pycache__" in existing_content and "*.pyc" in existing_content:
            return False  # Already has Python patterns
    
    # Append patterns (or create new file)
    patterns_to_add = []
    for line in PYTHON_GITIGNORE_PATTERNS.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and line not in existing_content:
            patterns_to_add.append(line)
    
    if not patterns_to_add and existing_content:
        return False  # Nothing to add
    
    # Write the gitignore
    if existing_content:
        # Append to existing
        new_content = existing_content.rstrip() + "\n\n# Added by Fleet Compliance Agent\n"
        new_content += "\n".join(patterns_to_add) + "\n"
    else:
        # Create new
        new_content = "# Python .gitignore (Fleet Compliance Agent)\n" + PYTHON_GITIGNORE_PATTERNS.strip() + "\n"
    
    gitignore_path.write_text(new_content, encoding="utf-8")
    return True


def commit_all(repo: Path, msg: str) -> bool:
    """
    Stage all changes and commit with a message.
    
    Ensures proper .gitignore exists before staging to exclude
    bytecode files (.pyc, __pycache__) and other generated files.
    
    Args:
        repo: Path to the repository working directory
        msg: Commit message
    
    Returns:
        True if changes were committed, False if nothing to commit
    
    Raises:
        RuntimeError: If commit fails for reasons other than empty changeset
    """
    # Ensure .gitignore exists before staging
    gitignore_added = ensure_gitignore(repo)
    if gitignore_added:
        # Stage the .gitignore first so it takes effect
        _run(["git", "add", ".gitignore"], cwd=repo)
    
    _run(["git", "add", "-A"], cwd=repo)
    try:
        _run(["git", "commit", "-m", msg], cwd=repo)
        return True
    except RuntimeError as e:
        if "nothing to commit" in str(e).lower():
            return False
        raise

def push_branch(repo: Path, branch: str) -> None:
    """
    Push a branch to the remote origin.
    
    Args:
        repo: Path to the repository working directory
        branch: Name of the branch to push
    
    Raises:
        RuntimeError: If push fails (no access, branch exists, etc.)
    """
    _run(["git", "push", "-u", "origin", branch], cwd=repo)

def open_pr(repo: Path, base: str, head: str, title: str, body: str, labels: list[str]) -> str:
    """
    Create a Pull Request using GitHub CLI.
    
    This function handles:
    - Creating labels if they don't exist
    - Creating the PR with `gh pr create`
    - Extracting PR URL from "already exists" errors (idempotent re-runs)
    - Retrying without labels if label errors occur
    
    Args:
        repo: Path to the repository working directory
        base: Base branch (e.g., "main")
        head: Head branch with changes (e.g., "feature/compliance")
        title: Pull request title
        body: Pull request description (supports Markdown)
        labels: List of labels to apply (created if missing)
    
    Returns:
        URL of the created (or existing) pull request
    
    Raises:
        RuntimeError: If PR creation fails and URL cannot be extracted
    """
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
