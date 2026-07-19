"""검증 가능한 자료와 영상 검색어를 미리 연결한 편집 주제 목록."""

import re
from difflib import SequenceMatcher
from typing import Iterable, List

from models import TopicPlan


VERIFIED_TOPICS = (
    TopicPlan(
        topic="QR 코드는 왜 일부가 가려져도 읽힐까",
        wiki_query="QR 코드",
        stock_queries=["QR code scan smartphone", "damaged QR code", "barcode scanner close up"],
        category="technology",
    ),
    TopicPlan(
        topic="오로라는 왜 극지방의 밤하늘에서 잘 보일까",
        wiki_query="오로라",
        stock_queries=["aurora borealis vertical", "northern lights sky", "polar night landscape"],
        category="nature",
    ),
    TopicPlan(
        topic="문어는 어떻게 피부색과 무늬를 바꿀까",
        wiki_query="문어",
        stock_queries=["octopus camouflage underwater", "octopus skin close up", "octopus coral reef"],
        category="nature",
    ),
    TopicPlan(
        topic="구름은 무거운데 어떻게 하늘에 떠 있을까",
        wiki_query="구름",
        stock_queries=["cumulus clouds aerial", "cloud timelapse sky", "mist water droplets"],
        category="nature",
    ),
    TopicPlan(
        topic="번개는 구름 속 전하를 어떻게 방전할까",
        wiki_query="번개",
        stock_queries=["lightning storm vertical", "storm clouds lightning", "lightning slow motion"],
        category="science",
    ),
    TopicPlan(
        topic="무지개는 왜 둥근 원의 일부처럼 보일까",
        wiki_query="무지개",
        stock_queries=["rainbow sky vertical", "rainbow after rain", "water prism rainbow"],
        category="nature",
    ),
    TopicPlan(
        topic="달은 왜 지구에서 늘 비슷한 면으로 보일까",
        wiki_query="달",
        stock_queries=["moon surface telescope", "full moon night vertical", "earth moon animation"],
        category="space",
    ),
    TopicPlan(
        topic="태풍의 눈은 왜 주변보다 비교적 고요할까",
        wiki_query="태풍",
        stock_queries=["typhoon satellite storm", "hurricane eye clouds", "tropical storm ocean"],
        category="nature",
    ),
    TopicPlan(
        topic="나침반 바늘은 왜 북쪽을 가리킬까",
        wiki_query="나침반",
        stock_queries=["compass needle close up", "compass navigation forest", "magnetic compass macro"],
        category="science",
    ),
    TopicPlan(
        topic="소리는 왜 우주 공간에서 전달되지 않을까",
        wiki_query="소리",
        stock_queries=["sound wave speaker close up", "astronaut space vertical", "audio waveform studio"],
        category="science",
    ),
    TopicPlan(
        topic="표면장력은 어떻게 물방울을 둥글게 만들까",
        wiki_query="표면장력",
        stock_queries=["water droplet macro", "water surface tension", "raindrop slow motion"],
        category="science",
    ),
    TopicPlan(
        topic="철새는 먼 이동 경로를 어떻게 찾을까",
        wiki_query="철새",
        stock_queries=["migratory birds flying", "bird flock sunset vertical", "birds navigation sky"],
        category="nature",
    ),
    TopicPlan(
        topic="나이테는 나무가 자란 환경을 어떻게 기록할까",
        wiki_query="나이테",
        stock_queries=["tree rings close up", "wood grain macro", "forest seasons timelapse"],
        category="nature",
    ),
    TopicPlan(
        topic="카멜레온은 왜 몸 색깔을 바꿀까",
        wiki_query="카멜레온",
        stock_queries=["chameleon color change", "chameleon skin close up", "chameleon branch vertical"],
        category="nature",
    ),
    TopicPlan(
        topic="파도는 물이 아닌 에너지를 어떻게 옮길까",
        wiki_query="파도",
        stock_queries=["ocean wave slow motion", "sea waves vertical", "water ripple close up"],
        category="science",
    ),
    TopicPlan(
        topic="지진파는 지구 내부를 어떻게 통과할까",
        wiki_query="지진파",
        stock_queries=["seismic wave animation", "seismograph close up", "earth layers animation"],
        category="science",
    ),
    TopicPlan(
        topic="화산재는 왜 비행기에 위험할까",
        wiki_query="화산재",
        stock_queries=["volcanic ash eruption", "airplane clouds vertical", "volcano plume close up"],
        category="science",
    ),
    TopicPlan(
        topic="자석은 왜 같은 극끼리 밀어낼까",
        wiki_query="자석",
        stock_queries=["magnet poles experiment", "magnetic field close up", "magnets science experiment"],
        category="science",
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
        if any(SequenceMatcher(None, current, old).ratio() >= 0.72 for old in recent):
            continue
        eligible.append(plan)
    return eligible or list(VERIFIED_TOPICS)

