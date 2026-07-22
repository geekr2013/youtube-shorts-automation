"""Gemini? ??? ??? ???, ?? ?? ??? ?? ??? ????."""

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
    """AI? ??? ??? ??? ??? ? ???? ???? ????."""
    narration = re.sub(r"\s+", " ", narration).strip()
    closing_loop = re.sub(r"\s+", " ", closing_loop).strip()
    valid_suffixes = ("?? ??? ?? ???", "?? ??? ?? ??...")
    if closing_loop.endswith(valid_suffixes) and narration.endswith(closing_loop):
        return narration, closing_loop

    fallback = "? ??? ?? ?? ??? ?? ???"
    if closing_loop and narration.endswith(closing_loop):
        prefix = narration[: -len(closing_loop)].rstrip()
    else:
        prefix = narration
        last_break = max(prefix.rfind(mark) for mark in (". ", "? ", "! ", "? "))
        if last_break >= int(len(prefix) * 0.65):
            prefix = prefix[: last_break + 1].rstrip()
    return f"{prefix} {fallback}".strip(), fallback


def normalize_question_hook(narration: str, hook: str) -> Tuple[str, str]:
    """AI? ???? ??? ?? ??? ??? ? ????? ??? ?? ??."""
    narration = re.sub(r"\s+", " ", narration).strip()
    hook = re.sub(r"\s+", " ", hook).strip()
    if hook.endswith(("?", "?")):
        return narration, hook

    fallback = "? ??? ? ????? ?? ?????"
    if len(narration) + len(fallback) + 1 <= 390:
        narration = f"{fallback} {narration}"
    elif hook and narration.startswith(hook):
        narration = f"{fallback} {narration[len(hook):].lstrip()}".strip()
    else:
        first_sentence = re.split(r"(?<=[.!??])\s+", narration, maxsplit=1)
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
            raise GeminiError("?? ??? AI ?? ??? ????.")
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
                raise GeminiError("Gemini ???? JSON? ?? ?????.")
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
                    raise GeminiError("? ??")
                LOGGER.info("GitHub Models ??: %s", self.github_model)
                return self._parse_json(text)
            except Exception as exc:
                errors.append(f"github/{self.github_model}: {exc}")
                LOGGER.warning("GitHub Models ??, Gemini? ??: %s", exc)

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
                        raise GeminiError("? ??")
                    LOGGER.info("Gemini ?? ??: %s", model)
                    return self._parse_json(text)
                except Exception as exc:
                    errors.append(f"key#{key_number}/{model}: {exc}")
                    LOGGER.warning(
                        "Gemini ?? ??(key=%s, model=%s): %s",
                        key_number,
                        model,
                        exc,
                    )
        raise GeminiError("Gemini ?? ?? - " + " | ".join(errors[-3:]))

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
            raise GeminiError("??? ?? ??? ????.")
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
??? ??? ??? ?? ??? ?? ????.
?? ?? ??? ??? ?? ??? ??? ???. ?? ?? ??? ?? ??? ???.
?? ??? ???? ?? ?? ??? ???? ?? ???? ?? ???? ??? ???? ???.

?? ??: {json.dumps(signals, ensure_ascii=False)}
?? ?? ??(?? ??): {json.dumps(list(recent_topics)[-30:], ensure_ascii=False)}
??? ????? ??? ??: {json.dumps(list(top_performers)[:5], ensure_ascii=False)}
??? ?? ???? ??? ?? ??? ??: {json.dumps(candidate_rows, ensure_ascii=False)}

