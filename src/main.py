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
from knowledge import research_exact_topic
from media_provider import StockMediaProvider
from metrics import fetch_video_metrics, update_records
from notifier import send_notification
from quality import QualityGateError, source_is_relevant, validate_package
from topic_catalog import eligible_topic_plans
from trend_scout import fetch_youtube_trends, top_performing_topics
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
    required = ["YOUTUBE_DATA_API_KEY"]
    if not (
        os.getenv("GITHUB_MODELS_TOKEN")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    ):
        missing.append("GitHub Models 또는 Gemini 인증 정보")
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
        "공개된 검증 자료 범위와 안전 기준을 자동 확인했습니다. "
        "청취를 방해하는 합성 배경음 없이 내레이션 중심으로 제작했습니다.\n\n"
        f"댓글 질문: {script.engagement_question}\n\n"
        f"#shorts #지식쇼츠 {hashtags}"
    )


def build_engagement_comment(script) -> str:
    return f"💬 {script.engagement_question}\n여러분의 경험이나 생각을 댓글로 알려주세요."


def write_preview_metadata(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_editorial_script(writer, plan, source, recent_topics):
    """작가 작성과 독립 편집 검수를 최대 두 번 수행한다."""
    feedback = []
    last_reason = "편집 검수를 통과하지 못했습니다."
    for attempt in range(2):
        try:
            script = writer.write_script(plan, source, editorial_feedback=feedback)
            validate_package(plan, script, source, recent_topics)
        except QualityGateError as exc:
            last_reason = str(exc)
            feedback = [last_reason]
            LOGGER.warning("자동 품질 기준 미달로 대본을 다시 작성합니다(%s/2): %s", attempt + 1, exc)
            continue
        review = writer.review_script(plan, source, script)
        if review["approved"]:
            return script, review
        last_reason = ", ".join(review["issues"][:3]) or f"편집 점수 {review['score']}점"
        feedback = review["issues"] or [
            "검증 자료에 직접 근거한 사실만 남기고 문장을 더 자연스럽고 구체적으로 다듬으세요."
        ]
        LOGGER.warning(
            "편집자 검수 미달로 대본을 다시 작성합니다(%s/2): %s점 / %s",
            attempt + 1,
            review["score"],
            last_reason,
        )
    raise QualityGateError("최종 편집 검수를 통과하지 못했습니다: " + last_reason)


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

    recent_topics = [item.get("topic", "") for item in records[-12:] if item.get("topic")]
    trends = fetch_youtube_trends(data_api_key)
    writer = GeminiWriter()
    top_topics = top_performing_topics(records)
    candidate_pool = eligible_topic_plans(recent_topics)
    ranked_candidates = writer.rank_topics(
        trends,
        recent_topics,
        top_topics,
        candidate_pool,
        limit=min(8, len(candidate_pool)),
    )
    plan = None
    source = None
    script = None
    editorial_review = None
    for topic_attempt, candidate in enumerate(ranked_candidates, start=1):
        LOGGER.info("선정 주제: %s (%s)", candidate.topic, candidate.trend_reason)
        try:
            candidate_source = research_exact_topic(candidate.wiki_query)
        except Exception as exc:
            LOGGER.warning("검증 문서 직접 조회 실패(%s): %s", candidate.wiki_query, exc)
            continue
        if not source_is_relevant(candidate, candidate_source):
            LOGGER.warning("등록된 주제와 검증 문서가 일치하지 않습니다: %s", candidate_source.title)
            continue
        try:
            candidate_script, candidate_review = create_editorial_script(
                writer,
                candidate,
                candidate_source,
                recent_topics,
            )
        except Exception as exc:
            LOGGER.warning("주제 편집 실패로 다음 검증 후보를 시도합니다(%s): %s", topic_attempt, exc)
            continue
        plan = candidate
        source = candidate_source
        script = candidate_script
        editorial_review = candidate_review
        if plan is not None:
            break
    if plan is None or source is None or script is None or editorial_review is None:
        raise QualityGateError("검증 자료와 최종 편집 기준을 모두 통과한 주제를 만들지 못했습니다.")

    provider = StockMediaProvider()
    clips = provider.fetch_clips(plan.stock_queries, media_dir, limit=4)
    final_video = render_short(
        clips,
        script.narration,
        render_dir,
    )
    duration = media_duration(final_video)
    audio_metadata_path = render_dir / "audio_metadata.json"
    audio_metadata = json.loads(audio_metadata_path.read_text(encoding="utf-8"))
    description = build_description(script, source, clips)
    metadata = {
        "topic": plan.topic,
        "title": script.title,
        "hook": script.hook,
        "midpoint_hook": script.midpoint_hook,
        "closing_loop": script.closing_loop,
        "engagement_comment": build_engagement_comment(script),
        "duration_seconds": round(duration, 2),
        "source": {"title": source.title, "url": source.url, "license": source.license_name},
        "editorial_review": editorial_review,
        "source_strategy": "curated exact-title Wikipedia document",
        "stock_assets": [
            {"provider": item.provider, "creator": item.creator, "url": item.source_url}
            for item in clips
        ],
        "tags": script.tags,
        "audio": audio_metadata,
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
        "engagement_comment": build_engagement_comment(script),
        "editorial_score": editorial_review["score"],
        "metrics": {"views": 0, "likes": 0, "comments": 0},
    }
    records.append(record)
    state["videos"] = records[-365:]
    save_state(state)
    write_preview_metadata(WORK_DIR / "metadata.json", {**metadata, **result, "dry_run": False})
    send_notification(
        f"[지식 쇼츠] 업로드 완료 - {script.title}",
        f"주제: {plan.topic}\n영상: {result['video_url']}\n출처: {source.url}\n\n"
        f"고정 댓글 추천 문구:\n{build_engagement_comment(script)}",
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

