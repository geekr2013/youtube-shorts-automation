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

from secret_utils import clean_secret

LOGGER = logging.getLogger(__name__)
UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
RETRIABLE_STATUS_CODES = {500, 502, 503, 504}
PUBLIC_VERIFY_TIMEOUT_SECONDS = 8 * 60
PUBLIC_VERIFY_INTERVAL_SECONDS = 15


class YouTubeAuthError(RuntimeError):
    pass


class YouTubeUploader:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        self.client_id = clean_secret(client_id or os.getenv("YOUTUBE_CLIENT_ID", ""))
        self.client_secret = clean_secret(
            client_secret or os.getenv("YOUTUBE_CLIENT_SECRET", "")
        )
        self.refresh_token = clean_secret(
            refresh_token or os.getenv("YOUTUBE_REFRESH_TOKEN", "")
        )
        self.youtube = self._authenticate()

    def _normalize_client(self) -> tuple[str, str, str]:
        token_uri = "https://oauth2.googleapis.com/token"
        if self.client_secret.strip().startswith("{"):
            try:
                payload = json.loads(self.client_secret)
                config = payload.get("installed") or payload.get("web") or {}
                client_id = clean_secret(config.get("client_id") or self.client_id)
                client_secret = clean_secret(config.get("client_secret", ""))
                token_uri = config.get("token_uri", token_uri)
                return client_id, client_secret, token_uri
            except json.JSONDecodeError as exc:
                raise YouTubeAuthError("YOUTUBE_CLIENT_SECRET JSON 형식이 잘못되었습니다.") from exc
        return clean_secret(self.client_id), clean_secret(self.client_secret), token_uri

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

    def _wait_until_ready(
        self,
        video_id: str,
        expected_privacy: str,
        timeout_seconds: int = PUBLIC_VERIFY_TIMEOUT_SECONDS,
        interval_seconds: int = PUBLIC_VERIFY_INTERVAL_SECONDS,
    ) -> Dict[str, str]:
        """Confirm that YouTube finished processing and applied the requested visibility."""
        deadline = time.monotonic() + timeout_seconds
        last_state = "not returned"
        while time.monotonic() < deadline:
            payload = self.youtube.videos().list(
                part="status,processingDetails",
                id=video_id,
            ).execute()
            items = payload.get("items") or []
            if not items:
                last_state = "video not returned yet"
            else:
                item = items[0]
                status = item.get("status") or {}
                processing = item.get("processingDetails") or {}
                privacy = str(status.get("privacyStatus") or "")
                upload_status = str(status.get("uploadStatus") or "")
                processing_status = str(processing.get("processingStatus") or "")
                last_state = (
                    f"privacy={privacy or 'unknown'}, upload={upload_status or 'unknown'}, "
                    f"processing={processing_status or 'unknown'}"
                )
                if upload_status in {"failed", "rejected", "deleted"} or processing_status == "terminated":
                    reason = status.get("failureReason") or status.get("rejectionReason") or last_state
                    raise RuntimeError(f"YouTube 처리 실패: {reason}")
                processed = upload_status == "processed" or processing_status == "succeeded"
                if privacy == expected_privacy and processed:
                    LOGGER.info("YouTube 공개·처리 확인 완료: %s", last_state)
                    return {
                        "privacy_status": privacy,
                        "upload_status": upload_status or "processed",
                        "processing_status": processing_status or "succeeded",
                    }
            time.sleep(interval_seconds)
        raise RuntimeError(
            "YouTube 업로드 요청은 완료됐지만 공개·처리 완료를 확인하지 못했습니다: "
            + last_state
        )

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        privacy: str = "public",
        category_id: str = "26",
    ) -> Dict[str, str]:
        if not video_path.exists():
            raise FileNotFoundError(video_path)
        body = {
            "snippet": {
                "title": title[:100],
                "description": description.encode("utf-8")[:4900].decode("utf-8", errors="ignore"),
                "tags": tags[:15],
                "categoryId": category_id,  # Howto & Style for Pilates guidance
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
                # The real workout footage includes a synthetic English guide voice.
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
        result.update(self._wait_until_ready(video_id, privacy))
        LOGGER.info("YouTube 공개 업로드 완료: %s", result["video_url"])
        return result

