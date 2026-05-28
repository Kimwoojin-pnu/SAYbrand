"""
한국 커뮤니티 경량 크롤러 (httpx + BeautifulSoup)

실제 동작하는 사이트 (2026-05 검증):
✅ 클리앙  (clien.net)   — div.list_item / .subject_fixed

robots.txt 차단 (selector 정의는 유지, 수집 시 자동 스킵):
⚠️ 루리웹  (ruliweb.com) — robots.txt Disallow: /search

검증 결과 동작 불가 사이트:
❌ 에펨코리아 (fmkorea.com) — 검색 결과 JS 렌더링
❌ 더쿠       (theqoo.net)  — 검색 URL 404
❌ 인스티즈   (instiz.net)  — JS 렌더링
❌ 나무위키   (namu.wiki)   — SPA, 정적 HTML 없음

⚠️ DC인사이드 (dcinside.com) — robots.txt Disallow: *
⚠️ 블라인드   (blind.so)    — 로그인 필수
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
        "clien": {
            "base_url": "https://www.clien.net",
            "search_url": "https://www.clien.net/service/search?q={keyword}&sort=recency",
            "post_selector": "div.list_item",
            "title_selector": ".subject_fixed",
            "link_selector": ".subject_fixed",
            "date_selector": ".list_time",
            "platform_name": "클리앙",
        },
        "ruliweb": {
            "base_url": "https://bbs.ruliweb.com",
            "search_url": "https://bbs.ruliweb.com/search?q={keyword}&search_type=subject_content",
            "post_selector": ".search_result_item",
            "title_selector": "a.title",
            "link_selector": "a.title",
            "date_selector": "span.time",
            "platform_name": "루리웹",
        },
    }

    async def search(
        self,
        keyword: str,
        limit: int = 20,
        days_back: int = 7,
        sites: list[str] | None = None,
    ) -> list[dict]:
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

                if not await robots_checker.is_allowed(search_url):
                    logger.info(
                        "[SKIP] %s: robots.txt 차단 — %s",
                        site["platform_name"], search_url,
                    )
                    continue

                domain = urlparse(search_url).netloc
                await rate_limiter.wait(domain)

                try:
                    resp = await client.get(search_url)
                    if resp.status_code != 200:
                        logger.warning(
                            "%s HTTP %s", site["platform_name"], resp.status_code
                        )
                        continue

                    per_site_limit = limit // len(target_sites) + 1
                    posts = self._parse_posts(
                        resp.text, site, keyword,
                        base_url=site["base_url"],
                        platform=site["platform_name"],
                        limit=per_site_limit,
                    )
                    logger.info(
                        "%s: %d건 파싱 (키워드=%r)", site["platform_name"], len(posts), keyword
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
        for item in items[:50]:
            if len(posts) >= limit:
                break
            try:
                title_el = item.select_one(site["title_selector"])
                link_el = item.select_one(site["link_selector"])
                date_el = (
                    item.select_one(site["date_selector"])
                    if site.get("date_selector")
                    else None
                )

                if not title_el or not link_el:
                    continue

                title = title_el.get_text(strip=True)
                if not title:
                    continue

                # link_el이 <a> 태그인 경우 href 직접 추출, 아니면 하위 <a> 탐색
                if link_el.name == "a":
                    href = link_el.get("href", "")
                else:
                    a_tag = link_el.find("a")
                    href = a_tag.get("href", "") if a_tag else ""

                post_url = urljoin(base_url, href) if href else ""

                # excerpt: 제목 외 본문 일부 포함
                excerpt = ""
                for desc_sel in [".inline_block", ".list_desc", ".description", "p"]:
                    desc_el = item.select_one(desc_sel)
                    if desc_el:
                        excerpt = desc_el.get_text(" ", strip=True)[:200]
                        break

                content = remove_pii(
                    (title + (" " + excerpt if excerpt else "")).strip()
                )

                posts.append(make_post(
                    platform=platform,
                    source_account=platform,
                    content=content,
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
        return [
            make_post(
                platform="클리앙[MOCK]",
                source_account="클리앙",
                content=f"[데모] {keyword} 관련 게시물 — 실제 수집 시 교체됩니다",
                post_url=f"https://www.clien.net/service/search?q={keyword}",
                published_at=datetime.now(timezone.utc),
                is_mock=True,
            )
        ][:limit]
