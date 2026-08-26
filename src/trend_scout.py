"""Collect public US YouTube performance signals without copying creators."""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from topic_catalog import VERIFIED_TOPICS

LOGGER = logging.getLogger(__name__)
YOUTUBE_VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"

EVERGREEN_SEEDS = [plan.topic for plan in VERIFIED_TOPICS]


def fetch_youtube_trends(api_key: str, region: str = "US") -> List[Dict[str, Any]]:
    if not api_key:
        return []
    results: List[Dict[str, Any]] = []
    # 전체·코미디·노하우·과학/기술 신호를 함께 보되 제목이나 소재를 복제하지 않는다.
    for category_id in ("0", "23", "26", "28"):
        try:
            response = requests.get(
                YOUTUBE_VIDEOS_ENDPOINT,
                params={
                    "key": api_key,
                    "part": "snippet,statistics",
                    "chart": "mostPopular",
                    "regionCode": region,
                    "videoCategoryId": category_id,
                    "maxResults": 12,
                },
                timeout=25,
            )
            response.raise_for_status()
            for item in response.json().get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                results.append(
                    {
                        "title": snippet.get("title", "")[:120],
                        "channel": snippet.get("channelTitle", "")[:60],
                        "tags": snippet.get("tags", [])[:6],
                        "views": int(stats.get("viewCount", 0) or 0),
                        "category_id": category_id,
                    }
                )
        except Exception as exc:
            LOGGER.warning("YouTube 인기 신호 수집 실패(category=%s): %s", category_id, exc)
    results.sort(key=lambda item: item.get("views", 0), reverse=True)
    return results[:20]


def top_performing_topics(records: List[Dict[str, Any]]) -> List[str]:
    scored = []
    for item in records:
        metrics = item.get("metrics", {})
        views = int(metrics.get("views", 0) or 0)
        likes = int(metrics.get("likes", 0) or 0)
        comments = int(metrics.get("comments", 0) or 0)
        score = views + likes * 20 + comments * 40
        if item.get("topic"):
            scored.append((score, item["topic"]))
    scored.sort(reverse=True)
    return [topic for _, topic in scored[:5]]


def _iso8601_seconds(value: str) -> int:
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(item or 0) for item in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def fetch_pilates_short_benchmarks(
    api_key: str,
    region: str = "US",
    now: datetime | None = None,
) -> List[Dict[str, Any]]:
    """최근 필라테스 쇼츠의 공개 성과 신호만 읽고 원본 영상은 사용하지 않는다."""
    if not api_key:
        return []
    current = now or datetime.now(timezone.utc)
    published_after = (current - timedelta(days=180)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        search = requests.get(
            YOUTUBE_SEARCH_ENDPOINT,
            params={
                "key": api_key,
                "part": "snippet",
                "q": "pilates workout shorts",
                "type": "video",
                "videoDuration": "short",
                "order": "viewCount",
                "publishedAfter": published_after,
                "regionCode": region,
                "relevanceLanguage": "en",
                "safeSearch": "strict",
                "maxResults": 25,
            },
            timeout=25,
        )
        search.raise_for_status()
        ids = [
            str(item.get("id", {}).get("videoId") or "")
            for item in search.json().get("items", [])
        ]
        ids = [item for item in ids if item]
        if not ids:
            return []
        details = requests.get(
            YOUTUBE_VIDEOS_ENDPOINT,
            params={
                "key": api_key,
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(ids),
                "maxResults": 50,
            },
            timeout=25,
        )
        details.raise_for_status()
    except Exception as exc:
        LOGGER.warning("필라테스 쇼츠 벤치마크 수집 실패: %s", exc)
        return []

    results: List[Dict[str, Any]] = []
    for item in details.json().get("items", []):
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        duration = _iso8601_seconds(item.get("contentDetails", {}).get("duration", ""))
        if not 8 <= duration <= 60:
            continue
        try:
            published = datetime.fromisoformat(str(snippet.get("publishedAt", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        age_days = max(1.0, (current - published).total_seconds() / 86400)
        views = int(statistics.get("viewCount", 0) or 0)
        likes = int(statistics.get("likeCount", 0) or 0)
        comments = int(statistics.get("commentCount", 0) or 0)
        velocity = views / age_days
        engagement = (likes + comments * 3) / max(views, 1)
        results.append(
            {
                "video_id": item.get("id", ""),
                "title": str(snippet.get("title") or "")[:120],
                "channel": str(snippet.get("channelTitle") or "")[:60],
                "published_at": published.isoformat(),
                "duration_seconds": duration,
                "views": views,
                "likes": likes,
                "comments": comments,
                "views_per_day": round(velocity, 1),
                "engagement_rate": round(engagement, 5),
                "score": round(velocity * (1 + min(engagement * 8, 0.5)), 1),
            }
        )
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:12]


def editing_profile(benchmarks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """과장 효능 문구는 배제하고 반복 가능한 편집 신호만 반환한다."""
    lowered = " ".join(str(item.get("title") or "").lower() for item in benchmarks)
    return {
        "sample_count": len(benchmarks),
        "motion_on_first_frame": True,
        "single_body_area_promise": True,
        "full_body_then_closeup": True,
        "save_cta": True,
        "benchmark_save_language_seen": any(token in lowered for token in ("save", "저장")),
        "short_numbered_routine": True,
        "loop_friendly_ending": True,
        "copied_titles": False,
        "copied_footage": False,
        "unsafe_transformation_claims": False,
    }

