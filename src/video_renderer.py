"""한국어 내레이션과 자막이 들어간 9:16 원본 쇼츠를 렌더링한다."""

import asyncio
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import edge_tts
import requests

from models import StockClip

LOGGER = logging.getLogger(__name__)
WIDTH = 1080
HEIGHT = 1920
CAPTION_X = 450
CAPTION_Y = 1220
CAPTION_MAX_WIDTH = 760
CAPTION_BASE_FONT_SIZE = 64
CAPTION_MIN_FONT_SIZE = 50
CAPTION_FADE_IN_MS = 100
CAPTION_FADE_OUT_MS = 80
LOOP_TAIL_SECONDS = 1.2
GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
GEMINI_TTS_VOICE = "Gacrux"
EDGE_TTS_VOICES = (
    "ko-KR-HyunsuMultilingualNeural",
    "ko-KR-HyunsuNeural",
    "ko-KR-InJoonNeural",
    "ko-KR-SunHiNeural",
)
AUDIO_MIX_MODE = "voice_only"


class RenderError(RuntimeError):
    pass


def _run(command: Sequence[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-2500:]
        raise RenderError(f"FFmpeg 실행 실패: {tail}")


def media_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except (TypeError, ValueError):
        return 0.0


def split_caption_chunks(text: str, max_chars: int = 22) -> List[str]:
    """어절을 자르지 않고 짧은 호흡 단위의 자막 묶음을 만든다."""
    words = re.findall(r"\S+", text)
    chunks: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        sentence_break = bool(re.search(r"[.!?？。…]$", current))
        if current and (len(candidate) > max_chars or (sentence_break and len(current) >= 8)):
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _visual_units(text: str) -> float:
    units = 0.0
    for character in text:
        if character.isspace():
            units += 0.35
        elif character.isascii() and character.isalnum():
            units += 0.55
        elif character in ",.!?？。…:;'\"()[]{}":
            units += 0.5
        else:
            units += 1.0
    return units


def caption_lines(text: str, max_line_chars: int = 13) -> List[str]:
    """어절을 보존하며 세로 영상 자막을 최대 두 줄로 나눈다."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned or _visual_units(cleaned) <= max_line_chars:
        return [cleaned] if cleaned else []

    words = cleaned.split(" ")
    if len(words) == 1:
        return [cleaned]

    candidates = []
    for index in range(1, len(words)):
        first = " ".join(words[:index])
        second = " ".join(words[index:])
        first_units = _visual_units(first)
        second_units = _visual_units(second)
        overflow = max(0.0, max(first_units, second_units) - max_line_chars)
        score = max(first_units, second_units) + abs(first_units - second_units) * 0.35 + overflow * 2
        candidates.append((score, first, second))
    _, first, second = min(candidates, key=lambda item: item[0])
    return [first, second]


def caption_font_size(lines: Sequence[str]) -> int:
    """긴 어절도 자르지 않고 안전 폭에 들어오도록 글자 크기를 조절한다."""
    longest = max((_visual_units(line) for line in lines), default=1.0)
    fitted = int(CAPTION_MAX_WIDTH / max(longest, 1.0))
    return max(CAPTION_MIN_FONT_SIZE, min(CAPTION_BASE_FONT_SIZE, fitted))


def caption_timeline(text: str, duration: float) -> List[Tuple[float, float, str]]:
    chunks = split_caption_chunks(text)
    if not chunks:
        return []
    weights = []
    for item in chunks:
        weight = max(2.0, _visual_units(item))
        if re.search(r"[.!?？。…]$", item):
            weight += 2.0
        elif re.search(r"[,，]$", item):
            weight += 1.0
        weights.append(weight)
    total = sum(weights)
    cursor = 0.0
    timeline = []
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        end = duration if index == len(chunks) - 1 else cursor + duration * weight / total
        timeline.append((cursor, end, chunk))
        cursor = end
    return timeline


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    total_centiseconds = int(round(seconds * 100))
    hours, remainder = divmod(total_centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole:02d}.{centiseconds:02d}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def write_ass(path: Path, narration: str, duration: float) -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Noto Sans CJK KR,64,&H00FFFFFF,&H000000FF,&H00101010,&H64000000,-1,0,0,0,100,100,0,0,1,3,1,5,140,260,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for start, end, text in caption_timeline(narration, duration):
        wrapped_lines = caption_lines(text)
        wrapped = "\n".join(wrapped_lines)
        font_size = caption_font_size(wrapped_lines)
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,"
            f"{{\\an5\\pos({CAPTION_X},{CAPTION_Y})\\fs{font_size}"
            f"\\fad({CAPTION_FADE_IN_MS},{CAPTION_FADE_OUT_MS})}}"
            f"{_ass_escape(wrapped)}\n"
        )
    path.write_text("".join(lines), encoding="utf-8-sig")


def prepare_narration_text(text: str) -> str:
    """문장 끝에서 자연스럽게 숨을 고르도록 낭독용 문단을 만든다."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?？。…])\s+", cleaned)
    return "\n".join(sentence.strip() for sentence in sentences if sentence.strip())


