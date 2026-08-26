"""검증을 마친 GitHub Actions 미리보기 영상을 그대로 YouTube에 공개한다."""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "published_topics.json"
LOGGER = logging.getLogger("publish-preview")


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
            "This edit uses human-reviewed, licensed Pexels footage featuring the same "
            "adult Pilates model. Full-body form views and targeted close-ups preserve "
            "the original movement, wardrobe, and body appearance.\n"
            "English AI voiceover and English on-screen captions. No background music.\n\n"
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


def publish_preview(preview_dir: Path) -> Dict[str, Any]:
    preview_dir = resolve_preview_dir(preview_dir)
    metadata_path = preview_dir / "metadata.json"
    video_path = preview_dir / "render" / "final_short.mp4"

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    preview_run_id = os.getenv("PREVIEW_RUN_ID", "")
    state = load_state()
    records = state.setdefault("videos", [])
    for record in records:
        if preview_run_id and record.get("preview_run_id") == preview_run_id:
            LOGGER.info("이미 공개한 테스트 영상입니다: %s", record.get("video_url", ""))
            return record

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
        category_id="26" if str(metadata.get("content_format") or "").startswith("pilates-") else "27",
    )

    record = {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "topic": metadata.get("topic", ""),
        "title": metadata.get("title", ""),
        "content_format": metadata.get("content_format", ""),
        "routine_id": metadata.get("routine_id", ""),
        "exercise_slugs": [item.get("slug", "") for item in metadata.get("exercises") or []],
        "source_ids": [item.get("source_id", "") for item in metadata.get("exercises") or []],
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
