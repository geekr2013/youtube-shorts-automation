"""YouTube의 한국 인기 신호를 저비용으로 수집한다."""

import logging
from typing import Any, Dict, List

import requests

LOGGER = logging.getLogger(__name__)
YOUTUBE_VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"

EVERGREEN_SEEDS = [
    "생물발광은 왜 빛날까",
    "구름의 무게는 얼마나 될까",
    "문어의 위장 원리",
    "벌집이 육각형인 이유",
    "오로라가 생기는 과정",
    "나무 나이테가 기록하는 기후",
    "사막의 모래가 노래하는 현상",
    "철새가 길을 찾는 방법",
    "번개가 지그재그로 이동하는 이유",
    "심해 생물이 압력을 견디는 방식",
    "로마 콘크리트가 오래가는 이유",
    "QR 코드가 일부 가려져도 읽히는 이유",
]


def fetch_youtube_trends(api_key: str, region: str = "KR") -> List[Dict[str, Any]]:
    if not api_key:
        return []
    results: List[Dict[str, Any]] = []
    for category_id in ("0", "28", "27"):  # 전체, 과학/기술, 교육
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

