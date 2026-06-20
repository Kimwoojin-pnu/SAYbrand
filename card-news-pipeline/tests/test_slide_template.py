from cardnews.slide_template import build_slide_html


def test_build_slide_html_inserts_content():
    result = build_slide_html("테스트 제목", "테스트 본문")

    assert "테스트 제목" in result
    assert "테스트 본문" in result
    assert "__HEADLINE__" not in result
    assert "__BODY__" not in result


def test_build_slide_html_escapes_special_characters():
    result = build_slide_html("<script>제목</script>", "A & B")

    assert "<script>제목</script>" not in result
    assert "&lt;script&gt;" in result
    assert "A &amp; B" in result
