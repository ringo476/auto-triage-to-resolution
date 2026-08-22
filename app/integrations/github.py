import asyncio
import os

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_URL = "https://api.github.com"

async def commit_and_push_changes(branch_name: str, commit_message: str) -> bool:
    """
    Runs local git bash commands to commit the AI's file changes and push them to GitHub.
    This must run BEFORE creating the Pull Request.
    """
    commands = [
        f"git checkout -b {branch_name}",
        "git add .",
        f'git commit -m "{commit_message}"',
        f"git push origin {branch_name}"
    ]
    
    for cmd in commands:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _stdout, stderr = await process.communicate()
        
        # If any git command fails (non-zero exit code), abort the sequence
        if process.returncode != 0:
            print(f"Git command failed: {cmd}\nError: {stderr.decode()}")
            return False
            
    # Switch back to main branch after pushing so the local repo is ready for the next bug
    cleanup_process = await asyncio.create_subprocess_shell(
        "git checkout main",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await cleanup_process.communicate()
            
    return True

@retry(wait=wait_exponential(multiplier=2, min=2, max=10), stop=stop_after_attempt(3))
async def create_pull_request(repo_name: str, branch_name: str, base_branch: str, title: str, body: str) -> str:
    """
    Hits the GitHub REST API to open a PR for the branch we just pushed.
    """
    if not GITHUB_TOKEN:
        return "Error: GITHUB_TOKEN is not set in environment."

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    url = f"{GITHUB_API_URL}/repos/{repo_name}/pulls"
    payload = {
        "title": title,
        "head": branch_name,
        "base": base_branch,
        "body": body
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("html_url", "PR created, but no URL returned.")
        except httpx.HTTPStatusError as e:
            return f"GitHub API Error: {e.response.text}"
        except Exception as e:  # noqa: BLE001
            return f"Request Error: {e!s}"