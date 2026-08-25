import httpx

from app.config import settings


async def send_slack_message(channel_id: str, text: str) -> bool:
    """
    Posts a message to a specific Slack channel.
    channel_id format: "C1234567890" (Do not use channel names like #general)
    """
    if not settings.SLACK_BOT_TOKEN:
        print("Error: SLACK_BOT_TOKEN is not set.")
        return False

    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"}
    payload = {
        "channel": channel_id,
        "text": text
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                print(f"Slack API Error: {data.get('error')}")
                return False
            return True
        except Exception as e:  # noqa: BLE001
            print(f"Request error: {e!s}")
            return False
