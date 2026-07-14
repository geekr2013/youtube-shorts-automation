"""한국어 내레이션과 자막이 들어간 9:16 원본 쇼츠를 렌더링한다."""

import asyncio
import logging
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import edge_tts

from models import StockClip

LOGGER = logging.getLogger(__name__)
WIDTH = 1080
HEIGHT = 1920
CAPTION_X = 470
CAPTION_Y = 1260
LOOP_TAIL_SECONDS = 1.2


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


def split_caption_chunks(text: str, max_chars: int = 20) -> List[str]:
    words = re.findall(r"\S+", text)
    chunks: List[str] = []
    current = ""
    for word in words:
        parts = [word[index : index + max_chars] for index in range(0, len(word), max_chars)]
        for part in parts:
            candidate = f"{current} {part}".strip()
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = part
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def caption_lines(text: str, max_line_chars: int = 10) -> List[str]:
    """세로 영상 안전 폭 안에서 한글 자막을 최대 두 줄로 나눈다."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned or len(cleaned) <= max_line_chars:
        return [cleaned] if cleaned else []

    midpoint = len(cleaned) / 2
    valid_spaces = [
        index
        for index, character in enumerate(cleaned)
        if character == " "
        and len(cleaned[:index].rstrip()) <= max_line_chars
        and len(cleaned[index + 1 :].lstrip()) <= max_line_chars
    ]
    if valid_spaces:
        split_at = min(valid_spaces, key=lambda index: abs(index - midpoint))
        return [cleaned[:split_at].rstrip(), cleaned[split_at + 1 :].lstrip()]

    split_at = math.ceil(len(cleaned) / 2)
    return [cleaned[:split_at].rstrip(), cleaned[split_at:].lstrip()]


def caption_timeline(text: str, duration: float) -> List[Tuple[float, float, str]]:
    chunks = split_caption_chunks(text)
    if not chunks:
        return []
    weights = [max(2, len(re.sub(r"\s", "", item))) for item in chunks]
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
Style: Caption,Noto Sans CJK KR,68,&H00FFFFFF,&H000000FF,&H00111111,&H78000000,-1,0,0,0,100,100,0,0,1,5,2,5,140,260,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for start, end, text in caption_timeline(narration, duration):
        wrapped = "\n".join(caption_lines(text))
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,"
            f"{{\\an5\\pos({CAPTION_X},{CAPTION_Y})}}{_ass_escape(wrapped)}\n"
        )
    path.write_text("".join(lines), encoding="utf-8-sig")


async def _synthesize(text: str, output: Path, voice: str) -> None:
    communicator = edge_tts.Communicate(text=text, voice=voice, rate="-2%", volume="+0%")
    await communicator.save(str(output))


def create_narration(text: str, output_dir: Path, voice: str = "ko-KR-SunHiNeural") -> Tuple[Path, float]:
    raw = output_dir / "narration_raw.mp3"
    voices = [voice, "ko-KR-InJoonNeural"]
    last_error = None
    for candidate in dict.fromkeys(voices):
        try:
            asyncio.run(_synthesize(text, raw, candidate))
            break
        except Exception as exc:
            last_error = exc
            LOGGER.warning("TTS 음성 실패(%s), 다른 음성을 시도합니다.", candidate)
    else:
        raise RenderError(f"한국어 내레이션을 만들지 못했습니다: {last_error}")
    raw_duration = media_duration(raw)
    if not 25 <= raw_duration <= 80:
        raise RenderError(f"내레이션 길이가 비정상입니다: {raw_duration:.1f}초")

    tempo = 1.0
    if raw_duration > 59:
        tempo = min(raw_duration / 57.0, 1.10)
    elif raw_duration < 36:
        tempo = max(raw_duration / 38.0, 0.92)
    normalized = output_dir / "narration.m4a"
    _run(
        [
            "ffmpeg", "-y", "-i", str(raw), "-filter:a",
            f"atempo={tempo:.4f},loudnorm=I=-16:LRA=11:TP=-1.5",
            "-c:a", "aac", "-b:a", "160k", str(normalized),
        ]
    )
    duration = media_duration(normalized)
    if not 35 <= duration <= 60:
        raise RenderError(f"정규화 후 내레이션 길이가 기준 밖입니다: {duration:.1f}초")
    return normalized, duration


def background_music_frequencies(style: str) -> Tuple[float, float, float]:
    """주제 유형에 맞는 잔잔한 3화음 주파수를 고른다."""
    normalized = style.lower()
    if any(keyword in normalized for keyword in ("기술", "과학", "tech", "science")):
        return 146.83, 185.00, 220.00
    if any(keyword in normalized for keyword in ("역사", "문화", "history", "culture")):
        return 110.00, 130.81, 164.81
    return 130.81, 164.81, 196.00


def create_background_music(output_dir: Path, duration: float, style: str) -> Path:
    """외부 음원 없이 영상 길이에 맞는 저음량 배경음을 만든다."""
    first, second, third = background_music_frequencies(style)
    expression = (
        f"(0.030*sin(2*PI*{first:.2f}*t)+"
        f"0.022*sin(2*PI*{second:.2f}*t)+"
        f"0.018*sin(2*PI*{third:.2f}*t))*(0.80+0.20*sin(2*PI*0.05*t))"
    )
    output = output_dir / "background_music.m4a"
    fade_out = max(0.0, duration - 2.0)
    _run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"aevalsrc={expression}:s=48000:d={duration:.3f}",
            "-filter:a",
            f"highpass=f=70,lowpass=f=1400,aecho=0.8:0.35:80:0.12,"
            f"afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out:.3f}:d=2",
            "-c:a", "aac", "-b:a", "128k", str(output),
        ]
    )
    return output


def render_short(
    clips: Iterable[StockClip],
    narration_text: str,
    output_dir: Path,
    output_name: str = "final_short.mp4",
    bgm_style: str = "curiosity",
) -> Path:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RenderError("FFmpeg 또는 FFprobe가 설치되어 있지 않습니다.")
    output_dir.mkdir(parents=True, exist_ok=True)
    clip_list = list(clips)
    if len(clip_list) < 2:
        raise RenderError("렌더링에는 서로 다른 영상 2개 이상이 필요합니다.")

    narration_path, duration = create_narration(narration_text, output_dir)
    background_music_path = create_background_music(output_dir, duration, bgm_style)
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
            "-i", str(background_music_path),
            "-filter_complex",
            f"[0:v]ass='{ass_filter_path}'[v];"
            "[2:a]volume=0.45[bgm];"
            "[1:a][bgm]amix=inputs=2:duration=first:normalize=0,"
            "alimiter=limit=0.95[a]",
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