def narration_audio_filter(raw_duration: float) -> str:
    """음색을 과도하게 누르지 않고 음량만 방송 수준으로 정리한다."""
    filters = []
    if raw_duration > 59:
        tempo = min(raw_duration / 58.0, 1.06)
        filters.append(f"atempo={tempo:.4f}")
    filters.extend(
        [
            "highpass=f=65",
            "lowpass=f=14500",
            "loudnorm=I=-16:LRA=10:TP=-1.5",
        ]
    )
    return ",".join(filters)


def _write_pcm_wave(path: Path, pcm: bytes, sample_rate: int = 24000) -> None:
    with wave.open(str(path), "wb") as audio_file:
        audio_file.setnchannels(1)
        audio_file.setsampwidth(2)
        audio_file.setframerate(sample_rate)
        audio_file.writeframes(pcm)


def _synthesize_gemini_tts(text: str, output: Path, api_key: str) -> None:
    prompt = (
        "차분하고 따뜻한 한국어 다큐멘터리 내레이터처럼 읽어주세요. "
        "광고처럼 과장하지 말고, 문장 사이에 자연스럽게 숨을 고르며, "
        "핵심 단어만 은은하게 강조하세요. 대본의 단어를 바꾸거나 덧붙이지 마세요.\n\n"
        f"대본:\n{text}"
    )
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_TTS_MODEL}:generateContent",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": GEMINI_TTS_VOICE}
                    }
                },
            },
        },
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    parts = payload.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    chunks = []
    sample_rate = 24000
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data") or {}
        if inline.get("data"):
            chunks.append(base64.b64decode(inline["data"]))
            mime_type = str(inline.get("mimeType") or inline.get("mime_type") or "")
            match = re.search(r"rate=(\d+)", mime_type)
            if match:
                sample_rate = int(match.group(1))
    if not chunks:
        raise RenderError("Gemini TTS 응답에 오디오가 없습니다.")
    _write_pcm_wave(output, b"".join(chunks), sample_rate)


async def _synthesize_edge_tts(text: str, output: Path, voice: str) -> None:
    communicator = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate="-2%",
        volume="+0%",
        pitch="+0Hz",
    )
    await communicator.save(str(output))


