"""저품질·고위험·반복 콘텐츠가 업로드되지 않도록 차단한다."""

import re
from difflib import SequenceMatcher
from typing import Iterable

from models import KnowledgeSource, ScriptPackage, TopicPlan

RISK_TERMS = {
    "대통령", "선거", "정당", "전쟁", "사망", "살인", "범죄", "마약",
    "도박", "코인", "주식 추천", "투자 추천", "치료법", "암 치료", "연예인",
}
HYPE_TERMS = {"충격", "역대급", "무조건", "소름", "실화냐", "미쳤다"}


class QualityGateError(RuntimeError):
    pass


def _normalized(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def validate_package(
    plan: TopicPlan,
    script: ScriptPackage,
    source: KnowledgeSource,
    recent_topics: Iterable[str],
) -> None:
    narration_length = len(script.narration)
    if not 200 <= narration_length <= 390:
        raise QualityGateError(f"대본 길이가 기준 밖입니다: {narration_length}자")
    if not script.narration.startswith(script.hook.rstrip(". ")) and script.hook not in script.narration[:100]:
        raise QualityGateError("첫 문장에 훅이 포함되지 않았습니다.")
    if not 8 <= len(script.title) <= 44:
        raise QualityGateError("제목 길이가 기준 밖입니다.")
    if not 5 <= len(script.tags) <= 8:
        raise QualityGateError("태그 수가 기준 밖입니다.")
    if not source.url.startswith("https://") or len(source.extract) < 350:
        raise QualityGateError("검증 자료가 부족합니다.")

    headline = f"{plan.topic} {script.title}"
    combined = f"{headline} {script.narration}"
    blocked = sorted(term for term in RISK_TERMS if term in headline)
    blocked.extend(sorted(term for term in HYPE_TERMS if term in combined))
    if blocked:
        raise QualityGateError("안전 기준에 걸린 표현: " + ", ".join(blocked))

    current = _normalized(plan.topic)
    for old in recent_topics:
        ratio = SequenceMatcher(None, current, _normalized(old)).ratio()
        if ratio >= 0.78:
            raise QualityGateError(f"최근 주제와 너무 비슷합니다: {old}")

