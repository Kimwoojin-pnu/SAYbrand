from pathlib import Path

from cardnews.db_source import load_threats
from cardnews.llm_scripter import generate_script_with_llm
from cardnews.models import CardNewsScript
from cardnews.renderer import render_slides
from cardnews.selector import select_best_candidate


def run_pipeline(
    output_dir: Path,
    used_ids: set[str] | None = None,
) -> CardNewsScript | None:
    records = load_threats()
    candidate = select_best_candidate(records, used_ids)

    if candidate is None:
        return None

    script = generate_script_with_llm(candidate)
    render_slides(script, output_dir)
    return script