??:
- candidate_ids?? ?? id? ??, ?? ?? ??????? ????? ??? ??? ?? {max(1, limit)}?? ????.
- ?? ?? ??? ??? ??? ?? ???.
- ?? ???? ??? ???? ??? ? ?? ?? ???? ??? ????.
- trend_reason?? 1?? ?? ??? ?? ?? ? ???? ??.
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
                    trend_reason=reason if position == 0 else "??? ?? ??",
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
            "\n?? ?? ???? ??? ??? ??? ???:\n- " + "\n- ".join(feedback[:6])
            if feedback
            else ""
        )
        prompt = f"""
??? ??? 1? ?? ??? ???. ?? '?? ??'? ??? ??? ??? ??? ? ???? ??? ????.

??: {plan.topic}
?? ?? ??: {source.title}
?? ?? URL: {source.url}
?? ?? ??:
{source.extract[:6000]}
{feedback_text}

?? ??:
- narration? ??? ?? ?? 220~320??? 42~55? ????.
- ? ??? ??? ?? ??? hook? ??? ??.
- 3~5?? ??? ??? ???????? ???? ????.
- midpoint_hook? ??? ???? ?? ?? ?? ?? ? ????. narration? 40~60% ??? ?? ??? ???.
- midpoint_hook? ??? ?? ??? ??? ? ?? ???? ??, ?? ?? ?????????? ???? ???.
- midpoint_hook? ?? ??? ?? ??, '??? ?? ??? ???' ?? ??? ??? ???? ???.
- closing_loop? narration? ??? ???? ??? '?? ??? ?? ???'?? ???. ?? ??? ? ??? ???? ????? ???? ??.
- engagement_question? ???? ?? ???? ??? ?? ?? ? ?? ?? ????. ??? ????? ? ?? ??? ???? ???.
- engagement_question? 15~45???, '???? ? ?? ??? ?? ??? ??????'?? ?? ?? ? ?? ??.
- ??? ?? ??, ??, ?? ??, ????? ??? ?? ???.
- ?? ???? ??? ???? ???? ??? ???. ??? ?? ???? ?? ????? ?? ???.
- '??', '???', '??', '???' ?? ??? ?? ??? ?? ???.
- title? 44? ??? ????? ????? #shorts? ???? ???.
- description_intro? ??? ??? ??? ???? 2????.
- tags? ??? ??? ?? ?? 5~8??? # ??? ????.
- ??? ?? ??? ??? ??? ??? ?? ???? ??.
- ???? ??? ? ????? ?? ?? ? ??? ? ??? ?? ?? ???? ??? ??? ??.
- ??, ???, ?? ???? ???? ???? ?? ??? ?? ???.
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
            first_sentence = re.split(r"(?<=[.!??])\s+", narration, maxsplit=1)[0].strip()
            hook = first_sentence or hook
        narration, hook = normalize_question_hook(narration, hook)

        tags = []
        for raw in result.get("tags", []):
            tag = re.sub(r"[#<>]", "", str(raw)).strip()
            if tag and tag not in tags:
                tags.append(tag[:30])
        for fallback in (plan.topic, plan.category, "??", "??", "??"):
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
        """?? ?? ??? ??? ?? ??? ?? ?? ??? ???."""
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
        last_issue = "?? ?? ?? ?? ??? ???? ????."
        for attempt in range(2):
            prompt = f"""
??? ??? ?? ??? ?? ?? ????.
?? ?? ??? ?? ??? ?? ??? ????? ?? ???? ????.

?? ??(JSON):
{json.dumps(source_chunks, ensure_ascii=False)}

??:
- translations ??? ??? {len(source_chunks)}??? ??.
- ? ??? ???? ?? ? ??? ????. ???? ??? ???.
- ??, ??, ????? ???? ??? ???? ???.
- ??? ????? ???? ???? ????? ??.
- ? ??? ???? 52?, ?? 76? ??? ??.
- ???, ???, ???, ??? ?? ???.
"""
            if attempt:
                prompt += f"\n?? ?? ??: {last_issue} ??? ??? ?? ????.\n"
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
                f"?? {len(source_chunks)}?, ?? {len(translations)}? ?? ?? ?? ??"
            )
        raise GeminiError("?? ?? ?? ??? ???? ?????: " + last_issue)

    def review_script(
        self,
        plan: TopicPlan,
        source: KnowledgeSource,
        script: ScriptPackage,
    ) -> Dict[str, Any]:
        """??? ?? ?????? ????? ???? ??? ???? ?????."""
        prompt = f"""
??? ??? ?? ??? ?? ????. ?? ??? ??? ??? ???? ????.

??: {plan.topic}
?? ?? ??: {source.title}
?? ?? ??: {source.extract[:6000]}
?? ???: {json.dumps(script.__dict__, ensure_ascii=False)}

?? ??:
- narration? ?? ??? ??? ????? ?? ??? ?? ?????? ??.
- ? ??? ??? ?????? ??, ???? ?? ? ?? ??? ???? ? ??.
- ?? ??? ????? ???? ??? ????? ?? ??? ??.
- ?? ??? ?? ??? ?? ???, ??? ? ???? ????? ???? ??.
- ?? ???? ??? ??? ? ??? ?? ???????? ??? ??? ??.
- score? ??? ?? ???? ? ???? 0~100?? ????. 80? ??? ????.
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

