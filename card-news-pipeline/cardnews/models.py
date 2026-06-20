from dataclasses import dataclass
from datetime import date


@dataclass
class ThreatRecord:
    id: str
    detected_at: date
    category: str
    summary: str
    impact_score: int


@dataclass
class Slide:
    headline: str
    body: str


@dataclass
class CardNewsScript:
    source_id: str
    title: str
    slides: list[Slide]
    description: str
    tags: list[str]
