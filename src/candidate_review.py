"""무료 실제 영상 후보를 업로드 없이 화면표로 만들어 사람이 검수할 수 있게 한다."""

import json
import shutil
import subprocess
from pathlib import Path

from media_provider import StockMediaProvider
from pilates_catalog import ROUTINES, routine_exercises
from pilates_video_strategy import build_clip_queries
from visual_quality import extract_review_frames


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "candidate-review"
CANDIDATES_PER_EXERCISE = 3


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
    routine = next(item for item in ROUTINES if item.routine_id == "no-jump")
    provider = StockMediaProvider()
    report = {"routine_id": routine.routine_id, "exercises": []}
    for exercise, query in zip(routine_exercises(routine), build_clip_queries(routine)):
        exercise_dir = OUTPUT_DIR / exercise.slug
        exercise_dir.mkdir(parents=True)
        candidates = provider.search_candidates(query)[:CANDIDATES_PER_EXERCISE]
        rows = []
        for rank, candidate in enumerate(candidates, start=1):
            try:
                clip = provider._download(candidate, exercise_dir / f"candidate-{rank}.mp4")
                frames = extract_review_frames(clip, exercise_dir / f"frames-{rank}")
                sheet = exercise_dir / f"candidate-{rank}-{clip.provider}-{clip.source_id}.jpg"
                _sheet(frames, sheet)
                clip.path.unlink(missing_ok=True)
                rows.append(
                    {
                        "rank": rank,
                        "provider": clip.provider,
                        "source_id": clip.source_id,
                        "source_url": clip.source_url,
                        "creator": clip.creator,
                        "query": query,
                        "sheet": sheet.relative_to(OUTPUT_DIR).as_posix(),
                    }
                )
            except Exception as exc:
                rows.append({"rank": rank, "error": str(exc)})
        report["exercises"].append(
            {"slug": exercise.slug, "name_en": exercise.name_en, "candidates": rows}
        )
    (OUTPUT_DIR / "candidates.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
