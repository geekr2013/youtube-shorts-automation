"""원본 한국어 지식 쇼츠를 매일 한 편 생성하고 업로드한다."""

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from ai_writer import GeminiWriter
from knowledge import research_topic
from media_provider import StockMediaProvider
from metrics import fetch_video_metrics, update_records
from notifier import send_notification
from quality import validate_package
from trend_scout import EVERGREEN_SEEDS, fetch_youtube_trends, top_performing_topics
from video_renderer import media_duration, render_short

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "published_topics.json"
WORK_DIR = DATA_DIR / "work"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOGGER = logging.getLogger("original-shorts")


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {"version": 1, "videos": []}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data.get("videos"), list):
            raise ValueError("videos가 목록이 아님")
        return data
    except Exception as exc:
        raise RuntimeError(f"운영 상태 파일을 읽지 못했습니다: {exc}") from exc


def save_state(state: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def check_configuration(for_upload: bool) -> List[str]:
    missing = []
    required = ["GEMINI_API_KEY", "YOUTUBE_DATA_API_KEY"]
    if not (os.getenv("PEXELS_API_KEY") or os.getenv("PIXABAY_API_KEY")):
        missing.append("PEXELS_API_KEY 또는 PIXABAY_API_KEY")
    if for_upload:
        required.extend(
            ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
        )
    missing.extend(name for name in required if not os.getenv(name))
    return missing


def build_description(script, source, clips) -> str:
    credits = []
    seen = set()
    for clip in clips:
        key = (clip.provider, clip.source_url)
        if key in seen:
            continue
        seen.add(key)
        creator = f" / {clip.creator}" if clip.creator else ""
        credits.append(f"- {clip.provider}{creator}: {clip.source_url}")
    hashtags = " ".join(f"#{tag.replace(' ', '')}" for tag in script.tags[:5])
    return (
        f"{script.description_intro}\n\n"
        f"검증 자료: {source.title}\n{source.url}\n"
        f"위키백과 텍스트 라이선스: {source.license_name}\n\n"
        "영상 자료 출처(각 제공처 라이선스 적용):\n"
        + "\n".join(credits)
        + "\n\nAI 도구를 주제 정리, 대본 작성 보조, 내레이션 제작에 사용했으며 "
        "공개된 검증 자료 범위와 안전 기준을 자동 확인했습니다.\n\n"
        f"#shorts #지식쇼츠 {hashtags}"
    )


def write_preview_metadata(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(dry_run: bool = False) -> Dict[str, Any]:
    missing = check_configuration(for_upload=not dry_run)
    if missing:
        raise RuntimeError("GitHub Secrets 누락: " + ", ".join(missing))

    state = load_state()
    records: List[Dict[str, Any]] = state["videos"]
    data_api_key = os.environ["YOUTUBE_DATA_API_KEY"]

    metrics = fetch_video_metrics(data_api_key, [item.get("video_id", "") for item in records])
    if update_records(records, metrics):
        save_state(state)
        LOGGER.info("기존 영상 성과를 갱신했습니다.")

    if WORK_DIR.exists():
        resolved = WORK_DIR.resolve()
        if DATA_DIR.resolve() not in resolved.parents:
            raise RuntimeError("작업 폴더 안전 확인에 실패했습니다.")
        shutil.rmtree(WORK_DIR)
    media_dir = WORK_DIR / "media"
    render_dir = WORK_DIR / "render"
    media_dir.mkdir(parents=True, exist_ok=True)
    render_dir.mkdir(parents=True, exist_ok=True)

    recent_topics = [item.get("topic", "") for item in records[-40:] if item.get("topic")]
    trends = fetch_youtube_trends(data_api_key)
    writer = GeminiWriter()
    plan = writer.select_topic(
        trends,
        recent_topics,
        top_performing_topics(records),
        EVERGREEN_SEEDS,
    )
    LOGGER.info("선정 주제: %s (%s)", plan.topic, plan.trend_reason)

    try:
        source = research_topic(plan.wiki_query)
    except Exception:
        source = research_topic(plan.topic)
    script = writer.write_script(plan, source)
    validate_package(plan, script, source, recent_topics)

    provider = StockMediaProvider()
    clips = provider.fetch_clips(plan.stock_queries, media_dir, limit=4)
    final_video = render_short(clips, script.narration, render_dir)
    duration = media_duration(final_video)
    description = build_description(script, source, clips)
    metadata = {
        "topic": plan.topic,
        "title": script.title,
        "hook": script.hook,
        "duration_seconds": round(duration, 2),
        "source": {"title": source.title, "url": source.url, "license": source.license_name},
        "stock_assets": [
            {"provider": item.provider, "creator": item.creator, "url": item.source_url}
            for item in clips
        ],
        "tags": script.tags,
        "dry_run": dry_run,
    }
    write_preview_metadata(WORK_DIR / "metadata.json", metadata)

    if dry_run:
        LOGGER.info("건식 실행 완료: 업로드하지 않았습니다.")
        return metadata

    # 설정 점검과 건식 실행은 YouTube 인증 패키지를 불러오지 않아도 된다.
    from youtube_uploader import YouTubeUploader

    uploader = YouTubeUploader()
    result = uploader.upload_video(
        final_video,
        title=f"{script.title} #shorts",
        description=description,
        tags=["shorts", "지식쇼츠", *script.tags],
        privacy=os.getenv("YOUTUBE_PRIVACY", "public"),
    )
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "published_at": now,
        "topic": plan.topic,
        "title": script.title,
        "video_id": result["video_id"],
        "video_url": result["video_url"],
        "source_url": source.url,
        "asset_urls": [item.source_url for item in clips],
        "metrics": {"views": 0, "likes": 0, "comments": 0},
    }
    records.append(record)
    state["videos"] = records[-365:]
    save_state(state)
    write_preview_metadata(WORK_DIR / "metadata.json", {**metadata, **result, "dry_run": False})
    send_notification(
        f"[지식 쇼츠] 업로드 완료 - {script.title}",
        f"주제: {plan.topic}\n영상: {result['video_url']}\n출처: {source.url}",
    )
    return {**metadata, **result}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="원본 AI 지식 쇼츠 자동화")
    parser.add_argument("--dry-run", action="store_true", help="영상만 만들고 업로드하지 않음")
    parser.add_argument("--check-config", action="store_true", help="비밀키 이름만 점검")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check_config:
            missing = check_configuration(for_upload=not args.dry_run)
            if missing:
                raise RuntimeError("GitHub Secrets 누락: " + ", ".join(missing))
            LOGGER.info("필수 GitHub Secrets 이름 확인 완료")
            return 0
        result = run(dry_run=args.dry_run)
        LOGGER.info("작업 완료: %s", result.get("video_url", "건식 실행"))
        return 0
    except Exception as exc:
        LOGGER.exception("자동화 실패: %s", exc)
        send_notification("[지식 쇼츠] 자동화 실패", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
