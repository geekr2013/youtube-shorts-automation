"""검증 자료와 생활밀착형 B급 유머 각도를 연결한 편집 주제 목록."""

import re
from difflib import SequenceMatcher
from typing import Iterable, List

from models import TopicPlan


VERIFIED_TOPICS = (
    TopicPlan(
        topic="QR 코드는 왜 반쯤 가려져도 출근 체크를 해낼까",
        wiki_query="QR 코드",
        stock_queries=["QR code scan smartphone", "damaged QR code", "barcode scanner close up"],
        category="technology",
        audience_angle="카페 주문과 출근 체크에서 매일 마주치는 QR 코드",
        comedy_angle="모서리 세 개만 보고도 정답을 맞히는 눈치 빠른 조별 과제 팀원",
    ),
    TopicPlan(
        topic="오로라는 왜 극지방에서만 조명 맛집을 열까",
        wiki_query="오로라",
        stock_queries=["aurora borealis vertical", "northern lights sky", "polar night landscape"],
        category="nature",
        audience_angle="여행 버킷리스트에서 늘 상위권인 오로라",
        comedy_angle="태양 입자와 지구 자기장이 차린 우주 조명 맛집",
    ),
    TopicPlan(
        topic="문어는 왜 위기 때 피부 배경화면부터 바꿀까",
        wiki_query="문어",
        stock_queries=["octopus camouflage underwater", "octopus skin close up", "octopus coral reef"],
        category="nature",
        audience_angle="카메라 필터보다 빠른 문어의 위장",
        comedy_angle="위험 알림이 오면 피부 테마부터 바꾸는 바다의 스마트폰",
    ),
    TopicPlan(
        topic="구름은 그렇게 무거운데 왜 아직 안 떨어질까",
        wiki_query="구름",
        stock_queries=["cumulus clouds aerial", "cloud timelapse sky", "mist water droplets"],
        category="nature",
        audience_angle="매일 올려다보지만 무게는 생각해 보지 않는 구름",
        comedy_angle="엄청난 단체 인원이 공중에서 흩어져 버티는 출근길 지하철의 반대 상황",
    ),
    TopicPlan(
        topic="번개는 왜 하늘에서 거대 정전기 싸움을 벌일까",
        wiki_query="번개",
        stock_queries=["lightning storm vertical", "storm clouds lightning", "lightning slow motion"],
        category="science",
        audience_angle="충전기와 정전기에 익숙한 시청자가 이해하기 쉬운 번개",
        comedy_angle="구름이 참다못해 벌이는 초대형 정전기 방전",
    ),
    TopicPlan(
        topic="무지개는 왜 매번 반쪽짜리 프로필 사진만 보여줄까",
        wiki_query="무지개",
        stock_queries=["rainbow sky vertical", "rainbow after rain", "water prism rainbow"],
        category="nature",
        audience_angle="사진은 많이 찍지만 완전한 원은 보기 힘든 무지개",
        comedy_angle="원형인데 지평선 때문에 늘 잘린 프로필 사진만 공개하는 셈",
    ),
    TopicPlan(
        topic="달은 왜 지구에 같은 셀카 각도만 고집할까",
        wiki_query="달",
        stock_queries=["moon surface telescope", "full moon night vertical", "earth moon animation"],
        category="space",
        audience_angle="매일 보이는 달이 같은 얼굴이라는 익숙한 의문",
        comedy_angle="공전과 자전이 맞아떨어져 한쪽 얼굴만 고집하는 셀카 장인",
    ),
    TopicPlan(
        topic="태풍의 눈은 왜 난리 한가운데 혼자 평온할까",
        wiki_query="태풍",
        stock_queries=["typhoon satellite storm", "hurricane eye clouds", "tropical storm ocean"],
        category="nature",
        audience_angle="뉴스에서 자주 듣는 태풍의 눈이라는 표현",
        comedy_angle="단체 채팅방이 폭발했는데 한가운데 혼자 알림을 끈 사람",
    ),
    TopicPlan(
        topic="나침반 바늘은 왜 북쪽에만 집착할까",
        wiki_query="나침반",
        stock_queries=["compass needle close up", "compass navigation forest", "magnetic compass macro"],
        category="science",
        audience_angle="지도 앱이 없을 때도 길을 찾던 오래된 도구",
        comedy_angle="어디에 놓아도 북쪽만 바라보는 흔들리지 않는 최애",
    ),
    TopicPlan(
        topic="우주에서 소리쳐도 왜 단체방이 조용할까",
        wiki_query="소리",
        stock_queries=["sound wave speaker close up", "astronaut space vertical", "audio waveform studio"],
        category="science",
        audience_angle="영화 속 우주 폭발음과 실제 우주의 차이",
        comedy_angle="전달 매체가 없어 아무리 말해도 읽씹조차 성립하지 않는 공간",
    ),
    TopicPlan(
        topic="물방울은 왜 모이기만 하면 동그란 척할까",
        wiki_query="표면장력",
        stock_queries=["water droplet macro", "water surface tension", "raindrop slow motion"],
        category="science",
        audience_angle="비 오는 날과 컵 가장자리에서 쉽게 보는 물방울",
        comedy_angle="표면적을 줄이려고 자동으로 둥글게 모이는 절약형 단체",
    ),
    TopicPlan(
        topic="철새는 지도 앱도 없이 어떻게 해외 출장을 갈까",
        wiki_query="철새",
        stock_queries=["migratory birds flying", "bird flock sunset vertical", "birds navigation sky"],
        category="nature",
        audience_angle="내비게이션 없이는 길을 잃는 현대인과 철새의 대비",
        comedy_angle="충전도 데이터도 없이 장거리 출장을 완주하는 베테랑",
    ),
    TopicPlan(
        topic="나이테는 왜 나무의 흑역사를 전부 저장할까",
        wiki_query="나이테",
        stock_queries=["tree rings close up", "wood grain macro", "forest seasons timelapse"],
        category="nature",
        audience_angle="사진첩과 기록 앱에 익숙한 시청자에게 친숙한 성장 기록",
        comedy_angle="삭제 버튼 없이 매년 한 줄씩 저장되는 나무의 자동 일기",
    ),
    TopicPlan(
        topic="카멜레온은 왜 기분을 피부로 스포할까",
        wiki_query="카멜레온",
        stock_queries=["chameleon color change", "chameleon skin close up", "chameleon branch vertical"],
        category="nature",
        audience_angle="감정을 숨기려 해도 표정에 드러나는 일상",
        comedy_angle="상태 메시지를 피부 전체에 띄우는 과한 프로필 설정",
    ),
    TopicPlan(
        topic="파도는 물은 두고 에너지만 택배할까",
        wiki_query="파도",
        stock_queries=["ocean wave slow motion", "sea waves vertical", "water ripple close up"],
        category="science",
        audience_angle="해변에서 직접 본 파도의 이동을 뒤집는 사실",
        comedy_angle="상자는 제자리에 두고 내용물만 전달하는 이상한 택배",
    ),
    TopicPlan(
        topic="지진파는 지구 속을 어떻게 엑스레이처럼 훑을까",
        wiki_query="지진파",
        stock_queries=["seismic wave animation", "seismograph close up", "earth layers animation"],
        category="science",
        audience_angle="병원 엑스레이와 비슷한 원리로 이해하는 지구 내부",
        comedy_angle="땅을 흔든 뒤 돌아오는 답장으로 지구 속을 추리하는 탐정",
    ),
    TopicPlan(
        topic="화산재는 먼지인데 왜 비행기를 세울까",
        wiki_query="화산재",
        stock_queries=["volcanic ash eruption", "airplane clouds vertical", "volcano plume close up"],
        category="science",
        audience_angle="작은 먼지와 거대한 비행기의 예상 밖 대결",
        comedy_angle="작아 보여도 뜨거운 엔진 안에서 유리처럼 변하는 악성 손님",
    ),
    TopicPlan(
        topic="자석은 왜 같은 극만 만나면 밀당부터 할까",
        wiki_query="자석",
        stock_queries=["magnet poles experiment", "magnetic field close up", "magnets science experiment"],
        category="science",
        audience_angle="냉장고 자석으로 누구나 바로 확인할 수 있는 현상",
        comedy_angle="같은 취향끼리 친해질 것 같지만 만나자마자 거리를 두는 사이",
    ),
    TopicPlan(
        topic="하품은 왜 옆 사람에게 무료 배포될까",
        wiki_query="하품",
        stock_queries=["person yawning close up", "friends yawning", "sleepy office worker"],
        category="everyday",
        audience_angle="영상이나 글만 봐도 따라 하게 되는 하품",
        comedy_angle="데이터도 없이 주변 사람에게 자동 공유되는 몸의 알림",
    ),
    TopicPlan(
        topic="팝콘은 왜 냄비 안에서 단체 폭발할까",
        wiki_query="팝콘",
        stock_queries=["popcorn popping slow motion", "popcorn bowl cinema", "corn kernels close up"],
        category="food",
        audience_angle="영화관에서 가장 익숙한 간식의 폭발 과정",
        comedy_angle="옥수수 알갱이 안 수증기가 퇴근문을 못 찾아 껍질을 열어 버리는 상황",
    ),
    TopicPlan(
        topic="양파는 왜 칼만 보면 사람부터 울릴까",
        wiki_query="양파",
        stock_queries=["cutting onion close up", "person crying onion", "onion cooking kitchen"],
        category="food",
        audience_angle="요리할 때 누구나 겪는 양파 눈물",
        comedy_angle="자기가 잘리면서 상대방 눈물부터 받아 내는 주방의 협상가",
    ),
    TopicPlan(
        topic="방귀는 왜 조용한 곳에서 존재감이 커질까",
        wiki_query="방귀",
        stock_queries=["embarrassed person office", "balloon air slow motion", "people holding laughter"],
        category="everyday",
        audience_angle="누구나 알지만 공개적으로 설명하지 않는 소리와 냄새",
        comedy_angle="평소에는 숨어 있다가 회의실에서만 단독 데뷔하는 몸의 가스",
    ),
    TopicPlan(
        topic="정전기는 왜 겨울만 되면 손끝에서 시비를 걸까",
        wiki_query="정전기",
        stock_queries=["static electricity spark", "winter sweater static", "hair static electricity"],
        category="everyday",
        audience_angle="겨울 문손잡이와 니트에서 반복되는 따끔한 경험",
        comedy_angle="건조한 날씨가 손끝에 몰래 충전해 둔 초소형 번개",
    ),
    TopicPlan(
        topic="딸꾹질은 왜 중요한 순간에 마이크를 잡을까",
        wiki_query="딸꾹질",
        stock_queries=["person hiccup reaction", "diaphragm breathing animation", "meeting embarrassed person"],
        category="everyday",
        audience_angle="회의와 수업 중 갑자기 시작되는 딸꾹질",
        comedy_angle="횡격막이 허락도 없이 짧은 솔로 무대를 시작하는 상황",
    ),
    TopicPlan(
        topic="모기는 왜 사람 많은데 꼭 나를 고를까",
        wiki_query="모기",
        stock_queries=["mosquito macro close up", "mosquito on skin", "person swatting mosquito"],
        category="everyday",
        audience_angle="여름밤마다 반복되는 모기 선택의 불공평함",
        comedy_angle="이산화탄소와 체온을 따라 좌석을 고르는 무단 예약 손님",
    ),
    TopicPlan(
        topic="GPS는 왜 길치인 나보다 내 위치를 잘 알까",
        wiki_query="GPS",
        stock_queries=["smartphone GPS navigation", "satellite earth animation", "person lost with map"],
        category="technology",
        audience_angle="지도 앱 없이는 낯선 골목도 어려운 일상",
        comedy_angle="하늘의 위성 여러 대가 내 위치 하나를 두고 단체 계산하는 상황",
    ),
)


def _normalized(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def eligible_topic_plans(recent_topics: Iterable[str]) -> List[TopicPlan]:
    """최근 업로드와 겹치지 않는 검증 주제만 반환한다."""
    recent = [_normalized(item) for item in recent_topics if item]
    eligible = []
    for plan in VERIFIED_TOPICS:
        current = _normalized(plan.topic)
        source_key = _normalized(plan.wiki_query)
        if any(
            SequenceMatcher(None, current, old).ratio() >= 0.72
            or (source_key and source_key in old)
            for old in recent
        ):
            continue
        eligible.append(plan)
    return eligible or list(VERIFIED_TOPICS)

