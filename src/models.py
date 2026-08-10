from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class TopicPlan:
    topic: str
    wiki_query: str
    stock_queries: List[str]
    category: str = "science"
    trend_reason: str = ""
    audience_angle: str = ""
    comedy_angle: str = ""


@dataclass
class KnowledgeSource:
    title: str
    url: str
    extract: str
    language: str
    license_name: str = "CC BY-SA 4.0"


@dataclass
class ScriptPackage:
    title: str
    hook: str
    narration: str
    description_intro: str
    midpoint_hook: str = ""
    closing_loop: str = ""
    engagement_question: str = ""
    comedy_beat: str = ""
    tags: List[str] = field(default_factory=list)
    caption_translations: List[str] = field(default_factory=list)


@dataclass
class StockClip:
    path: Path
    provider: str
    source_url: str
    creator: str = ""

