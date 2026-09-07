"""Keep a permanent source-ID denylist independent of the rolling video history."""

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Set


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "data" / "used_source_ids.json"


def source_ids_from_records(records: Iterable[Mapping[str, Any]]) -> Set[str]:
    """Read both current source_ids and legacy nested source records."""
    used: Set[str] = set()
    for record in records:
        used.update(str(value) for value in (record.get("source_ids") or []) if str(value))
        used.update(
            str(item.get("source_id") or "")
            for item in (record.get("sources") or [])
            if str(item.get("source_id") or "")
        )
    return used


def load_used_source_ids(records: Iterable[Mapping[str, Any]] = ()) -> Set[str]:
    used = source_ids_from_records(records)
    if not LEDGER_PATH.exists():
        return used
    payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    values = payload.get("source_ids", []) if isinstance(payload, dict) else payload
    used.update(str(value) for value in values if str(value))
    return used


def save_used_source_ids(source_ids: Iterable[str]) -> None:
    values = sorted({str(value) for value in source_ids if str(value)}, key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value))
    LEDGER_PATH.write_text(
        json.dumps({"version": 1, "source_ids": values}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
