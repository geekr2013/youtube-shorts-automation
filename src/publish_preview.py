"""검증을 마친 GitHub Actions 미리보기 영상을 그대로 YouTube에 공개한다."""

import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from pilates_catalog import ROUTINES, routine_exercises
from pilates_video_strategy import (
    FIXED_CONTENT_FORMAT,
    FIXED_LICENSE_NAME,
    FIXED_LICENSE_URL,
    FIXED_MODEL_CREATOR,
    FIXED_MODEL_ID,
    FIXED_MODEL_PROVIDER,
    FIXED_MODEL_SOURCES,
    FIXED_SOURCE_DETAILS,
    REAL_VIDEO_ROUTINE_IDS,
    is_fixed_model_source,
    require_requested_production_model,
)
from source_ledger import load_used_source_ids, save_used_source_ids

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "published_topics.json"
LOGGER = logging.getLogger("publish-preview")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_preview_description(metadata: Dict[str, Any]) -> str:
    if str(metadata.get("content_format") or "").startswith("pilates-"):
        exercises = metadata.get("exercises") or []
        lines = [
            f"{index:02d} — {str(item.get('name_en', '')).title()} · {item.get('prescription_en', '')}"
            for index, item in enumerate(exercises, start=1)
        ]
        engagement = str(metadata.get("engagement_comment") or "").strip()
        credits = [
            f"- {item.get('source_provider', 'Footage')}: {item.get('source_creator', '')} — {item.get('source_url', '')}"
            for item in exercises
            if item.get("source_url")
        ]
        return (
            f"{metadata.get('title', 'HANA Pilates')}\n\n"
            + "\n".join(lines)
            + "\n\nMove slowly, keep breathing, and stay within a comfortable range. "
            "Stop if you feel pain, dizziness, or discomfort. Consult a qualified "
            "professional when personal health circumstances require it.\n\n"
            f"This edit uses human-reviewed footage under the {FIXED_LICENSE_NAME}. The same "
            "primary adult workout participant remains the focus across one reviewed production batch. "
            "Orientation views and "
            "targeted close-ups preserve "
            "the original movement, wardrobe, and body appearance.\n"
            "HANA is the guide voice and editorial persona; the footage participant does not "
            "endorse this channel.\n"
            "English AI voiceover and English on-screen captions. No background music.\n\n"
            f"Footage license: {FIXED_LICENSE_URL}\n\n"
            + (("Footage credits\n" + "\n".join(credits) + "\n\n") if credits else "")
            + (f"{engagement}\n\n" if engagement else "")
            + "#Shorts #Pilates #PilatesWorkout #HomeWorkout #Mobility"
        )
    source = metadata.get("source") or {}
    credits = []
    seen = set()
    for asset in metadata.get("stock_assets") or []:
        url = str(asset.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        creator = str(asset.get("creator") or "").strip()
        label = str(asset.get("provider") or "영상 자료").strip()
        credits.append(f"- {label}{f' / {creator}' if creator else ''}: {url}")

    tags = [str(tag).replace("#", "").strip() for tag in metadata.get("tags") or []]
    hashtags = " ".join(f"#{tag.replace(' ', '')}" for tag in tags[:5] if tag)
    engagement = str(metadata.get("engagement_comment") or "").strip()
    return (
        f"{metadata.get('title', '한입지식')}의 원리를 1분 안에 알아봅니다.\n\n"
        f"검증 자료: {source.get('title', '')}\n{source.get('url', '')}\n"
        f"위키백과 텍스트 라이선스: {source.get('license', 'CC BY-SA 4.0')}\n\n"
        "영상 자료 출처(각 제공처 라이선스 적용):\n"
        + "\n".join(credits)
        + "\n\nAI 도구를 주제 정리, 대본 작성 보조, 내레이션 제작에 사용했습니다. "
        "청취를 방해하는 합성 배경음 없이 내레이션 중심으로 제작했습니다.\n\n"
        + (f"{engagement}\n\n" if engagement else "")
        + f"#shorts #지식쇼츠 {hashtags}"
    )


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {"version": 1, "videos": []}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def resolve_preview_dir(preview_dir: Path) -> Path:
    """Find the artifact root regardless of GitHub's preserved upload prefix."""
    candidates = [preview_dir, preview_dir / "work"]
    if preview_dir.exists():
        candidates.extend(path.parent for path in preview_dir.rglob("metadata.json"))

    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if (
            (candidate / "metadata.json").is_file()
            and (candidate / "render" / "final_short.mp4").is_file()
        ):
            return candidate
    raise FileNotFoundError("검증 영상 또는 메타데이터를 찾지 못했습니다.")


def validate_active_model_preview(metadata: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Fail closed unless the artifact belongs to the active reviewed model generation."""
    if metadata.get("content_format") != FIXED_CONTENT_FORMAT:
        raise ValueError("현재 고정 모델 형식의 검증 영상이 아닙니다.")
    if metadata.get("dry_run") is not True:
        raise ValueError("건식 실행으로 생성한 검증 영상만 공개할 수 있습니다.")
    if metadata.get("content_language") != "en" or metadata.get("target_market") != "US/global":
        raise ValueError("영어·미국/글로벌용 검증 영상이 아닙니다.")
    instructor = metadata.get("instructor") or {}
    if (
        instructor.get("identity_locked") is not True
        or instructor.get("adult_confirmed") is not True
        or instructor.get("visual_model_id") != FIXED_MODEL_ID
        or instructor.get("visual_source_provider") != FIXED_MODEL_PROVIDER
        or instructor.get("visual_source_creator") != FIXED_MODEL_CREATOR
    ):
        raise ValueError("현재 고정 모델의 신원 정보가 일치하지 않습니다.")

    exercises = metadata.get("exercises") or []
    if len(exercises) != 3:
        raise ValueError("정확히 세 동작으로 검수한 영상만 공개할 수 있습니다.")
    slugs = [str(item.get("slug") or "") for item in exercises]
    source_ids = [str(item.get("source_id") or "") for item in exercises]
    if any(not value for value in slugs) or len(set(slugs)) != 3:
        raise ValueError("동작 정보가 없거나 중복되었습니다.")
    if any(not value for value in source_ids) or len(set(source_ids)) != 3:
        raise ValueError("원본 영상 정보가 없거나 중복되었습니다.")
    routine_id = str(metadata.get("routine_id") or "")
    routine_by_id = {item.routine_id: item for item in ROUTINES}
    if routine_id not in REAL_VIDEO_ROUTINE_IDS:
        raise ValueError("현재 공개 승인된 루틴이 아닙니다.")
    expected_slugs = [item.slug for item in routine_exercises(routine_by_id[routine_id])]
    if slugs != expected_slugs:
        raise ValueError("검수한 루틴의 동작 순서와 일치하지 않습니다.")

    for item, slug, source_id in zip(exercises, slugs, source_ids):
        provider = str(item.get("source_provider") or "")
        creator = str(item.get("source_creator") or "")
        source_url = str(item.get("source_url") or "")
        source = FIXED_SOURCE_DETAILS.get(slug) or {}
        quality = item.get("visual_quality") or {}
        if (
            FIXED_MODEL_SOURCES.get(slug) != source_id
            or not is_fixed_model_source(slug, provider, source_id, creator)
            or source_url != str(source.get("source_url") or "")
            or str(item.get("source_download_url") or "") != str(source.get("download_url") or "")
            or str(item.get("source_sha256") or "") != str(source.get("sha256") or "")
            or int(item.get("source_width") or 0) != int(source.get("width") or 0)
            or int(item.get("source_height") or 0) != int(source.get("height") or 0)
            or abs(float(item.get("source_duration_seconds") or 0) - float(source.get("duration_seconds") or 0)) > 0.001
            or str(item.get("full_view_mode") or "fill") != str(source.get("full_view_mode") or "fill")
            or str(item.get("close_view_mode") or "fill") != str(source.get("close_view_mode") or "fill")
            or quality.get("passed") is not True
            or quality.get("approved") is not True
            or quality.get("joint_context") is not True
            or quality.get("sexualized_framing") is not False
            or quality.get("adult_confirmed") is not True
            or not str(quality.get("reason") or "").strip()
            or quality.get("identity_locked") is not True
            or quality.get("identity_id") != FIXED_MODEL_ID
        ):
            raise ValueError(f"검수된 고정 모델 원본과 일치하지 않습니다: {slug}")
    return exercises


def publish_preview(preview_dir: Path) -> Dict[str, Any]:
    preview_dir = resolve_preview_dir(preview_dir)
    metadata_path = preview_dir / "metadata.json"
    video_path = preview_dir / "render" / "final_short.mp4"

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    exercises = validate_active_model_preview(metadata)
    expected_video_sha256 = str(metadata.get("video_sha256") or "")
    if len(expected_video_sha256) != 64 or file_sha256(video_path) != expected_video_sha256:
        raise ValueError("검수한 최종 영상 파일의 SHA-256과 일치하지 않습니다.")
    require_requested_production_model()
    preview_run_id = os.getenv("PREVIEW_RUN_ID", "")
    if not preview_run_id.isdigit():
        raise ValueError("검증 실행 번호가 없거나 올바르지 않습니다.")
    state = load_state()
    records = state.setdefault("videos", [])
    for record in records:
        if preview_run_id and record.get("preview_run_id") == preview_run_id:
            LOGGER.info("이미 공개한 테스트 영상입니다: %s", record.get("video_url", ""))
            return record
    source_ids = [str(item.get("source_id") or "") for item in exercises]
    if set(source_ids).intersection(load_used_source_ids(records)):
        raise ValueError("영구 원본 장부에 이미 사용한 원본이 포함되어 있습니다.")
    for record in records:
        is_fixed_generation = str(record.get("content_format") or "").startswith(
            "pilates-fixed-model-real-video-"
        )
        if is_fixed_generation and record.get("routine_id") == metadata.get("routine_id"):
            raise ValueError("이미 공개한 현재 모델 루틴입니다.")
        if set(source_ids).intersection(str(item) for item in record.get("source_ids") or []):
            raise ValueError("과거 공개 영상에서 이미 사용한 원본이 포함되어 있습니다.")

    from notifier import send_notification
    from youtube_uploader import YouTubeUploader

    uploader = YouTubeUploader()
    public_tags = list(dict.fromkeys(["shorts", *metadata.get("tags", [])]))
    result = uploader.upload_video(
        video_path,
        title=f"{metadata['title']} #shorts",
        description=build_preview_description(metadata),
        tags=public_tags,
        privacy="public",
        category_id="26",
    )

    record = {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "topic": metadata.get("topic", ""),
        "title": metadata.get("title", ""),
        "content_format": metadata.get("content_format", ""),
        "visual_model_id": FIXED_MODEL_ID,
        "visual_source_provider": FIXED_MODEL_PROVIDER,
        "visual_source_creator": FIXED_MODEL_CREATOR,
        "routine_id": metadata.get("routine_id", ""),
        "exercise_slugs": [item.get("slug", "") for item in exercises],
        "source_ids": source_ids,
        "sources": [
            {
                "source_id": item.get("source_id", ""),
                "provider": item.get("source_provider", ""),
                "creator": item.get("source_creator", ""),
                "source_url": item.get("source_url", ""),
                "sha256": item.get("source_sha256", ""),
                "width": item.get("source_width", 0),
                "height": item.get("source_height", 0),
                "duration_seconds": item.get("source_duration_seconds", 0),
            }
            for item in exercises
        ],
        "instructor_id": (metadata.get("instructor") or {}).get("id", ""),
        "video_id": result["video_id"],
        "video_url": result["video_url"],
        "source_url": (metadata.get("source") or {}).get("url", ""),
        "asset_urls": [
            asset.get("url", "") for asset in metadata.get("stock_assets") or []
        ],
        "engagement_comment": metadata.get("engagement_comment", ""),
        "preview_run_id": preview_run_id,
        "metrics": {"views": 0, "likes": 0, "comments": 0},
    }
    records.append(record)
    save_used_source_ids(load_used_source_ids(records) | set(source_ids))
    state["videos"] = records[-365:]
    save_state(state)

    completed = {**metadata, **result, "dry_run": False}
    metadata_path.write_text(
        json.dumps(completed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    send_notification(
        f"[Shorts] Preview published — {metadata.get('title', '')}",
        f"Video: {result['video_url']}\n\n"
        f"Suggested pinned comment:\n{metadata.get('engagement_comment', '')}",
    )
    return completed


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    preview_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "preview-promotion"
    try:
        result = publish_preview(preview_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception:
        LOGGER.exception("테스트 영상 공개 실패")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
