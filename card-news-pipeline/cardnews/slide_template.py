import base64
import html
from datetime import date
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "templates" / "slide.html"

_DAYS_KO = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

_IMG_PLACEHOLDER = """<div class="img-placeholder">
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <rect x="4" y="8" width="40" height="32" rx="4" stroke="white" stroke-width="2"/>
        <circle cx="16" cy="20" r="4" stroke="white" stroke-width="2"/>
        <path d="M4 32L14 22L20 28L30 18L44 32" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <div class="img-placeholder-txt">AI 이미지</div>
</div>"""


def build_slide_html(headline: str, body: str, image_path: Path | None = None) -> str:
    today = date.today()
    date_str = f"{today.strftime('%Y.%m.%d')}.({_DAYS_KO[today.weekday()]}) 기준"

    if image_path and image_path.exists():
        b64 = base64.b64encode(image_path.read_bytes()).decode()
        image_html = f'<img src="data:image/jpeg;base64,{b64}" style="width:100%;height:100%;object-fit:cover;border-radius:16px;"/>'
    else:
        image_html = _IMG_PLACEHOLDER

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return (
        template
        .replace("__HEADLINE__", html.escape(headline))
        .replace("__BODY__", html.escape(body))
        .replace("__DATE__", date_str)
        .replace("__IMAGE_HTML__", image_html)
    )
