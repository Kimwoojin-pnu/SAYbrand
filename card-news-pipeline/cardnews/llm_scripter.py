import json
import logging
import os

import anthropic

_logger = logging.getLogger(__name__)

from cardnews.models import CardNewsScript, Slide, ThreatRecord
from cardnews.scripter import generate_script

_MODEL = "claude-haiku-4-5-20251001"

_PROMPT_TEMPLATE = """다음 브랜드 위협 데이터를 바탕으로 유튜브 쇼츠용 카드뉴스 스크립트를 작성해주세요.

위협 유형: {category}
내용 요약: {summary}
위험 점수: {impact_score}/10

요구사항:
- 실제 뉴스 기사처럼 작성할 것 (특정 브랜드/기업/개인명은 가명화·일반화)
- 슬라이드 정확히 1장
- headline: 뉴스 기사 제목처럼 핵심을 담은 강렬한 한 문장, 반드시 1줄 (줄바꿈 없이 20자 이내)
- body: 해당 이슈의 배경, 경위, 파급효과를 3~4문장으로 설명 (150자 이내)
- 태그는 5개, #없이 문자열만

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "title": "...",
  "slides": [
    {{"headline": "...", "body": "..."}}
  ],
  "description": "...",
  "tags": ["...", "...", "...", "...", "..."]
}}"""


def generate_script_with_llm(record: ThreatRecord) -> CardNewsScript:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return generate_script(record)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": _PROMPT_TEMPLATE.format(
                        category=record.category,
                        summary=record.summary,
                        impact_score=record.impact_score,
                    ),
                }
            ],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip().rstrip("`").strip()
        data = json.loads(raw)
        return CardNewsScript(
            source_id=record.id,
            title=data["title"],
            slides=[Slide(headline=s["headline"], body=s["body"]) for s in data["slides"]],
            description=data["description"],
            tags=data["tags"],
        )
    except Exception as exc:
        _logger.warning("LLM 스크립팅 실패, 템플릿으로 폴백: %s", exc)
        return generate_script(record)
