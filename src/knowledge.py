"""위키백과 공개 API에서 대본의 검증 근거를 가져온다."""

import logging
from typing import Optional

import requests

from models import KnowledgeSource

LOGGER = logging.getLogger(__name__)


class KnowledgeError(RuntimeError):
    pass


def _select_wikipedia_page(pages):
    """검색 결과의 글 길이가 아니라 위키백과 검색 순위를 우선한다."""
    usable_pages = []
    for page in pages:
        extract = " ".join(str(page.get("extract", "")).split())
        if len(extract) >= 300:
            rank = int(page.get("index", 999999))
            usable_pages.append((rank, -len(extract), page, extract))
    if not usable_pages:
        return None
    _, _, page, extract = min(usable_pages, key=lambda item: (item[0], item[1]))
    return page, extract


def _fetch_from_wikipedia(query: str, language: str) -> Optional[KnowledgeSource]:
    endpoint = f"https://{language}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": 3,
        "prop": "extracts|info",
        "explaintext": 1,
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
    selected = _select_wikipedia_page(pages)
    if not selected:
        return None
    page, extract = selected
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

