"""Pexels/Pixabay에서 라이선스가 허용된 실제 동영상을 내려받는다."""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from models import StockClip

LOGGER = logging.getLogger(__name__)
MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024
MIN_VIDEO_SECONDS = 4.0
MAX_VIDEO_SECONDS = 90.0
MIN_VIDEO_EDGE = 720
MIN_FRAME_RATE = 20.0


class MediaError(RuntimeError):
    pass


class StockMediaProvider:
    def __init__(self, pexels_key: str = "", pixabay_key: str = ""):
        self.pexels_key = pexels_key or os.getenv("PEXELS_API_KEY", "")
        self.pixabay_key = pixabay_key or os.getenv("PIXABAY_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "OriginalShortsMVP/1.0"})

    @staticmethod
    def _best_pexels_file(video: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        files = [
            item for item in video.get("video_files", [])
            if item.get("link") and item.get("file_type") == "video/mp4"
        ]
        if not files:
            return None

        def score(item: Dict[str, Any]) -> Tuple[int, int, int]:
            width = int(item.get("width", 0) or 0)
            height = int(item.get("height", 0) or 0)
            portrait = 1 if height >= width else 0
            usable = 1 if width >= 720 and height >= 720 else 0
            oversize_penalty = -1 if width > 1920 or height > 1920 else 0
            return portrait, usable, oversize_penalty

        files.sort(key=score, reverse=True)
        return files[0]

    def _search_pexels(self, query: str) -> List[Dict[str, Any]]:
        if not self.pexels_key:
            return []
        response = self.session.get(
            "https://api.pexels.com/v1/videos/search",
            headers={"Authorization": self.pexels_key},
            params={
                "query": query,
                "per_page": 24,
                "orientation": "portrait",
                "size": "medium",
                "locale": "en-US",
            },
            timeout=30,
        )
        response.raise_for_status()
        results = []
        for video in response.json().get("videos", []):
            media_file = self._best_pexels_file(video)
            if not media_file:
                continue
            user = video.get("user", {})
            results.append(
                {
                    "download_url": media_file["link"],
                    "source_url": video.get("url", "https://www.pexels.com/videos/"),
                    "creator": user.get("name", "Pexels creator"),
                    "provider": "Pexels",
                    "query": query,
                    "source_id": str(video.get("id") or ""),
                    "width": int(media_file.get("width", 0) or 0),
                    "height": int(media_file.get("height", 0) or 0),
                    "duration": float(video.get("duration", 0) or 0),
                }
            )
        return results

    def _search_pixabay(self, query: str) -> List[Dict[str, Any]]:
        if not self.pixabay_key:
            return []
        response = self.session.get(
            "https://pixabay.com/api/videos/",
            params={
                "key": self.pixabay_key,
                "q": query,
                "per_page": 20,
                "safesearch": "true",
                "video_type": "film",
            },
            timeout=30,
        )
        response.raise_for_status()
        results = []
        for hit in response.json().get("hits", []):
            variants = hit.get("videos", {})
            media = variants.get("medium") or variants.get("small") or variants.get("tiny")
            if not media or not media.get("url"):
                continue
            results.append(
                {
                    "download_url": media["url"],
                    "source_url": hit.get("pageURL", "https://pixabay.com/videos/"),
                    "creator": hit.get("user", "Pixabay creator"),
                    "provider": "Pixabay",
                    "query": query,
                    "source_id": str(hit.get("id") or ""),
                    "width": int(media.get("width", 0) or 0),
                    "height": int(media.get("height", 0) or 0),
                    "duration": float(hit.get("duration", 0) or 0),
                }
            )
        return results

    @staticmethod
    def _frame_rate(value: str) -> float:
        try:
            numerator, denominator = value.split("/", 1)
            return float(numerator) / max(float(denominator), 1.0)
        except (AttributeError, TypeError, ValueError, ZeroDivisionError):
            return 0.0

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _probe_video(cls, path: Path) -> Dict[str, Any]:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise MediaError("실제 동영상 검증에 FFprobe가 필요합니다.")
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,avg_frame_rate,nb_frames:format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise MediaError("받은 파일을 동영상으로 확인하지 못했습니다.")
        payload = json.loads(result.stdout or "{}")
        streams = payload.get("streams") or []
        if not streams:
            raise MediaError("동영상 화면 트랙이 없습니다.")
        stream = streams[0]
        duration = float((payload.get("format") or {}).get("duration", 0) or 0)
        width = int(stream.get("width", 0) or 0)
        height = int(stream.get("height", 0) or 0)
        fps = cls._frame_rate(str(stream.get("avg_frame_rate") or "0/1"))
        frame_count = cls._safe_int(stream.get("nb_frames", 0))
        if not MIN_VIDEO_SECONDS <= duration <= MAX_VIDEO_SECONDS:
            raise MediaError(f"동영상 길이가 기준 밖입니다: {duration:.1f}초")
        if min(width, height) < MIN_VIDEO_EDGE:
            raise MediaError(f"동영상 해상도가 낮습니다: {width}x{height}")
        if fps < MIN_FRAME_RATE:
            raise MediaError(f"동영상 프레임 속도가 낮습니다: {fps:.1f}fps")
        if frame_count and frame_count < int(duration * MIN_FRAME_RATE * 0.8):
            raise MediaError("실제 움직임을 담은 연속 프레임이 부족합니다.")
        return {
            "duration": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
        }

    def _download(self, candidate: Dict[str, Any], path: Path) -> StockClip:
        with self.session.get(candidate["download_url"], stream=True, timeout=90) as response:
            response.raise_for_status()
            expected = int(response.headers.get("content-length", 0) or 0)
            if expected and expected > MAX_DOWNLOAD_BYTES:
                raise MediaError("스톡 영상 파일이 너무 큽니다.")
            written = 0
            with path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > MAX_DOWNLOAD_BYTES:
                        raise MediaError("스톡 영상 다운로드 한도를 넘었습니다.")
                    handle.write(chunk)
        if path.stat().st_size < 100_000:
            path.unlink(missing_ok=True)
            raise MediaError("스톡 영상 파일이 손상되었습니다.")
        try:
            probe = self._probe_video(path)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return StockClip(
            path=path,
            provider=candidate["provider"],
            source_url=candidate["source_url"],
            creator=candidate["creator"],
            query=str(candidate.get("query") or ""),
            source_id=str(candidate.get("source_id") or ""),
            width=int(probe["width"]),
            height=int(probe["height"]),
            duration=float(probe["duration"]),
        )

    def fetch_clips(
        self,
        queries: Iterable[str],
        output_dir: Path,
        limit: int = 4,
        min_required: int = 2,
        one_per_query: bool = False,
    ) -> List[StockClip]:
        if not self.pexels_key and not self.pixabay_key:
            raise MediaError("PEXELS_API_KEY 또는 PIXABAY_API_KEY가 필요합니다.")
        output_dir.mkdir(parents=True, exist_ok=True)
        clips: List[StockClip] = []
        seen = set()
        for query in [item.strip() for item in queries if item.strip()]:
            clips_before_query = len(clips)
            candidates: List[Dict[str, Any]] = []
            for searcher in (self._search_pexels, self._search_pixabay):
                try:
                    candidates.extend(searcher(query))
                except Exception as exc:
                    LOGGER.warning("%s 스톡 검색 실패(%s): %s", searcher.__name__, query, exc)
            candidates.sort(
                key=lambda item: (
                    int(item.get("height", 0) >= item.get("width", 0)),
                    int(MIN_VIDEO_SECONDS <= float(item.get("duration", 0) or 0) <= 45),
                    min(int(item.get("width", 0) or 0), int(item.get("height", 0) or 0)),
                ),
                reverse=True,
            )
            for candidate in candidates:
                identity = (
                    str(candidate.get("provider") or ""),
                    str(candidate.get("source_id") or candidate.get("download_url") or ""),
                )
                if identity in seen:
                    continue
                seen.add(identity)
                try:
                    clip = self._download(candidate, output_dir / f"clip_{len(clips) + 1}.mp4")
                    clips.append(clip)
                    LOGGER.info("스톡 영상 확보: %s / %s", candidate["provider"], query)
                    break
                except Exception as exc:
                    LOGGER.warning("스톡 영상 다운로드 실패: %s", exc)
            if one_per_query and len(clips) == clips_before_query:
                raise MediaError(f"동작과 직접 연결된 실제 영상을 찾지 못했습니다: {query}")
            if len(clips) >= limit:
                break
        if len(clips) < min_required:
            raise MediaError(f"서로 다른 실제 운동 영상을 {min_required}개 이상 확보하지 못했습니다.")
        return clips

