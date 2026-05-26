from datetime import datetime, timedelta
from sqlalchemy import select
from backend.db.database import AsyncSessionLocal
from backend.models.orm import User, Threat, Alert, Keyword, Organization, OrganizationMember

_THREATS = [
    {
        "module": "A", "threat_type": "logo_spoof", "severity": "critical",
        "platform": "instagram", "source_account": "@saybrand_official_kr",
        "source_url": "https://instagram.com/saybrand_official_kr",
        "content_preview": "공식 로고를 92% 유사도로 복사한 사칭 계정. 팔로워 12,400명. 제품 할인 사기 게시물 다수 확인.",
        "confidence": 0.95, "risk_score": 95,
        "bot_probability": None, "is_organized": True,
        "ai_analysis": "해당 계정은 공식 브랜드 로고를 미세하게 변형하여 사용 중입니다. 계정명 패턴(@브랜드명_official_kr), 프로필 사진 유사도 94%, 게시물 스타일 완전 모방 확인. 팔로워 12,400명에게 가짜 할인 이벤트로 개인정보 수집 시도가 탐지되었습니다. 즉각적인 법적 조치와 플랫폼 신고가 필요합니다.",
        "ai_response_suggestion": "1. Instagram 신고 센터를 통해 '브랜드 사칭' 사유로 즉시 신고\n2. 법무팀에 계정 정지 가처분 신청 검토 의뢰\n3. 공식 채널을 통해 사칭 계정 존재를 고객에게 공지\n4. 팔로워 개인정보 유출 범위 확인 후 피해 고지 준비",
        "status": "active", "minutes_ago": 8,
    },
    {
        "module": "A", "threat_type": "account_impersonation", "severity": "critical",
        "platform": "x", "source_account": "@SAYbrand_Ofcl",
        "source_url": "https://x.com/SAYbrand_Ofcl",
        "content_preview": "CEO 프로필 사진을 도용해 투자 사기 멘션 게시. 하루 만에 리트윗 3,200회 확산.",
        "confidence": 0.91, "risk_score": 88,
        "bot_probability": 0.83, "is_organized": True,
        "ai_analysis": "CEO 공개 프로필 사진을 무단 사용하는 사칭 계정이 투자 유도 사기를 진행 중입니다. 게시물 확산 속도(시간당 리트윗 400회)는 봇 네트워크 개입을 강하게 시사합니다. 봇 확률 0.83으로 조직적 공격으로 판단됩니다.",
        "ai_response_suggestion": "1. X(Twitter) 공식 신고 채널을 통해 '신원 도용' 사유로 즉시 신고\n2. 법적 조치를 위한 스크린샷 및 게시물 URL 증거 수집\n3. 투자자 및 미디어 채널에 공식 입장문 선제 배포\n4. 사내 PR팀과 즉각 대응 메시지 협의",
        "status": "active", "minutes_ago": 22,
    },
    {
        "module": "B", "threat_type": "organized_rumor", "severity": "high",
        "platform": "youtube", "source_account": "SAYbrand_Truth_Channel",
        "source_url": "https://youtube.com/watch?v=fake123",
        "content_preview": "\"[충격] 브랜드가드 제품 원료 허위 표시 의혹\" 영상 조회수 48만. 댓글 97%가 유사 문구 반복.",
        "confidence": 0.87, "risk_score": 74,
        "bot_probability": 0.79, "is_organized": True,
        "ai_analysis": "조직적으로 기획된 허위정보 캠페인입니다. 댓글 분석 결과 97%가 3개의 유사 문구를 변형 반복 사용 중이며, 댓글 계정 평균 생성일이 14일 미만입니다. 봇 확률 0.79. 영상 자체의 인용 자료는 모두 출처 불명의 스크린샷입니다.",
        "ai_response_suggestion": "1. YouTube 허위정보 정책 위반으로 신고 접수\n2. 실제 원료 성분표 및 인증서를 공식 채널에 투명하게 게시\n3. 소비자 신뢰 회복을 위한 팩트체크 영상 제작 및 배포\n4. 언론사에 보도 자료를 선제 발송하여 프레임 선점",
        "status": "active", "minutes_ago": 45,
    },
    {
        "module": "B", "threat_type": "viral_rumor", "severity": "high",
        "platform": "instagram", "source_account": "@expose_brandguard",
        "source_url": "https://instagram.com/p/fakeid001",
        "content_preview": "브랜드가드 고객 데이터 유출 주장 게시물. 스토리 공유 8,200회. 진위 불명 캡처 이미지 첨부.",
        "confidence": 0.82, "risk_score": 71,
        "bot_probability": None, "is_organized": False,
        "ai_analysis": "개인정보 유출 허위 주장이 빠르게 확산 중입니다. 첨부 이미지는 포토샵 편집 흔적이 확인됩니다(메타데이터 불일치). 그러나 시각적 충격이 크고 확산 속도(시간당 스토리 공유 1,100회)가 높아 즉각 대응이 필요합니다.",
        "ai_response_suggestion": "1. 즉각적인 공식 부인 성명 발표 (24시간 이내)\n2. 정보보안 전문가와 함께 실제 유출 여부 검증 후 결과 공개\n3. 법적 대응 준비: 허위사실 유포 고소 검토\n4. 고객 대상 안심 이메일 발송",
        "status": "reviewing", "minutes_ago": 90,
    },
    {
        "module": "C", "threat_type": "executive_exposure", "severity": "high",
        "platform": "x", "source_account": "@insider_leak_kr",
        "source_url": "https://x.com/insider_leak_kr/status/fake789",
        "content_preview": "\"[단독] 브랜드가드 CFO, 경쟁사 미팅 포착\" 게시물. 첨부 사진 얼굴 인식 85% 일치.",
        "confidence": 0.78, "risk_score": 65,
        "bot_probability": None, "is_organized": False,
        "ai_analysis": "CFO 관련 허위 내부 정보 유출 시도입니다. 사진의 얼굴 유사도는 85%이나 배경 및 날짜 EXIF 데이터 분석 결과 2년 전 공개 행사 사진으로 확인됩니다. 게시 계정은 이전에도 유사한 기업 루머를 유포한 이력이 있습니다.",
        "ai_response_suggestion": "1. 당사자(CFO)에게 즉시 상황 보고 및 법적 자문 연결\n2. 사진 원본 출처 확인 후 반박 자료 준비\n3. 경쟁사에 공식 확인 요청 (필요 시)\n4. 내부 보안 감사를 통해 실제 정보 유출 경로 점검",
        "status": "active", "minutes_ago": 130,
    },
    {
        "module": "B", "threat_type": "bot_attack", "severity": "medium",
        "platform": "x", "source_account": "@bot_swarm_kr_001",
        "source_url": "https://x.com/search?q=%EB%B8%8C%EB%9E%9C%EB%93%9C%EA%B0%80%EB%93%9C+%EC%82%AC%EA%B8%B0",
        "content_preview": "\"브랜드가드 사기\" 해시태그 트렌딩 조작 시도. 계정 연령 평균 6일, 동일 문구 반복.",
        "confidence": 0.75, "risk_score": 54,
        "bot_probability": 0.91, "is_organized": True,
        "ai_analysis": "해시태그 트렌딩을 조작하기 위한 봇 네트워크 공격입니다. 참여 계정 87%의 생성일이 7일 미만이며, 게시물 내용이 3개 템플릿으로 구성됩니다. 봇 확률 0.91 (매우 높음). 현재 국내 X 트렌드 18위 진입을 시도 중입니다.",
        "ai_response_suggestion": "1. X 플랫폼 Trust & Safety팀에 조직적 봇 공격 신고\n2. 트렌드 알림 모니터링 강화 (1시간 간격)\n3. 실제 고객 보이스를 활용한 긍정 콘텐츠 캠페인으로 대응\n4. PR 에이전시와 위기 대응 시나리오 점검",
        "status": "active", "minutes_ago": 180,
    },
    {
        "module": "A", "threat_type": "logo_spoof", "severity": "medium",
        "platform": "youtube", "source_account": "SAYbrand_Official_Store",
        "source_url": "https://youtube.com/channel/UCfake456",
        "content_preview": "공식 로고 유사 이미지 사용 쇼핑 유도 채널. 구독자 2,100명. 가품 판매 의혹.",
        "confidence": 0.71, "risk_score": 48,
        "bot_probability": None, "is_organized": False,
        "ai_analysis": "공식 브랜드 로고와 78% 유사한 썸네일을 사용하는 채널입니다. 영상 내 판매 링크가 공식 쇼핑몰이 아닌 제3자 사이트로 연결됩니다. 가품 판매 가능성이 있으며, 소비자 피해로 이어질 수 있습니다.",
        "ai_response_suggestion": "1. YouTube 저작권 침해 신고 (DMCA)\n2. 링크된 외부 쇼핑몰 도메인 법적 조치 검토\n3. 공식 인증 쇼핑몰 리스트를 홈페이지에 명확히 게시",
        "status": "active", "minutes_ago": 240,
    },
    {
        "module": "C", "threat_type": "reputation_attack", "severity": "medium",
        "platform": "instagram", "source_account": "@expose_company_kr",
        "source_url": "https://instagram.com/p/fakeid002",
        "content_preview": "마케팅팀 직원 개인 SNS 발언 캡처 확산. 브랜드 이미지와 상충하는 내용 포함.",
        "confidence": 0.68, "risk_score": 45,
        "bot_probability": None, "is_organized": False,
        "ai_analysis": "직원 개인 계정의 발언이 맥락 없이 잘려 확산되고 있습니다. 원문은 개인 의견임을 명시했으나, 확산 과정에서 회사 공식 입장으로 오인될 여지가 있습니다. 즉각적 위기 수준은 아니나 지속 모니터링이 필요합니다.",
        "ai_response_suggestion": "1. 해당 직원과 조용히 소통하여 상황 파악\n2. 필요 시 직원 SNS 가이드라인 재교육\n3. 확산 범위가 커지면 '개인 의견' 명시 공식 코멘트 준비",
        "status": "reviewing", "minutes_ago": 360,
    },
    {
        "module": "B", "threat_type": "negative_review_cluster", "severity": "medium",
        "platform": "naver", "source_account": "naver_blog_expose",
        "source_url": "https://blog.naver.com/fake_expose",
        "content_preview": "네이버 블로그 부정 리뷰 클러스터 탐지. 48시간 내 유사 리뷰 23건 집중 게시.",
        "confidence": 0.65, "risk_score": 42,
        "bot_probability": 0.61, "is_organized": True,
        "ai_analysis": "단기간에 집중된 부정 리뷰는 경쟁사 개입 또는 조직적 공격의 패턴을 보입니다. 리뷰 작성자 계정 분석 결과 평균 가입 기간 21일, 리뷰 이력 없는 신규 계정이 65%입니다. 봇 확률 0.61.",
        "ai_response_suggestion": "1. 네이버 리뷰 시스템에 허위 리뷰 신고\n2. 실제 고객 긍정 리뷰 작성 유도 캠페인 검토\n3. 리뷰 패턴 모니터링 지속",
        "status": "active", "minutes_ago": 480,
    },
    {
        "module": "C", "threat_type": "internal_info_leak", "severity": "medium",
        "platform": "x", "source_account": "@anon_insider_kr",
        "source_url": "https://x.com/anon_insider_kr/status/fake321",
        "content_preview": "내부 조직 개편 정보 유출 의혹. 비공개 슬라이드로 보이는 이미지 첨부.",
        "confidence": 0.62, "risk_score": 38,
        "bot_probability": None, "is_organized": False,
        "ai_analysis": "첨부된 슬라이드 이미지의 폰트, 레이아웃, 색상이 내부 템플릿과 유사합니다. 실제 내부 자료 여부는 추가 확인이 필요하나, 만약 실제라면 정보보안 사고입니다. 확산 속도는 낮아 아직 주요 미디어에 도달하지 않았습니다.",
        "ai_response_suggestion": "1. 법무팀 및 정보보안팀에 즉시 보고\n2. 내부 자료 유출 경로 긴급 점검\n3. 해당 게시물 법적 삭제 요청 검토",
        "status": "active", "minutes_ago": 600,
    },
    {
        "module": "A", "threat_type": "watermark_removal", "severity": "low",
        "platform": "instagram", "source_account": "@content_reuse_kr",
        "source_url": "https://instagram.com/p/fakeid003",
        "content_preview": "공식 제품 이미지에서 워터마크 제거 후 무단 재사용. 팔로워 3,400명.",
        "confidence": 0.58, "risk_score": 25,
        "bot_probability": None, "is_organized": False,
        "ai_analysis": "공식 제품 촬영 이미지가 워터마크 제거 후 재배포되고 있습니다. 직접적인 브랜드 훼손보다는 저작권 침해 이슈입니다. 팔로워 수가 적어 확산 리스크는 낮습니다.",
        "ai_response_suggestion": "1. Instagram 저작권 침해 신고\n2. 향후 공식 이미지 워터마크 강화 검토",
        "status": "resolved", "minutes_ago": 1440,
    },
    {
        "module": "B", "threat_type": "negative_comment", "severity": "low",
        "platform": "youtube", "source_account": "disgruntled_user_yt",
        "source_url": "https://youtube.com/watch?v=realvid&lc=fake",
        "content_preview": "공식 채널 영상에 부정적 댓글 연속 게시. 좋아요 34개. 특정 직원 이름 언급.",
        "confidence": 0.51, "risk_score": 22,
        "bot_probability": 0.12, "is_organized": False,
        "ai_analysis": "실제 불만 고객으로 추정되는 단일 계정의 반복 부정 댓글입니다. 봇 확률 0.12 (낮음). 고객 경험 개선이 근본적 해결책입니다. 특정 직원 이름 언급이 있어 해당 직원 보호 차원 모니터링이 필요합니다.",
        "ai_response_suggestion": "1. 고객 불만 공개 답변으로 브랜드 신뢰 회복\n2. DM을 통해 직접 문제 해결 제안\n3. 언급된 직원에게 상황 공유",
        "status": "resolved", "minutes_ago": 2880,
    },
    {
        "module": "C", "threat_type": "casual_mention", "severity": "low",
        "platform": "instagram", "source_account": "@regular_user_kim",
        "source_url": "https://instagram.com/p/fakeid004",
        "content_preview": "일반 사용자 불만 게시물. 제품 배송 지연 불만. 팔로워 280명.",
        "confidence": 0.47, "risk_score": 18,
        "bot_probability": None, "is_organized": False,
        "ai_analysis": "팔로워가 적은 일반 사용자의 실제 불만 게시물입니다. 확산 가능성은 낮으나 고객 서비스 차원에서 적절한 대응이 필요합니다.",
        "ai_response_suggestion": "1. 댓글로 공감 표현 및 고객센터 연결\n2. 배송 문제 내부 확인 후 개선",
        "status": "resolved", "minutes_ago": 4320,
    },
    {
        "module": "B", "threat_type": "competitor_mention", "severity": "low",
        "platform": "x", "source_account": "@brand_comparison",
        "source_url": "https://x.com/brand_comparison/status/fake111",
        "content_preview": "경쟁사 제품과 비교 게시물. 가격 대비 성능 부정적 언급. 리트윗 47회.",
        "confidence": 0.43, "risk_score": 15,
        "bot_probability": 0.08, "is_organized": False,
        "ai_analysis": "경쟁사 팬 또는 중립적 비교 콘텐츠로 보입니다. 봇 개입 없음 (봇 확률 0.08). 자연적인 시장 반응이며 과도한 대응은 오히려 역효과를 낳을 수 있습니다.",
        "ai_response_suggestion": "1. 자사 제품 강점을 부각하는 콘텐츠로 간접 대응\n2. 직접 반박보다는 고객 만족 사례 공유 권장",
        "status": "resolved", "minutes_ago": 5760,
    },
    {
        "module": "A", "threat_type": "similar_logo", "severity": "low",
        "platform": "tiktok", "source_account": "@similar_brand_official",
        "source_url": "https://tiktok.com/@similar_brand_official",
        "content_preview": "로고 색상 구성 유사 신규 브랜드 계정. 의도적 모방 여부 확인 필요.",
        "confidence": 0.40, "risk_score": 12,
        "bot_probability": None, "is_organized": False,
        "ai_analysis": "로고의 색상과 형태가 65% 유사한 신규 브랜드입니다. 등록 상표 침해 여부 확인이 필요하나, 현재 팔로워가 적어 당장의 소비자 혼동 가능성은 낮습니다.",
        "ai_response_suggestion": "1. 지식재산권 담당자에게 유사 로고 사전 검토 의뢰\n2. 성장 추이 모니터링 후 필요 시 법적 조치",
        "status": "active", "minutes_ago": 7200,
    },
]

