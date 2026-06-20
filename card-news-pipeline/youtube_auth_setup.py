"""YouTube Data API 리프레시 토큰 발급용 1회성 스크립트.

사용법:
1. Google Cloud Console에서 OAuth 클라이언트(애플리케이션 유형: 데스크톱 앱)를 만들고
   client_secret.json 파일을 다운로드해 이 파일과 같은 위치에 둔다.
2. `python youtube_auth_setup.py` 실행 — 브라우저가 열리면 업로드에 사용할
   Google 계정으로 로그인하고 권한을 동의한다.
3. 출력된 YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN 값을
   .env 파일에 그대로 붙여넣는다.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    print(f"\n아래 URL을 브라우저에서 열어 Google 계정으로 로그인하세요:\n\n{auth_url}\n")
    code = input("브라우저에 표시된 코드를 여기에 붙여넣으세요: ").strip()
    flow.fetch_token(code=code)
    credentials = flow.credentials

    print(f"YOUTUBE_CLIENT_ID={credentials.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={credentials.client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={credentials.refresh_token}")


if __name__ == "__main__":
    main()
