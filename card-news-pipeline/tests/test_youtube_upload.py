from pathlib import Path
from unittest.mock import MagicMock, patch

import httplib2
import pytest
from googleapiclient.errors import HttpError

from cardnews.review_status import ReviewStatus
from cardnews.youtube_upload import (
    YouTubeCredentialsError,
    build_youtube_client,
    set_thumbnail,
    upload_video,
)


def test_build_youtube_client_raises_without_env_vars(monkeypatch):
    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN", raising=False)

    with pytest.raises(YouTubeCredentialsError):
        build_youtube_client()


def test_build_youtube_client_builds_with_credentials(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "client-id")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "refresh-token")

    with patch("cardnews.youtube_upload.Credentials") as mock_credentials_cls, \
            patch("cardnews.youtube_upload.Request") as mock_request_cls, \
            patch("cardnews.youtube_upload.build", return_value="youtube-client") as mock_build:
        client = build_youtube_client()

    mock_credentials_cls.assert_called_once_with(
        token=None,
        refresh_token="refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    mock_credentials_cls.return_value.refresh.assert_called_once_with(mock_request_cls.return_value)
    mock_build.assert_called_once_with("youtube", "v3", credentials=mock_credentials_cls.return_value)
    assert client == "youtube-client"


def _http_error(status: int) -> HttpError:
    resp = httplib2.Response({"status": status})
    return HttpError(resp=resp, content=b"error")


def _sample_status(video_path: str = "") -> ReviewStatus:
    return ReviewStatus(
        source_id="threat-003",
        message_id="m",
        channel_id="c",
        status="approved",
        title="브랜드를 위협하는 순간",
        description="설명입니다",
        tags=["브랜드리스크", "해시태그확산"],
        video_path=video_path,
    )


def test_upload_video_returns_video_id(tmp_path):
    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")
    status = _sample_status(str(video_path))

    mock_request = MagicMock()
    mock_request.next_chunk.return_value = (None, {"id": "abc123"})

    mock_youtube = MagicMock()
    mock_youtube.videos.return_value.insert.return_value = mock_request

    with patch("cardnews.youtube_upload.MediaFileUpload"):
        video_id = upload_video(mock_youtube, status, video_path)

    assert video_id == "abc123"

    call_kwargs = mock_youtube.videos.return_value.insert.call_args.kwargs
    assert call_kwargs["part"] == "snippet,status"
    assert call_kwargs["body"]["snippet"]["title"] == status.title
    assert call_kwargs["body"]["snippet"]["description"] == status.description + "\n\n#Shorts"
    assert call_kwargs["body"]["snippet"]["tags"] == status.tags + ["Shorts"]
    assert call_kwargs["body"]["status"]["privacyStatus"] == "private"


def test_upload_video_uploads_until_response_ready(tmp_path):
    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")
    status = _sample_status(str(video_path))

    mock_request = MagicMock()
    mock_request.next_chunk.side_effect = [(MagicMock(), None), (MagicMock(), {"id": "xyz789"})]

    mock_youtube = MagicMock()
    mock_youtube.videos.return_value.insert.return_value = mock_request

    with patch("cardnews.youtube_upload.MediaFileUpload"):
        video_id = upload_video(mock_youtube, status, video_path)

    assert video_id == "xyz789"
    assert mock_request.next_chunk.call_count == 2


def test_set_thumbnail_calls_thumbnails_set(tmp_path):
    thumbnail_path = tmp_path / "threat-003_slide_01.png"
    thumbnail_path.write_bytes(b"fake-png")

    mock_youtube = MagicMock()

    with patch("cardnews.youtube_upload.MediaFileUpload") as mock_media:
        set_thumbnail(mock_youtube, "abc123", thumbnail_path)

    mock_media.assert_called_once_with(str(thumbnail_path))
    mock_youtube.thumbnails.return_value.set.assert_called_once_with(
        videoId="abc123", media_body=mock_media.return_value
    )
    mock_youtube.thumbnails.return_value.set.return_value.execute.assert_called_once()


def test_upload_video_retries_on_server_error_and_succeeds(tmp_path):
    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")
    status = _sample_status(str(video_path))

    mock_request = MagicMock()
    mock_request.next_chunk.side_effect = [
        _http_error(503),
        _http_error(503),
        (None, {"id": "retry-success"}),
    ]

    mock_youtube = MagicMock()
    mock_youtube.videos.return_value.insert.return_value = mock_request

    with patch("cardnews.youtube_upload.MediaFileUpload"), \
            patch("cardnews.youtube_upload.time.sleep"):
        video_id = upload_video(mock_youtube, status, video_path)

    assert video_id == "retry-success"
    assert mock_request.next_chunk.call_count == 3


def test_upload_video_raises_after_max_retries(tmp_path):
    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")
    status = _sample_status(str(video_path))

    mock_request = MagicMock()
    mock_request.next_chunk.side_effect = _http_error(503)

    mock_youtube = MagicMock()
    mock_youtube.videos.return_value.insert.return_value = mock_request

    with patch("cardnews.youtube_upload.MediaFileUpload"), \
            patch("cardnews.youtube_upload.time.sleep"):
        with pytest.raises(HttpError):
            upload_video(mock_youtube, status, video_path)

    assert mock_request.next_chunk.call_count == 4  # 1 initial + 3 retries


def test_upload_video_does_not_retry_on_client_error(tmp_path):
    video_path = tmp_path / "threat-003.mp4"
    video_path.write_bytes(b"fake-mp4")
    status = _sample_status(str(video_path))

    mock_request = MagicMock()
    mock_request.next_chunk.side_effect = _http_error(403)

    mock_youtube = MagicMock()
    mock_youtube.videos.return_value.insert.return_value = mock_request

    with patch("cardnews.youtube_upload.MediaFileUpload"), \
            patch("cardnews.youtube_upload.time.sleep"):
        with pytest.raises(HttpError):
            upload_video(mock_youtube, status, video_path)

    assert mock_request.next_chunk.call_count == 1  # no retry
