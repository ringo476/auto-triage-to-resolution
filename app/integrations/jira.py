import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings


@retry(wait=wait_exponential(multiplier=2, min=2, max=10), stop=stop_after_attempt(3))
async def create_jira_ticket(summary: str, description: str, issue_type: str = "Bug") -> str:
    """
    Creates a Jira issue and returns the direct URL to the ticket.
    Using Jira API v2 for simplified raw string descriptions.
    """
    if not all([settings.JIRA_DOMAIN, settings.JIRA_EMAIL, settings.JIRA_API_TOKEN, settings.JIRA_PROJECT_KEY]):
        return "Error: Missing Jira environment variables."

    url = f"https://{settings.JIRA_DOMAIN}.atlassian.net/rest/api/2/issue"

    # httpx handles Basic Auth natively
    auth = httpx.BasicAuth(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}

    payload = {
        "fields": {
            "project": {"key": settings.JIRA_PROJECT_KEY},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type}
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, auth=auth)
            response.raise_for_status()
            data = response.json()
            return f"https://{settings.JIRA_DOMAIN}.atlassian.net/browse/{data.get('key')}"
        except httpx.HTTPStatusError as e:
            return f"Jira API Error: {e.response.text}"
        except Exception as e:  # noqa: BLE001
            return f"Request Error: {e!s}"
