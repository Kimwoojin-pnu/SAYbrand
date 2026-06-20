import os

import requests


def send_alert(message: str) -> None:
    webhook_url = os.environ.get("DISCORD_ALERT_WEBHOOK_URL")
    if not webhook_url:
        print("DISCORD_ALERT_WEBHOOK_URL이 설정되지 않아 알림을 보내지 않았습니다.")
        return

    try:
        requests.post(webhook_url, json={"content": message}, timeout=10)
    except requests.exceptions.RequestException as error:
        print(f"실패 알림 전송 중 오류가 발생했습니다: {error}")
