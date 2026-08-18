import os

import httpx

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

async def send_slack_message(channel_id: str, text: str) -> bool:
    """
    Posts a message to a specific Slack channel.
    channel_id format: "C1234567890" (Do not use channel names like #general)
    """
    if not SLACK_BOT_TOKEN:
        print("Error: SLACK_BOT_TOKEN is not set.")
        return False

    url = "https://slack.com/api/chat.postMessage"
    headers={
        "Authorization":f"Bearer {SLACK_BOT_TOKEN}",
        "CONTENT-TYPE":"application/json"
    }
    payload={
        "channel":channel_id,
        "content":text
    }
    async with httpx.AsyncClient() as client:
        try:
            response=await client.post(url,json=payload,headers=headers)
            response.raise_for_status()
            data=response.json()
            if not data.get("ok"):
                print(f"Slack API Error:{data.get('ok')}")
                return False
            return True
        except Exception as e:
            print(f"Request error: {e!s}")
            return False