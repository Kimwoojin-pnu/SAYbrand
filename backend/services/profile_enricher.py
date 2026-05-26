import logging
import httpx
from backend.config import settings
from backend.models.schemas import DartLookupResult, WikidataLookupResult

logger = logging.getLogger(__name__)

_DART_BASE = "https://opendart.fss.or.kr/api"
_WIKIDATA_BASE = "https://www.wikidata.org/w/api.php"


async def enrich_from_dart(corp_code: str) -> DartLookupResult | None:
    if not settings.dart_api_key:
        logger.warning("DART_API_KEY not set — skipping enrichment")
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{_DART_BASE}/company.json",
                params={"crtfc_key": settings.dart_api_key, "corp_code": corp_code},
            )
        if resp.status_code != 200:
            return None

        data = resp.json()
        if data.get("status") != "000":
            return None

        return DartLookupResult(
            corp_name=data.get("corp_name", ""),
            ceo_name=data.get("ceo_nm", ""),
            industry=data.get("induty_code", ""),
            established_at=data.get("est_dt"),
            homepage=data.get("hm_url"),
        )
    except Exception as e:
        logger.warning(f"DART API error: {e}")
        return None


async def search_wikidata(company_name: str) -> WikidataLookupResult | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 1단계: 기업명으로 QID 검색
            search_resp = await client.get(
                _WIKIDATA_BASE,
                params={
                    "action": "wbsearchentities",
                    "search": company_name,
                    "language": "ko",
                    "format": "json",
                    "limit": 1,
                },
            )
            if search_resp.status_code != 200:
                return None

            results = search_resp.json().get("search", [])
            if not results:
                return None

            qid = results[0]["id"]
            label = results[0].get("label", company_name)

            # 2단계: QID로 속성 조회
            entity_resp = await client.get(
                _WIKIDATA_BASE,
                params={
                    "action": "wbgetentities",
                    "ids": qid,
                    "props": "claims",
                    "format": "json",
                },
            )
            if entity_resp.status_code != 200:
                return WikidataLookupResult(wikidata_id=qid, label=label)

            claims = entity_resp.json().get("entities", {}).get(qid, {}).get("claims", {})

        def _claim_value(prop: str) -> str | None:
            items = claims.get(prop, [])
            if not items:
                return None
            dv = items[0].get("mainsnak", {}).get("datavalue", {})
            val = dv.get("value")
            if isinstance(val, str):
                return val
            if isinstance(val, dict):
                return val.get("id") or val.get("text")
            return None

        logo_raw = _claim_value("P18")
        logo_url = (
            f"https://commons.wikimedia.org/wiki/Special:FilePath/{logo_raw.replace(' ', '_')}"
            if logo_raw else None
        )

        return WikidataLookupResult(
            wikidata_id=qid,
            label=label,
            logo_url=logo_url,
            instagram_handle=_claim_value("P2003"),
            twitter_handle=_claim_value("P2002"),
            youtube_channel=_claim_value("P2397"),
        )

    except Exception as e:
        logger.warning(f"Wikidata API error: {e}")
        return None
