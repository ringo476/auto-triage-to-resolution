import asyncio

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

GITHUB_API_URL = "https://api.github.com"


async def commit_and_push_changes(repo_path: str, branch_name: str, commit_message: str) -> bool:
    """
    Runs git commands in `repo_path` to commit the AI's file changes and push
    them to GitHub. This must run BEFORE creating the Pull Request.
    """
    commands = [
        # -B (not -b): resets the branch if it already exists, so a retried
        # run for the same ticket_id doesn't fail with "branch already exists".
        ["git", "checkout", "-B", branch_name],
        ["git", "add", "."],
        ["git", "commit", "-m", commit_message],
        ["git", "push", "origin", branch_name],
    ]

    for cmd in commands:
        # Argument-list form (no shell=True) so nothing in commit_message or
        # branch_name — both ultimately derived from LLM/user-supplied text —
        # can be interpreted as shell syntax.
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _stdout, stderr = await process.communicate()

        if process.returncode != 0:
            print(f"Git command failed: {' '.join(cmd)}\nError: {stderr.decode()}")
            return False

    # Switch back to main branch after pushing so the local repo is ready for the next bug
    cleanup_process = await asyncio.create_subprocess_exec(
        "git", "checkout", settings.GITHUB_BASE_BRANCH,
        cwd=repo_path,
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
    if not settings.GITHUB_TOKEN:
        return "Error: GITHUB_TOKEN is not set in environment."

    headers = {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
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
