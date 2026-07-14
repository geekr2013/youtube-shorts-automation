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


class GeminiError(RuntimeError):
    pass


class GeminiWriter:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            raise GeminiError("GEMINI_API_KEY가 없습니다.")
        self.requested_model = model or os.getenv("GEMINI_MODEL", "")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "OriginalShortsMVP/1.0"})
        self._model_candidates: Optional[List[str]] = None

    def _discover_models(self) -> List[str]:
        if self._model_candidates is not None:
            return self._model_candidates

        available: List[str] = []
        try:
            response = self.session.get(
                f"{API_BASE}/models", params={"key": self.api_key}, timeout=20
            )
            response.raise_for_status()
            for item in response.json().get("models", []):
                methods = item.get("supportedGenerationMethods", [])
                if "generateContent" not in methods:
                    continue
                name = item.get("name", "").replace("models/", "")
                if "flash" in name and "image" not in name and "tts" not in name:
                    available.append(name)
        except Exception as exc:
            LOGGER.warning("Gemini 모델 목록 조회 실패, 기본 후보를 사용합니다: %s", exc)

        preferred = [
            self.requested_model,
            "gemini-3.5-flash",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
        ]
        ordered: List[str] = []
        for name in preferred + available:
            if name and name not in ordered and (not available or name in available):
                ordered.append(name)
        if not ordered:
            ordered = [name for name in preferred if name]
        self._model_candidates = ordered[:6]
        return self._model_candidates

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

    def _generate(self, prompt: str, schema: Dict[str, Any], temperature: float) -> Dict[str, Any]:
        errors: List[str] = []
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        for model in self._discover_models():
            try:
                response = self.session.post(
                    f"{API_BASE}/models/{model}:generateContent",
                    params={"key": self.api_key},
                    json=payload,
                    timeout=90,
                )
                response.raise_for_status()
                candidates = response.json().get("candidates") or []
                parts = candidates[0]["content"]["parts"] if candidates else []
                text = "".join(part.get("text", "") for part in parts)
                if not text:
                    raise GeminiError("빈 응답")
                LOGGER.info("Gemini 모델 사용: %s", model)
                return self._parse_json(text)
            except Exception as exc:
                errors.append(f"{model}: {exc}")
                LOGGER.warning("Gemini 후보 모델 실패: %s", model)
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
            "type": "OBJECT",
            "properties": {
                "topic": {"type": "STRING"},
                "wiki_query": {"type": "STRING"},
                "stock_queries": {"type": "ARRAY", "items": {"type": "STRING"}},
                "category": {"type": "STRING"},
                "trend_reason": {"type": "STRING"},
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
        return TopicPlan(
            topic=str(result["topic"]).strip(),
            wiki_query=str(result["wiki_query"]).strip(),
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
- 자료에 없는 숫자, 추정, 최신 뉴스, 건강·투자 조언은 넣지 않는다.
- '충격', '무조건', '소름', '역대급' 같은 과장과 구독 요청을 쓰지 않는다.
- title은 44자 이내의 자연스러운 한국어이며 #shorts를 포함하지 않는다.
- description_intro는 영상의 교육적 가치를 설명하는 2문장이다.
- tags는 한국어 중심의 관련 태그 5~8개이며 # 기호는 제외한다.
- 기계적 목록 낭독이 아니라 관찰과 해설이 있는 이야기로 쓴다.
"""
        schema = {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING"},
                "hook": {"type": "STRING"},
                "narration": {"type": "STRING"},
                "description_intro": {"type": "STRING"},
                "tags": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["title", "hook", "narration", "description_intro", "tags"],
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
            tags=tags[:8],
        )
