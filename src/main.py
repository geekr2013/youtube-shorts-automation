"""라이선스 허용 실제 운동 영상으로 필라테스 쇼츠를 매일 제작·업로드한다."""

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

from media_provider import StockMediaProvider
from metrics import fetch_video_metrics, update_records
from models import StockClip
from notifier import send_notification
from pilates_catalog import (
    INSTRUCTOR_ID,
    INSTRUCTOR_NAME_EN,
    INSTRUCTOR_NAME_KO,
    build_narration,
    routine_exercises,
    select_routine,
    validate_routine,
)
from pilates_renderer import media_duration, render_pilates_short
from pilates_video_strategy import SOURCE_REQUIREMENTS, build_clip_queries
from trend_scout import editing_profile, fetch_pilates_short_benchmarks


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "published_topics.json"
WORK_DIR = DATA_DIR / "work"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOGGER = logging.getLogger("pilates-shorts")


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {"version": 2, "videos": []}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data.get("videos"), list):
            raise ValueError("videos가 목록이 아님")
        data["version"] = max(2, int(data.get("version", 1)))
        return data
    except Exception as exc:
        raise RuntimeError(f"운영 상태 파일을 읽지 못했습니다: {exc}") from exc


def save_state(state: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_configuration(for_upload: bool) -> List[str]:
    missing: List[str] = []
    if not (os.getenv("PEXELS_API_KEY") or os.getenv("PIXABAY_API_KEY")):
        missing.append("PEXELS_API_KEY 또는 PIXABAY_API_KEY")
    if for_upload:
        required = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
        missing.extend(name for name in required if not os.getenv(name))
    return missing


def build_title(routine) -> str:
    return f"저장하고 따라 하는 {routine.title_ko} 3동작 | {routine.title_en}"


def build_engagement_comment(routine) -> str:
    return f"💬 {routine.engagement_question}\n무리하지 않은 범위에서 알려주세요."


def _source_credit_lines(clips: Sequence[StockClip]) -> List[str]:
    return [
        f"- {clip.provider}: {clip.creator} — {clip.source_url}"
        for clip in clips
    ]


def build_description(routine, clips: Sequence[StockClip] = ()) -> str:
    exercises = routine_exercises(routine)
    movement_lines = [
        f"{index}. {item.name_ko} / {item.name_en} — {item.prescription_ko}"
        for index, item in enumerate(exercises, start=1)
    ]
    return (
        f"첫 화면부터 바로 따라 하는 {routine.intro_ko}\n\n"
        + "\n".join(movement_lines)
        + "\n\n호흡을 멈추지 말고 천천히 진행하세요. 통증, 어지러움 또는 불편함이 느껴지면 즉시 중단하세요. "
        "부상, 질환, 임신 등 개인 상황이 있다면 운동 전에 의료진 또는 자격을 갖춘 지도자와 상담하세요.\n\n"
        f"안내 브랜드: {INSTRUCTOR_NAME_KO} / {INSTRUCTOR_NAME_EN}\n"
        "Pexels 또는 Pixabay에서 사용이 허용된 실제 사람의 연속 운동 영상을 가져와 "
        "전신 구도와 목표 근육 클로즈업으로 재편집했습니다. 출연자는 영상마다 달라질 수 있습니다.\n"
        "배경음악 없이 AI 한국어 여성 안내 음성과 한·영 자막으로 제작했습니다.\n\n"
        + (("영상 출처\n" + "\n".join(_source_credit_lines(clips)) + "\n\n") if clips else "")
        + f"댓글 질문: {routine.engagement_question}\n\n"
        "#shorts #필라테스 #홈트 #운동자세 #Pilates #Workout"
    )


def write_metadata(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _refresh_metrics(records: List[Dict[str, Any]]) -> None:
    api_key = os.getenv("YOUTUBE_DATA_API_KEY", "").strip()
    if not api_key:
        return
    metrics = fetch_video_metrics(api_key, [str(item.get("video_id") or "") for item in records])
    if metrics and update_records(records, metrics):
        save_state({"version": 2, "videos": records})
        LOGGER.info("기존 영상 성과를 갱신했습니다.")


def run(dry_run: bool = False) -> Dict[str, Any]:
    missing = check_configuration(for_upload=not dry_run)
    if missing:
        raise RuntimeError("GitHub Secrets 누락: " + ", ".join(missing))

    state = load_state()
    records: List[Dict[str, Any]] = state["videos"]
    _refresh_metrics(records)

    if WORK_DIR.exists():
        resolved = WORK_DIR.resolve()
        if DATA_DIR.resolve() not in resolved.parents:
            raise RuntimeError("작업 폴더 안전 확인에 실패했습니다.")
        shutil.rmtree(WORK_DIR)
    render_dir = WORK_DIR / "render"
    render_dir.mkdir(parents=True, exist_ok=True)

    routine = select_routine(records)
    validate_routine(routine)
    LOGGER.info("선정 루틴: %s / %s", routine.title_ko, routine.title_en)
    clip_queries = build_clip_queries(routine)
    provider = StockMediaProvider()
    clips = provider.fetch_clips(
        clip_queries,
        WORK_DIR / "licensed-source",
        limit=3,
        min_required=3,
        one_per_query=True,
    )
    if len(clips) != len(routine.exercise_slugs):
        raise RuntimeError("세 동작과 실제 영상 소스의 수가 일치하지 않습니다.")
    api_key = os.getenv("YOUTUBE_DATA_API_KEY", "").strip()
    benchmarks = fetch_pilates_short_benchmarks(api_key) if api_key else []
    trend_profile = editing_profile(benchmarks)
    LOGGER.info("최근 필라테스 쇼츠 벤치마크: %d개", len(benchmarks))
    final_video = render_pilates_short(routine, render_dir, clips)
    duration = media_duration(final_video)
    audio_metadata = json.loads((render_dir / "audio_metadata.json").read_text(encoding="utf-8"))
    caption_metadata = json.loads((render_dir / "caption_metadata.json").read_text(encoding="utf-8"))
    visual_metadata = json.loads((render_dir / "visual_metadata.json").read_text(encoding="utf-8"))
    exercises = routine_exercises(routine)
    metadata: Dict[str, Any] = {
        "content_format": "pilates-real-video-v1",
        "routine_id": routine.routine_id,
        "topic": routine.title_ko,
        "title": build_title(routine),
        "instructor": {
            "id": f"{INSTRUCTOR_ID}-voice",
            "name_ko": INSTRUCTOR_NAME_KO,
            "name_en": INSTRUCTOR_NAME_EN,
            "identity_locked": False,
            "adult_age": 25,
            "synthetic_voice": True,
            "real_human_footage": True,
        },
        "exercises": [
            {
                "slug": item.slug,
                "name_ko": item.name_ko,
                "name_en": item.name_en,
                "prescription_ko": item.prescription_ko,
                "prescription_en": item.prescription_en,
                "cue_ko": item.cue_ko,
                "cue_en": item.cue_en,
                "equipment": item.equipment,
                "source_provider": clip.provider,
                "source_creator": clip.creator,
                "source_url": clip.source_url,
                "source_id": clip.source_id,
                "search_query": clip.query,
                "camera_angle": item.camera_angle,
                "muscle_focus": item.muscle_focus,
            }
            for item, clip in zip(exercises, clips)
        ],
        "narration": build_narration(routine),
        "engagement_comment": build_engagement_comment(routine),
        "duration_seconds": round(duration, 2),
        "audio": audio_metadata,
        "captions": caption_metadata,
        "visuals": visual_metadata,
        "source_requirements": list(SOURCE_REQUIREMENTS),
        "trend_profile": trend_profile,
        "trend_benchmarks": benchmarks[:5],
        "safety": {"medical_claims": False, "stop_on_pain": True, "beginner_intensity": True},
        "tags": ["필라테스", "홈트", "운동자세", "Pilates", "Workout", "FormTips"],
        "dry_run": dry_run,
    }
    write_metadata(WORK_DIR / "metadata.json", metadata)

    if dry_run:
        LOGGER.info("건식 실행 완료: 업로드하지 않았습니다.")
        return metadata

    from youtube_uploader import YouTubeUploader

    uploader = YouTubeUploader()
    result = uploader.upload_video(
        final_video,
        title=f"{build_title(routine)} #shorts",
        description=build_description(routine, clips),
        tags=["shorts", "필라테스", "홈트", "운동자세", "Pilates", "Workout", "FormTips"],
        privacy=os.getenv("YOUTUBE_PRIVACY", "public"),
        category_id="26",
    )
    record = {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "content_format": "pilates-real-video-v1",
        "routine_id": routine.routine_id,
        "topic": routine.title_ko,
        "title": build_title(routine),
        "instructor_id": f"{INSTRUCTOR_ID}-voice",
        "video_id": result["video_id"],
        "video_url": result["video_url"],
        "exercise_slugs": list(routine.exercise_slugs),
        "source_ids": [clip.source_id for clip in clips],
        "engagement_comment": build_engagement_comment(routine),
        "metrics": {"views": 0, "likes": 0, "comments": 0},
    }
    records.append(record)
    state["version"] = 2
    state["videos"] = records[-365:]
    save_state(state)
    completed = {**metadata, **result, "dry_run": False}
    write_metadata(WORK_DIR / "metadata.json", completed)
    send_notification(
        f"[하나 필라테스] 업로드 완료 - {routine.title_ko}",
        f"영상: {result['video_url']}\n\n고정 댓글 추천 문구:\n{build_engagement_comment(routine)}",
    )
    return completed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="하나 필라테스 쇼츠 자동화")
    parser.add_argument("--dry-run", action="store_true", help="영상만 만들고 업로드하지 않음")
    parser.add_argument("--check-config", action="store_true", help="필수 설정 이름만 점검")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check_config:
            missing = check_configuration(for_upload=not args.dry_run)
            if missing:
                raise RuntimeError("GitHub Secrets 누락: " + ", ".join(missing))
            LOGGER.info("필수 설정 확인 완료")
            return 0
        result = run(dry_run=args.dry_run)
        LOGGER.info("작업 완료: %s", result.get("video_url", "건식 실행"))
        return 0
    except Exception as exc:
        LOGGER.exception("자동화 실패: %s", exc)
        send_notification("[하나 필라테스] 자동화 실패", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
