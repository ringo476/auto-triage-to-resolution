import os

import httpx

JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")            # e.g., "yourcompany"
JIRA_EMAIL = os.getenv("JIRA_EMAIL")              # e.g., "bot@yourcompany.com"
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")      # Your Atlassian API token
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")  # e.g., "ENG"

async def create_jira_ticket(summary: str, description: str, issue_type: str = "Bug") -> str:
    """
    Creates a Jira issue and returns the direct URL to the ticket.
    Using Jira API v2 for simplified raw string descriptions.
    """
    if not all([JIRA_DOMAIN, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY]):
        return "Error: Missing Jira environment variables."

    url = f"https://{JIRA_DOMAIN}.atlassian.net/rest/api/2/issue"
    
    # httpx handles Basic Auth natively
    auth = httpx.BasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
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
            return f"https://{JIRA_DOMAIN}.atlassian.net/browse/{data.get('key')}"
        except httpx.HTTPStatusError as e:
            return f"Jira API Error: {e.response.text}"
        except Exception as e:
            return f"Request Error: {e!s}"