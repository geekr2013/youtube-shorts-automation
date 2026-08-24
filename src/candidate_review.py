"""무료 실제 영상 후보를 업로드 없이 화면표로 만들어 사람이 검수할 수 있게 한다."""

import json
import shutil
import subprocess
from pathlib import Path

from media_provider import StockMediaProvider
from pilates_catalog import EXERCISES
from pilates_video_strategy import (
    EXERCISE_VIDEO_SEARCH,
    FIXED_MODEL_CREATOR,
    FIXED_MODEL_ID,
    FIXED_MODEL_SOURCES,
    is_fixed_model_source,
)
from visual_quality import extract_review_frames


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "candidate-review"


def _sheet(frames, output: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("후보 화면표에 FFmpeg가 필요합니다.")
    filters = []
    for index in range(3):
        filters.append(
            f"[{index}:v]scale=360:640:force_original_aspect_ratio=decrease,"
            f"pad=360:640:(ow-iw)/2:(oh-ih)/2:black[v{index}]"
        )
    filters.append("[v0][v1][v2]hstack=inputs=3[out]")
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            *sum((["-i", str(frame)] for frame in frames), []),
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not output.exists():
        raise RuntimeError("후보 화면표 생성에 실패했습니다.")


def main() -> int:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    provider = StockMediaProvider()
    report = {
        "scope": "fixed-model-motion-review",
        "identity_locked": True,
        "identity_id": FIXED_MODEL_ID,
        "creator": FIXED_MODEL_CREATOR,
        "exercises": [],
    }
    for slug, source_id in FIXED_MODEL_SOURCES.items():
        exercise = EXERCISES[slug]
        exercise_dir = OUTPUT_DIR / exercise.slug
        exercise_dir.mkdir(parents=True)
        query = EXERCISE_VIDEO_SEARCH[slug]
        clip = provider.fetch_pexels_source(
            source_id,
            exercise_dir / f"source-{source_id}.mp4",
            query=query,
        )
        if not is_fixed_model_source(slug, clip.provider, clip.source_id, clip.creator):
            raise RuntimeError(f"고정 모델 검증 실패: {slug} / {clip.source_id} / {clip.creator}")
        frames = extract_review_frames(clip, exercise_dir / "frames")
        sheet = exercise_dir / f"{slug}-{source_id}.jpg"
        _sheet(frames, sheet)
        clip.path.unlink(missing_ok=True)
        report["exercises"].append({
            "slug": exercise.slug,
            "name_en": exercise.name_en,
            "provider": clip.provider,
            "source_id": clip.source_id,
            "source_url": clip.source_url,
            "creator": clip.creator,
            "query": query,
            "sheet": sheet.relative_to(OUTPUT_DIR).as_posix(),
        })
    (OUTPUT_DIR / "candidates.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
