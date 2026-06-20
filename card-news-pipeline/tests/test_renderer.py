from cardnews.models import CardNewsScript, Slide
from cardnews.renderer import render_slides

SCRIPT = CardNewsScript(
    source_id="threat-test",
    title="테스트 카드뉴스",
    slides=[
        Slide(headline="첫 번째 슬라이드", body="첫 번째 본문"),
        Slide(headline="두 번째 슬라이드", body="두 번째 본문"),
    ],
    description="테스트 설명",
    tags=["테스트"],
)


def test_render_slides_creates_one_png_per_slide(tmp_path):
    output_paths = render_slides(SCRIPT, tmp_path)

    assert len(output_paths) == 2
    assert output_paths[0].name == "threat-test_slide_01.png"
    assert output_paths[1].name == "threat-test_slide_02.png"
    for path in output_paths:
        assert path.exists()
        assert path.stat().st_size > 0
