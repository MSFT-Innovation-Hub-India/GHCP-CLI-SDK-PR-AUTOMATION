"""Test script for the agentic loop with custom tools."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from fleet_agent.agent_loop import run_agent

async def test_single_repo():
    """Test with a single repository."""
    result = await run_agent('''Process this repository: https://github.com/ssrikantan/contoso-orders-api

Start by searching the knowledge base for health endpoint policies, then clone the repository and detect compliance drift.''')
    
    print('\\n=== Test Complete ===')
    print(f'Tool calls: {len(result.tool_calls)}')
    print(f'PRs created: {len(result.prs_created)}')
    for pr in result.prs_created:
        print(f'  - {pr}')

async def test_all_repos():
    """Test with all repositories from config."""
    import json
    from pathlib import Path
    
    repos_config = Path(__file__).parent / "config" / "repos.json"
    repos = json.loads(repos_config.read_text(encoding="utf-8"))["repos"]
    
    user_input = f"""Analyze and enforce compliance on these FastAPI repositories:

{chr(10).join(f'• {url}' for url in repos)}

For each repository:
1. Search knowledge base for compliance policies (health endpoints, logging, security)
2. Clone the repository
3. Detect compliance drift
4. Scan for security vulnerabilities
5. Create a feature branch
6. Apply compliance patches
7. Get required approvals
8. Run tests
9. Commit and push changes
10. Create a Pull Request with policy evidence in the description

Process all repositories completely."""
    
    result = await run_agent(user_input)
    
    print('\\n=== Test Complete ===')
    print(f'Tool calls: {len(result.tool_calls)}')
    print(f'PRs created: {len(result.prs_created)}')
    for pr in result.prs_created:
        print(f'  - {pr}')

if __name__ == '__main__':
    # Run single repo test by default
    asyncio.run(test_single_repo())
