"""Gemini를 이용해 주제를 고르고, 출처 범위 안에서 원본 대본을 작성한다."""

import json
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from models import KnowledgeSource, ScriptPackage, TopicPlan

LOGGER = logging.getLogger(__name__)
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GITHUB_MODELS_ENDPOINT = "https://models.github.ai/inference/chat/completions"
DEFAULT_MODELS = (
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)


class GeminiError(RuntimeError):
    pass


def normalize_loop_ending(narration: str, closing_loop: str) -> Tuple[str, str]:
    """AI가 형식을 놓쳐도 마지막 장면이 첫 질문으로 이어지게 보정한다."""
    narration = re.sub(r"\s+", " ", narration).strip()
    closing_loop = re.sub(r"\s+", " ", closing_loop).strip()
    valid_suffixes = ("처음 장면을 다시 보면…", "처음 장면을 다시 보면...")
    if closing_loop.endswith(valid_suffixes) and narration.endswith(closing_loop):
        return narration, closing_loop

    fallback = "이 사실을 알고 처음 장면을 다시 보면…"
    if closing_loop and narration.endswith(closing_loop):
        prefix = narration[: -len(closing_loop)].rstrip()
    else:
        prefix = narration
        last_break = max(prefix.rfind(mark) for mark in (". ", "? ", "! ", "。 "))
        if last_break >= int(len(prefix) * 0.65):
            prefix = prefix[: last_break + 1].rstrip()
    return f"{prefix} {fallback}".strip(), fallback


def normalize_question_hook(narration: str, hook: str) -> Tuple[str, str]:
    """AI가 질문형을 놓치면 사실 문장을 보존한 채 자연스러운 질문을 앞에 둔다."""
    narration = re.sub(r"\s+", " ", narration).strip()
    hook = re.sub(r"\s+", " ", hook).strip()
    if hook.endswith(("?", "？")):
        return narration, hook

    fallback = "이 현상이 왜 일어나는지 알고 계셨나요?"
    if len(narration) + len(fallback) + 1 <= 390:
        narration = f"{fallback} {narration}"
    elif hook and narration.startswith(hook):
        narration = f"{fallback} {narration[len(hook):].lstrip()}".strip()
    else:
        first_sentence = re.split(r"(?<=[.!?？])\s+", narration, maxsplit=1)
        narration = f"{fallback} {first_sentence[-1]}".strip()
    return narration, fallback


