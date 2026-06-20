import logging
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from cardnews.models import CardNewsScript

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_logger = logging.getLogger(__name__)

_ENDPOINT = "https://gateway.pixazo.ai/getImage/v1/getSDXLImage"

_PROMPT_TEMPLATE = """브랜드 위기 뉴스 삽화. 제목: {headline}. 내용: {body}. 어둡고 긴장감 있는 분위기, 추상적 시각화, 텍스트 없음."""


def generate_image_with_pixazo(script: CardNewsScript, output_path: Path) -> Path | None:
    api_key = os.environ.get("PIXAZO_API_KEY")
    if not api_key:
        return None

    try:
        slide = script.slides[0]
        prompt = _PROMPT_TEMPLATE.format(
            headline=slide.headline,
            body=slide.body,
        )

        resp = requests.post(
            _ENDPOINT,
            headers={
                "Ocp-Apim-Subscription-Key": api_key,
                "Content-Type": "application/json",
            },
            json={"prompt": prompt},
            timeout=60,
        )
        resp.raise_for_status()

        image_url = resp.json()["imageUrl"]
        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(img_resp.content)
        _logger.info("Pixazo 이미지 생성 완료: %s", output_path)
        return output_path

    except Exception as exc:
        _logger.warning("Pixazo 이미지 생성 실패, HTML 렌더러로 폴백: %s", exc)
        return None
