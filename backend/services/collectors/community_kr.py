"""
한국 커뮤니티 경량 크롤러 (httpx + BeautifulSoup)

사이트별 법적 상태 (수집 전 robots.txt 자동 확인):

✅ 에펨코리아 (fmkorea.com)     — 공개 게시판, 검색 허용
✅ 더쿠 (theqoo.net)           — 공개 게시판
✅ 인스티즈 (instiz.net)        — 공개 게시판
✅ 클리앙 (clien.net)           — 공개 게시판
✅ 루리웹 (ruliweb.com)         — 공개 게시판
✅ 나무위키 (namu.wiki)          — CC BY-NC-SA 라이선스, 명시적 허용

⚠️ DC인사이드 (dcinside.com)   — robots.txt Disallow: * → robots_checker가 자동 차단
⚠️ 블라인드 (blind.so)          — 로그인 필수 → 수집 불가
⚠️ 네이버 카페                  — 로그인 필요 → Naver Search API 사용
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin, quote

import httpx
from bs4 import BeautifulSoup

from backend.services.collectors.base import BaseCollector, make_post
from backend.services.collectors.compliance import (
    robots_checker, rate_limiter,
    remove_pii, SAYBRAND_USER_AGENT,
)

logger = logging.getLogger(__name__)


class KoreanCommunityCollector(BaseCollector):

    SITES = {
        "fmkorea": {
            "base_url": "https://www.fmkorea.com",
            "search_url": "https://www.fmkorea.com/search.php?mid=home&act=IS&is_keyword={keyword}&x=0&y=0",
            "post_selector": "li.li_best2_pic, li.post_item, .bd_lst_tb tr",
            "title_selector": ".title a, td.subject a",
            "link_selector": ".title a, td.subject a",
            "date_selector": ".date, td.time",
            "platform_name": "에펨코리아",
        },
        "theqoo": {
            "base_url": "https://theqoo.net",
            "search_url": "https://theqoo.net/search?keyword={keyword}",
            "post_selector": ".list_item, tr.notice, tr:not(.notice)",
            "title_selector": "a.title, .subject a",
            "link_selector": "a.title, .subject a",
            "date_selector": ".date, .time",
            "platform_name": "더쿠",
        },
        "clien": {
            "base_url": "https://www.clien.net",
            "search_url": "https://www.clien.net/service/search?q={keyword}&sort=recency",
            "post_selector": ".list_item, .list-board-item",
            "title_selector": ".list_subject a, .subject_fixed a",
            "link_selector": ".list_subject a",
            "date_selector": ".list_time, span.timestamp",
            "platform_name": "클리앙",
        },
        "ruliweb": {
            "base_url": "https://bbs.ruliweb.com",
            "search_url": "https://bbs.ruliweb.com/search?q={keyword}&search_type=subject_content",
            "post_selector": "tr.table_body, .board_list tr",
            "title_selector": "a.deco, .title a",
            "link_selector": "a.deco, .title a",
            "date_selector": "td.time, .date",
            "platform_name": "루리웹",
        },
        "instiz": {
            "base_url": "https://www.instiz.net",
            "search_url": "https://www.instiz.net/pt?k={keyword}",
            "post_selector": ".list_table tr, .feed_list li",
            "title_selector": ".subject a, .title a",
            "link_selector": ".subject a, .title a",
            "date_selector": ".date, .time",
            "platform_name": "인스티즈",
        },
        "namu": {
            "base_url": "https://namu.wiki",
            "search_url": "https://namu.wiki/Search?q={keyword}",
            "post_selector": ".search-result, .wiki-result",
            "title_selector": "a.result-title, h4 a",
            "link_selector": "a.result-title, h4 a",
            "date_selector": None,
            "platform_name": "나무위키",
        },
    }

    async def search(
        self,
        keyword: str,
        limit: int = 20,
        days_back: int = 7,
        sites: list[str] | None = None,
    ) -> list[dict]:
        """
        지정된 커뮤니티에서 키워드 검색.
        robots.txt 차단된 URL은 자동 건너뜀.
        """
        target_sites = sites or list(self.SITES.keys())
        results: list[dict] = []

        headers = {
            "User-Agent": SAYBRAND_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        }

        async with httpx.AsyncClient(
            headers=headers,
            timeout=10,
            follow_redirects=True,
        ) as client:
            for site_key in target_sites:
                if site_key not in self.SITES:
                    continue
                site = self.SITES[site_key]
                search_url = site["search_url"].format(keyword=quote(keyword))

                # robots.txt 체크 — 차단이면 건너뜀
                if not await robots_checker.is_allowed(search_url):
                    logger.info(
                        "[SKIP] %s: robots.txt 차단 — %s",
                        site["platform_name"], search_url,
                    )
                    continue

                # Rate Limiting
                domain = urlparse(search_url).netloc
                await rate_limiter.wait(domain)

                try:
                    resp = await client.get(search_url)
                    if resp.status_code != 200:
                        continue

                    per_site_limit = limit // len(target_sites) + 1
                    posts = self._parse_posts(
                        resp.text, site, keyword,
                        base_url=site["base_url"],
                        platform=site["platform_name"],
                        limit=per_site_limit,
                    )
                    results.extend(posts)

                except httpx.TimeoutException:
                    logger.warning("%s 요청 타임아웃", site["platform_name"])
                except Exception as e:
                    logger.warning("%s 수집 실패: %s", site["platform_name"], e)

        return results[:limit]

    def _parse_posts(
        self,
        html: str,
        site: dict,
        keyword: str,
        base_url: str,
        platform: str,
        limit: int,
    ) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        posts: list[dict] = []

        items = soup.select(site["post_selector"])
        for item in items[:30]:
            if len(posts) >= limit:
                break
            try:
                title_el = item.select_one(site["title_selector"])
                link_el = item.select_one(site["link_selector"])
                date_el = item.select_one(site["date_selector"]) \
                          if site["date_selector"] else None

                if not title_el or not link_el:
                    continue

                title = title_el.get_text(strip=True)
                href = link_el.get("href", "")
                post_url = urljoin(base_url, href) if href else ""

                # 키워드 포함 여부 확인
                if keyword.lower() not in title.lower():
                    continue

                # PII 제거
                clean_title = remove_pii(title)

                posts.append(make_post(
                    platform=platform,
                    source_account=platform,
                    content=clean_title,
                    post_url=post_url,
                    published_at=self._parse_date(
                        date_el.get_text(strip=True) if date_el else ""
                    ),
                    is_mock=False,
                ))
            except Exception:
                continue

        return posts

    def _parse_date(self, date_str: str) -> datetime:
        """날짜 문자열 파싱 — 실패 시 현재 시각"""
        import re
        patterns = [
            r"(\d{4})[.\-/](\d{2})[.\-/](\d{2})",
            r"(\d{2})[.\-/](\d{2})[.\-/](\d{2})",
            r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
        ]
        for pattern in patterns:
            m = re.search(pattern, date_str)
            if m:
                try:
                    groups = m.groups()
                    year = 2000 + int(groups[0]) if len(groups[0]) == 2 else int(groups[0])
                    return datetime(year, int(groups[1]), int(groups[2]), tzinfo=timezone.utc)
                except Exception:
                    pass
        return datetime.now(timezone.utc)

    def _mock_posts(self, keyword: str, limit: int) -> list[dict]:
        """테스트 시 Mock 반환"""
        return [
            make_post(
                platform="에펨코리아[MOCK]",
                source_account="에펨코리아",
                content=f"[데모] {keyword} 관련 게시물 — 실제 수집 시 교체됩니다",
                post_url=f"https://www.fmkorea.com/search?keyword={keyword}",
                published_at=datetime.now(timezone.utc),
                is_mock=True,
            )
        ][:limit]
