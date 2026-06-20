from cardnews.mock_data import load_sample_threats
from cardnews.pipeline import run_pipeline


def test_run_pipeline_generates_script_and_slide_files(tmp_path):
    script = run_pipeline(tmp_path)

    assert script is not None
    generated_files = sorted(tmp_path.glob(f"{script.source_id}_slide_*.png"))
    assert len(generated_files) == len(script.slides)
    for path in generated_files:
        assert path.stat().st_size > 0


def test_run_pipeline_returns_none_when_every_record_already_used(tmp_path, monkeypatch):
    from unittest.mock import patch
    from cardnews.mock_data import load_sample_threats as _load_sample

    sample = _load_sample()
    used_ids = {record.id for record in sample}

    with patch("cardnews.pipeline.load_threats", return_value=sample):
        result = run_pipeline(tmp_path, used_ids=used_ids)

    assert result is None
