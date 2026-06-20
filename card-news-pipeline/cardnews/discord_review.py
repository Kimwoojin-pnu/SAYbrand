from contextlib import ExitStack
from pathlib import Path
from urllib.parse import quote

import requests

from cardnews.models import CardNewsScript

APPROVE_EMOJI = "✅"  # ✅
REJECT_EMOJI = "❌"  # ❌


def send_preview(
    script: CardNewsScript,
    video_path: Path,
    slide_paths: list[Path],
    webhook_url: str,
) -> dict:
    content = (
        f"**{script.title}**\n"
        f"{script.description}\n"
        f"태그: {', '.join(script.tags)}\n"
        f"영상 파일: {video_path}\n\n"
        f"승인하려면 {APPROVE_EMOJI}, 반려하려면 {REJECT_EMOJI} 로 반응해주세요."
    )

    with ExitStack() as stack:
        files = {
            f"files[{index}]": (slide_path.name, stack.enter_context(open(slide_path, "rb")), "image/png")
            for index, slide_path in enumerate(slide_paths)
        }
        response = requests.post(
            webhook_url,
            params={"wait": "true"},
            data={"content": content},
            files=files,
            timeout=30,
        )

    response.raise_for_status()
    return response.json()


DISCORD_API_BASE = "https://discord.com/api/v10"


def check_reaction(channel_id: str, message_id: str, bot_token: str) -> str:
    headers = {"Authorization": f"Bot {bot_token}"}
    base_url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages/{message_id}/reactions"

    approve_response = requests.get(f"{base_url}/{quote(APPROVE_EMOJI)}", headers=headers, timeout=30)
    approve_response.raise_for_status()
    if approve_response.json():
        return "approved"

    reject_response = requests.get(f"{base_url}/{quote(REJECT_EMOJI)}", headers=headers, timeout=30)
    reject_response.raise_for_status()
    if reject_response.json():
        return "rejected"

    return "pending"
