"""실제 필라테스 영상 검색어와 근육 클로즈업 구도를 정의한다."""

from typing import Dict, List, Tuple

from pilates_catalog import Routine, routine_exercises


EXERCISE_VIDEO_SEARCH: Dict[str, str] = {
    "dead-bug": "woman dead bug core workout yoga mat fitted activewear",
    "glute-bridge": "woman glute bridge workout yoga mat fitted activewear",
    "bird-dog": "woman bird dog core workout yoga mat",
    "side-leg-lift": "woman side leg lift pilates workout",
    "spine-twist": "woman seated pilates twist studio",
    "ring-side-bend": "woman pilates ring exercise studio",
    "modified-plank": "woman knee plank workout yoga mat",
    "kneeling-push-up": "woman kneeling push up workout mat",
    "inner-thigh-lift": "woman inner thigh leg lift pilates",
}

# 0은 상체, 1은 하체 쪽으로 확대 중심을 이동한다.
MUSCLE_CLOSEUP_Y: Dict[str, float] = {
    "dead-bug": 0.48,
    "glute-bridge": 0.62,
    "bird-dog": 0.55,
    "side-leg-lift": 0.66,
    "spine-twist": 0.34,
    "ring-side-bend": 0.38,
    "modified-plank": 0.48,
    "kneeling-push-up": 0.34,
    "inner-thigh-lift": 0.69,
}

SOURCE_REQUIREMENTS: Tuple[str, ...] = (
    "real continuous human movement",
    "professional fitted activewear",
    "uncluttered workout area",
    "major joints and target muscle line visible",
    "no medical or body-transformation claim",
)


def build_clip_queries(routine: Routine) -> List[str]:
    """각 동작마다 한 개의 구체적인 실제 영상 검색어를 만든다."""
    return [EXERCISE_VIDEO_SEARCH[item.slug] for item in routine_exercises(routine)]


def closeup_focus_y(exercise_slug: str) -> float:
    return MUSCLE_CLOSEUP_Y.get(exercise_slug, 0.52)
