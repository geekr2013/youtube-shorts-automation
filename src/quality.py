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
TOPIC_STOPWORDS = {"이유", "원리", "과정", "방법", "무엇", "어떻게", "정체", "사실"}


class QualityGateError(RuntimeError):
    pass


def _normalized(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def _topic_terms(text: str):
    suffixes = ("에서는", "에서", "으로", "하는", "되는", "처럼", "까지", "부터", "에게", "한테", "로", "인", "이", "가", "은", "는", "을", "를", "의")
    terms = []
    for raw in re.findall(r"[0-9A-Za-z가-힣]{2,}", text.lower()):
        term = raw
        for suffix in suffixes:
            if term.endswith(suffix) and len(term) - len(suffix) >= 2:
                term = term[: -len(suffix)]
                break
        if term not in TOPIC_STOPWORDS and term not in terms:
            terms.append(term)
    return terms


def source_is_relevant(plan: TopicPlan, source: KnowledgeSource) -> bool:
    corpus = _normalized(f"{source.title} {source.extract[:2400]}")
    terms = _topic_terms(plan.topic)
    if not terms:
        return bool(_normalized(source.title))
    matches = sum(1 for term in terms if _normalized(term) in corpus)
    required = 2 if len(terms) >= 2 else 1
    return matches >= required


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
    if not script.hook.endswith(("?", "？")):
        raise QualityGateError("첫 문장 훅이 질문형이 아닙니다.")
    midpoint_position = script.narration.find(script.midpoint_hook)
    midpoint_ratio = midpoint_position / max(1, narration_length)
    if len(script.midpoint_hook) < 8 or not 0.32 <= midpoint_ratio <= 0.68:
        raise QualityGateError("중간 반전 훅이 대본 중앙에 포함되지 않았습니다.")
    if len(script.closing_loop) < 8 or not script.narration.endswith(script.closing_loop):
        raise QualityGateError("마지막 문장이 시작 훅으로 이어지는 루프 구조가 아닙니다.")
    if not script.closing_loop.endswith(("처음 장면을 다시 보면…", "처음 장면을 다시 보면...")):
        raise QualityGateError("루프 문장이 첫 장면으로 자연스럽게 연결되지 않습니다.")
    if not 15 <= len(script.engagement_question) <= 45 or not script.engagement_question.endswith(("?", "？")):
        raise QualityGateError("댓글 참여 질문이 자연스러운 질문형 문장이 아닙니다.")
    if not 8 <= len(script.title) <= 44:
        raise QualityGateError("제목 길이가 기준 밖입니다.")
    if not 5 <= len(script.tags) <= 8:
        raise QualityGateError("태그 수가 기준 밖입니다.")
    if not source.url.startswith("https://") or len(source.extract) < 350:
        raise QualityGateError("검증 자료가 부족합니다.")
    if not source_is_relevant(plan, source):
        raise QualityGateError("주제와 검증 자료의 핵심 내용이 일치하지 않습니다.")

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

