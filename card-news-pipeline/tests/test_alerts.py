from unittest.mock import patch

import requests

from cardnews.alerts import send_alert


def test_send_alert_skips_when_webhook_not_configured(monkeypatch, capsys):
    monkeypatch.delenv("DISCORD_ALERT_WEBHOOK_URL", raising=False)

    with patch("cardnews.alerts.requests.post") as mock_post:
        send_alert("테스트 알림")

    mock_post.assert_not_called()
    captured = capsys.readouterr()
    assert "DISCORD_ALERT_WEBHOOK_URL이 설정되지 않아" in captured.out


def test_send_alert_posts_message_to_webhook(monkeypatch):
    monkeypatch.setenv("DISCORD_ALERT_WEBHOOK_URL", "https://discord.com/api/webhooks/alert")

    with patch("cardnews.alerts.requests.post") as mock_post:
        send_alert("업로드 실패")

    mock_post.assert_called_once_with(
        "https://discord.com/api/webhooks/alert",
        json={"content": "업로드 실패"},
        timeout=10,
    )


def test_send_alert_handles_request_exception(monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_ALERT_WEBHOOK_URL", "https://discord.com/api/webhooks/alert")

    with patch("cardnews.alerts.requests.post", side_effect=requests.exceptions.RequestException("boom")):
        send_alert("업로드 실패")

    captured = capsys.readouterr()
    assert "실패 알림 전송 중 오류가 발생했습니다" in captured.out
