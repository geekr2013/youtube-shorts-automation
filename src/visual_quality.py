"""실제 운동 영상이 지정 동작과 화면 품질 기준에 맞는지 무료 Gemini로 검수한다."""

import base64
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import requests

from models import StockClip
from pilates_catalog import Exercise


LOGGER = logging.getLogger(__name__)
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash-lite")
MIN_EXERCISE_MATCH = 0.82
MIN_REALISM = 0.85
MIN_VISIBILITY = 0.78
MIN_PROFESSIONAL_ATTIRE = 0.75
FRAME_POSITIONS = (0.2, 0.5, 0.8)


class VisualQualityError(RuntimeError):
    pass


def extract_review_frames(clip: StockClip, output_dir: Path) -> List[Path]:
    """동영상 초·중·후반 프레임을 작게 추출해 동작의 지속성과 일치도를 확인한다."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise VisualQualityError("AI 화면 검수에 FFmpeg가 필요합니다.")
    output_dir.mkdir(parents=True, exist_ok=True)
    duration = max(float(clip.duration), 4.0)
    paths: List[Path] = []
    for index, position in enumerate(FRAME_POSITIONS, start=1):
        frame_path = output_dir / f"frame_{index}.jpg"
        result = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{duration * position:.3f}",
                "-i",
                str(clip.path),
                "-frames:v",
                "1",
                "-vf",
                "scale=768:-2:force_original_aspect_ratio=decrease",
                "-q:v",
                "4",
                str(frame_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not frame_path.exists() or frame_path.stat().st_size < 5_000:
            raise VisualQualityError("운동 영상 검수 프레임을 만들지 못했습니다.")
        paths.append(frame_path)
    return paths


def _schema() -> Dict[str, Any]:
    score = {"type": "number", "minimum": 0, "maximum": 1}
    return {
        "type": "object",
        "properties": {
            "approved": {"type": "boolean"},
            "exercise_match": score,
            "realism": score,
            "visibility": score,
            "professional_attire": score,
            "safe_framing": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": [
            "approved",
            "exercise_match",
            "realism",
            "visibility",
            "professional_attire",
            "safe_framing",
            "reason",
        ],
    }


def _score(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def meets_visual_thresholds(result: Dict[str, Any]) -> bool:
    return bool(
        result.get("approved")
        and result.get("safe_framing")
        and _score(result.get("exercise_match")) >= MIN_EXERCISE_MATCH
        and _score(result.get("realism")) >= MIN_REALISM
        and _score(result.get("visibility")) >= MIN_VISIBILITY
        and _score(result.get("professional_attire")) >= MIN_PROFESSIONAL_ATTIRE
    )


class GeminiVisualQualityGate:
    def __init__(self, api_key: str = "", model: str = ""):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
        self.model = model or GEMINI_VISION_MODEL
        if not self.api_key:
            raise VisualQualityError("실제 운동 영상의 AI 화면 검수 키가 없습니다.")

    def review(self, clip: StockClip, exercise: Exercise, output_dir: Path) -> Dict[str, Any]:
        frames = extract_review_frames(clip, output_dir)
        prompt = (
            "You are a strict senior Pilates video editor. Review the three chronological frames "
            "from one continuous, real stock video. Do not infer a match from workout clothing alone.\n"
            f"Expected exercise: {exercise.name_ko} / {exercise.name_en}.\n"
            f"Teaching cue: {exercise.cue_en}. Camera target: {exercise.camera_angle}. "
            f"Target area: {exercise.muscle_focus}.\n"
            "Approve only when at least two frames clearly demonstrate the expected exercise and the "
            "sequence plausibly shows its movement. The subject must be an adult, look like real camera "
            "footage with natural anatomy and skin/light, wear professional fitted sportswear that does "
            "not hide joint alignment, and be framed for instruction rather than sexual emphasis. Reject "
            "nudity, underwear-like styling, obstructed limbs, large logos, clutter, heavy beauty filters, "
            "AI/anatomy artifacts, or a different exercise. Scores are 0 to 1. Keep the reason brief."
        )
        parts: List[Dict[str, Any]] = [{"text": prompt}]
        for frame in frames:
            parts.append(
                {
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": base64.b64encode(frame.read_bytes()).decode("ascii"),
                    }
                }
            )
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                json={
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {
                        "temperature": 0,
                        "responseMimeType": "application/json",
                        "responseSchema": _schema(),
                    },
                },
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise VisualQualityError("무료 AI 화면 검수 요청에 실패해 업로드를 중단합니다.") from exc
        try:
            raw = payload["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(raw)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise VisualQualityError("AI 화면 검수 결과를 해석하지 못했습니다.") from exc
        normalized = {
            "approved": bool(result.get("approved")),
            "exercise_match": _score(result.get("exercise_match")),
            "realism": _score(result.get("realism")),
            "visibility": _score(result.get("visibility")),
            "professional_attire": _score(result.get("professional_attire")),
            "safe_framing": bool(result.get("safe_framing")),
            "reason": str(result.get("reason") or "검수 사유 없음")[:240],
            "model": self.model,
            "sample_count": len(frames),
        }
        normalized["passed"] = meets_visual_thresholds(normalized)
        LOGGER.info(
            "AI 화면 검수 %s: match=%.2f realism=%.2f visibility=%.2f / %s",
            "통과" if normalized["passed"] else "거절",
            normalized["exercise_match"],
            normalized["realism"],
            normalized["visibility"],
            normalized["reason"],
        )
        return normalized
