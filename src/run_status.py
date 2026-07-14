"""GitHub Actions의 마지막 실행 결과를 공개 상태 파일로 남긴다."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "data" / "automation_status.json"


def build_status(env: Dict[str, str]) -> Dict[str, str]:
    event = env.get("RUN_EVENT", "unknown")
    dry_requested = env.get("DRY_RUN_REQUESTED", "").lower() == "true"
    upload_outcome = env.get("UPLOAD_OUTCOME", "")
    is_dry_run = upload_outcome == "skipped" and (
        event == "push" or (event == "workflow_dispatch" and dry_requested)
    )
    mode = "dry-run" if is_dry_run else "upload"
    outcome = env.get("DRY_RUN_OUTCOME" if is_dry_run else "UPLOAD_OUTCOME", "unknown")
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "outcome": outcome,
        "event": event,
        "run_id": env.get("RUN_ID", ""),
        "commit_sha": env.get("RUN_SHA", ""),
    }


def main() -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(
        json.dumps(build_status(dict(os.environ)), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

