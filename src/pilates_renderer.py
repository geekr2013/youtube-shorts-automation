"""고정된 하나 강사 자산으로 한·영 필라테스 쇼츠를 렌더링한다."""

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
from typing import Dict, List, Sequence, Tuple

import edge_tts
import requests

from pilates_catalog import (
    INSTRUCTOR_NAME_EN,
    INSTRUCTOR_NAME_KO,
    ROOT,
    Routine,
    build_narration,
    routine_exercises,
    validate_routine,
)


LOGGER = logging.getLogger(__name__)
WIDTH = 1080
HEIGHT = 1920
GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
GEMINI_TTS_VOICE = "Aoede"
EDGE_TTS_VOICES = (
    "ko-KR-SunHiNeural",
    "ko-KR-HyunsuMultilingualNeural",
    "ko-KR-InJoonNeural",
)
AUDIO_MIX_MODE = "voice_only"
REFERENCE_IMAGE = ROOT / "assets" / "instructor" / "hana-reference.jpg"


class PilatesRenderError(RuntimeError):
    pass


def _run(command: Sequence[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-3000:]
        raise PilatesRenderError(f"FFmpeg 실행 실패: {tail}")


def media_duration(path: Path) -> float:
    if shutil.which("ffprobe"):
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        try:
            return float(result.stdout.strip())
        except (TypeError, ValueError):
            pass
    if shutil.which("ffmpeg"):
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(path)], capture_output=True, text=True
        )
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
        if match:
            hours, minutes, seconds = match.groups()
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return 0.0


def prepare_narration_text(text: str) -> str:
    sentences = re.split(r"(?<=[.!?。])\s+", re.sub(r"\s+", " ", text).strip())
    return "\n".join(sentence.strip() for sentence in sentences if sentence.strip())


def narration_audio_filter(raw_duration: float) -> str:
    filters: List[str] = []
    if raw_duration > 47:
        filters.append(f"atempo={min(raw_duration / 46.0, 1.06):.4f}")
    filters.extend(("highpass=f=65", "lowpass=f=14500", "loudnorm=I=-16:LRA=9:TP=-1.5"))
    return ",".join(filters)


def _write_pcm_wave(path: Path, pcm: bytes, sample_rate: int = 24000) -> None:
    with wave.open(str(path), "wb") as audio_file:
        audio_file.setnchannels(1)
        audio_file.setsampwidth(2)
        audio_file.setframerate(sample_rate)
        audio_file.writeframes(pcm)


def _synthesize_gemini_tts(text: str, output: Path, api_key: str) -> None:
    prompt = (
        "자연스럽고 편안한 이십 대 한국인 여성 필라테스 강사처럼 읽어주세요. "
        "홍보 말투나 과장된 AI 억양은 피하고, 동작 이름 뒤에는 짧게 쉬며, "
        "횟수와 자세 주의점은 또렷하지만 부드럽게 안내하세요. "
        "한글로 적힌 숫자는 적힌 그대로 자연스럽게 읽고, 대본을 바꾸거나 덧붙이지 마세요.\n\n"
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
    parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    chunks: List[bytes] = []
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
        raise PilatesRenderError("Gemini TTS 응답에 오디오가 없습니다.")
    _write_pcm_wave(output, b"".join(chunks), sample_rate)


async def _synthesize_edge_tts(text: str, output: Path, voice: str) -> None:
    communicator = edge_tts.Communicate(text=text, voice=voice, rate="-4%", volume="+0%", pitch="+0Hz")
    await communicator.save(str(output))


def create_narration(text: str, output_dir: Path) -> Tuple[Path, float, Dict[str, str]]:
    if any(character.isdigit() for character in text):
        raise PilatesRenderError("내레이션 숫자는 한글로 작성해야 합니다.")
    prepared = prepare_narration_text(text)
    raw = output_dir / "narration_raw.wav"
    engine = "Gemini expressive TTS"
    selected_voice = GEMINI_TTS_VOICE
    last_error: Exception | None = None
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            _synthesize_gemini_tts(prepared, raw, api_key)
        except Exception as exc:
            last_error = exc
            LOGGER.warning("Gemini 여성 음성 실패, 무료 한국어 여성 음성으로 전환합니다: %s", exc)
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
                LOGGER.warning("대체 음성 실패(%s), 다음 음성을 시도합니다.", candidate)
        else:
            raise PilatesRenderError(f"한국어 여성 내레이션을 만들지 못했습니다: {last_error}")
    raw_duration = media_duration(raw)
    if not 22 <= raw_duration <= 50:
        raise PilatesRenderError(f"내레이션 길이가 기준 밖입니다: {raw_duration:.1f}초")
    normalized = output_dir / "narration.m4a"
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw),
            "-filter:a",
            narration_audio_filter(raw_duration),
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(normalized),
        ]
    )
    duration = media_duration(normalized)
    if not 22 <= duration <= 48:
        raise PilatesRenderError(f"정규화 후 내레이션 길이가 기준 밖입니다: {duration:.1f}초")
    return normalized, duration, {
        "narration_engine": engine,
        "narration_voice": selected_voice,
        "voice_character": "young adult Korean female Pilates instructor",
        "count_style": "native Korean words",
        "background_music": "none",
        "mix_mode": AUDIO_MIX_MODE,
    }


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole:02d}.{fraction:02d}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def segment_plan(duration: float) -> List[float]:
    intro = min(3.4, max(2.8, duration * 0.11))
    outro = min(2.8, max(2.2, duration * 0.08))
    movement = (duration - intro - outro) / 3
    if movement < 5.5:
        raise PilatesRenderError("동작 안내 시간이 너무 짧습니다.")
    return [intro, movement, movement, movement, outro]


