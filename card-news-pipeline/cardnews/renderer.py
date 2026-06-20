import logging
from pathlib import Path

from playwright.sync_api import sync_playwright

from cardnews.models import CardNewsScript
from cardnews.pixazo_image_generator import generate_image_with_pixazo
from cardnews.slide_template import build_slide_html

_logger = logging.getLogger(__name__)

SLIDE_WIDTH = 1080
SLIDE_HEIGHT = 1920


def render_slides(script: CardNewsScript, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": SLIDE_WIDTH, "height": SLIDE_HEIGHT})

        try:
            for index, slide in enumerate(script.slides, start=1):
                # Pixazo로 히어로 이미지 생성
                hero_image_path = output_dir / f"{script.source_id}_hero_{index:02d}.jpg"
                hero_script = CardNewsScript(
                    source_id=script.source_id,
                    title=script.title,
                    slides=[slide],
                    description=script.description,
                    tags=script.tags,
                )
                result = generate_image_with_pixazo(hero_script, hero_image_path)
                if result is None:
                    _logger.info("Pixazo 이미지 없음, 플레이스홀더 사용")
                    hero_image_path = None

                html = build_slide_html(slide.headline, slide.body, image_path=hero_image_path)
                output_path = output_dir / f"{script.source_id}_slide_{index:02d}.png"
                page.set_content(html, wait_until="networkidle")
                page.screenshot(path=str(output_path))
                output_paths.append(output_path)
        finally:
            browser.close()

    return output_paths