class GeminiWriter:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_keys = list(
            dict.fromkeys(
                key
                for key in (
                    api_key or os.getenv("GEMINI_API_KEY", ""),
                    os.getenv("GOOGLE_API_KEY", ""),
                )
                if key
            )
        )
        self.github_token = os.getenv("GITHUB_MODELS_TOKEN", "")
        self.github_model = os.getenv("GITHUB_MODELS_MODEL", "openai/gpt-4.1")
        if not self.api_keys and not self.github_token:
            raise GeminiError("사용 가능한 AI 인증 정보가 없습니다.")
        self.requested_model = model or os.getenv("GEMINI_MODEL", "")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "OriginalShortsMVP/1.0"})

    def _model_candidates(self) -> List[str]:
        return list(dict.fromkeys(name for name in (self.requested_model, *DEFAULT_MODELS) if name))

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.S)
            if not match:
                raise GeminiError("Gemini 응답에서 JSON을 찾지 못했습니다.")
            return json.loads(match.group(0))

    @staticmethod
    def _extract_interaction_text(data: Dict[str, Any]) -> str:
        if isinstance(data.get("output_text"), str):
            return data["output_text"].strip()
        for step in reversed(data.get("steps") or []):
            if step.get("type") != "model_output":
                continue
            text = "".join(
                part.get("text", "")
                for part in step.get("content") or []
                if part.get("type") == "text"
            ).strip()
            if text:
                return text
        return ""

    @staticmethod
    def _extract_chat_text(data: Dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""
        return str(choices[0].get("message", {}).get("content", "")).strip()

    @staticmethod
    def _strict_schema(value: Any) -> Any:
        if isinstance(value, dict):
            result = {key: GeminiWriter._strict_schema(item) for key, item in value.items()}
            if result.get("type") == "object":
                result.setdefault("additionalProperties", False)
            return result
        if isinstance(value, list):
            return [GeminiWriter._strict_schema(item) for item in value]
        return value

    @staticmethod
    def _error_message(response: Any) -> str:
        try:
            message = response.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            message = ""
        return (message or response.text or response.reason)[:300]

    def _generate(self, prompt: str, schema: Dict[str, Any], temperature: float) -> Dict[str, Any]:
        errors: List[str] = []
        if self.github_token:
            try:
                response = self.session.post(
                    GITHUB_MODELS_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {self.github_token}",
                        "Accept": "application/vnd.github+json",
                        "Content-Type": "application/json",
                        "X-GitHub-Api-Version": "2026-03-10",
                    },
                    json={
                        "model": self.github_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "Return only one valid JSON object that follows the user's requested fields.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": temperature,
                        "max_tokens": 1800,
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "shorts_response",
                                "strict": True,
                                "schema": self._strict_schema(schema),
                            },
                        },
                    },
                    timeout=90,
                )
                if not response.ok:
                    raise GeminiError(
                        f"HTTP {response.status_code}: {self._error_message(response)}"
                    )
                text = self._extract_chat_text(response.json())
                if not text:
                    raise GeminiError("빈 응답")
                LOGGER.info("GitHub Models 사용: %s", self.github_model)
                return self._parse_json(text)
            except Exception as exc:
                errors.append(f"github/{self.github_model}: {exc}")
                LOGGER.warning("GitHub Models 실패, Gemini로 전환: %s", exc)

        payload = {
            "input": prompt,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            },
            "generation_config": {"temperature": temperature},
        }
        for key_number, api_key in enumerate(self.api_keys, start=1):
            for model in self._model_candidates():
                try:
                    payload["model"] = model
                    response = self.session.post(
                        f"{API_BASE}/interactions",
                        headers={
                            "x-goog-api-key": api_key,
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=90,
                    )
                    if not response.ok:
                        raise GeminiError(
                            f"HTTP {response.status_code}: {self._error_message(response)}"
                        )
                    text = self._extract_interaction_text(response.json())
                    if not text:
                        raise GeminiError("빈 응답")
                    LOGGER.info("Gemini 모델 사용: %s", model)
                    return self._parse_json(text)
                except Exception as exc:
                    errors.append(f"key#{key_number}/{model}: {exc}")
                    LOGGER.warning(
                        "Gemini 후보 실패(key=%s, model=%s): %s",
                        key_number,
                        model,
                        exc,
                    )
        raise GeminiError("Gemini 생성 실패 - " + " | ".join(errors[-3:]))

    def rank_topics(
        self,
        trend_signals: Iterable[Dict[str, Any]],
        recent_topics: Iterable[str],
        top_performers: Iterable[str],
        verified_candidates: Iterable[TopicPlan],
        limit: int = 6,
    ) -> List[TopicPlan]:
        signals = list(trend_signals)[:20]
        candidates = list(verified_candidates)
        if not candidates:
            raise GeminiError("검증된 주제 후보가 없습니다.")
        candidate_rows = [
            {
                "id": index,
                "topic": plan.topic,
                "source_title": plan.wiki_query,
                "category": plan.category,
                "stock_queries": plan.stock_queries,
            }
            for index, plan in enumerate(candidates)
        ]
        prompt = f"""
당신은 한국어 유튜브 교육 쇼츠의 책임 편집자다.
아래 검증 후보만 사용해 오늘 제작할 순서를 정한다. 후보 밖의 주제를 새로 만들지 않는다.
인기 신호는 시청자의 현재 관심 분야를 파악하는 참고 자료로만 쓰고 제목이나 영상을 복제하지 않는다.

인기 신호: {json.dumps(signals, ensure_ascii=False)}
최근 사용 주제(반복 금지): {json.dumps(list(recent_topics)[-30:], ensure_ascii=False)}
성과가 상대적으로 좋았던 주제: {json.dumps(list(top_performers)[:5], ensure_ascii=False)}
출처와 스톡 검색어를 사람이 미리 검토한 후보: {json.dumps(candidate_rows, ensure_ascii=False)}

조건:
- candidate_ids에는 후보 id만 넣고, 예상 시청 지속률·시각적 매력·설명 명확성 순으로 최대 {max(1, limit)}개를 정렬한다.
- 최근 사용 주제와 비슷한 후보는 뒤로 보낸다.
- 단기 유행보다 사실을 선명하게 설명할 수 있고 오래 검색되는 소재를 우선한다.
- trend_reason에는 1순위 선택 이유를 과장 없이 한 문장으로 쓴다.
"""
        schema = {
            "type": "object",
            "properties": {
                "candidate_ids": {"type": "array", "items": {"type": "integer"}},
                "trend_reason": {"type": "string"},
            },
            "required": ["candidate_ids", "trend_reason"],
        }
        result = self._generate(prompt, schema, temperature=0.35)
        ordered_ids = []
        for raw in result.get("candidate_ids", []):
            try:
                candidate_id = int(raw)
            except (TypeError, ValueError):
                continue
            if 0 <= candidate_id < len(candidates) and candidate_id not in ordered_ids:
                ordered_ids.append(candidate_id)
        ordered_ids.extend(index for index in range(len(candidates)) if index not in ordered_ids)
        reason = str(result.get("trend_reason", "")).strip()
        ranked = []
        for position, candidate_id in enumerate(ordered_ids[: max(1, limit)]):
            selected = candidates[candidate_id]
            ranked.append(
                TopicPlan(
                    topic=selected.topic,
                    wiki_query=selected.wiki_query,
                    stock_queries=list(selected.stock_queries),
                    category=selected.category,
                    trend_reason=reason if position == 0 else "검증된 편집 후보",
                )
            )
        return ranked

    def select_topic(
        self,
        trend_signals: Iterable[Dict[str, Any]],
        recent_topics: Iterable[str],
        top_performers: Iterable[str],
        verified_candidates: Iterable[TopicPlan],
    ) -> TopicPlan:
        return self.rank_topics(
            trend_signals,
            recent_topics,
            top_performers,
            verified_candidates,
            limit=1,
        )[0]

    def write_script(
        self,
        plan: TopicPlan,
        source: KnowledgeSource,
        editorial_feedback: Optional[Iterable[str]] = None,
    ) -> ScriptPackage:
        feedback = [str(item).strip() for item in (editorial_feedback or []) if str(item).strip()]
        feedback_text = (
            "\n이전 편집 검토에서 지적된 내용을 반드시 고친다:\n- " + "\n- ".join(feedback[:6])
            if feedback
            else ""
        )
        prompt = f"""
당신은 한국어 1분 지식 영상의 작가다. 아래 '검증 자료'에 명시된 사실만 사용해 완전히 새 문장으로 대본을 작성한다.

주제: {plan.topic}
검증 자료 제목: {source.title}
검증 자료 URL: {source.url}
검증 자료 본문:
{source.extract[:6000]}
{feedback_text}

작성 규칙:
- narration은 한국어 공백 포함 220~320자이며 42~55초 분량이다.
- 첫 문장은 의외성 있는 질문형 hook과 같아야 한다.
- 3~5개의 구체적 사실을 원인→과정→결과 흐름으로 설명한다.
- midpoint_hook은 자료로 확인되는 반전 또는 관점 전환 한 문장이다. narration의 40~60% 지점에 문장 그대로 넣는다.
- midpoint_hook은 주제의 핵심 원리나 결과를 더 깊게 설명해야 하며, 관련 없는 문화·일화·곁가지로 전환하지 않는다.
- midpoint_hook은 매번 주제에 맞게 쓰고, '하지만 진짜 놀라운 사실은' 같은 상투적 문구를 반복하지 않는다.
- closing_loop는 narration의 마지막 문장이며 반드시 '처음 장면을 다시 보면…'으로 끝낸다. 바로 다음에 첫 질문이 재생돼도 자연스럽게 이어져야 한다.
- engagement_question은 시청자가 관찰 경험이나 선호를 짧게 답할 수 있는 쉬운 질문이다. 지식을 시험하거나 긴 이유 설명을 요구하지 않는다.
- engagement_question은 15~45자이며, '여러분이 본 가장 신기한 구름 모양은 무엇인가요?'처럼 바로 답할 수 있게 쓴다.
- 자료에 없는 숫자, 추정, 최신 뉴스, 건강·투자 조언은 넣지 않는다.
- 다른 현상과의 비유를 원인이나 근거처럼 바꾸지 않는다. 자료가 직접 설명하지 않는 인과관계는 쓰지 않는다.
- '충격', '무조건', '소름', '역대급' 같은 과장과 구독 요청을 쓰지 않는다.
- title은 44자 이내의 자연스러운 한국어이며 #shorts를 포함하지 않는다.
- description_intro는 영상의 교육적 가치를 설명하는 2문장이다.
- tags는 한국어 중심의 관련 태그 5~8개이며 # 기호는 제외한다.
- 기계적 목록 낭독이 아니라 관찰과 해설이 있는 이야기로 쓴다.
- 음성으로 읽었을 때 자연스럽게 숨을 고를 수 있도록 한 문장을 짧게 쓰고 마침표와 쉼표를 적절히 쓴다.
- 괄호, 슬래시, 기호 나열처럼 기계음이 어색하게 읽을 표현은 쓰지 않는다.
"""
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "hook": {"type": "string"},
                "narration": {"type": "string"},
                "description_intro": {"type": "string"},
                "midpoint_hook": {"type": "string"},
                "closing_loop": {"type": "string"},
                "engagement_question": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "title",
                "hook",
                "narration",
                "description_intro",
                "midpoint_hook",
                "closing_loop",
                "engagement_question",
                "tags",
            ],
        }
        result = self._generate(prompt, schema, temperature=0.72)
        narration = re.sub(r"\s+", " ", str(result["narration"])).strip()
        narration, closing_loop = normalize_loop_ending(
            narration,
            str(result["closing_loop"]),
        )
        hook = re.sub(r"\s+", " ", str(result["hook"])).strip()
        if not narration.startswith(hook.rstrip(". ")):
            first_sentence = re.split(r"(?<=[.!?？])\s+", narration, maxsplit=1)[0].strip()
            hook = first_sentence or hook
        narration, hook = normalize_question_hook(narration, hook)

        tags = []
        for raw in result.get("tags", []):
            tag = re.sub(r"[#<>]", "", str(raw)).strip()
            if tag and tag not in tags:
                tags.append(tag[:30])
        for fallback in (plan.topic, plan.category, "지식", "과학", "교양"):
            tag = re.sub(r"[#<>]", "", str(fallback)).strip()[:30]
            if len(tags) >= 5:
                break
            if tag and tag not in tags:
                tags.append(tag)
        title = re.sub(r"#?shorts", "", str(result["title"]), flags=re.I)
        title = re.sub(r"[<>#]", "", title).strip()
        return ScriptPackage(
            title=title[:44],
            hook=hook,
            narration=narration,
            description_intro=str(result["description_intro"]).strip(),
            midpoint_hook=re.sub(r"\s+", " ", str(result["midpoint_hook"])).strip(),
            closing_loop=closing_loop,
            engagement_question=re.sub(
                r"\s+", " ", str(result["engagement_question"])
            ).strip(),
            tags=tags[:8],
        )

    def translate_caption_chunks(self, chunks: Iterable[str]) -> List[str]:
        """한글 자막 묶음과 정확히 같은 순서의 짧은 영문 자막을 만든다."""
        source_chunks = [re.sub(r"\s+", " ", str(item)).strip() for item in chunks]
        source_chunks = [item for item in source_chunks if item]
        if not source_chunks:
            return []

        schema = {
            "type": "object",
            "properties": {
                "translations": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["translations"],
        }
        last_issue = "영문 자막 수가 한글 자막과 일치하지 않습니다."
        for attempt in range(2):
            prompt = f"""
당신은 한국어 지식 쇼츠의 영문 자막 편집자다.
아래 한글 자막을 같은 순서와 같은 개수의 자연스러운 영어 자막으로 번역한다.

한글 자막(JSON):
{json.dumps(source_chunks, ensure_ascii=False)}

규칙:
- translations 배열은 반드시 {len(source_chunks)}개여야 한다.
- 각 항목은 대응하는 한글 한 항목만 번역한다. 합치거나 나누지 않는다.
- 사실, 숫자, 고유명사를 바꾸거나 설명을 덧붙이지 않는다.
- 영어권 다큐멘터리 자막처럼 간결하고 자연스럽게 쓴다.
- 한 항목은 가능하면 52자, 최대 76자 이내로 쓴다.
- 따옴표, 이모지, 머리말, 번호를 넣지 않는다.
"""
            if attempt:
                prompt += f"\n이전 결과 문제: {last_issue} 정확한 개수를 다시 확인한다.\n"
            result = self._generate(prompt, schema, temperature=0.18)
            translations = [
                re.sub(r"\s+", " ", str(item)).strip()
                for item in result.get("translations", [])
            ]
            valid = (
                len(translations) == len(source_chunks)
                and all(item and re.search(r"[A-Za-z]", item) for item in translations)
                and all(len(item) <= 90 for item in translations)
            )
            if valid:
                return translations
            last_issue = (
                f"필요 {len(source_chunks)}개, 수신 {len(translations)}개 또는 길이 기준 초과"
            )
        raise GeminiError("영문 자막 품질 기준을 통과하지 못했습니다: " + last_issue)

    def review_script(
        self,
        plan: TopicPlan,
        source: KnowledgeSource,
        script: ScriptPackage,
    ) -> Dict[str, Any]:
        """업로드 전에 사실성·문장 품질·화면 적합성을 편집자 관점으로 재검토한다."""
        prompt = f"""
당신은 한국어 지식 쇼츠의 최종 편집자다. 검증 자료와 대본을 대조해 냉정하게 검수한다.

주제: {plan.topic}
검증 자료 제목: {source.title}
검증 자료 본문: {source.extract[:6000]}
대본 패키지: {json.dumps(script.__dict__, ensure_ascii=False)}

검수 기준:
- narration의 모든 구체적 사실과 인과관계가 검증 자료로 직접 뒷받침되어야 한다.
- 첫 질문은 주제에 구체적이어야 하며, 어디에나 붙일 수 있는 상투적 질문이면 안 된다.
- 짧은 문장과 자연스러운 호흡으로 한국어 아나운서가 읽기 편해야 한다.
- 중간 전환은 핵심 설명을 깊게 만들고, 결말은 첫 장면으로 자연스럽게 이어져야 한다.
- 스톡 영상으로 장면을 구성할 수 있어야 하며 과장·낚시·구독 요청이 없어야 한다.
- score는 사람이 바로 공개해도 될 완성도를 0~100으로 평가한다. 80점 이상만 승인한다.
"""
        schema = {
            "type": "object",
            "properties": {
                "approved": {"type": "boolean"},
                "score": {"type": "integer"},
                "facts_supported": {"type": "boolean"},
                "natural_korean": {"type": "boolean"},
                "visualizable": {"type": "boolean"},
                "issues": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "approved",
                "score",
                "facts_supported",
                "natural_korean",
                "visualizable",
                "issues",
            ],
        }
        result = self._generate(prompt, schema, temperature=0.15)
        score = max(0, min(100, int(result.get("score", 0) or 0)))
        facts_supported = bool(result.get("facts_supported"))
        natural_korean = bool(result.get("natural_korean"))
        visualizable = bool(result.get("visualizable"))
        issues = [str(item).strip() for item in result.get("issues", []) if str(item).strip()]
        approved = bool(result.get("approved")) and score >= 80
        approved = approved and facts_supported and natural_korean and visualizable
        return {
            "approved": approved,
            "score": score,
            "facts_supported": facts_supported,
            "natural_korean": natural_korean,
            "visualizable": visualizable,
            "issues": issues,
        }

