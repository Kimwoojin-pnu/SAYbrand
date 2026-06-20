from datetime import date
from unittest.mock import MagicMock, patch

from cardnews.llm_scripter import generate_script_with_llm
from cardnews.models import CardNewsScript, ThreatRecord

RECORD = ThreatRecord(
    id="threat-llm-test",
    detected_at=date(2026, 6, 16),
    category="HIGH",
    summary="SNS에서 부정 리뷰가 빠르게 확산되고 있습니다.",
    impact_score=9,
)


def test_generate_script_with_llm_falls_back_to_template_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    script = generate_script_with_llm(RECORD)

    assert isinstance(script, CardNewsScript)
    assert script.source_id == RECORD.id
    assert len(script.slides) >= 1


def test_generate_script_with_llm_uses_claude_when_api_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    llm_response_json = """{
        "title": "브랜드 위기, 당신의 차례가 될 수 있습니다",
        "slides": [
            {"headline": "충격적인 사건이 일어났습니다", "body": "SNS에서 부정 리뷰가 빠르게 확산되며 한 브랜드의 신뢰가 무너지기 시작했습니다."},
            {"headline": "왜 이렇게 빠르게 퍼질까요?", "body": "알고리즘은 부정 콘텐츠에 더 많은 노출을 줍니다. 몇 시간 만에 수만 명에게 도달합니다."},
            {"headline": "미리 알았다면 막을 수 있었습니다", "body": "SAYbrand는 이런 위협을 탐지 즉시 알려드립니다. 지금 무료로 시작하세요."}
        ],
        "description": "브랜드 리스크 실시간 감지 — SAYbrand와 함께 위기를 예방하세요.",
        "tags": ["브랜드리스크", "온라인평판", "위기관리", "마케팅", "SAYbrand"]
    }"""

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=llm_response_json)]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("cardnews.llm_scripter.anthropic.Anthropic", return_value=mock_client):
        script = generate_script_with_llm(RECORD)

    assert script.source_id == RECORD.id
    assert script.title == "브랜드 위기, 당신의 차례가 될 수 있습니다"
    assert len(script.slides) == 3
    assert script.slides[0].headline == "충격적인 사건이 일어났습니다"
    assert "브랜드리스크" in script.tags


def test_generate_script_with_llm_falls_back_on_invalid_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="이건 JSON이 아닙니다")]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("cardnews.llm_scripter.anthropic.Anthropic", return_value=mock_client):
        script = generate_script_with_llm(RECORD)

    assert isinstance(script, CardNewsScript)
    assert script.source_id == RECORD.id