def create_narration(text: str, output_dir: Path) -> Tuple[Path, float, Dict[str, str]]:
    prepared = prepare_narration_text(text)
    raw = output_dir / "narration_raw.wav"
    engine = "Gemini expressive TTS"
    selected_voice = GEMINI_TTS_VOICE
    last_error = None
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            _synthesize_gemini_tts(prepared, raw, api_key)
        except Exception as exc:
            last_error = exc
            LOGGER.warning("Gemini TTS 실패, 무료 한국어 신경망 음성으로 전환합니다: %s", exc)
    if not raw.exists():
        raw = output_dir / "narration_raw.mp3"
        engine = "Microsoft neural TTS fallback"
        for candidate in EDGE_TTS_VOICES:
            try:
                asyncio.run(_synthesize_edge_tts(prepared, raw, candidate))
                selected_voice = candidate
                break
            except Exception as exc:
                last_error = exc
                LOGGER.warning("TTS 음성 실패(%s), 다른 음성을 시도합니다.", candidate)
        else:
            raise RenderError(f"한국어 내레이션을 만들지 못했습니다: {last_error}")
    raw_duration = media_duration(raw)
    if not 25 <= raw_duration <= 63:
        raise RenderError(f"내레이션 길이가 비정상입니다: {raw_duration:.1f}초")

    normalized = output_dir / "narration.m4a"
    _run(
        [
            "ffmpeg", "-y", "-i", str(raw), "-filter:a",
            narration_audio_filter(raw_duration),
            "-c:a", "aac", "-b:a", "160k", str(normalized),
        ]
    )
    duration = media_duration(normalized)
    if not 28 <= duration <= 60:
        raise RenderError(f"정규화 후 내레이션 길이가 기준 밖입니다: {duration:.1f}초")
    return normalized, duration, {
        "narration_engine": engine,
        "narration_voice": selected_voice,
        "pacing": "sentence-aware natural Korean",
        "background_music": "none",
        "mix_mode": AUDIO_MIX_MODE,
    }


def render_short(
    clips: Iterable[StockClip],
    narration_text: str,
    output_dir: Path,
    output_name: str = "final_short.mp4",
) -> Path:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RenderError("FFmpeg 또는 FFprobe가 설치되어 있지 않습니다.")
    output_dir.mkdir(parents=True, exist_ok=True)
    clip_list = list(clips)
    if len(clip_list) < 2:
        raise RenderError("렌더링에는 서로 다른 영상 2개 이상이 필요합니다.")

    narration_path, duration, audio_metadata = create_narration(narration_text, output_dir)
    (output_dir / "audio_metadata.json").write_text(
        json.dumps(audio_metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ass_path = output_dir / "captions.ass"
    write_ass(ass_path, narration_text, duration)

    loop_tail_duration = min(LOOP_TAIL_SECONDS, duration * 0.04)
    segment_duration = (duration - loop_tail_duration) / len(clip_list)
    segments: List[Path] = []
    for index, clip in enumerate(clip_list):
        segment = output_dir / f"segment_{index + 1}.mp4"
        _run(
            [
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(clip.path),
                "-t", f"{segment_duration:.3f}",
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,setsar=1,fps=30,"
                "eq=contrast=1.04:saturation=1.06:brightness=-0.02,"
                "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.10:t=fill",
                "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "21",
                "-pix_fmt", "yuv420p", str(segment),
            ]
        )
        segments.append(segment)

    loop_tail = output_dir / "segment_loop_tail.mp4"
    _run(
        [
            "ffmpeg", "-y", "-t", f"{loop_tail_duration:.3f}",
            "-i", str(clip_list[0].path),
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,setsar=1,fps=30,"
            "eq=contrast=1.04:saturation=1.06:brightness=-0.02,"
            "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.10:t=fill,reverse",
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "21",
            "-pix_fmt", "yuv420p", str(loop_tail),
        ]
    )
    segments.append(loop_tail)

    concat_file = output_dir / "segments.txt"
    concat_file.write_text(
        "".join(f"file '{item.as_posix()}'\n" for item in segments), encoding="utf-8"
    )
    visual = output_dir / "visual.mp4"
    _run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-t", f"{duration:.3f}", "-c", "copy", str(visual),
        ]
    )

    final_path = output_dir / output_name
    ass_filter_path = ass_path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    _run(
        [
            "ffmpeg", "-y", "-i", str(visual), "-i", str(narration_path),
            "-filter_complex",
            f"[0:v]ass='{ass_filter_path}'[v];"
            "[1:a]alimiter=limit=0.95[a]",
            "-map", "[v]", "-map", "[a]",
            "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "medium",
            "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            "-pix_fmt", "yuv420p", str(final_path),
        ]
    )
    if not final_path.exists() or final_path.stat().st_size < 500_000:
        raise RenderError("최종 영상 파일이 생성되지 않았습니다.")
    LOGGER.info("최종 영상 생성: %.1f초 / %.1fMB", duration, final_path.stat().st_size / 1024 / 1024)
    return final_path

