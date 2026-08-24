"""검수된 필라테스 동작과 장기 순환용 루틴 목록."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
INSTRUCTOR_ID = "hana-v1"
INSTRUCTOR_NAME_KO = "하나"
INSTRUCTOR_NAME_EN = "HANA"
POSE_DIR = ROOT / "assets" / "instructor" / "poses"
MOTION_STILL_DIR = ROOT / "assets" / "instructor" / "motion-stills"


@dataclass(frozen=True)
class Exercise:
    slug: str
    name_ko: str
    name_en: str
    pose_file: str
    prescription_ko: str
    prescription_en: str
    cue_ko: str
    cue_en: str
    voice_ko: str
    motion_start_file: str
    motion_end_file: str
    camera_angle: str
    muscle_focus: str
    bilateral: bool = False
    equipment: str = "매트"

    @property
    def pose_path(self) -> Path:
        return (POSE_DIR / self.pose_file).resolve()

    @property
    def motion_start_path(self) -> Path:
        return MOTION_STILL_DIR / self.motion_start_file

    @property
    def motion_end_path(self) -> Path:
        return MOTION_STILL_DIR / self.motion_end_file


@dataclass(frozen=True)
class Routine:
    routine_id: str
    title_ko: str
    title_en: str
    intro_ko: str
    exercise_slugs: Tuple[str, str, str]
    engagement_question: str


EXERCISES: Dict[str, Exercise] = {
    "dead-bug": Exercise(
        slug="dead-bug",
        name_ko="데드버그",
        name_en="DEAD BUG",
        pose_file="dead-bug.jpg",
        prescription_ko="좌우 6회씩",
        prescription_en="6 EACH SIDE",
        cue_ko="허리가 뜨지 않게",
        cue_en="KEEP YOUR BACK HEAVY",
        voice_ko="허리가 뜨지 않게, 내쉬며 좌우 여섯 번씩 움직여요.",
        motion_start_file="dead-bug-start.png",
        motion_end_file="dead-bug-extend.png",
        camera_angle="overhead",
        muscle_focus="복부·고관절·대퇴부",
        bilateral=True,
    ),
    "glute-bridge": Exercise(
        slug="glute-bridge",
        name_ko="브릿지",
        name_en="GLUTE BRIDGE",
        pose_file="glute-bridge.jpg",
        prescription_ko="8회",
        prescription_en="8 REPS",
        cue_ko="무릎은 나란히 유지",
        cue_en="KEEP KNEES PARALLEL",
        voice_ko="무릎을 나란히 두고, 내쉬며 골반을 여덟 번 들어 올려요.",
        motion_start_file="glute-bridge-down.png",
        motion_end_file="glute-bridge-up.png",
        camera_angle="side-three-quarter",
        muscle_focus="복부·둔근·햄스트링",
    ),
    "bird-dog": Exercise(
        slug="bird-dog",
        name_ko="사이드 플랭크 플로우",
        name_en="SIDE PLANK FLOW",
        pose_file="bird-dog.jpg",
        prescription_ko="좌우 5회씩",
        prescription_en="5 EACH SIDE",
        cue_ko="지지 손목 아래 어깨",
        cue_en="SHOULDER OVER WRIST",
        voice_ko="지지 손목 아래에 어깨를 두고, 옆구리 힘으로 좌우 다섯 번씩 천천히 움직여요.",
        motion_start_file="bird-dog-start.png",
        motion_end_file="bird-dog-extend.png",
        camera_angle="side-three-quarter",
        muscle_focus="복부·복사근·둔근·어깨",
        bilateral=True,
    ),
    "side-leg-lift": Exercise(
        slug="side-leg-lift",
        name_ko="사이드 레그 리프트",
        name_en="SIDE LEG LIFT",
        pose_file="side-leg-lift.jpg",
        prescription_ko="좌우 8회씩",
        prescription_en="8 EACH SIDE",
        cue_ko="골반은 포개서 고정",
        cue_en="STACK YOUR HIPS",
        voice_ko="골반을 포개어 고정하고, 위쪽 다리를 좌우 여덟 번씩 들어요.",
        motion_start_file="side-leg-lift-down.png",
        motion_end_file="side-leg-lift-up.png",
        camera_angle="side-full-body",
        muscle_focus="옆구리·중둔근·외측 대퇴부",
        bilateral=True,
    ),
    "spine-twist": Exercise(
        slug="spine-twist",
        name_ko="스파인 트위스트",
        name_en="SPINE TWIST",
        pose_file="spine-twist.jpg",
        prescription_ko="좌우 5회씩",
        prescription_en="5 EACH SIDE",
        cue_ko="허리를 길게 세우기",
        cue_en="SIT TALL",
        voice_ko="허리를 길게 세우고, 내쉬며 상체를 좌우 다섯 번씩 돌려요.",
        motion_start_file="spine-twist-center.png",
        motion_end_file="spine-twist-right.png",
        camera_angle="front-three-quarter",
        muscle_focus="복부·복사근·흉곽",
        bilateral=True,
    ),
    "ring-side-bend": Exercise(
        slug="ring-side-bend",
        name_ko="링 사이드 밴드",
        name_en="RING SIDE BEND",
        pose_file="ring-side-bend.jpg",
        prescription_ko="좌우 5회씩",
        prescription_en="5 EACH SIDE",
        cue_ko="골반은 가운데 고정",
        cue_en="KEEP HIPS CENTERED",
        voice_ko="링을 머리 위로 들고, 골반을 가운데 둔 채 좌우 다섯 번씩 기울여요.",
        motion_start_file="ring-side-center.png",
        motion_end_file="ring-side-bend.png",
        camera_angle="front-alignment",
        muscle_focus="복부·복사근·골반",
        bilateral=True,
        equipment="필라테스 링",
    ),
    "modified-plank": Exercise(
        slug="modified-plank",
        name_ko="포어암 플랭크",
        name_en="FOREARM PLANK",
        pose_file="modified-plank.jpg",
        prescription_ko="20초",
        prescription_en="20 SECONDS",
        cue_ko="머리부터 발뒤꿈치까지 길게",
        cue_en="HEAD TO HEELS IN ONE LINE",
        voice_ko="어깨 아래에 팔꿈치를 두고, 머리부터 발뒤꿈치까지 길게 스무 초 버텨요.",
        motion_start_file="modified-plank-prep.png",
        motion_end_file="modified-plank-hold.png",
        camera_angle="side-three-quarter",
        muscle_focus="복부·둔근·대퇴부·어깨",
    ),
    "kneeling-push-up": Exercise(
        slug="kneeling-push-up",
        name_ko="무릎 푸시업",
        name_en="KNEELING PUSH-UP",
        pose_file="../motion-stills/kneeling-push-up-bottom.png",
        prescription_ko="6회",
        prescription_en="6 REPS",
        cue_ko="가슴과 골반을 함께 내리기",
        cue_en="LOWER CHEST AND HIPS TOGETHER",
        voice_ko="가슴과 골반이 함께 내려가도록, 팔꿈치를 뒤로 접으며 여섯 번 움직여요.",
        motion_start_file="kneeling-push-up-top.png",
        motion_end_file="kneeling-push-up-bottom.png",
        camera_angle="side-front-three-quarter",
        muscle_focus="가슴·전면 어깨·삼두근·복부",
    ),
    "inner-thigh-lift": Exercise(
        slug="inner-thigh-lift",
        name_ko="이너 타이 리프트",
        name_en="INNER THIGH LIFT",
        pose_file="../motion-stills/inner-thigh-lift-up.png",
        prescription_ko="좌우 8회씩",
        prescription_en="8 EACH SIDE",
        cue_ko="골반은 고정하고 안쪽 허벅지로",
        cue_en="LIFT FROM YOUR INNER THIGH",
        voice_ko="골반을 고정하고, 아래쪽 다리를 안쪽 허벅지 힘으로 좌우 여덟 번씩 들어요.",
        motion_start_file="inner-thigh-lift-down.png",
        motion_end_file="inner-thigh-lift-up.png",
        camera_angle="side-front-lower-body",
        muscle_focus="내전근·하복부·고관절·대퇴부",
        bilateral=True,
    ),
    "plank-control": Exercise(
        slug="plank-control",
        name_ko="플랭크 코어 컨트롤",
        name_en="PLANK CORE CONTROL",
        pose_file="modified-plank.jpg",
        prescription_ko="20초",
        prescription_en="20 SECONDS",
        cue_ko="배꼽을 당기고 골반 고정",
        cue_en="BRACE CORE AND HOLD HIPS",
        voice_ko="팔꿈치는 어깨 아래에 두고, 배꼽을 가볍게 당긴 채 스무 초 동안 호흡해요.",
        motion_start_file="modified-plank-prep.png",
        motion_end_file="modified-plank-hold.png",
        camera_angle="side-three-quarter",
        muscle_focus="복부·복사근·둔근·어깨",
    ),
    "plank-reset": Exercise(
        slug="plank-reset",
        name_ko="플랭크 리셋",
        name_en="PLANK RESET",
        pose_file="modified-plank.jpg",
        prescription_ko="5회",
        prescription_en="5 REPS",
        cue_ko="등을 길게 유지하며 뒤로",
        cue_en="KEEP YOUR SPINE LONG",
        voice_ko="플랭크에서 등을 길게 유지하며 엉덩이를 뒤로 보내고, 다섯 번 부드럽게 돌아와요.",
        motion_start_file="modified-plank-hold.png",
        motion_end_file="modified-plank-prep.png",
        camera_angle="side-three-quarter",
        muscle_focus="복부·광배근·어깨·고관절",
    ),
    "knee-fold": Exercise(
        slug="knee-fold",
        name_ko="코어 니 폴드",
        name_en="CORE KNEE FOLD",
        pose_file="dead-bug.jpg",
        prescription_ko="6회",
        prescription_en="6 REPS",
        cue_ko="허리가 뜨지 않을 만큼만",
        cue_en="KEEP YOUR LOW BACK HEAVY",
        voice_ko="허리가 뜨지 않는 범위에서, 내쉬며 무릎을 여섯 번 접었다 길게 펴요.",
        motion_start_file="dead-bug-start.png",
        motion_end_file="dead-bug-extend.png",
        camera_angle="overhead",
        muscle_focus="복부·고관절·대퇴부",
    ),
    "supine-leg-flow": Exercise(
        slug="supine-leg-flow",
        name_ko="누운 다리 플로우",
        name_en="SUPINE LEG FLOW",
        pose_file="dead-bug.jpg",
        prescription_ko="좌우 5회씩",
        prescription_en="5 EACH SIDE",
        cue_ko="골반은 매트에 안정적으로",
        cue_en="KEEP YOUR PELVIS STEADY",
        voice_ko="골반을 매트에 안정적으로 두고, 허리가 뜨지 않게 좌우 다섯 번씩 다리를 바꿔요.",
        motion_start_file="dead-bug-start.png",
        motion_end_file="dead-bug-extend.png",
        camera_angle="overhead",
        muscle_focus="하복부·고관절·대퇴부",
        bilateral=True,
    ),
    "single-knee-stretch": Exercise(
        slug="single-knee-stretch",
        name_ko="싱글 니 스트레치",
        name_en="SINGLE KNEE STRETCH",
        pose_file="dead-bug.jpg",
        prescription_ko="좌우 5회씩",
        prescription_en="5 EACH SIDE",
        cue_ko="어깨 힘을 빼고 무릎 당기기",
        cue_en="RELAX SHOULDERS AND DRAW IN",
        voice_ko="어깨 힘을 빼고, 무릎을 가슴 쪽으로 좌우 다섯 번씩 천천히 당겨요.",
        motion_start_file="dead-bug-start.png",
        motion_end_file="dead-bug-extend.png",
        camera_angle="overhead",
        muscle_focus="복부·고관절·둔근",
        bilateral=True,
    ),
}


ROUTINES: Tuple[Routine, ...] = (
    Routine("morning-core", "아침 코어 깨우기", "MORNING CORE", "굳은 몸을 깨우는 초급 코어 세 동작입니다.", ("dead-bug", "bird-dog", "glute-bridge"), "아침 운동과 저녁 운동 중 언제가 더 편한가요?"),
    Routine("hip-stability", "골반 안정 루틴", "HIP STABILITY", "골반을 안정적으로 쓰는 세 동작을 이어갑니다.", ("glute-bridge", "side-leg-lift", "bird-dog"), "브릿지와 버드독 중 어느 동작이 더 어려웠나요?"),
    Routine("desk-reset", "앉아 있던 몸 리셋", "DESK RESET", "오래 앉아 있던 날 가볍게 움직이는 세 동작입니다.", ("ring-side-bend", "spine-twist", "bird-dog"), "오늘 의자에 몇 시간 정도 앉아 있었나요?"),
    Routine("beginner-core", "초보 코어 삼종 세트", "BEGINNER CORE", "처음 시작하기 좋은 코어 세 동작입니다.", ("dead-bug", "modified-plank", "glute-bridge"), "세 동작 중 저장해두고 싶은 동작은 무엇인가요?"),
    Routine("no-jump", "층간소음 없는 홈트", "NO-JUMP PILATES", "점프 없이 조용하게 이어가는 세 동작입니다.", ("bird-dog", "glute-bridge", "modified-plank"), "집에서 가장 자주 운동하는 시간대는 언제인가요?"),
    Routine("side-line", "옆라인 컨트롤", "SIDE-LINE CONTROL", "옆면과 중심을 함께 조절하는 세 동작입니다.", ("side-leg-lift", "ring-side-bend", "modified-plank"), "왼쪽과 오른쪽 중 어느 쪽이 더 어려웠나요?"),
    Routine("evening-gentle", "저녁의 부드러운 코어", "EVENING CORE", "하루 끝에 힘을 과하게 쓰지 않는 세 동작입니다.", ("spine-twist", "dead-bug", "glute-bridge"), "운동 후 가장 편안해진 부위는 어디인가요?"),
    Routine("balance-control", "균형 잡는 코어", "BALANCE & CONTROL", "흔들림을 줄이고 천천히 조절하는 세 동작입니다.", ("bird-dog", "dead-bug", "ring-side-bend"), "균형 동작에서 어느 방향이 더 흔들렸나요?"),
    Routine("mat-essential", "매트 필라테스 기본", "MAT ESSENTIALS", "매트 한 장으로 연습하는 기본 세 동작입니다.", ("glute-bridge", "spine-twist", "dead-bug"), "매트 운동은 맨발과 양말 중 어느 쪽을 선호하나요?"),
    Routine("posture-flow", "상체 정렬 플로우", "POSTURE FLOW", "상체를 길게 세우는 감각에 집중하는 세 동작입니다.", ("spine-twist", "ring-side-bend", "bird-dog"), "오늘 가장 시원하게 느껴진 동작은 무엇인가요?"),
    Routine("upper-body-core", "가슴과 코어 컨트롤", "UPPER BODY CORE", "가슴과 팔, 중심을 함께 쓰는 초급 세 동작입니다.", ("kneeling-push-up", "modified-plank", "bird-dog"), "가슴과 팔 중 어느 부위가 먼저 힘들어졌나요?"),
    Routine("inner-thigh-control", "힙과 안쪽 허벅지", "HIPS & INNER THIGHS", "골반을 고정하고 둔근과 내전근을 차분히 쓰는 세 동작입니다.", ("inner-thigh-lift", "glute-bridge", "side-leg-lift"), "안쪽 허벅지와 엉덩이 중 어느 부위가 더 잘 느껴졌나요?"),
    Routine("fixed-plank-core", "코어가 보이는 플랭크", "PLANK CORE CONTROL", "같은 모델의 자연스러운 움직임으로 복부 힘을 확인하는 플랭크 세 동작입니다.", ("modified-plank", "plank-control", "plank-reset"), "세 플랭크 중 복부에 가장 잘 느껴진 동작은 무엇인가요?"),
    Routine("fixed-supine-core", "누워서 코어 컨트롤", "SUPINE CORE CONTROL", "허리가 뜨지 않는 범위에서 천천히 조절하는 누운 코어 세 동작입니다.", ("knee-fold", "supine-leg-flow", "single-knee-stretch"), "오른쪽과 왼쪽 중 어느 쪽이 더 안정적이었나요?"),
    Routine("fixed-core-mix", "복부 집중 코어 플로우", "CORE CLOSE-UP FLOW", "복부 움직임이 잘 보이는 누운 동작과 플랭크를 연결합니다.", ("knee-fold", "plank-control", "supine-leg-flow"), "누운 동작과 플랭크 중 어느 쪽이 더 어려웠나요?"),
)


def select_routine(records: Iterable[Dict[str, Any]], today: date | None = None) -> Routine:
    """최근 다섯 편과 겹치지 않는 루틴을 날짜 기반으로 안정적으로 선택한다."""
    recent = [str(item.get("routine_id") or "") for item in list(records)[-5:]]
    available = [routine for routine in ROUTINES if routine.routine_id not in recent]
    candidates = available or list(ROUTINES)
    day = today or date.today()
    return candidates[day.toordinal() % len(candidates)]


def routine_exercises(routine: Routine) -> List[Exercise]:
    return [EXERCISES[slug] for slug in routine.exercise_slugs]


def build_narration(routine: Routine) -> str:
    movements = routine_exercises(routine)
    order = ("첫 번째", "두 번째", "마지막")
    sentences = [routine.intro_ko]
    for label, exercise in zip(order, movements):
        sentences.append(f"{label}, {exercise.name_ko}. {exercise.voice_ko}")
    sentences.append("호흡은 편안하게 이어가고, 통증이 느껴지면 바로 멈추세요.")
    return " ".join(sentences)


def validate_routine(routine: Routine) -> None:
    if len(routine.exercise_slugs) != 3 or len(set(routine.exercise_slugs)) != 3:
        raise ValueError("한 루틴에는 서로 다른 동작 세 개가 필요합니다.")
    narration = build_narration(routine)
    if any(character.isdigit() for character in narration):
        raise ValueError("한국어 내레이션에는 숫자 표기를 사용할 수 없습니다.")
    blocked = ("치료", "완치", "통증 제거", "살이 빠", "지방 제거")
    if any(term in narration for term in blocked):
        raise ValueError("의료 또는 과장 효과 표현을 사용할 수 없습니다.")
    for exercise in routine_exercises(routine):
        if not all((exercise.name_ko, exercise.name_en, exercise.cue_ko, exercise.cue_en)):
            raise ValueError(f"한·영 안내가 누락되었습니다: {exercise.slug}")
        if exercise.camera_angle not in {
            "overhead",
            "side-three-quarter",
            "side-full-body",
            "front-three-quarter",
            "front-alignment",
            "side-front-three-quarter",
            "side-front-lower-body",
        }:
            raise ValueError(f"검수되지 않은 카메라 구도입니다: {exercise.camera_angle}")


def all_pose_paths() -> Sequence[Path]:
    return tuple(exercise.pose_path for exercise in EXERCISES.values())
