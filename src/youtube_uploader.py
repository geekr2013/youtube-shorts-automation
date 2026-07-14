"""GitHub Secrets의 OAuth 정보로 YouTube에 원본 영상을 업로드한다."""

import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

LOGGER = logging.getLogger(__name__)
UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
RETRIABLE_STATUS_CODES = {500, 502, 503, 504}


class YouTubeAuthError(RuntimeError):
    pass


class YouTubeUploader:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        self.client_id = client_id or os.getenv("YOUTUBE_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("YOUTUBE_CLIENT_SECRET", "")
        self.refresh_token = refresh_token or os.getenv("YOUTUBE_REFRESH_TOKEN", "")
        self.youtube = self._authenticate()

    def _normalize_client(self) -> tuple[str, str, str]:
        token_uri = "https://oauth2.googleapis.com/token"
        if self.client_secret.strip().startswith("{"):
            try:
                payload = json.loads(self.client_secret)
                config = payload.get("installed") or payload.get("web") or {}
                client_id = self.client_id or config.get("client_id", "")
                client_secret = config.get("client_secret", "")
                token_uri = config.get("token_uri", token_uri)
                return client_id, client_secret, token_uri
            except json.JSONDecodeError as exc:
                raise YouTubeAuthError("YOUTUBE_CLIENT_SECRET JSON 형식이 잘못되었습니다.") from exc
        return self.client_id, self.client_secret, token_uri

    def _authenticate(self):
        client_id, client_secret, token_uri = self._normalize_client()
        if not all([client_id, client_secret, self.refresh_token]):
            raise YouTubeAuthError(
                "YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN이 필요합니다."
            )
        credentials = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=[UPLOAD_SCOPE],
        )
        try:
            credentials.refresh(Request())
        except Exception as exc:
            raise YouTubeAuthError(f"YouTube 인증 토큰을 갱신하지 못했습니다: {exc}") from exc
        LOGGER.info("YouTube OAuth 인증 완료")
        return build("youtube", "v3", credentials=credentials, cache_discovery=False)

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        privacy: str = "public",
    ) -> Dict[str, str]:
        if not video_path.exists():
            raise FileNotFoundError(video_path)
        body = {
            "snippet": {
                "title": title[:100],
                "description": description.encode("utf-8")[:4900].decode("utf-8", errors="ignore"),
                "tags": tags[:15],
                "categoryId": "27",  # Education
                "defaultLanguage": "ko",
                "defaultAudioLanguage": "ko",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
                # AI 음성을 사용하므로 보수적으로 공개한다. 공개 자체는 수익화 자격을 제한하지 않는다.
                "containsSyntheticMedia": True,
            },
        }
        media = MediaFileUpload(
            str(video_path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True
        )
        request = self.youtube.videos().insert(
            part="snippet,status", body=body, media_body=media, notifySubscribers=True
        )
        response = None
        retry = 0
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    LOGGER.info("YouTube 업로드 진행: %d%%", int(status.progress() * 100))
            except HttpError as exc:
                if exc.resp.status not in RETRIABLE_STATUS_CODES or retry >= 5:
                    raise
                retry += 1
                delay = random.uniform(1, min(32, 2 ** retry))
                LOGGER.warning("YouTube 일시 오류, %.1f초 뒤 재시도", delay)
                time.sleep(delay)
        video_id = str(response["id"])
        result = {
            "video_id": video_id,
            "video_url": f"https://www.youtube.com/shorts/{video_id}",
        }
        LOGGER.info("YouTube 업로드 완료: %s", result["video_url"])
        return result