def write_overlay_ass(path: Path, routine: Routine, duration: float) -> Dict[str, object]:
    exercises = routine_exercises(routine)
    lengths = segment_plan(duration)
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Brand,NanumGothic,34,&H00FFFFFF,&H00FFFFFF,&H66000000,&H00000000,-1,0,0,0,100,100,1,0,1,2,0,7,58,180,80,1
Style: Intro,NanumGothic,66,&H00FFFFFF,&H00FFFFFF,&H88000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,5,80,210,300,1
Style: Title,NanumGothic,58,&H00FFFFFF,&H00FFFFFF,&H99000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,7,82,220,1020,1
Style: Cue,NanumGothic,45,&H00FFFFFF,&H00FFFFFF,&H99000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,7,82,220,1160,1
Style: English,NanumGothic,29,&H00E8E1D8,&H00E8E1D8,&H99000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,7,82,220,1230,1
Style: Reps,NanumGothic,39,&H0000EBD7,&H0000EBD7,&H99000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,7,82,220,1320,1
Style: Panel,Arial,20,&H66000000,&H66000000,&H66000000,&H66000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines: List[str] = []
    cursor = 0.0

    def dialogue(start: float, end: float, style: str, text: str, layer: int = 2) -> None:
        lines.append(
            f"Dialogue: {layer},{_ass_time(start)},{_ass_time(end)},{style},,0,0,0,,{{\\fad(140,100)}}{text}\n"
        )

    dialogue(0, duration, "Brand", f"{INSTRUCTOR_NAME_EN} PILATES", 4)
    intro_end = lengths[0]
    intro_text = f"{{\\pos(540,820)}}{_ass_escape(routine.title_ko)}\\N{{\\fs38\\c&H00E8E1D8&}}{_ass_escape(routine.title_en)}"
    dialogue(0, intro_end, "Intro", intro_text, 3)
    cursor = intro_end

    for index, (exercise, length) in enumerate(zip(exercises, lengths[1:4]), start=1):
        end = cursor + length
        is_standing = exercise.slug == "ring-side-bend"
        panel_y = 990 if is_standing else 210
        title_y = 1020 if is_standing else 250
        cue_y = 1160 if is_standing else 390
        english_y = 1230 if is_standing else 465
        reps_y = 1320 if is_standing else 560
        panel = rf"{{\p1\1c&H101820&\1a&H55&\pos(48,{panel_y})}}m 0 0 l 804 0 l 804 430 l 0 430{{\p0}}"
        dialogue(cursor, end, "Panel", panel, 0)
        dialogue(cursor, end, "Title", f"{{\\pos(82,{title_y})}}{index}/3  {_ass_escape(exercise.name_ko)}\\N{{\\fs34\\c&H00E8E1D8&}}{_ass_escape(exercise.name_en)}", 3)
        dialogue(cursor, end, "Cue", f"{{\\pos(82,{cue_y})}}{_ass_escape(exercise.cue_ko)}", 3)
        dialogue(cursor, end, "English", f"{{\\pos(82,{english_y})}}{_ass_escape(exercise.cue_en)}", 3)
        dialogue(cursor, end, "Reps", f"{{\\pos(82,{reps_y})}}{_ass_escape(exercise.prescription_ko)}  ·  {exercise.prescription_en}", 3)
        cursor = end

    outro_text = "{\\pos(540,820)}저장하고 천천히 따라 해요\\N{\\fs34\\c&H00E8E1D8&}SAVE & MOVE WITH CONTROL"
    dialogue(cursor, duration, "Intro", outro_text, 3)
    path.write_text(header + "".join(lines), encoding="utf-8-sig")
    return {
        "language_mode": "ko+en",
        "layout": "YouTube Shorts safe-area panels",
        "korean_title_font_size": 58,
        "english_cue_font_size": 29,
        "segment_durations": [round(item, 2) for item in lengths],
    }


