"""위키백과 공개 API에서 대본의 검증 근거를 가져온다."""

import logging
from typing import Optional

import requests

from models import KnowledgeSource

LOGGER = logging.getLogger(__name__)


class KnowledgeError(RuntimeError):
    pass


def _fetch_from_wikipedia(query: str, language: str) -> Optional[KnowledgeSource]:
    endpoint = f"https://{language}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": 1,
        "prop": "extracts|info",
        "explaintext": 1,
        "exintro": 1,
        "exchars": 6000,
        "inprop": "url",
        "format": "json",
        "formatversion": 2,
        "origin": "*",
    }
    response = requests.get(
        endpoint,
        params=params,
        headers={"User-Agent": "OriginalShortsMVP/1.0 (educational video research)"},
        timeout=30,
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", [])
    if not pages:
        return None
    page = pages[0]
    extract = " ".join(str(page.get("extract", "")).split())
    if len(extract) < 350:
        return None
    return KnowledgeSource(
        title=str(page.get("title", query)),
        url=str(page.get("fullurl", "")),
        extract=extract,
        language=language,
    )


def research_topic(query: str) -> KnowledgeSource:
    errors = []
    for language in ("ko", "en"):
        try:
            source = _fetch_from_wikipedia(query, language)
            if source:
                return source
        except Exception as exc:
            errors.append(f"{language}: {exc}")
            LOGGER.warning("위키백과 자료 조회 실패(%s): %s", language, exc)
    raise KnowledgeError("검증 가능한 위키백과 자료를 찾지 못했습니다. " + " | ".join(errors))