_ALERT_MESSAGES = [
    ("critical", "사칭 계정 탐지: @saybrand_official_kr (인스타그램)", "dashboard"),
    ("critical", "CEO 사칭 계정 확산 경보 — 봇 확률 83%", "dashboard"),
    ("high", "허위 원료 정보 유튜브 영상 조회수 48만 돌파", "dashboard"),
    ("high", "고객 데이터 유출 허위 주장 스토리 8,200회 공유", "dashboard"),
    ("high", "CFO 관련 루머 X(트위터) 빠른 확산 감지", "dashboard"),
    ("medium", "봇 네트워크 해시태그 트렌딩 조작 시도 탐지", "dashboard"),
    ("medium", "유튜브 유사 로고 쇼핑 채널 신규 탐지", "dashboard"),
    ("medium", "네이버 블로그 부정 리뷰 클러스터 48시간 내 23건", "dashboard"),
]

_KEYWORDS = [
    ("브랜드가드", ["instagram", "x", "youtube"]),
    ("SAYbrand", ["instagram", "x", "youtube"]),
    ("브랜드가드 사기", ["instagram", "x", "naver"]),
    ("브랜드가드 후기", ["instagram", "youtube", "naver"]),
    ("브랜드가드 CEO", ["x", "instagram"]),
]


