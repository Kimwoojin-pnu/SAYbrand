import os
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from cardnews.review_status import ReviewStatus

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
TOKEN_URI = "https://oauth2.googleapis.com/token"


class YouTubeCredentialsError(RuntimeError):
    """필요한 YouTube OAuth 환경변수가 설정되지 않았을 때 발생."""


def build_youtube_client():
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        raise YouTubeCredentialsError(
            "YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN 환경변수가 모두 설정되어야 합니다. "
            "youtube_auth_setup.py 스크립트로 발급받은 값을 .env에 설정해주세요."
        )

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=[YOUTUBE_UPLOAD_SCOPE],
    )
    credentials.refresh(Request())

    return build("youtube", "v3", credentials=credentials)


YOUTUBE_CATEGORY_ID = "25"  # News & Politics
_RETRYABLE_STATUS = {500, 503}
_MAX_RETRIES = 3


def upload_video(youtube, status: ReviewStatus, video_path: Path) -> str:
    body = {
        "snippet": {
            "title": status.title,
            "description": status.description + "\n\n#Shorts",
            "tags": status.tags + ["Shorts"],
            "categoryId": YOUTUBE_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": "private",
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    retry = 0
    response = None
    while response is None:
        try:
            _, response = request.next_chunk()
        except HttpError as error:
            if error.resp.status not in _RETRYABLE_STATUS or retry >= _MAX_RETRIES:
                raise
            time.sleep(2 ** retry)
            retry += 1

    return response["id"]


def set_thumbnail(youtube, video_id: str, thumbnail_path: Path) -> None:
    youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))).execute()
