"""Inspect exact Pexels IDs before locking a new recurring visual model."""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, List

from candidate_review import _sheet
from media_provider import StockMediaProvider
from visual_quality import extract_review_frames


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "model-candidate-review"
MAX_SCAN_IDS = 150
MAX_RENDERED_SOURCES = 36


def parse_source_ids(value: str) -> List[str]:
    """Parse comma-separated IDs and small inclusive numeric ranges."""
    result: List[str] = []
    seen = set()
    for token in (item.strip() for item in value.split(",")):
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            if not start_text.isdigit() or not end_text.isdigit():
                raise ValueError(f"Invalid Pexels ID range: {token}")
            start, end = int(start_text), int(end_text)
            if end < start:
                raise ValueError(f"Reversed Pexels ID range: {token}")
            values = (str(item) for item in range(start, end + 1))
        else:
            if not token.isdigit():
                raise ValueError(f"Invalid Pexels ID: {token}")
            values = (token,)
        for source_id in values:
            if source_id in seen:
                continue
            seen.add(source_id)
            result.append(source_id)
            if len(result) > MAX_SCAN_IDS:
                raise ValueError(f"Candidate scan is limited to {MAX_SCAN_IDS} IDs")
    if not result:
        raise ValueError("MODEL_CANDIDATE_SOURCE_IDS is required")
    return result


def main() -> int:
    raw_source_ids = os.getenv("MODEL_CANDIDATE_SOURCE_IDS", "").strip()
    search_query = os.getenv("MODEL_CANDIDATE_QUERY", "").strip()
    expected_creator = os.getenv("MODEL_CANDIDATE_CREATOR", "").strip()
    render = os.getenv("MODEL_CANDIDATE_RENDER", "false").lower() == "true"
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    provider = StockMediaProvider()
    discovered: Dict[str, dict] = {}
    if raw_source_ids:
        source_ids = parse_source_ids(raw_source_ids)
    elif search_query:
        for page in range(1, 3):
            for candidate in provider._search_pexels(search_query, per_page=80, page=page):
                source_id = str(candidate.get("source_id") or "")
                if source_id:
                    discovered.setdefault(source_id, candidate)
        source_ids = list(discovered)[:MAX_SCAN_IDS]
        if not source_ids:
            raise RuntimeError("No Pexels candidates matched the search query")
    else:
        raise ValueError("MODEL_CANDIDATE_SOURCE_IDS or MODEL_CANDIDATE_QUERY is required")
    report = {
        "scope": "new-fixed-model-candidate-review",
        "search_query": search_query,
        "expected_creator": expected_creator,
        "rendered_motion_frames": render,
        "sources": [],
    }
    matched = 0
    rendered = 0
    for source_id in source_ids:
        item = {"source_id": source_id}
        try:
            metadata = discovered.get(source_id) or provider._get_pexels_by_id(
                source_id, query="fixed model review"
            )
            item.update({
                "status": "metadata_match" if not expected_creator or metadata["creator"] == expected_creator else "creator_mismatch",
                "provider": metadata["provider"],
                "creator": metadata["creator"],
                "source_url": metadata["source_url"],
                "width": metadata["width"],
                "height": metadata["height"],
                "duration": metadata["duration"],
            })
            if item["status"] == "metadata_match":
                matched += 1
                if render and rendered < MAX_RENDERED_SOURCES:
                    source_dir = OUTPUT_DIR / source_id
                    clip = provider.fetch_pexels_source(
                        source_id,
                        source_dir / f"source-{source_id}.mp4",
                        query="fixed model review",
                    )
                    frames = extract_review_frames(clip, source_dir / "frames")
                    sheet = source_dir / f"source-{source_id}.jpg"
                    _sheet(frames, sheet)
                    clip.path.unlink(missing_ok=True)
                    item["sheet"] = sheet.relative_to(OUTPUT_DIR).as_posix()
                    rendered += 1
        except Exception as exc:
            item.update({"status": "unavailable", "error": str(exc)[:240]})
        report["sources"].append(item)

    # This tool verifies source metadata and renders motion frames for a human
    # editorial decision. It deliberately does not call a metadata match an
    # approved exercise or an approved recurring identity.
    report["metadata_match_count"] = matched
    report["rendered_count"] = rendered
    (OUTPUT_DIR / "candidates.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not matched:
        raise RuntimeError("No candidate source matched the expected Pexels creator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