def _render_still_segment(image: Path, output: Path, duration: float, punch_in: bool) -> None:
    zoom_speed = "0.00055" if punch_in else "0.00035"
    filter_graph = (
        "scale=1200:2134:force_original_aspect_ratio=increase,"
        "crop=1200:2134,"
        f"zoompan=z='min(zoom+{zoom_speed},1.055)':x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,"
        "eq=contrast=1.025:saturation=1.02:brightness=-0.01,format=yuv420p"
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image),
            "-t",
            f"{duration:.3f}",
            "-vf",
            filter_graph,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ]
    )


def render_pilates_short(routine: Routine, output_dir: Path, output_name: str = "final_short.mp4") -> Path:
    if not shutil.which("ffmpeg"):
        raise PilatesRenderError("FFmpeg가 설치되어 있지 않습니다.")
    if not REFERENCE_IMAGE.exists():
        raise PilatesRenderError("하나 강사 기준 이미지가 없습니다.")
    validate_routine(routine)
    output_dir.mkdir(parents=True, exist_ok=True)
    narration = build_narration(routine)
    narration_path, duration, audio_metadata = create_narration(narration, output_dir)
    lengths = segment_plan(duration)
    images = [REFERENCE_IMAGE, *(item.pose_path for item in routine_exercises(routine)), REFERENCE_IMAGE]
    segments: List[Path] = []
    for index, (image, length) in enumerate(zip(images, lengths)):
        segment = output_dir / f"segment_{index + 1}.mp4"
        _render_still_segment(image, segment, length, punch_in=index % 2 == 1)
        segments.append(segment)

    concat_file = output_dir / "segments.txt"
    concat_file.write_text(
        "".join(f"file '{item.resolve().as_posix()}'\n" for item in segments),
        encoding="utf-8",
    )
    visual = output_dir / "visual.mp4"
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-t",
            f"{duration:.3f}",
            "-c",
            "copy",
            str(visual),
        ]
    )
    ass_path = output_dir / "captions.ass"
    caption_metadata = write_overlay_ass(ass_path, routine, duration)
    ass_filter_path = ass_path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    final_path = output_dir / output_name
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(visual),
            "-i",
            str(narration_path),
            "-filter_complex",
            f"[0:v]ass='{ass_filter_path}'[v];[1:a]alimiter=limit=0.95[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            "-pix_fmt",
            "yuv420p",
            str(final_path),
        ]
    )
    if not final_path.exists() or final_path.stat().st_size < 500_000:
        raise PilatesRenderError("최종 필라테스 영상 파일이 생성되지 않았습니다.")
    (output_dir / "audio_metadata.json").write_text(
        json.dumps(audio_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "caption_metadata.json").write_text(
        json.dumps(caption_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    LOGGER.info("필라테스 쇼츠 생성: %.1f초 / %.1fMB", duration, final_path.stat().st_size / 1024 / 1024)
    return final_path
