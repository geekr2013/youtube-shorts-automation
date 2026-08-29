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
    "kneeling-push-up": "woman knee push ups workout mat",
    "inner-thigh-lift": "woman side lying inner thigh leg lift exercise mat",
    "plank-control": "woman forearm plank core control side view exercise mat",
    "plank-reset": "woman plank to child pose exercise mat side view",
    "knee-fold": "woman supine knee fold core exercise close up",
    "supine-leg-flow": "woman supine alternating leg core flow exercise mat",
    "single-knee-stretch": "woman single knee stretch supine exercise mat",
    "forearm-plank-flow": "woman forearm plank transition exercise mat",
    "lateral-lunge-flow": "woman lateral lunge flow exercise mat",
    "squat-reach-flow": "woman squat to overhead reach exercise",
    "standing-fold": "woman standing forward fold exercise mat",
    "cat-cow-flow": "woman cat cow flow exercise mat",
    "sun-salutation-flow": "woman sun salutation plank flow exercise mat",
    "fold-to-seat": "woman forward fold to seated stretch exercise mat",
    "standing-shoulder-open": "woman standing shoulder stretch activewear",
    "overhead-reach": "woman overhead reach mobility exercise",
    "seated-side-bend": "woman seated side bend exercise mat",
    "seated-hamstring": "woman seated hamstring stretch exercise mat",
    "seated-leg-extension": "woman seated leg extension stretch exercise mat",
    "supine-leg-stretch": "woman supine leg stretch exercise mat",
    "seated-arm-flow": "woman seated arm mobility flow exercise mat",
    "supine-knee-hug": "woman supine knee hug stretch exercise mat",
    "neck-release": "woman seated neck release stretch",
    "rear-shoulder-open": "woman standing rear shoulder stretch activewear",
    "tall-reach": "woman standing overhead reach posture exercise",
    "standing-side-reach": "woman standing side reach exercise",
    "forward-fold-flow": "woman forward fold flow exercise mat",
    "seated-forward-fold": "woman seated forward fold exercise mat",
    "side-mobility-flow": "woman side mobility stretch exercise mat",
    "hip-open-flow": "woman hip mobility flow exercise mat",
    "butterfly-stretch": "woman butterfly stretch exercise mat",
    "foot-release": "woman foot ankle mobility stretch exercise mat",
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
    "plank-control": 0.48,
    "plank-reset": 0.48,
    "knee-fold": 0.52,
    "supine-leg-flow": 0.58,
    "single-knee-stretch": 0.52,
    "forearm-plank-flow": 0.48,
    "lateral-lunge-flow": 0.64,
    "squat-reach-flow": 0.58,
    "standing-fold": 0.58,
    "cat-cow-flow": 0.50,
    "sun-salutation-flow": 0.48,
    "fold-to-seat": 0.56,
    "standing-shoulder-open": 0.36,
    "overhead-reach": 0.38,
    "seated-side-bend": 0.44,
    "seated-hamstring": 0.66,
    "seated-leg-extension": 0.60,
    "supine-leg-stretch": 0.60,
    "seated-arm-flow": 0.38,
    "supine-knee-hug": 0.56,
    "neck-release": 0.33,
    "rear-shoulder-open": 0.36,
    "tall-reach": 0.42,
    "standing-side-reach": 0.48,
    "forward-fold-flow": 0.56,
    "seated-forward-fold": 0.62,
    "side-mobility-flow": 0.58,
    "hip-open-flow": 0.62,
    "butterfly-stretch": 0.66,
    "foot-release": 0.72,
}

SOURCE_REQUIREMENTS: Tuple[str, ...] = (
    "real continuous human movement",
    "professional fitted crop activewear with the abdomen line unobstructed",
    "uncluttered workout area",
    "major joints and target muscle line visible",
    "no medical or body-transformation claim",
)

# 무료 스톡 검색에서 비교적 반복 확보가 가능한 맨몸 동작 중심 루틴이다.
# 링·세부 회전처럼 검색 결과 오차가 큰 루틴은 자동 공개 대상에서 제외한다.
REAL_VIDEO_ROUTINE_IDS: Tuple[str, ...] = (
    "fixed-plank-transition",
    "fixed-lower-body-flow",
    "fixed-spinal-flow",
    "fixed-shoulder-mobility",
    "fixed-hamstring-release",
    "fixed-gentle-recovery",
    "fixed-standing-posture",
    "fixed-beginner-flow",
    "fixed-hip-mobility",
)

