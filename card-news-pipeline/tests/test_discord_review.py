from unittest.mock import MagicMock, patch

from cardnews.discord_review import check_reaction, send_preview
from cardnews.models import CardNewsScript, Slide


def _sample_script() -> CardNewsScript:
    return CardNewsScript(
        source_id="threat-003",
        title="브랜드를 위협하는 순간: 해시태그 확산",
        slides=[Slide(headline="이런 일이 있었습니다", body="본문")],
        description="설명입니다",
        tags=["브랜드리스크", "해시태그확산"],
    )


def test_send_preview_posts_to_webhook_and_returns_message_info(tmp_path):
    slide_path = tmp_path / "threat-003_slide_01.png"
    slide_path.write_bytes(b"fake-png")
    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")

    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "msg123", "channel_id": "chan456"}

    with patch("cardnews.discord_review.requests.post", return_value=mock_response) as mock_post:
        result = send_preview(
            _sample_script(), video_path, [slide_path], "https://discord.com/api/webhooks/x/y"
        )

    assert result == {"id": "msg123", "channel_id": "chan456"}
    mock_response.raise_for_status.assert_called_once()

    _, kwargs = mock_post.call_args
    assert kwargs["params"] == {"wait": "true"}
    assert "브랜드를 위협하는 순간" in kwargs["data"]["content"]
    assert "files[0]" in kwargs["files"]


def test_check_reaction_returns_approved_when_checkmark_present():
    approve_response = MagicMock()
    approve_response.json.return_value = [{"id": "user1"}]

    with patch("cardnews.discord_review.requests.get", return_value=approve_response):
        result = check_reaction("chan456", "msg123", "bot-token")

    assert result == "approved"


def test_check_reaction_returns_rejected_when_only_x_present():
    approve_response = MagicMock()
    approve_response.json.return_value = []
    reject_response = MagicMock()
    reject_response.json.return_value = [{"id": "user1"}]

    with patch(
        "cardnews.discord_review.requests.get",
        side_effect=[approve_response, reject_response],
    ):
        result = check_reaction("chan456", "msg123", "bot-token")

    assert result == "rejected"


def test_check_reaction_returns_pending_when_no_reactions():
    empty_response = MagicMock()
    empty_response.json.return_value = []

    with patch("cardnews.discord_review.requests.get", return_value=empty_response):
        result = check_reaction("chan456", "msg123", "bot-token")

    assert result == "pending"
