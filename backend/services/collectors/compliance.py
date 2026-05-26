"""법적 준수 공통 레이어 — 모든 수집기가 반드시 통과"""
import urllib.robotparser
import re
import asyncio
import httpx
from datetime import datetime

# SAYbrand 봇 식별 User-Agent
# 봇임을 숨기지 않는 것이 법적으로 안전
SAYBRAND_USER_AGENT = (
    "SAYbrand-Monitor/1.0 "
    "(Brand protection service; "
    "contact: legal@saybrand.ai; "
    "https://saybrand.ai/bot-policy)"
)

# 개인식별정보 제거 패턴
PII_PATTERNS = [
    r"\b\d{3}-\d{4}-\d{4}\b",          # 전화번호
    r"\b\d{2,3}-\d{3,4}-\d{4}\b",      # 지역 전화
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # 이메일
    r"\b\d{6}-[1-4]\d{6}\b",            # 주민번호
    r"\b\d{3}-\d{2}-\d{5}\b",           # 사업자등록번호
    r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
    r".{1,10}[시군구읍면동리].{1,20}\d{1,5}",  # 상세 주소
]


class RobotsTxtChecker:
    """robots.txt 캐시 — 도메인당 1시간 캐싱"""
    _cache: dict[str, tuple[urllib.robotparser.RobotFileParser, datetime]] = {}

    async def is_allowed(self, url: str) -> bool:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        # 캐시 확인 (1시간)
        if domain in self._cache:
            parser, cached_at = self._cache[domain]
            if (datetime.utcnow() - cached_at).total_seconds() < 3600:
                allowed = parser.can_fetch(SAYBRAND_USER_AGENT, url)
                if not allowed:
                    allowed = parser.can_fetch("*", url)
                return allowed

        # robots.txt 가져오기
        robots_url = f"{domain}/robots.txt"
        parser = urllib.robotparser.RobotFileParser()
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(robots_url)
                parser.parse(resp.text.splitlines())
        except Exception:
            # robots.txt 없으면 허용으로 간주
            parser.set_url(robots_url)
            parser.allow_all = True

        self._cache[domain] = (parser, datetime.utcnow())
        return parser.can_fetch("*", url)


def remove_pii(text: str) -> str:
    """개인식별정보 마스킹"""
    for pattern in PII_PATTERNS:
        text = re.sub(pattern, "[개인정보제거]", text)
    return text


class RateLimiter:
    """도메인별 요청 간격 제어"""
    _last_request: dict[str, datetime] = {}
    MIN_INTERVAL_SECONDS = 2.0  # 최소 2초

    async def wait(self, domain: str):
        if domain in self._last_request:
            elapsed = (datetime.utcnow() - self._last_request[domain]).total_seconds()
            if elapsed < self.MIN_INTERVAL_SECONDS:
                await asyncio.sleep(self.MIN_INTERVAL_SECONDS - elapsed)
        self._last_request[domain] = datetime.utcnow()


# 전역 싱글턴
robots_checker = RobotsTxtChecker()
rate_limiter = RateLimiter()
