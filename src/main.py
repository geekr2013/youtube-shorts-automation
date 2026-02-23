import os
import sys
import re
import subprocess
import logging
import textwrap
from pathlib import Path
import google.generativeai as genai
from gtts import gTTS
from aagag_collector import AAGAGCollector
from youtube_uploader import YouTubeUploader

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# 환경 변수 및 경로 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ENABLE_BGM = os.getenv("ENABLE_BGM", "false").lower() == "true"
ROOT_DIR = Path.cwd()
BGM_PATH = ROOT_DIR / "data/music" / "background.mp3"

def get_safe_font_path():
    """시스템 폰트 경로를 찾고 FFmpeg용으로 이스케이프 처리합니다."""
    fonts = [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]
    for f in fonts:
        if os.path.exists(f):
            # FFmpeg 필터 내에서 콜론(:)은 특수문자이므로 \: 로 바꿔야 합니다.
            return f.replace(":", "\\:")
    return None

def sanitize_filename(filename):
    base, ext = os.path.splitext(filename)
    clean_base = re.sub(r'[^\w\s\d가-힣]', '', base).replace(' ', '_')
    return f"{clean_base[:50]}{ext}"

def get_video_duration(file_path):
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(file_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except: return 0.0

def has_audio(file_path):
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', str(file_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except: return False

# Gemini 초기화
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

def generate_ai_script(title):
    if not model: return title
    try:
        prompt = f"쇼츠 제목 '{title}'을 보고 시청자가 흥미를 느낄 수 있게 10초 내외의 구어체 나레이션 대본을 한 문장으로 써줘."
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return f"오늘 영상은 {title} 입니다. 정말 흥미롭네요!"

def convert_to_monetizable_format(video_path, title_text):
    """에러 234 방지를 위한 경로 최적화 가공 로직"""
    v_path = Path(video_path)
    output_path = v_path.parent / f"{v_path.stem}_monetized.mp4"
    
    # [핵심] 경로 문제를 피하기 위해 현재 작업 디렉토리에 임시 파일 생성
    text_file_name = "temp_title_render.txt"
    wrapped_text = "\n".join(textwrap.wrap(title_text, width=15))
    
    try:
        with open(text_file_name, "w", encoding="utf-8") as f:
            f.write(wrapped_text)
        
        font_path_escaped = get_safe_font_path()
        
        # 필터 설명: 배경 블러 + 원본 중앙 + 텍스트 파일(경로 없이 이름만) 읽기
        filter_str = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg];"
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        
        if font_path_escaped:
            # textfile='파일명' 형식으로 경로 구분자(/) 사용을 최소화
            filter_str += (
                f",drawtext=fontfile='{font_path_escaped}':textfile='{text_file_name}':"
                f"fontcolor=white:fontsize=80:line_spacing=20:box=1:boxcolor=black@0.5:"
                f"boxborderw=30:x=(w-text_w)/2:y=150"
            )

        cmd = [
            'ffmpeg', '-i', str(v_path),
            '-vf', filter_str,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-c:a', 'aac', '-y', str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except Exception as e:
        logger.error(f"❌ 영상 가공 실패: {e}")
        return None
    finally:
        if os.path.exists(text_file_name):
            os.remove(text_file_name)

def main():
    logger.info("🚀 수익화 자동화 시스템 가동 (Fix: Path Escape Logic)")
    success_count = 0
    try:
        uploader = YouTubeUploader()
        collector = AAGAGCollector()
        videos = collector.collect_and_download(max_videos=5)
        
        for idx, video in enumerate(videos, 1):
            v_path = video.get('video_path')
            if not v_path or get_video_duration(v_path) <= 0: continue

            # 파일명 정규화
            safe_name = sanitize_filename(os.path.basename(v_path))
            safe_path = os.path.join(os.path.dirname(v_path), safe_name)
            os.rename(v_path, safe_path)
            v_path = safe_path

            logger.info(f"🎬 [{idx}/{len(videos)}] {video.get('title')}")
            temp_files = []
            
            try:
                clean_title = re.sub(r'_\d+$', '', video.get('title')).strip().replace('_', ' ')
                script = generate_ai_script(clean_title)
                
                # 1. 영상 가공 (에러 234 방지 로직 적용됨)
                proc_path = convert_to_monetizable_format(v_path, clean_title)
                if not proc_path: continue
                temp_files.append(proc_path)
                
                # 2. TTS 생성
                tts_file = f"data/videos/voice_{idx}.mp3"
                gTTS(text=script, lang='ko').save(tts_file)
                temp_files.append(tts_file)

                # 3. 오디오 믹싱
                final_output = proc_path.replace('.mp4', '_final.mp4')
                use_bgm = ENABLE_BGM and BGM_PATH.exists()
                
                if use_bgm:
                    mix = "[0:a]volume=0.8[orig];[1:a]volume=2.5[tts];[2:a]volume=0.1:loop=-1[bgm];[orig][tts][bgm]amix=inputs=3:duration=first[a]"
                    cmd = ['ffmpeg', '-i', proc_path, '-i', tts_file, '-i', str(BGM_PATH), '-filter_complex', mix, '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-y', final_output]
                else:
                    mix = "[1:a]volume=2.5[tts];[0:a]volume=1.0[orig];[orig][tts]amix=inputs=2:duration=first[a]" if has_audio(proc_path) else "[1:a]volume=2.5[a]"
                    cmd = ['ffmpeg', '-i', proc_path, '-i', tts_file, '-filter_complex', mix, '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-y', final_output]
                
                subprocess.run(cmd, capture_output=True)
                temp_files.append(final_output)

                # 4. 유튜브 업로드
                if uploader.authenticated:
                    uploader.upload_video(video_path=final_output, title=f"{clean_title} #shorts", description=f"{script}\n#이슈 #유머", tags=["shorts"])
                    success_count += 1
                    logger.info("✅ 업로드 완료")
                
                # 정리
                for f in temp_files + [v_path]:
                    if os.path.exists(f): os.remove(f)

            except Exception as e:
                logger.error(f"❌ 개별 처리 실패: {e}")

        logger.info(f"🎉 최종 업로드 성공: {success_count}개")
        if success_count == 0 and len(videos) > 0: sys.exit(1)

    except Exception as e:
        logger.error(f"❌ 메인 시스템 에러: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
