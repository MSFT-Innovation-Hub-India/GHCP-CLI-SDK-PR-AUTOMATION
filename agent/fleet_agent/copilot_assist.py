"""
GitHub Copilot SDK Integration
==============================
This module provides the integration point for the GitHub Copilot CLI SDK.

The SDK enables AI-powered capabilities for:
- Generating high-quality PR descriptions
- Suggesting code fixes and improvements
- Creating rollout and testing plans
- Analyzing code for potential issues

Integration Patterns:
1. Direct SDK integration (recommended for production) - USE_COPILOT_SDK=true
2. CLI subprocess integration (simpler, for demos) - USE_COPILOT_CLI=true
3. Deterministic fallback (always works)

Environment Variables:
- USE_COPILOT_SDK: Enable SDK integration (recommended)
- USE_COPILOT_CLI: Enable CLI subprocess integration (fallback)
- COPILOT_MODEL: Model to use (default: gpt-4o)
"""

from __future__ import annotations
import asyncio
import os
import json
import subprocess
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class CopilotDraft:
    """Result from Copilot-assisted drafting."""
    text: str
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None


def _build_prompt(
    prompt: str,
    evidence: str,
    changes: Iterable[str],
    context: Optional[dict] = None,
) -> str:
    """Build the full prompt for Copilot."""
    bullet_changes = "\n".join([f"- {c}" for c in changes]) or "- (none)"
    
    full_prompt = f"""{prompt}

## Policy Evidence (from knowledge base)
{evidence}

## Changes Made
{bullet_changes}
"""
    
    if context:
        full_prompt += f"\n## Additional Context\n{json.dumps(context, indent=2)}\n"
    
    full_prompt += """
## Output Format
Please provide a professional PR description with:
1. **Summary** - Brief overview of the changes
2. **Changes** - Bullet list of specific modifications
3. **Policy Compliance** - How this addresses fleet policies
4. **Risk Assessment** - Any deployment considerations
5. **Testing** - Verification steps performed
"""
    
    return full_prompt


def _draft_with_sdk_direct(prompt: str) -> CopilotDraft:
    """
    Draft using direct SDK integration.
    
    This is the recommended approach for production use.
    Requires the GitHub Copilot SDK to be installed: pip install github-copilot-sdk
    
    The SDK communicates with the Copilot CLI in server mode via JSON-RPC.
    Authentication is handled via GitHub CLI (gh auth login) or environment variables.
    """
    try:
        from copilot import CopilotClient
        
        async def _run_sdk():
            model = os.getenv("COPILOT_MODEL", "gpt-4o")
            
            client = CopilotClient()
            await client.start()
            
            try:
                session = await client.create_session({
                    "model": model,
                    "system_message": {
                        "content": "You are a helpful assistant for creating professional PR descriptions. Be concise and focus on technical accuracy."
                    }
                })
                
                # Collect response using events
                response_text = ""
                done = asyncio.Event()
                
                def on_event(event):
                    nonlocal response_text
                    if event.type.value == "assistant.message":
                        response_text = event.data.content
                    elif event.type.value == "session.idle":
                        done.set()
                
                session.on(on_event)
                await session.send({"prompt": prompt})
                
                # Wait for completion with timeout
                try:
                    await asyncio.wait_for(done.wait(), timeout=60.0)
                except asyncio.TimeoutError:
                    print("Copilot SDK timeout")
                    return None
                
                await session.destroy()
                
                if response_text:
                    return CopilotDraft(
                        text=response_text,
                        model_used=model,
                        tokens_used=None,
                    )
                return None
                
            finally:
                await client.stop()
        
        # Run the async function
        return asyncio.run(_run_sdk())
        
    except ImportError as e:
        print(f"Copilot SDK not installed: {e}")
        print("Install with: pip install github-copilot-sdk")
        return None
    except Exception as e:
        print(f"SDK integration error: {e}")
        return None


