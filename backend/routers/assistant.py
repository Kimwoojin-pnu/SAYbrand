"""AI 어시스턴트 — Gemini 기반 브랜드 위기 대응 챗"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.middleware.auth import require_login
from backend.services.ai.gemini_client import gemini_call

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assistant", tags=["assistant"])

_SYSTEM_PROMPT = """당신은 SAYbrand의 브랜드 위기 커뮤니케이션·마케팅 리스크 전문 AI 어시스턴트입니다.

전문 영역:
- 브랜드 위기 대응 전략 (불매운동·갑질 폭로·제품 결함·ESG 위반·광고 논란 등)
- SNS 공식 대응 메시지 초안 (실제 사용 가능한 문구 수준으로)
- 위기 단계별 커뮤니케이션 타임라인 (골든타임 1시간 / 24시간 / 72시간)
- 스테이크홀더별 메시지 전략 (소비자·언론·투자자·내부 직원)
- 경쟁사 공격·캠페인 역풍 대응
- 마케팅 캠페인 사전 리스크 진단

응답 원칙:
1. 구체적 실행 문구 제시 — "모니터링 강화" 같은 추상적 답변 금지
2. 위기 단계 명시 — 현재 상황이 1단계(감지)·2단계(확산)·3단계(위기) 중 어디인지 판단
3. 메시지 초안 제공 — 요청 시 실제 SNS 게시 가능한 수준의 문구 작성
4. 한국 소비자 정서 반영 — 국내 SNS 반응 패턴과 정서 고려
응답은 한국어로, 최대 400자 이내."""


class ChatRequest(BaseModel):
    message: str
    context: str = ""


class ChatResponse(BaseModel):
    reply: str
    is_mock: bool = False


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user=Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="메시지를 입력하세요.")

    prompt = req.message[:500]
    if req.context:
        prompt = f"[컨텍스트]\n{req.context[:300]}\n\n[질문]\n{prompt}"

    result = await gemini_call(
        prompt=prompt,
        model_name="gemini-2.5-flash-lite",
        cache_ttl=300,
        expect_json=False,
        max_output_tokens=600,
        system_instruction=_SYSTEM_PROMPT,
    )

    if result is None:
        return ChatResponse(
            reply="[Mock] GEMINI_API_KEY 설정 시 AI 어시스턴트가 활성화됩니다. 브랜드 위기 대응, 커뮤니케이션 전략, 리스크 분석 등을 질문해보세요.",
            is_mock=True,
        )

    return ChatResponse(reply=str(result)[:600])
