"""검수된 필라테스 동작과 장기 순환용 루틴 목록."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
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
    "forearm-plank-flow": Exercise(
        slug="forearm-plank-flow", name_ko="포어암 플랭크 플로우", name_en="FOREARM PLANK FLOW",
        pose_file="modified-plank.jpg", prescription_ko="5회", prescription_en="5 REPS",
        cue_ko="어깨 아래 팔꿈치 유지", cue_en="KEEP ELBOWS UNDER SHOULDERS",
        voice_ko="어깨 아래에 팔꿈치를 두고, 중심을 단단히 잡으며 다섯 번 천천히 연결해요.",
        motion_start_file="modified-plank-prep.png", motion_end_file="modified-plank-hold.png",
        camera_angle="side-three-quarter", muscle_focus="복부·어깨·둔근",
    ),
    "lateral-lunge-flow": Exercise(
        slug="lateral-lunge-flow", name_ko="사이드 런지 플로우", name_en="LATERAL LUNGE FLOW",
        pose_file="side-leg-lift.jpg", prescription_ko="좌우 5회씩", prescription_en="5 EACH SIDE",
        cue_ko="무릎과 발끝 같은 방향", cue_en="TRACK KNEE OVER TOES",
        voice_ko="무릎과 발끝을 같은 방향으로 두고, 엉덩이를 뒤로 보내며 좌우 다섯 번씩 움직여요.",
        motion_start_file="side-leg-lift-down.png", motion_end_file="side-leg-lift-up.png",
        camera_angle="front-alignment", muscle_focus="둔근·내전근·대퇴부", bilateral=True,
    ),
    "squat-reach-flow": Exercise(
        slug="squat-reach-flow", name_ko="스쿼트 리치", name_en="SQUAT TO REACH",
        pose_file="glute-bridge.jpg", prescription_ko="6회", prescription_en="6 REPS",
        cue_ko="발바닥 전체로 밀기", cue_en="PRESS THROUGH YOUR WHOLE FOOT",
        voice_ko="발바닥 전체로 바닥을 밀고, 앉았다 일어나며 팔을 위로 여섯 번 길게 뻗어요.",
        motion_start_file="glute-bridge-down.png", motion_end_file="glute-bridge-up.png",
        camera_angle="front-three-quarter", muscle_focus="둔근·대퇴부·복부",
    ),
    "standing-fold": Exercise(
        slug="standing-fold", name_ko="스탠딩 포워드 폴드", name_en="STANDING FORWARD FOLD",
        pose_file="spine-twist.jpg", prescription_ko="5회", prescription_en="5 REPS",
        cue_ko="무릎을 편안하게 풀기", cue_en="KEEP A SOFT BEND IN KNEES",
        voice_ko="무릎을 편안하게 풀고, 척추를 길게 유지하며 다섯 번 천천히 접었다 올라와요.",
        motion_start_file="spine-twist-center.png", motion_end_file="spine-twist-right.png",
        camera_angle="front-three-quarter", muscle_focus="햄스트링·둔근·척추기립근",
    ),
    "cat-cow-flow": Exercise(
        slug="cat-cow-flow", name_ko="캣 카우 플로우", name_en="CAT COW FLOW",
        pose_file="bird-dog.jpg", prescription_ko="6회", prescription_en="6 REPS",
        cue_ko="호흡에 맞춰 척추 움직이기", cue_en="MOVE WITH YOUR BREATH",
        voice_ko="손목 아래 어깨, 무릎 아래 골반을 두고 호흡에 맞춰 척추를 여섯 번 부드럽게 움직여요.",
        motion_start_file="bird-dog-start.png", motion_end_file="bird-dog-extend.png",
        camera_angle="side-three-quarter", muscle_focus="복부·척추기립근·어깨",
    ),
    "sun-salutation-flow": Exercise(
        slug="sun-salutation-flow", name_ko="선 플로우", name_en="SUN FLOW",
        pose_file="modified-plank.jpg", prescription_ko="3회", prescription_en="3 ROUNDS",
        cue_ko="허리가 꺾이지 않게 중심 유지", cue_en="KEEP YOUR CORE SUPPORTED",
        voice_ko="허리가 꺾이지 않게 중심을 유지하고, 플랭크와 상체 열기를 세 번 부드럽게 연결해요.",
        motion_start_file="modified-plank-prep.png", motion_end_file="modified-plank-hold.png",
        camera_angle="side-three-quarter", muscle_focus="복부·가슴·어깨·척추기립근",
    ),
    "fold-to-seat": Exercise(
        slug="fold-to-seat", name_ko="폴드 투 시트", name_en="FOLD TO SEAT",
        pose_file="spine-twist.jpg", prescription_ko="5회", prescription_en="5 REPS",
        cue_ko="반동 없이 천천히 이동", cue_en="MOVE SLOWLY WITHOUT BOUNCING",
        voice_ko="반동을 쓰지 말고, 서서 접는 자세에서 앉은 자세까지 다섯 번 천천히 연결해요.",
        motion_start_file="spine-twist-center.png", motion_end_file="spine-twist-right.png",
        camera_angle="front-three-quarter", muscle_focus="햄스트링·고관절·척추기립근",
    ),
    "standing-shoulder-open": Exercise(
        slug="standing-shoulder-open", name_ko="스탠딩 숄더 오픈", name_en="STANDING SHOULDER OPEN",
        pose_file="ring-side-bend.jpg", prescription_ko="좌우 20초", prescription_en="20 SECONDS EACH",
        cue_ko="갈비뼈는 들리지 않게", cue_en="KEEP YOUR RIBS DOWN",
        voice_ko="갈비뼈가 들리지 않게 중심을 잡고, 어깨 뒤쪽을 좌우 스무 초씩 부드럽게 열어요.",
        motion_start_file="ring-side-center.png", motion_end_file="ring-side-bend.png",
        camera_angle="front-alignment", muscle_focus="어깨·상완·흉곽", bilateral=True,
    ),
    "overhead-reach": Exercise(
        slug="overhead-reach", name_ko="오버헤드 리치", name_en="OVERHEAD REACH",
        pose_file="ring-side-bend.jpg", prescription_ko="6회", prescription_en="6 REPS",
        cue_ko="어깨는 귀에서 멀리", cue_en="KEEP SHOULDERS AWAY FROM EARS",
        voice_ko="어깨를 귀에서 멀리 두고, 손끝을 천장으로 여섯 번 길게 뻗어요.",
        motion_start_file="ring-side-center.png", motion_end_file="ring-side-bend.png",
        camera_angle="front-alignment", muscle_focus="복부·광배근·어깨",
    ),
    "seated-side-bend": Exercise(
        slug="seated-side-bend", name_ko="시티드 사이드 밴드", name_en="SEATED SIDE BEND",
        pose_file="ring-side-bend.jpg", prescription_ko="좌우 5회씩", prescription_en="5 EACH SIDE",
        cue_ko="양쪽 좌골은 바닥에", cue_en="KEEP BOTH HIPS GROUNDED",
        voice_ko="양쪽 골반을 바닥에 안정적으로 두고, 옆구리를 좌우 다섯 번씩 길게 늘려요.",
        motion_start_file="ring-side-center.png", motion_end_file="ring-side-bend.png",
        camera_angle="front-three-quarter", muscle_focus="복사근·광배근·골반", bilateral=True,
    ),
    "seated-hamstring": Exercise(
        slug="seated-hamstring", name_ko="시티드 햄스트링", name_en="SEATED HAMSTRING STRETCH",
        pose_file="spine-twist.jpg", prescription_ko="좌우 20초", prescription_en="20 SECONDS EACH",
        cue_ko="등을 길게 유지", cue_en="KEEP YOUR SPINE LONG",
        voice_ko="등을 길게 유지하고, 통증 없는 범위에서 다리 뒤쪽을 좌우 스무 초씩 늘려요.",
        motion_start_file="spine-twist-center.png", motion_end_file="spine-twist-right.png",
        camera_angle="front-three-quarter", muscle_focus="햄스트링·종아리·둔근", bilateral=True,
    ),
    "seated-leg-extension": Exercise(
        slug="seated-leg-extension", name_ko="시티드 레그 익스텐션", name_en="SEATED LEG EXTENSION",
        pose_file="dead-bug.jpg", prescription_ko="좌우 5회씩", prescription_en="5 EACH SIDE",
        cue_ko="가슴을 열고 중심 유지", cue_en="LIFT THROUGH YOUR CHEST",
        voice_ko="가슴을 열고 중심을 유지한 채, 다리를 좌우 다섯 번씩 천천히 펴고 접어요.",
        motion_start_file="dead-bug-start.png", motion_end_file="dead-bug-extend.png",
        camera_angle="front-three-quarter", muscle_focus="복부·대퇴부·햄스트링", bilateral=True,
    ),
    "supine-leg-stretch": Exercise(
        slug="supine-leg-stretch", name_ko="누운 다리 스트레치", name_en="SUPINE LEG STRETCH",
        pose_file="dead-bug.jpg", prescription_ko="좌우 20초", prescription_en="20 SECONDS EACH",
        cue_ko="골반은 매트에 안정적으로", cue_en="KEEP YOUR PELVIS STEADY",
        voice_ko="골반을 매트에 안정적으로 두고, 무릎을 편안하게 풀어 좌우 스무 초씩 늘려요.",
        motion_start_file="dead-bug-start.png", motion_end_file="dead-bug-extend.png",
        camera_angle="overhead", muscle_focus="햄스트링·종아리·하복부", bilateral=True,
    ),
    "seated-arm-flow": Exercise(
        slug="seated-arm-flow", name_ko="시티드 암 플로우", name_en="SEATED ARM FLOW",
        pose_file="ring-side-bend.jpg", prescription_ko="6회", prescription_en="6 REPS",
        cue_ko="어깨 힘을 빼고 길게", cue_en="RELAX SHOULDERS AND REACH",
        voice_ko="어깨 힘을 빼고, 척추를 세운 채 양팔을 여섯 번 천천히 들어 올려요.",
        motion_start_file="ring-side-center.png", motion_end_file="ring-side-bend.png",
        camera_angle="front-three-quarter", muscle_focus="어깨·광배근·흉곽",
    ),
    "supine-knee-hug": Exercise(
        slug="supine-knee-hug", name_ko="누운 무릎 당기기", name_en="SUPINE KNEE HUG",
        pose_file="dead-bug.jpg", prescription_ko="좌우 5회씩", prescription_en="5 EACH SIDE",
        cue_ko="어깨와 목은 편안하게", cue_en="RELAX YOUR NECK AND SHOULDERS",
        voice_ko="어깨와 목의 힘을 빼고, 무릎을 가슴 쪽으로 좌우 다섯 번씩 부드럽게 당겨요.",
        motion_start_file="dead-bug-start.png", motion_end_file="dead-bug-extend.png",
        camera_angle="overhead", muscle_focus="둔근·고관절·하복부", bilateral=True,
    ),
    "neck-release": Exercise(
        slug="neck-release", name_ko="넥 릴리스", name_en="NECK RELEASE",
        pose_file="spine-twist.jpg", prescription_ko="좌우 20초", prescription_en="20 SECONDS EACH",
        cue_ko="어깨는 아래로 편안하게", cue_en="LET YOUR SHOULDERS DROP",
        voice_ko="어깨를 아래로 편안하게 내리고, 목 옆선을 좌우 스무 초씩 천천히 늘려요.",
        motion_start_file="spine-twist-center.png", motion_end_file="spine-twist-right.png",
        camera_angle="front-three-quarter", muscle_focus="목·승모근·어깨", bilateral=True,
    ),
    "rear-shoulder-open": Exercise(
        slug="rear-shoulder-open", name_ko="리어 숄더 오픈", name_en="REAR SHOULDER OPEN",
        pose_file="ring-side-bend.jpg", prescription_ko="20초", prescription_en="20 SECONDS",
        cue_ko="허리를 꺾지 않고 가슴 열기", cue_en="OPEN CHEST WITHOUT ARCHING",
        voice_ko="허리를 꺾지 않고, 양손을 뒤로 보내 가슴과 어깨 앞쪽을 스무 초 동안 열어요.",
        motion_start_file="ring-side-center.png", motion_end_file="ring-side-bend.png",
        camera_angle="front-alignment", muscle_focus="가슴·어깨·상완",
    ),
    "tall-reach": Exercise(
        slug="tall-reach", name_ko="톨 리치", name_en="TALL REACH",
        pose_file="ring-side-bend.jpg", prescription_ko="6회", prescription_en="6 REPS",
        cue_ko="발바닥부터 손끝까지 길게", cue_en="REACH FROM FEET TO FINGERTIPS",
        voice_ko="발바닥으로 바닥을 누르고, 손끝까지 몸을 여섯 번 길게 뻗어요.",
        motion_start_file="ring-side-center.png", motion_end_file="ring-side-bend.png",
        camera_angle="front-alignment", muscle_focus="복부·광배근·종아리",
    ),
    "standing-side-reach": Exercise(
        slug="standing-side-reach", name_ko="스탠딩 사이드 리치", name_en="STANDING SIDE REACH",
        pose_file="ring-side-bend.jpg", prescription_ko="좌우 5회씩", prescription_en="5 EACH SIDE",
        cue_ko="골반은 정면에 고정", cue_en="KEEP HIPS FACING FORWARD",
        voice_ko="골반을 정면에 두고, 옆구리를 좌우 다섯 번씩 길게 뻗어요.",
        motion_start_file="ring-side-center.png", motion_end_file="ring-side-bend.png",
        camera_angle="front-alignment", muscle_focus="복사근·광배근·골반", bilateral=True,
    ),
    "forward-fold-flow": Exercise(
        slug="forward-fold-flow", name_ko="포워드 폴드 플로우", name_en="FORWARD FOLD FLOW",
        pose_file="spine-twist.jpg", prescription_ko="5회", prescription_en="5 REPS",
        cue_ko="무릎을 잠그지 않기", cue_en="KEEP YOUR KNEES SOFT",
        voice_ko="무릎을 잠그지 말고, 숨을 내쉬며 상체를 다섯 번 천천히 접었다 올려요.",
        motion_start_file="spine-twist-center.png", motion_end_file="spine-twist-right.png",
        camera_angle="front-three-quarter", muscle_focus="햄스트링·둔근·척추기립근",
    ),
    "seated-forward-fold": Exercise(
        slug="seated-forward-fold", name_ko="시티드 포워드 폴드", name_en="SEATED FORWARD FOLD",
        pose_file="spine-twist.jpg", prescription_ko="20초", prescription_en="20 SECONDS",
        cue_ko="배와 허벅지를 가깝게", cue_en="HINGE FROM YOUR HIPS",
        voice_ko="허리만 둥글게 말지 말고, 고관절에서 접어 다리 뒤쪽을 스무 초 동안 늘려요.",
        motion_start_file="spine-twist-center.png", motion_end_file="spine-twist-right.png",
        camera_angle="front-three-quarter", muscle_focus="햄스트링·둔근·척추기립근",
    ),
    "side-mobility-flow": Exercise(
        slug="side-mobility-flow", name_ko="사이드 모빌리티 플로우", name_en="SIDE MOBILITY FLOW",
        pose_file="side-leg-lift.jpg", prescription_ko="좌우 5회씩", prescription_en="5 EACH SIDE",
        cue_ko="가슴과 무릎 같은 방향", cue_en="ALIGN CHEST WITH YOUR KNEE",
        voice_ko="가슴과 무릎을 같은 방향으로 두고, 옆구리와 안쪽 허벅지를 좌우 다섯 번씩 열어요.",
        motion_start_file="side-leg-lift-down.png", motion_end_file="side-leg-lift-up.png",
        camera_angle="front-three-quarter", muscle_focus="복사근·내전근·둔근", bilateral=True,
    ),
    "hip-open-flow": Exercise(
        slug="hip-open-flow", name_ko="힙 오픈 플로우", name_en="HIP OPEN FLOW",
        pose_file="side-leg-lift.jpg", prescription_ko="좌우 5회씩", prescription_en="5 EACH SIDE",
        cue_ko="통증 없는 범위에서 천천히", cue_en="MOVE SLOWLY WITHOUT PAIN",
        voice_ko="통증 없는 범위에서, 골반 주변을 좌우 다섯 번씩 천천히 열고 닫아요.",
        motion_start_file="side-leg-lift-down.png", motion_end_file="side-leg-lift-up.png",
        camera_angle="front-three-quarter", muscle_focus="고관절·둔근·내전근", bilateral=True,
    ),
    "butterfly-stretch": Exercise(
        slug="butterfly-stretch", name_ko="버터플라이 스트레치", name_en="BUTTERFLY STRETCH",
        pose_file="side-leg-lift.jpg", prescription_ko="20초", prescription_en="20 SECONDS",
        cue_ko="무릎을 억지로 누르지 않기", cue_en="DO NOT FORCE YOUR KNEES DOWN",
        voice_ko="발바닥을 가볍게 맞대고, 무릎을 억지로 누르지 않은 채 스무 초 동안 호흡해요.",
        motion_start_file="side-leg-lift-down.png", motion_end_file="side-leg-lift-up.png",
        camera_angle="front-three-quarter", muscle_focus="고관절·내전근·골반",
    ),
    "foot-release": Exercise(
        slug="foot-release", name_ko="발목과 발바닥 풀기", name_en="ANKLE AND FOOT RELEASE",
        pose_file="side-leg-lift.jpg", prescription_ko="좌우 20초", prescription_en="20 SECONDS EACH",
        cue_ko="통증 없는 범위에서 부드럽게", cue_en="KEEP THE PRESSURE GENTLE",
        voice_ko="통증 없는 범위에서 발가락과 발목을 좌우 스무 초씩 부드럽게 풀어요.",
        motion_start_file="side-leg-lift-down.png", motion_end_file="side-leg-lift-up.png",
        camera_angle="side-front-lower-body", muscle_focus="발바닥·발목·종아리", bilateral=True,
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
    Routine("fixed-plank-transition", "플랭크 연결 동작", "PLANK TRANSITIONS", "복부 힘을 유지하며 플랭크 자세를 단계별로 연결합니다.", ("modified-plank", "plank-reset", "forearm-plank-flow"), "세 동작 중 중심 잡기가 가장 어려웠던 동작은 무엇인가요?"),
    Routine("fixed-lower-body-flow", "하체 모빌리티 플로우", "LOWER BODY FLOW", "둔근과 허벅지를 여러 방향으로 쓰는 서서 하는 세 동작입니다.", ("lateral-lunge-flow", "squat-reach-flow", "standing-fold"), "좌우 중 어느 방향의 런지가 더 편했나요?"),
    Routine("fixed-spinal-flow", "척추를 깨우는 플로우", "SPINAL WAKE-UP FLOW", "호흡과 함께 척추를 부드럽게 움직이는 세 동작입니다.", ("cat-cow-flow", "sun-salutation-flow", "fold-to-seat"), "아침과 저녁 중 언제 이 플로우를 따라 하고 싶나요?"),
    Routine("fixed-shoulder-mobility", "어깨와 옆구리 열기", "SHOULDER MOBILITY", "굳은 어깨와 옆구리를 천천히 여는 세 동작입니다.", ("standing-shoulder-open", "overhead-reach", "seated-side-bend"), "왼쪽과 오른쪽 어깨 중 어느 쪽이 더 뻣뻣했나요?"),
    Routine("fixed-hamstring-release", "다리 뒤쪽 스트레치", "HAMSTRING RELEASE", "앉거나 누워서 다리 뒤쪽을 무리 없이 늘리는 세 동작입니다.", ("seated-hamstring", "seated-leg-extension", "supine-leg-stretch"), "좌우 다리 중 어느 쪽이 더 당겼나요?"),
    Routine("fixed-gentle-recovery", "상체 긴장 완화", "GENTLE RECOVERY", "어깨와 목, 고관절의 긴장을 차분히 푸는 세 동작입니다.", ("seated-arm-flow", "supine-knee-hug", "neck-release"), "오늘 가장 편안해진 부위는 어디인가요?"),
    Routine("fixed-standing-posture", "서서 하는 자세 리셋", "STANDING POSTURE RESET", "서 있는 자세에서 가슴과 옆구리를 길게 여는 세 동작입니다.", ("rear-shoulder-open", "tall-reach", "standing-side-reach"), "세 동작 중 가장 시원했던 움직임은 무엇인가요?"),
    Routine("fixed-beginner-flow", "초보 전신 유연성", "BEGINNER FLEXIBILITY", "반동 없이 전신을 천천히 연결하는 초급 세 동작입니다.", ("forward-fold-flow", "seated-forward-fold", "side-mobility-flow"), "서서 하는 동작과 앉아서 하는 동작 중 어느 쪽이 편했나요?"),
    Routine("fixed-hip-mobility", "고관절과 발목 풀기", "HIP AND ANKLE MOBILITY", "골반부터 발목까지 하체 관절을 천천히 푸는 세 동작입니다.", ("hip-open-flow", "butterfly-stretch", "foot-release"), "고관절과 발목 중 어느 부위가 더 뻣뻣했나요?"),
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


ROUTINE_COPY_EN: Dict[str, Tuple[str, str]] = {
    "fixed-plank-transition": (
        "Build steadier core control through three clean plank transitions.",
        "Which plank transition challenged your control the most?",
    ),
    "fixed-lower-body-flow": (
        "Open the hips and wake up the legs with three controlled standing moves.",
        "Which felt stronger today: the lateral lunge or the squat to reach?",
    ),
    "fixed-spinal-flow": (
        "Reset a stiff spine with three slow, breath-led movements.",
        "Would you use this flow in the morning or after a long day?",
    ),
    "fixed-shoulder-mobility": (
        "Release stiff shoulders and side-body tension with three gentle mobility moves.",
        "Which shoulder felt tighter today: left or right?",
    ),
    "fixed-hamstring-release": (
        "Lengthen the back of the legs with three controlled, no-bounce stretches.",
        "Which side felt tighter during this hamstring flow?",
    ),
    "fixed-gentle-recovery": (
        "Ease upper-body tension with three calm recovery movements.",
        "Which move helped you feel the most relaxed?",
    ),
    "fixed-standing-posture": (
        "Stand taller with three simple posture-reset movements.",
        "Which movement made your posture feel the most open?",
    ),
    "fixed-beginner-flow": (
        "Move through a beginner-friendly, full-body flexibility flow.",
        "Did the standing move or the seated move feel more comfortable?",
    ),
    "fixed-hip-mobility": (
        "Loosen the hips and ankles with three controlled mobility moves.",
        "Which felt stiffer today: your hips or your ankles?",
    ),
}


def routine_intro_en(routine: Routine) -> str:
    custom = ROUTINE_COPY_EN.get(routine.routine_id)
    if custom:
        return custom[0]
    return f"A focused three-move {routine.title_en.lower()} routine with clear, controlled form."


def routine_engagement_question_en(routine: Routine) -> str:
    custom = ROUTINE_COPY_EN.get(routine.routine_id)
    if custom:
        return custom[1]
    return "Which of the three movements felt best in your body today?"


_NUMBER_WORDS = {
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
    "20": "twenty",
}


def _spoken_prescription(value: str) -> str:
    text = value.strip().upper()
    patterns = (
        (r"^(\d+) SECONDS EACH$", "{count} seconds on each side"),
        (r"^(\d+) EACH SIDE$", "{count} controlled repetitions on each side"),
        (r"^(\d+) SECONDS$", "{count} seconds"),
        (r"^(\d+) REPS$", "{count} controlled repetitions"),
        (r"^(\d+) ROUNDS$", "{count} smooth rounds"),
    )
    for pattern, template in patterns:
        match = re.fullmatch(pattern, text)
        if match:
            count = _NUMBER_WORDS.get(match.group(1), match.group(1))
            return template.format(count=count)
    return text.lower()


def build_narration(routine: Routine) -> str:
    movements = routine_exercises(routine)
    order = ("First", "Next", "Finally")
    sentences = [routine_intro_en(routine)]
    for label, exercise in zip(order, movements):
        sentences.append(
            f"{label}, {exercise.name_en.title()}. "
            f"{exercise.cue_en.capitalize()}. "
            f"Complete {_spoken_prescription(exercise.prescription_en)}."
        )
    sentences.append(
        "Breathe steadily, work within a comfortable range, and stop if you feel pain, "
        "dizziness, or discomfort."
    )
    return " ".join(sentences)


def validate_routine(routine: Routine) -> None:
    if len(routine.exercise_slugs) != 3 or len(set(routine.exercise_slugs)) != 3:
        raise ValueError("한 루틴에는 서로 다른 동작 세 개가 필요합니다.")
    narration = build_narration(routine)
    if any(character.isdigit() for character in narration):
        raise ValueError("영어 내레이션의 횟수는 자연어로 작성해야 합니다.")
    if re.search(r"[가-힣ㄱ-ㅎㅏ-ㅣ]", narration):
        raise ValueError("공개 내레이션에는 영어만 사용할 수 있습니다.")
    blocked = ("cure", "heal", "pain-free", "spot reduce", "burn fat")
    legacy_blocked = ("치료", "완치", "통증 제거", "살이 빠", "지방 제거")
    if any(term in narration.lower() for term in blocked) or any(
        term in routine.intro_ko for term in legacy_blocked
    ):
        raise ValueError("의료 또는 과장 효과 표현을 사용할 수 없습니다.")
    for exercise in routine_exercises(routine):
        if not all((exercise.name_en, exercise.cue_en, exercise.prescription_en)):
            raise ValueError(f"영어 안내가 누락되었습니다: {exercise.slug}")
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