def _draft_with_cli(prompt: str) -> CopilotDraft:
    """
    Draft using GitHub Copilot CLI subprocess.
    
    This approach uses the `gh copilot` CLI extension.
    
    Prerequisites:
        gh extension install github/gh-copilot
        gh auth login
    
    Note: CLI approach is simpler but less efficient than direct SDK.
    """
    try:
        # Check if gh copilot is available
        result = subprocess.run(
            ["gh", "copilot", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode != 0:
            return None  # type: ignore
        
        # Use gh copilot suggest for generating content
        # Note: The actual CLI interface may vary
        result = subprocess.run(
            ["gh", "copilot", "suggest", "-t", "shell"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if result.returncode == 0 and result.stdout:
            return CopilotDraft(
                text=result.stdout,
                model_used="gh-copilot-cli",
                tokens_used=None,
            )
    except FileNotFoundError:
        # gh CLI not installed
        pass
    except subprocess.TimeoutExpired:
        print("Copilot CLI timed out")
    except Exception as e:
        print(f"Copilot CLI error: {e}")
    
    return None  # type: ignore


def _draft_deterministic(
    evidence: str,
    changes: Iterable[str],
    mode_note: str = "Copilot SDK disabled",
) -> CopilotDraft:
    """
    Generate deterministic PR description (fallback mode).
    
    This ensures the demo always works end-to-end even without Copilot.
    Use this as a template for what the Copilot-generated version should look like.
    """
    bullet_changes = "\n".join([f"- {c}" for c in changes]) or "- (none)"
    
    text = f"""## Summary
This PR enforces fleet compliance policies across the service. It addresses gaps in observability, operational readiness, and security standards identified by the fleet compliance agent.

## Changes
{bullet_changes}

## Policy Compliance
This PR addresses the following fleet policies:

### OPS-2.1 Health & Readiness
- Added `/healthz` endpoint for Kubernetes liveness probes
- Added `/readyz` endpoint for Kubernetes readiness probes
- Both endpoints return standard JSON response format

### OBS-1.1 Structured Logging  
- Configured `structlog` for JSON-formatted logs
- Added service context (name, version) to all log entries
- Replaced `print()` statements with structured logger

### OBS-3.2 Trace Correlation
- Added `RequestContextMiddleware` for correlation ID handling
- Extracts/generates `trace_id` from W3C `traceparent` header
- Propagates `x-request-id` and `x-trace-id` in responses

## Evidence (Policies Referenced)
{evidence}

## Risk Assessment
- **Risk Level:** Low
- **Breaking Changes:** None - additive changes only
- **Rollback:** Safe to revert if issues detected

## Testing
- [ ] Unit tests added for health endpoints
- [ ] Correlation headers verified in response
- [ ] Structured log format validated

## Deployment
- Standard deployment pipeline
- No special rollout requirements
- Monitor error rates post-deployment

---
*Generated by Fleet Compliance Agent ({mode_note})*
"""
    
    return CopilotDraft(text=text, model_used="deterministic")


def draft_pr_body(
    prompt: str,
    evidence: str,
    changes: Iterable[str],
    use_copilot: bool = False,
    context: Optional[dict] = None,
) -> CopilotDraft:
    """
    Draft the PR body using available methods.
    
    Attempts in order based on environment settings:
    1. Direct SDK integration (if USE_COPILOT_SDK=true and SDK available)
    2. CLI subprocess (if USE_COPILOT_CLI=true and CLI available)
    3. Deterministic fallback (always works)
    
    Args:
        prompt: The instruction for what to generate
        evidence: Policy evidence from RAG search
        changes: List of files/changes made
        use_copilot: Whether to attempt Copilot integration (legacy param)
        context: Optional additional context dict
    
    Returns:
        CopilotDraft with the generated PR body
    """
    changes_list = list(changes)
    
    # Check environment settings
    use_sdk = os.getenv("USE_COPILOT_SDK", "false").lower() == "true"
    use_cli = os.getenv("USE_COPILOT_CLI", "false").lower() == "true"
    
    # Legacy support: use_copilot param enables CLI mode
    if use_copilot and not use_sdk:
        use_cli = True
    
    if not use_sdk and not use_cli:
        return _draft_deterministic(evidence, changes_list, "Copilot SDK disabled")
    
    # Build the full prompt
    full_prompt = _build_prompt(prompt, evidence, changes_list, context)
    
    # Try direct SDK first if enabled
    if use_sdk:
        print("Using GitHub Copilot SDK for PR description...")
        result = _draft_with_sdk_direct(full_prompt)
        if result:
            return result
        print("SDK failed, trying CLI fallback...")
    
    # Try CLI approach if enabled
    if use_cli or use_sdk:  # SDK enables CLI as fallback
        print("Using GitHub Copilot CLI for PR description...")
        result = _draft_with_cli(full_prompt)
        if result:
            return result
    
    # Fall back to deterministic
    mode_note = "Copilot SDK/CLI requested but not available"
    return _draft_deterministic(evidence, changes_list, mode_note)


def suggest_code_fix(
    file_path: str,
    issue_description: str,
    code_snippet: str,
    use_copilot: bool = False,
) -> Optional[str]:
    """
    Suggest a code fix using Copilot.
    
    This is an optional enhancement - the agent uses deterministic patching
    by default for reliability, but can use Copilot for novel fixes.
    
    Args:
        file_path: Path to the file being fixed
        issue_description: Description of the issue to fix
        code_snippet: The code that needs fixing
        use_copilot: Whether to use Copilot for suggestions
    
    Returns:
        Suggested fix as string, or None if unavailable
    """
    if not use_copilot:
        return None
    
    prompt = f"""Fix the following code issue:

File: {file_path}
Issue: {issue_description}

Current code:
```python
{code_snippet}
```

Provide the corrected code only, no explanation.
"""
    
    # Try SDK
    result = _draft_with_sdk_direct(prompt)
    if result:
        return result.text
    
    # Try CLI
    result = _draft_with_cli(prompt)
    if result:
        return result.text
    
    return None


def generate_test_suggestions(
    file_path: str,
    code_content: str,
    use_copilot: bool = False,
) -> Optional[str]:
    """
    Generate test suggestions for code using Copilot.
    
    Args:
        file_path: Path to the file to generate tests for
        code_content: The code content
        use_copilot: Whether to use Copilot
    
    Returns:
        Suggested test code, or None if unavailable
    """
    if not use_copilot:
        return None
    
    prompt = f"""Generate pytest unit tests for the following code:

File: {file_path}

```python
{code_content}
```

Generate comprehensive tests covering:
1. Happy path scenarios
2. Edge cases
3. Error handling

Use pytest fixtures and assertions. Output only the test code.
"""
    
    result = _draft_with_sdk_direct(prompt)
    if result:
        return result.text
    
    result = _draft_with_cli(prompt)
    if result:
        return result.text
    
    return None
