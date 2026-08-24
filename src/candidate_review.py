"""무료 실제 영상 후보를 업로드 없이 화면표로 만들어 사람이 검수할 수 있게 한다."""

import json
import shutil
import subprocess
from pathlib import Path

from media_provider import StockMediaProvider
from pilates_catalog import EXERCISES
from pilates_video_strategy import EXERCISE_VIDEO_SEARCH
from visual_quality import extract_review_frames


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "candidate-review"
CANDIDATES_PER_QUERY = 2

# 예약 실행에서 반복적으로 확보하지 못한 동작을 여러 검색 표현으로 찾는다.
# 파일은 공개하지 않고 화면표만 남겨 사람이 자세를 확인한다.
SEARCH_VARIANTS = {
    "dead-bug": (
        EXERCISE_VIDEO_SEARCH["dead-bug"],
        "woman dead bug core workout on back",
        "woman alternating arm leg exercise lying on mat",
        "woman tabletop toe taps core exercise",
    ),
    "kneeling-push-up": (
        EXERCISE_VIDEO_SEARCH["kneeling-push-up"],
        "woman knee push ups workout mat",
        "woman modified push up knees on floor",
        "woman beginner push up on knees side view",
    ),
}


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
    report = {"scope": "scheduled-failure-recovery", "exercises": []}
    for slug, queries in SEARCH_VARIANTS.items():
        exercise = EXERCISES[slug]
        exercise_dir = OUTPUT_DIR / exercise.slug
        exercise_dir.mkdir(parents=True)
        rows = []
        seen = set()
        for query_index, query in enumerate(queries, start=1):
            candidates = provider.search_candidates(query)[:CANDIDATES_PER_QUERY]
            for rank, candidate in enumerate(candidates, start=1):
                identity = (candidate.get("provider"), candidate.get("source_id"))
                if identity in seen:
                    continue
                seen.add(identity)
                label = f"q{query_index}-r{rank}"
                try:
                    clip = provider._download(candidate, exercise_dir / f"candidate-{label}.mp4")
                    frames = extract_review_frames(clip, exercise_dir / f"frames-{label}")
                    sheet = exercise_dir / f"candidate-{label}-{clip.provider}-{clip.source_id}.jpg"
                    _sheet(frames, sheet)
                    clip.path.unlink(missing_ok=True)
                    rows.append(
                        {
                            "query_rank": query_index,
                            "candidate_rank": rank,
                            "provider": clip.provider,
                            "source_id": clip.source_id,
                            "source_url": clip.source_url,
                            "creator": clip.creator,
                            "query": query,
                            "sheet": sheet.relative_to(OUTPUT_DIR).as_posix(),
                        }
                    )
                except Exception as exc:
                    rows.append({"query_rank": query_index, "candidate_rank": rank, "error": str(exc)})
        report["exercises"].append(
            {"slug": exercise.slug, "name_en": exercise.name_en, "candidates": rows}
        )
    (OUTPUT_DIR / "candidates.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
