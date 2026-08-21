"""실제 필라테스 영상 검색어와 근육 클로즈업 구도를 정의한다."""

from datetime import date
from typing import Any, Dict, Iterable, List, Tuple

from pilates_catalog import ROUTINES, Routine, routine_exercises


EXERCISE_VIDEO_SEARCH: Dict[str, str] = {
    "dead-bug": "woman lying dead bug exercise arms legs yoga mat",
    "glute-bridge": "woman glute bridge workout yoga mat fitted activewear",
    "bird-dog": "woman side plank leg reach exercise mat",
    "side-leg-lift": "woman side lying leg lift exercise stacked hips mat",
    "spine-twist": "woman seated pilates twist studio",
    "ring-side-bend": "woman pilates ring exercise studio",
    "modified-plank": "woman forearm plank side view exercise mat",
    "kneeling-push-up": "woman kneeling push up side view exercise mat",
    "inner-thigh-lift": "woman side lying inner thigh leg lift exercise mat",
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

# 무료 스톡 검색에서 비교적 반복 확보가 가능한 맨몸 동작 중심 루틴이다.
# 링·세부 회전처럼 검색 결과 오차가 큰 루틴은 자동 공개 대상에서 제외한다.
REAL_VIDEO_ROUTINE_IDS: Tuple[str, ...] = (
    "no-jump",
    "morning-core",
    "beginner-core",
    "upper-body-core",
)

# 화면표로 초·중·후반을 사람이 직접 확인한 공개 Pexels 소스다.
# API 검색 결과에 남아 있는 동안 우선 사용하며, 사라지면 일반 검색과 AI 검수로 돌아간다.
PREFERRED_SOURCE_IDS: Dict[str, Tuple[str, ...]] = {
    "bird-dog": ("6437919",),
    "glute-bridge": ("6525525",),
    "modified-plank": ("7589753",),
}


def build_clip_queries(routine: Routine) -> List[str]:
    """각 동작마다 한 개의 구체적인 실제 영상 검색어를 만든다."""
    return [EXERCISE_VIDEO_SEARCH[item.slug] for item in routine_exercises(routine)]


def closeup_focus_y(exercise_slug: str) -> float:
    return MUSCLE_CLOSEUP_Y.get(exercise_slug, 0.52)


def real_video_routine_candidates(
    records: Iterable[Dict[str, Any]], today: date | None = None, limit: int = 3
) -> List[Routine]:
    """최근 반복을 피하면서, 검수 실패 시 시도할 무료 실제 영상 루틴을 정한다."""
    recent = {str(item.get("routine_id") or "") for item in list(records)[-5:]}
    by_id = {item.routine_id: item for item in ROUTINES}
    supported = [by_id[routine_id] for routine_id in REAL_VIDEO_ROUTINE_IDS]
    available = [item for item in supported if item.routine_id not in recent] or supported
    return available[: max(1, limit)]
