from cardnews.models import CardNewsScript, Slide, ThreatRecord


def generate_script(record: ThreatRecord) -> CardNewsScript:
    title = f"브랜드를 위협하는 순간: {record.category}"

    slides = [
        Slide(headline=title, body=record.summary),
    ]

    description = (
        f"[{record.category}] 사례로 알아보는 브랜드 리스크 — "
        "SAYbrand와 함께 미리 대비하세요."
    )
    tags = ["브랜드리스크", "온라인평판", record.category.replace(" ", "")]

    return CardNewsScript(
        source_id=record.id,
        title=title,
        slides=slides,
        description=description,
        tags=tags,
    )