FIXED_MODEL_ID = "miriam-alonso-core-v1"
FIXED_MODEL_CREATOR = "Miriam Alonso"
FIXED_CONTENT_FORMAT = "pilates-fixed-model-real-video-v2"
FIXED_MODEL_SOURCES: Dict[str, str] = {
    "modified-plank": "7589746",
    "plank-control": "7589748",
    "plank-reset": "7590458",
    "knee-fold": "7590852",
    "supine-leg-flow": "7590846",
    "single-knee-stretch": "7590845",
    "forearm-plank-flow": "7589753",
    "lateral-lunge-flow": "7590813",
    "squat-reach-flow": "7590815",
    "standing-fold": "7590814",
    "cat-cow-flow": "7590823",
    "sun-salutation-flow": "7589751",
    "fold-to-seat": "7590847",
    "standing-shoulder-open": "7590389",
    "overhead-reach": "7590390",
    "seated-side-bend": "7590404",
    "seated-hamstring": "7590424",
    "seated-leg-extension": "7590436",
    "supine-leg-stretch": "7590463",
    "seated-arm-flow": "7590406",
    "supine-knee-hug": "7590433",
    "neck-release": "7590462",
    "rear-shoulder-open": "7590456",
    "tall-reach": "7590461",
    "standing-side-reach": "7590854",
    "forward-fold-flow": "7590427",
    "seated-forward-fold": "7590455",
    "side-mobility-flow": "7589756",
    "hip-open-flow": "7590851",
    "butterfly-stretch": "7590454",
    "foot-release": "7590849",
}

# 화면표로 초·중·후반을 사람이 직접 확인한 공개 Pexels 소스다.
# API 검색 결과에 남아 있는 동안 우선 사용하며, 사라지면 일반 검색과 AI 검수로 돌아간다.
PREFERRED_SOURCE_IDS: Dict[str, Tuple[str, ...]] = {
    slug: (source_id,) for slug, source_id in FIXED_MODEL_SOURCES.items()
}


def is_human_reviewed_source(exercise_slug: str, provider: str, source_id: str) -> bool:
    """Return true only for an exact public source checked from three sampled frames."""
    return provider == "Pexels" and source_id in PREFERRED_SOURCE_IDS.get(exercise_slug, ())


def is_fixed_model_source(
    exercise_slug: str, provider: str, source_id: str, creator: str = ""
) -> bool:
    """Accept only the exact adult model/session sources reviewed from motion frames."""
    if not is_human_reviewed_source(exercise_slug, provider, source_id):
        return False
    return bool(creator.strip()) and creator.strip() == FIXED_MODEL_CREATOR


def build_clip_queries(routine: Routine) -> List[str]:
    """각 동작마다 한 개의 구체적인 실제 영상 검색어를 만든다."""
    return [EXERCISE_VIDEO_SEARCH[item.slug] for item in routine_exercises(routine)]


def closeup_focus_y(exercise_slug: str) -> float:
    return MUSCLE_CLOSEUP_Y.get(exercise_slug, 0.52)


def real_video_routine_candidates(
    records: Iterable[Dict[str, Any]], today: date | None = None, limit: int = 3
) -> List[Routine]:
    """Return only never-published routine/source sets for the locked adult model."""
    fixed_records = [
        item for item in records if str(item.get("content_format") or "") == FIXED_CONTENT_FORMAT
    ]
    used_routines = {str(item.get("routine_id") or "") for item in fixed_records}
    used_sources = {
        str(source_id)
        for item in fixed_records
        for source_id in (item.get("source_ids") or [])
        if str(source_id)
    }
    by_id = {item.routine_id: item for item in ROUTINES}
    supported = [by_id[routine_id] for routine_id in REAL_VIDEO_ROUTINE_IDS]
    day = today or date.today()
    start = day.toordinal() % len(supported)
    rotated = supported[start:] + supported[:start]
    available = [
        item
        for item in rotated
        if item.routine_id not in used_routines
        and not {
            FIXED_MODEL_SOURCES.get(exercise.slug, "")
            for exercise in routine_exercises(item)
        }.intersection(used_sources)
    ]
    return available[: max(1, limit)]