async def seed_mock_data() -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(User).limit(1))
        if existing.scalar_one_or_none():
            return

        user = User(
            name="김민준",
            email="minjun.kim@acme-corp.kr",
            company="ACME 코퍼레이션",
            user_type="brand",
        )
        session.add(user)
        await session.flush()

        # 기본 조직 생성
        org = Organization(
            name="ACME 코퍼레이션",
            slug="acme-corp",
            owner_user_id=user.id,
            invite_mode="approval",
            subscription_tier="pro",
            subscription_status="active",
        )
        session.add(org)
        await session.flush()

        session.add(
            OrganizationMember(
                org_id=org.id,
                user_id=user.id,
                role="owner",
                status="active",
                joined_at=datetime.utcnow(),
            )
        )
        await session.flush()

        now = datetime.utcnow()
        threat_objs = []
        for t in _THREATS:
            detected = now - timedelta(minutes=t["minutes_ago"])
            threat = Threat(
                user_id=user.id,
                org_id=org.id,
                module=t["module"],
                threat_type=t["threat_type"],
                severity=t["severity"],
                platform=t["platform"],
                source_account=t["source_account"],
                source_url=t["source_url"],
                content_preview=t["content_preview"],
                confidence=t["confidence"],
                risk_score=t["risk_score"],
                ai_analysis=t.get("ai_analysis"),
                ai_response_suggestion=t.get("ai_response_suggestion"),
                bot_probability=t.get("bot_probability"),
                is_organized=t.get("is_organized"),
                status=t["status"],
                detected_at=detected,
                updated_at=detected,
            )
            session.add(threat)
            threat_objs.append(threat)

        await session.flush()

        for i, (severity, message, channel) in enumerate(_ALERT_MESSAGES):
            alert = Alert(
                threat_id=threat_objs[i].id,
                severity=severity,
                message=message,
                channel=channel,
                sent_at=now - timedelta(minutes=_THREATS[i]["minutes_ago"]),
            )
            session.add(alert)

        for keyword, platforms in _KEYWORDS:
            kw = Keyword(
                user_id=user.id,
                org_id=org.id,
                keyword=keyword,
                platforms=platforms,
                active=True,
            )
            session.add(kw)

        await session.commit()
