from cardnews.review_status import ReviewStatus, load_review_status, save_review_status


def test_save_and_load_review_status_round_trip(tmp_path):
    path = tmp_path / "review_status.json"
    status = ReviewStatus(
        source_id="threat-003",
        message_id="msg123",
        channel_id="chan456",
        status="pending",
        retry_count=0,
    )

    save_review_status(path, status)
    loaded = load_review_status(path)

    assert loaded == status


def test_load_review_status_returns_none_when_missing(tmp_path):
    path = tmp_path / "does_not_exist.json"

    assert load_review_status(path) is None


def test_review_status_round_trip_with_youtube_fields(tmp_path):
    path = tmp_path / "review_status.json"
    status = ReviewStatus(
        source_id="threat-003",
        message_id="m",
        channel_id="c",
        status="uploaded",
        retry_count=0,
        title="제목",
        description="설명",
        tags=["a", "b"],
        video_path="/output/threat-003.mp4",
        youtube_video_id="abc123",
        published_at="2026-06-12T00:00:00+00:00",
        error_message="실패 사유",
    )

    save_review_status(path, status)

    assert load_review_status(path) == status
