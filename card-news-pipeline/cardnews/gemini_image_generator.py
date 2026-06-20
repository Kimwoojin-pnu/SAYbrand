import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from cardnews.models import CardNewsScript

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """Professional Korean brand risk monitoring card news image, portrait 9:16 ratio, dark editorial design.

Layout top to bottom:
1. Thin top bar on very dark navy (#0f0f1c): green live dot + Korean text "오늘의 브랜드 모니터링 리포트" on left, "SAYbrand AI WATCH" dim white on right.
2. Dark green gradient banner (#004d22): circular Starbucks-style logo (green circle with white letter S), bold white Korean text "스타벅스 코리아", right side bright green text "Powered by SAYbrand".
3. Large dark area (#0c0c14): small red dot + red uppercase Korean "실시간 위기 감지 리포트" label, then very large bold serif Korean headline "{headline}". Top-right corner: small label "RISK SCORE", large red number "100", red rounded badge "CRITICAL".
4. Thin horizontal divider line.
5. Dark card section labeled "오늘의 주요 이슈": card with red-orange left border stripe, green "ONLINE" tag and red "CRITICAL" tag, Korean body text: "{body}". Right column: large red "100", text "/ 100", small label "RISK INDEX".
6. Hashtag pills row: #브랜드리스크 #온라인평판 #스타벅스코리아 #위기관리.
7. Bottom 4-column stats bar: [warning icon + "위험도" + red "CRITICAL"] [check icon + "탐지 엔진" + green "AI Risk Watch"] [star icon + "브랜드 신뢰" + red "하락 중"] [chart icon + "모니터링" + "실시간"].
8. Footer: small green S circle, "브랜드 와치 | SAYbrand WATCH" left, "Powered by AI Brand Intelligence" right.

Colors: dark navy-black background, dark green brand bar, bright red (#ff4444) risk elements, bright green (#22c55e) positive, white text. High contrast professional news aesthetic."""


def generate_image_with_gemini(script: CardNewsScript, output_path: Path) -> Path | None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        slide = script.slides[0]
        prompt = _PROMPT_TEMPLATE.format(
            headline=slide.headline,
            body=slide.body,
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        image_bytes = None
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and part.inline_data.mime_type.startswith("image/"):
                image_bytes = part.inline_data.data
                break

        if image_bytes is None:
            raise ValueError("응답에 이미지가 없습니다")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)
        _logger.info("Gemini 이미지 생성 완료: %s", output_path)
        return output_path

    except Exception as exc:
        _logger.warning("Gemini 이미지 생성 실패, HTML 렌더러로 폴백: %s", exc)
        return None
