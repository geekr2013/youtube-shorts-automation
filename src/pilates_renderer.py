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

from models import StockClip
from pilates_catalog import (
    INSTRUCTOR_NAME_EN,
    INSTRUCTOR_NAME_KO,
    ROOT,
    Routine,
    build_narration,
    routine_exercises,
    validate_routine,
)
from pilates_video_strategy import FIXED_MODEL_ID, closeup_focus_y


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
REFERENCE_IMAGE = ROOT / "assets" / "instructor" / "hana-alignment-reference.png"
MOTION_MODE = "licensed-real-video-with-form-closeups"
FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "ffmpeg")
FFPROBE_BINARY = os.getenv("FFPROBE_BINARY", "ffprobe")


class PilatesRenderError(RuntimeError):
    pass


def _run(command: Sequence[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-3000:]
        raise PilatesRenderError(f"FFmpeg 실행 실패: {tail}")


def media_duration(path: Path) -> float:
    if shutil.which(FFPROBE_BINARY):
        result = subprocess.run(
            [
                FFPROBE_BINARY,
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
    if shutil.which(FFMPEG_BINARY):
        result = subprocess.run(
            [FFMPEG_BINARY, "-hide_banner", "-i", str(path)], capture_output=True, text=True
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
            FFMPEG_BINARY,
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
    movement = duration / 3
    if movement < 5.5:
        raise PilatesRenderError("동작 안내 시간이 너무 짧습니다.")
    return [movement, movement, duration - movement * 2]


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
Style: Hook,NanumGothic,68,&H00FFFFFF,&H00FFFFFF,&H99000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,7,82,116,160,1
Style: Title,NanumGothic,58,&H00FFFFFF,&H00FFFFFF,&H99000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,7,82,116,160,1
Style: Cue,NanumGothic,48,&H00FFFFFF,&H00FFFFFF,&H99000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,7,82,116,300,1
Style: English,NanumGothic,31,&H00E8E1D8,&H00E8E1D8,&H99000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,7,82,116,370,1
Style: Reps,NanumGothic,42,&H0000EBD7,&H0000EBD7,&H99000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,7,82,116,440,1
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

    hook_end = min(2.2, lengths[0] * 0.36)
    hook_panel = r"{\p1\1c&H101820&\1a&H48&\pos(48,120)}m 0 0 l 900 0 l 900 310 l 0 310{\p0}"
    dialogue(0, hook_end, "Panel", hook_panel, 0)
    hook_text = (
        f"{{\\pos(82,160)}}{_ass_escape(routine.title_ko)}\\N"
        f"{{\\fs36\\c&H00E8E1D8&}}3 MOVES · {_ass_escape(routine.title_en)}"
    )
    dialogue(0, hook_end, "Hook", hook_text, 3)

    for index, (exercise, length) in enumerate(zip(exercises, lengths), start=1):
        end = cursor + length
        text_start = hook_end if index == 1 else cursor
        text_end = end - (1.7 if index == 3 else 0.0)
        panel = r"{\p1\1c&H101820&\1a&H48&\pos(48,120)}m 0 0 l 900 0 l 900 390 l 0 390{\p0}"
        dialogue(text_start, text_end, "Panel", panel, 0)
        dialogue(text_start, text_end, "Title", f"{{\\pos(82,160)}}{index}/3  {_ass_escape(exercise.name_ko)}\\N{{\\fs34\\c&H00E8E1D8&}}{_ass_escape(exercise.name_en)}", 3)
        dialogue(text_start, text_end, "Cue", f"{{\\pos(82,300)}}{_ass_escape(exercise.cue_ko)}", 3)
        dialogue(text_start, text_end, "English", f"{{\\pos(82,370)}}{_ass_escape(exercise.cue_en)}", 3)
        dialogue(text_start, text_end, "Reps", f"{{\\pos(82,440)}}{_ass_escape(exercise.prescription_ko)}  ·  {exercise.prescription_en}", 3)
        cursor = end

    outro_start = max(0.0, duration - 1.7)
    dialogue(outro_start, duration, "Panel", hook_panel, 0)
    outro_text = "{\\pos(82,160)}저장하고 오늘 한 세트\\N{\\fs36\\c&H00E8E1D8&}SAVE & TRY ONE SET TODAY"
    dialogue(outro_start, duration, "Hook", outro_text, 3)
    path.write_text(header + "".join(lines), encoding="utf-8-sig")
    return {
        "language_mode": "ko+en",
        "layout": "YouTube Shorts safe-area panels",
        "korean_title_font_size": 58,
        "english_cue_font_size": 31,
        "hook": "movement starts on frame one; no static intro card",
        "wrap_mode": "explicit lines; no automatic Korean syllable splitting",
        "movement_visibility": "top safe-area panel keeps the torso, hips, legs and major joints visible",
        "segment_durations": [round(item, 2) for item in lengths],
    }


def _render_still_segment(image: Path, output: Path, duration: float, punch_in: bool) -> None:
    zoom_speed = "0.00055" if punch_in else "0.00035"
    filter_graph = (
        "scale=1200:2134:force_original_aspect_ratio=increase,"
        "crop=1200:2134,"
        f"zoompan=z='min(zoom+{zoom_speed},1.055)':x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,"
        "eq=contrast=1.03:saturation=1.01:brightness=-0.018:gamma=0.97,"
        "colorlevels=romax=0.95:gomax=0.95:bomax=0.95,"
        "unsharp=5:5:0.22:3:3:0,format=yuv420p"
    )
    _run(
        [
            FFMPEG_BINARY,
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
            "-r",
            "30",
            "-fps_mode",
            "cfr",
            "-video_track_timescale",
            "30000",
            str(output),
        ]
    )


def _render_motion_segment(exercise, output: Path, duration: float) -> None:
    """검수된 시작·수축 키프레임을 짧은 디졸브로 반복 시연한다."""
    transition = min(0.20, max(0.14, duration * 0.015))
    phase = duration / 4
    start_clip = output.with_name(f"{output.stem}_start.mp4")
    end_clip = output.with_name(f"{output.stem}_end.mp4")
    _render_still_segment(exercise.motion_start_path, start_clip, phase, punch_in=False)
    _render_still_segment(exercise.motion_end_path, end_clip, phase, punch_in=True)
    split_start = "[0:v]fps=30,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS,split=4[s0][s1][s2raw][s3raw]"
    split_end = "[1:v]fps=30,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS,split=4[e0][e1][e2raw][e3raw]"
    filters: List[str] = [split_start, split_end]
    if exercise.bilateral:
        filters.extend(("[s2raw]hflip[s2]", "[s3raw]hflip[s3]", "[e2raw]hflip[e2]", "[e3raw]hflip[e3]"))
    else:
        filters.extend(("[s2raw]null[s2]", "[s3raw]null[s3]", "[e2raw]null[e2]", "[e3raw]null[e3]"))
    blend_start = max(0.0, phase - transition)
    progress = f"min(max((T-{blend_start:.3f})/{transition:.3f},0),1)"
    blend = f"if(lt(T,{blend_start:.3f}),A,A*(1-{progress})+B*{progress})"
    filters.extend(
        (
            f"[s0][e0]blend=all_expr='{blend}':shortest=1[p0]",
            f"[e1][s1]blend=all_expr='{blend}':shortest=1[p1]",
            f"[s2][e2]blend=all_expr='{blend}':shortest=1[p2]",
            f"[e3][s3]blend=all_expr='{blend}':shortest=1[p3]",
            "[p0][p1][p2][p3]concat=n=4:v=1:a=0[outv]",
        )
    )
    try:
        _run(
            [
                FFMPEG_BINARY,
                "-y",
                "-i",
                str(start_clip),
                "-i",
                str(end_clip),
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[outv]",
                "-t",
                f"{duration:.3f}",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
                "-fps_mode",
                "cfr",
                "-video_track_timescale",
                "30000",
                str(output),
            ]
        )
    finally:
        start_clip.unlink(missing_ok=True)
        end_clip.unlink(missing_ok=True)


def _natural_grade_filter() -> str:
    """피부 질감을 지우지 않고 과한 광택과 스톡 영상 편차만 완화한다."""
    return (
        "eq=contrast=1.02:saturation=0.96:brightness=-0.012:gamma=0.99,"
        "colorlevels=romax=0.97:gomax=0.97:bomax=0.97,"
        "hqdn3d=0.8:0.8:2:2,unsharp=5:5:0.12:3:3:0,format=yuv420p"
    )


def _render_real_video_segment(exercise, clip: StockClip, output: Path, duration: float) -> None:
    """실제 연속 동작을 전신 구도에서 목표 근육 클로즈업으로 연결한다."""
    source_duration = clip.duration or media_duration(clip.path)
    if source_duration < 4.0:
        raise PilatesRenderError(f"실제 동영상 길이가 부족합니다: {clip.path}")
    transition = min(0.28, max(0.18, duration * 0.018))
    # 자세 전체를 먼저 확인한 뒤, 첫 검수 영상처럼 대부분을 코어 클로즈업에 쓴다.
    full_duration = duration * 0.32
    close_duration = duration - full_duration + transition
    full_seek = min(0.7, max(0.0, source_duration - 1.0))
    close_seek = full_seek + full_duration - transition
    focus_y = closeup_focus_y(exercise.slug)
    grade = _natural_grade_filter()
    full_filter = (
        "fps=30,scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920:x=(iw-1080)/2:y=(ih-1920)/2,setsar=1," + grade
    )
    close_filter = (
        "fps=30,scale=1458:2592:force_original_aspect_ratio=increase,"
        f"crop=1080:1920:x=(iw-1080)/2:y='min(max((ih-1920)*{focus_y:.3f},0),ih-1920)',"
        "setsar=1," + grade
    )
    _run(
        [
            FFMPEG_BINARY,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(clip.path),
            "-filter_complex",
            f"[0:v]split=2[fullraw][closeraw];"
            f"[fullraw]trim=start={full_seek:.3f}:duration={full_duration:.3f},"
            f"setpts=PTS-STARTPTS,{full_filter}[full];"
            f"[closeraw]trim=start={close_seek:.3f}:duration={close_duration:.3f},"
            f"setpts=PTS-STARTPTS,{close_filter}[close];"
            f"[full][close]xfade=transition=fade:duration={transition:.3f}:"
            f"offset={full_duration - transition:.3f}[outv]",
            "-map",
            "[outv]",
            "-t",
            f"{duration:.3f}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-fps_mode",
            "cfr",
            "-video_track_timescale",
            "30000",
            str(output),
        ]
    )


def render_pilates_short(
    routine: Routine,
    output_dir: Path,
    clips: Sequence[StockClip],
    output_name: str = "final_short.mp4",
) -> Path:
    if not shutil.which(FFMPEG_BINARY):
        raise PilatesRenderError("FFmpeg가 설치되어 있지 않습니다.")
    validate_routine(routine)
    if len(clips) != 3:
        raise PilatesRenderError("각 동작에 대응하는 실제 동영상 세 개가 필요합니다.")
    for clip in clips:
        if not clip.path.exists() or clip.path.suffix.lower() != ".mp4":
            raise PilatesRenderError(f"실제 동영상 파일이 없습니다: {clip.path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    narration = build_narration(routine)
    narration_path, duration, audio_metadata = create_narration(narration, output_dir)
    lengths = segment_plan(duration)
    exercises = routine_exercises(routine)
    segments: List[Path] = []
    for index, (exercise, clip, length) in enumerate(zip(exercises, clips, lengths), start=1):
        segment = output_dir / f"segment_{index}.mp4"
        _render_real_video_segment(exercise, clip, segment, length)
        segments.append(segment)

    visual = output_dir / "visual.mp4"
    concat_inputs: List[str] = []
    concat_filters: List[str] = []
    for index, segment in enumerate(segments):
        concat_inputs.extend(("-i", str(segment)))
        concat_filters.append(f"[{index}:v]fps=30,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v{index}]")
    concat_filters.append("[v0][v1][v2]concat=n=3:v=1:a=0[outv]")
    _run(
        [
            FFMPEG_BINARY,
            "-y",
            *concat_inputs,
            "-filter_complex",
            ";".join(concat_filters),
            "-map",
            "[outv]",
            "-t",
            f"{duration:.3f}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-fps_mode",
            "cfr",
            "-video_track_timescale",
            "30000",
            str(visual),
        ]
    )
    ass_path = output_dir / "captions.ass"
    caption_metadata = write_overlay_ass(ass_path, routine, duration)
    ass_filter_path = ass_path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    final_path = output_dir / output_name
    _run(
        [
            FFMPEG_BINARY,
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
    contact_sheet = output_dir / "contact-sheet.jpg"
    _run(
        [
            FFMPEG_BINARY,
            "-y",
            "-i",
            str(final_path),
            "-vf",
            (
                "fps=1/4,scale=270:480:force_original_aspect_ratio=decrease,"
                "pad=270:480:(ow-iw)/2:(oh-ih)/2:black,tile=3x3"
            ),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(contact_sheet),
        ]
    )
    (output_dir / "audio_metadata.json").write_text(
        json.dumps(audio_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "caption_metadata.json").write_text(
        json.dumps(caption_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "visual_metadata.json").write_text(
        json.dumps(
            {
                "motion_mode": MOTION_MODE,
                "paid_video_generation": False,
                "real_human_footage": True,
                "identity_locked": True,
                "identity_id": FIXED_MODEL_ID,
                "wardrobe_target": "reviewed fitted crop activewear with the abdomen line unobstructed",
                "lighting": "source-preserving natural grade with reduced highlight glare",
                "sequence": "brief full-body orientation followed by sustained muscle-focused close-up",
                "closeup_focus_y": [closeup_focus_y(item.slug) for item in exercises],
                "camera_angles": [item.camera_angle for item in exercises],
                "muscle_focus": [item.muscle_focus for item in exercises],
                "sources": [
                    {
                        "provider": clip.provider,
                        "creator": clip.creator,
                        "source_url": clip.source_url,
                        "source_id": clip.source_id,
                        "query": clip.query,
                        "resolution": f"{clip.width}x{clip.height}",
                        "duration": round(clip.duration, 2),
                        "visual_quality": clip.visual_quality,
                    }
                    for clip in clips
                ],
                "contact_sheet": contact_sheet.name,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    LOGGER.info("필라테스 쇼츠 생성: %.1f초 / %.1fMB", duration, final_path.stat().st_size / 1024 / 1024)
    return final_path
