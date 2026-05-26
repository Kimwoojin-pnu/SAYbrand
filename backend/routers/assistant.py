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

_SYSTEM_PROMPT = """당신은 SAYbrand 브랜드 위기 대응 AI 어시스턴트입니다.
사용자의 브랜드 모니터링 데이터를 기반으로 위기 대응 전략, 커뮤니케이션 가이드, 리스크 평가를 제공합니다.
응답은 한국어로, 구체적이고 실행 가능한 조언을 제시하세요.
최대 300자 이내로 답변하세요."""


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
        model_name="gemini-2.0-flash",
        cache_ttl=300,
        expect_json=False,
        max_output_tokens=400,
        system_instruction=_SYSTEM_PROMPT,
    )

    if result is None:
        return ChatResponse(
            reply="[Mock] GEMINI_API_KEY 설정 시 AI 어시스턴트가 활성화됩니다. 브랜드 위기 대응, 커뮤니케이션 전략, 리스크 분석 등을 질문해보세요.",
            is_mock=True,
        )

    return ChatResponse(reply=str(result)[:600])
