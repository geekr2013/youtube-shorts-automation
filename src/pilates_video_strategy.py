"""실제 필라테스 영상 검색어와 검수된 고정 세션을 정의한다."""

import json
from datetime import date
from pathlib import Path
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
    "reformer-leg-press": "woman reformer leg press pilates foot straps",
    "reformer-single-leg-control": "woman reformer single leg control pilates",
    "reformer-double-leg-extension": "woman reformer double leg extension pilates",
    "reformer-knee-fold-press": "woman reformer knee fold press pilates",
    "reformer-chest-lift": "woman reformer chest lift pilates",
    "reformer-strap-crunch": "woman reformer strap crunch pilates",
    "reformer-knee-stretch": "woman reformer knee stretch pilates side view",
    "reformer-long-stretch": "woman reformer long stretch plank pilates",
    "seated-reformer-stretch": "woman seated reformer stretch pilates",
    "standing-arm-open": "woman standing pilates arm opening exercise",
    "standing-side-shift": "woman standing pilates side shift exercise",
    "standing-leg-press": "woman standing reformer leg press pilates",
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
    "reformer-leg-press": 0.58,
    "reformer-single-leg-control": 0.60,
    "reformer-double-leg-extension": 0.60,
    "reformer-knee-fold-press": 0.58,
    "reformer-chest-lift": 0.46,
    "reformer-strap-crunch": 0.48,
    "reformer-knee-stretch": 0.50,
    "reformer-long-stretch": 0.48,
    "seated-reformer-stretch": 0.40,
    "standing-arm-open": 0.42,
    "standing-side-shift": 0.54,
    "standing-leg-press": 0.66,
}

SOURCE_REQUIREMENTS: Tuple[str, ...] = (
    "real continuous human movement",
    "professional fitted crop activewear with the abdomen line unobstructed",
    "uncluttered workout area",
    "major joints and target muscle line visible",
    "no medical or body-transformation claim",
)

# 같은 실제 성인 주 시연자가 등장하고 개별 Free License가 확인된 세 루틴만 공개한다.
REAL_VIDEO_ROUTINE_IDS: Tuple[str, ...] = (
    "hana-supine-reformer-core",
    "hana-standing-reformer-flow",
    "hana-reformer-core-series",
)

ROOT = Path(__file__).resolve().parents[1]
FIXED_SOURCE_MANIFEST_PATH = (
    ROOT / "assets" / "instructor" / "mixkit-sports-center-peach-v1.json"
)
FIXED_SOURCE_MANIFEST: Dict[str, Any] = json.loads(
    FIXED_SOURCE_MANIFEST_PATH.read_text(encoding="utf-8")
)
FIXED_MODEL_ID = str(FIXED_SOURCE_MANIFEST["model_id"])
FIXED_MODEL_PROVIDER = str(FIXED_SOURCE_MANIFEST["provider"])
FIXED_MODEL_CREATOR = str(FIXED_SOURCE_MANIFEST["creator"])
FIXED_CONTENT_FORMAT = str(FIXED_SOURCE_MANIFEST["content_format"])
FIXED_LICENSE_NAME = str(FIXED_SOURCE_MANIFEST["license"]["name"])
FIXED_LICENSE_URL = str(FIXED_SOURCE_MANIFEST["license"]["url"])
REQUESTED_PRODUCTION_MODEL_ID = "mixkit-sports-center-peach-v1"
FIXED_SOURCE_DETAILS: Dict[str, Dict[str, Any]] = {
    str(slug): dict(details)
    for slug, details in FIXED_SOURCE_MANIFEST["sources"].items()
}
FIXED_MODEL_SOURCES: Dict[str, str] = {
    slug: str(details["source_id"]) for slug, details in FIXED_SOURCE_DETAILS.items()
}

# 각 항목 페이지의 Free License 문구와 초·중·후반 실제 동작을 2026-08-31에 확인했다.
PREFERRED_SOURCE_IDS: Dict[str, Tuple[str, ...]] = {
    slug: (source_id,) for slug, source_id in FIXED_MODEL_SOURCES.items()
}


def production_model_ready() -> bool:
    """Return true only when every public source and its commercial license are locked."""
    license_record = FIXED_SOURCE_MANIFEST.get("license") or {}
    sources_ready = bool(FIXED_SOURCE_DETAILS) and all(
        details.get("public_approved") is True
        and bool(str(details.get("review_notes") or "").strip())
        and len(str(details.get("sha256") or "")) == 64
        for details in FIXED_SOURCE_DETAILS.values()
    )
    return (
        FIXED_MODEL_ID == REQUESTED_PRODUCTION_MODEL_ID
        and license_record.get("commercial_youtube_allowed") is True
        and sources_ready
    )


def require_requested_production_model() -> None:
    """Block every public path if the approved filmed session is disconnected."""
    if production_model_ready():
        return
    raise RuntimeError(
        "Public upload blocked: the approved Mixkit motion model is not connected. "
        f"Current footage model is {FIXED_MODEL_ID}."
    )


def is_human_reviewed_source(exercise_slug: str, provider: str, source_id: str) -> bool:
    """Return true only for an exact public source checked from three sampled frames."""
    details = FIXED_SOURCE_DETAILS.get(exercise_slug) or {}
    return (
        provider == FIXED_MODEL_PROVIDER
        and source_id in PREFERRED_SOURCE_IDS.get(exercise_slug, ())
        and details.get("public_approved") is True
        and bool(str(details.get("review_notes") or "").strip())
    )


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


def full_focus_x(exercise_slug: str) -> float:
    details = FIXED_SOURCE_DETAILS.get(exercise_slug, {})
    return min(1.0, max(0.0, float(details.get("full_focal_x", 0.5))))


def closeup_focus_x(exercise_slug: str) -> float:
    details = FIXED_SOURCE_DETAILS.get(exercise_slug, {})
    return min(1.0, max(0.0, float(details.get("closeup_focal_x", 0.5))))


def closeup_zoom(exercise_slug: str) -> float:
    details = FIXED_SOURCE_DETAILS.get(exercise_slug, {})
    return min(1.4, max(1.0, float(details.get("closeup_zoom", 1.35))))


def source_start_seconds(exercise_slug: str) -> float:
    details = FIXED_SOURCE_DETAILS.get(exercise_slug, {})
    return max(0.0, float(details.get("start_seconds", 0.7)))


def caption_panel_y(exercise_slug: str) -> int:
    """Place the compact caption card in a reviewed Shorts-safe empty region."""
    details = FIXED_SOURCE_DETAILS.get(exercise_slug, {})
    return min(1040, max(80, int(details.get("caption_y", 80))))


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
    available = [
        item
        for item in supported
        if item.routine_id not in used_routines
        and not {
            FIXED_MODEL_SOURCES.get(exercise.slug, "")
            for exercise in routine_exercises(item)
        }.intersection(used_sources)
    ]
    return available[: max(1, limit)]
