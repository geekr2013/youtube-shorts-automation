"""Gemini를 이용해 주제를 고르고, 출처 범위 안에서 원본 대본을 작성한다."""

import json
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional

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

    def select_topic(
        self,
        trend_signals: Iterable[Dict[str, Any]],
        recent_topics: Iterable[str],
        top_performers: Iterable[str],
        evergreen_seeds: Iterable[str],
    ) -> TopicPlan:
        signals = list(trend_signals)[:20]
        prompt = f"""
당신은 한국어 유튜브 교육 쇼츠의 책임 편집자다.
아래 인기 신호는 소재 탐색에만 사용하고 제목이나 영상을 복제하지 않는다.

인기 신호: {json.dumps(signals, ensure_ascii=False)}
최근 사용 주제(반복 금지): {json.dumps(list(recent_topics)[-30:], ensure_ascii=False)}
성과가 상대적으로 좋았던 주제: {json.dumps(list(top_performers)[:5], ensure_ascii=False)}
안전한 상시 후보: {json.dumps(list(evergreen_seeds), ensure_ascii=False)}

조건:
- 45~58초 안에 설명 가능한 과학·기술·자연·역사 상식 하나를 고른다.
- 정치, 사건사고, 연예인, 의료 조언, 투자, 논쟁, 공포 조장 주제는 제외한다.
- 한국어 위키백과에서 단일 문서로 사실을 확인할 수 있어야 한다.
- 시청자가 첫 2초에 궁금해할 질문이 생기고, 스톡 영상으로 표현 가능해야 한다.
- stock_queries는 Pexels에서 찾기 쉬운 영어 검색어 3개로 쓴다.
- trend_reason에는 선택 이유를 과장 없이 한 문장으로 쓴다.
"""
        schema = {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "wiki_query": {"type": "string"},
                "stock_queries": {"type": "array", "items": {"type": "string"}},
                "category": {"type": "string"},
                "trend_reason": {"type": "string"},
            },
            "required": ["topic", "wiki_query", "stock_queries", "category", "trend_reason"],
        }
        result = self._generate(prompt, schema, temperature=0.55)
        queries = [str(item).strip() for item in result.get("stock_queries", []) if str(item).strip()]
        for fallback in ("science nature", "technology close up", "natural world"):
            if len(queries) >= 3:
                break
            if fallback not in queries:
                queries.append(fallback)
        topic = str(result.get("topic", "")).strip()
        if not topic:
            raise GeminiError("AI 응답에 주제가 없습니다.")
        return TopicPlan(
            topic=topic,
            wiki_query=str(result.get("wiki_query") or topic).strip(),
            stock_queries=queries[:4],
            category=str(result.get("category", "science")).strip(),
            trend_reason=str(result.get("trend_reason", "")).strip(),
        )

    def write_script(self, plan: TopicPlan, source: KnowledgeSource) -> ScriptPackage:
        prompt = f"""
당신은 한국어 1분 지식 영상의 작가다. 아래 '검증 자료'에 명시된 사실만 사용해 완전히 새 문장으로 대본을 작성한다.

주제: {plan.topic}
검증 자료 제목: {source.title}
검증 자료 URL: {source.url}
검증 자료 본문:
{source.extract[:6000]}

작성 규칙:
- narration은 한국어 공백 포함 230~360자이며 45~58초 분량이다.
- 첫 문장은 의외성 있는 질문형 hook과 같아야 한다.
- 3~5개의 구체적 사실을 원인→과정→결과 흐름으로 설명한다.
- midpoint_hook은 자료로 확인되는 반전 또는 관점 전환 한 문장이다. narration의 40~60% 지점에 문장 그대로 넣는다.
- midpoint_hook은 매번 주제에 맞게 쓰고, '하지만 진짜 놀라운 사실은' 같은 상투적 문구를 반복하지 않는다.
- closing_loop는 narration의 마지막 문장이다. 첫 질문의 핵심 소재로 자연스럽게 돌아가 영상이 다시 시작돼도 이어지게 쓴다.
- engagement_question은 시청자가 자기 경험이나 생각을 짧게 답할 수 있는 주제 관련 질문 한 문장이다.
- 자료에 없는 숫자, 추정, 최신 뉴스, 건강·투자 조언은 넣지 않는다.
- '충격', '무조건', '소름', '역대급' 같은 과장과 구독 요청을 쓰지 않는다.
- title은 44자 이내의 자연스러운 한국어이며 #shorts를 포함하지 않는다.
- description_intro는 영상의 교육적 가치를 설명하는 2문장이다.
- tags는 한국어 중심의 관련 태그 5~8개이며 # 기호는 제외한다.
- 기계적 목록 낭독이 아니라 관찰과 해설이 있는 이야기로 쓴다.
- 음성으로 읽었을 때 자연스럽게 숨을 고를 수 있도록 짧은 문장과 쉼표를 적절히 쓴다.
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
        hook = re.sub(r"\s+", " ", str(result["hook"])).strip()
        if not narration.startswith(hook.rstrip(". ")):
            first_sentence = re.split(r"(?<=[.!?？])\s+", narration, maxsplit=1)[0].strip()
            hook = first_sentence or hook

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
            closing_loop=re.sub(r"\s+", " ", str(result["closing_loop"])).strip(),
            engagement_question=re.sub(
                r"\s+", " ", str(result["engagement_question"])
            ).strip(),
            tags=tags[:8],
        )

