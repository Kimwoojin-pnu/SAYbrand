from copy import deepcopy
from datetime import date

from cardnews.models import ThreatRecord

SAMPLE_THREATS: list[ThreatRecord] = [
    ThreatRecord(
        id="threat-001",
        detected_at=date(2026, 6, 1),
        category="허위 리뷰 확산",
        summary=(
            "한 식품 브랜드의 신제품에 대해 사실과 다른 성분 정보를 담은 리뷰가 "
            "SNS에서 빠르게 퍼지며 검색 결과 상위권에 노출되기 시작했습니다."
        ),
        impact_score=8,
    ),
    ThreatRecord(
        id="threat-002",
        detected_at=date(2026, 6, 3),
        category="불만 게시글 확산",
        summary=(
            "고객 응대 지연에 대한 불만 게시글이 커뮤니티에서 공감을 얻으며 "
            "빠르게 공유되기 시작했습니다."
        ),
        impact_score=6,
    ),
    ThreatRecord(
        id="threat-003",
        detected_at=date(2026, 6, 5),
        category="해시태그 확산",
        summary=(
            "한 브랜드의 마케팅 문구가 오해를 사며 부정적인 해시태그와 함께 "
            "빠르게 퍼지고 있습니다."
        ),
        impact_score=9,
    ),
    ThreatRecord(
        id="threat-004",
        detected_at=date(2026, 6, 6),
        category="가품 유통 의심",
        summary=(
            "온라인 마켓에서 정품과 유사한 가품이 유통되고 있다는 "
            "소비자 제보가 늘고 있습니다."
        ),
        impact_score=7,
    ),
]


def load_sample_threats() -> list[ThreatRecord]:
    return deepcopy(SAMPLE_THREATS)
