"""위키백과 공개 API에서 대본의 검증 근거를 가져온다."""

import logging
import re
from typing import Optional

import requests

from models import KnowledgeSource

LOGGER = logging.getLogger(__name__)


class KnowledgeError(RuntimeError):
    pass


def _normalized(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def _select_wikipedia_page(pages, query: str = ""):
    """검색 순위와 제목 관련성을 함께 보고 가장 직접적인 문서를 고른다."""
    usable_pages = []
    normalized_query = _normalized(query)
    for page in pages:
        extract = " ".join(str(page.get("extract", "")).split())
        if len(extract) >= 300:
            rank = int(page.get("index", 999999))
            title = _normalized(str(page.get("title", "")))
            direct_title_match = int(
                bool(normalized_query)
                and (normalized_query in title or title in normalized_query)
            )
            usable_pages.append((-direct_title_match, rank, -len(extract), page, extract))
    if not usable_pages:
        return None
    _, _, _, page, extract = min(
        usable_pages,
        key=lambda item: (item[0], item[1], item[2]),
    )
    return page, extract


def _source_from_page(page, query: str, language: str) -> Optional[KnowledgeSource]:
    if page.get("missing") is not None:
        return None
    extract = " ".join(str(page.get("extract", "")).split())
    if len(extract) < 300:
        return None
    return KnowledgeSource(
        title=str(page.get("title", query)),
        url=str(page.get("fullurl", "")),
        extract=extract,
        language=language,
    )


def _fetch_exact_from_wikipedia(title: str, language: str) -> Optional[KnowledgeSource]:
    endpoint = f"https://{language}.wikipedia.org/w/api.php"
    response = requests.get(
        endpoint,
        params={
            "action": "query",
            "titles": title,
            "redirects": 1,
            "prop": "extracts|info",
            "explaintext": 1,
            "exchars": 7000,
            "inprop": "url",
            "format": "json",
            "formatversion": 2,
            "origin": "*",
        },
        headers={"User-Agent": "OriginalShortsMVP/2.0 (educational video research)"},
        timeout=30,
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", [])
    if not pages:
        return None
    return _source_from_page(pages[0], title, language)


def _fetch_from_wikipedia(query: str, language: str) -> Optional[KnowledgeSource]:
    endpoint = f"https://{language}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": 10,
        "gsrnamespace": 0,
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
        headers={"User-Agent": "OriginalShortsMVP/2.0 (educational video research)"},
        timeout=30,
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", [])
    if not pages:
        return None
    selected = _select_wikipedia_page(pages, query)
    if not selected:
        return None
    page, extract = selected
    return _source_from_page({**page, "extract": extract}, query, language)


def research_exact_topic(title: str) -> KnowledgeSource:
    """편집 목록에 등록된 한국어 위키백과 문서를 제목으로 직접 가져온다."""
    try:
        source = _fetch_exact_from_wikipedia(title, "ko")
        if source:
            return source
    except Exception as exc:
        LOGGER.warning("위키백과 정확 문서 조회 실패(%s): %s", title, exc)
        raise KnowledgeError(f"검증 문서 '{title}'를 직접 가져오지 못했습니다: {exc}") from exc
    raise KnowledgeError(f"검증 문서 '{title}'가 없거나 본문이 부족합니다.")


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

