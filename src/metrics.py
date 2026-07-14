"""공개 YouTube 통계를 수집해 다음 주제 선택에 반영한다."""

import logging
from typing import Any, Dict, Iterable

import requests

LOGGER = logging.getLogger(__name__)


def fetch_video_metrics(api_key: str, video_ids: Iterable[str]) -> Dict[str, Dict[str, int]]:
    ids = [item for item in video_ids if item]
    if not api_key or not ids:
        return {}
    output: Dict[str, Dict[str, int]] = {}
    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]
        try:
            response = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "key": api_key,
                    "part": "statistics,status",
                    "id": ",".join(batch),
                },
                timeout=30,
            )
            response.raise_for_status()
            for item in response.json().get("items", []):
                stats = item.get("statistics", {})
                output[item["id"]] = {
                    "views": int(stats.get("viewCount", 0) or 0),
                    "likes": int(stats.get("likeCount", 0) or 0),
                    "comments": int(stats.get("commentCount", 0) or 0),
                }
        except Exception as exc:
            LOGGER.warning("YouTube 성과 수집 실패: %s", exc)
    return output


def update_records(records: list[Dict[str, Any]], metrics: Dict[str, Dict[str, int]]) -> bool:
    changed = False
    for record in records:
        video_id = record.get("video_id")
        if video_id in metrics and record.get("metrics") != metrics[video_id]:
            record["metrics"] = metrics[video_id]
            changed = True
    return changed

