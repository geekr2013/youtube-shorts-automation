"""Pexels/Pixabay의 사용 허가된 스톡 영상을 내려받는다."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from models import StockClip

LOGGER = logging.getLogger(__name__)
MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024


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

    def _search_pexels(self, query: str) -> List[Dict[str, str]]:
        if not self.pexels_key:
            return []
        response = self.session.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": self.pexels_key},
            params={"query": query, "per_page": 15, "orientation": "portrait"},
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
                }
            )
        return results

    def _search_pixabay(self, query: str) -> List[Dict[str, str]]:
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
                }
            )
        return results

    def _download(self, candidate: Dict[str, str], path: Path) -> StockClip:
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
        return StockClip(
            path=path,
            provider=candidate["provider"],
            source_url=candidate["source_url"],
            creator=candidate["creator"],
        )

    def fetch_clips(self, queries: Iterable[str], output_dir: Path, limit: int = 4) -> List[StockClip]:
        if not self.pexels_key and not self.pixabay_key:
            raise MediaError("PEXELS_API_KEY 또는 PIXABAY_API_KEY가 필요합니다.")
        output_dir.mkdir(parents=True, exist_ok=True)
        clips: List[StockClip] = []
        seen = set()
        for query in [item.strip() for item in queries if item.strip()]:
            candidates: List[Dict[str, str]] = []
            for searcher in (self._search_pexels, self._search_pixabay):
                try:
                    candidates.extend(searcher(query))
                except Exception as exc:
                    LOGGER.warning("%s 스톡 검색 실패(%s): %s", searcher.__name__, query, exc)
            for candidate in candidates:
                if candidate["download_url"] in seen:
                    continue
                seen.add(candidate["download_url"])
                try:
                    clip = self._download(candidate, output_dir / f"clip_{len(clips) + 1}.mp4")
                    clips.append(clip)
                    LOGGER.info("스톡 영상 확보: %s / %s", candidate["provider"], query)
                    break
                except Exception as exc:
                    LOGGER.warning("스톡 영상 다운로드 실패: %s", exc)
            if len(clips) >= limit:
                break
        if len(clips) < 2:
            raise MediaError("서로 다른 스톡 영상을 2개 이상 확보하지 못했습니다.")
        return clips

