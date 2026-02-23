import os
import sys
import re
import subprocess
import logging
from pathlib import Path
import google.generativeai as genai
from gtts import gTTS
from aagag_collector import AAGAGCollector
from youtube_uploader import YouTubeUploader

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# 경로 및 설정
ROOT_DIR = Path(__file__).parent.parent
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ENABLE_BGM = os.getenv("ENABLE_BGM", "false").lower() == "true"
BGM_PATH = str((ROOT_DIR / "data/music/background.mp3").absolute())

# [중요] GitHub Actions 환경에서 폰트 경로 자동 탐색
def get_safe_font_path():
    """시스템에 설치된 나눔고딕 혹은 기본 폰트를 찾습니다."""
    system_fonts = [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
    ]
    for font in system_fonts:
        if os.path.exists(font):
            return font
    return None

def escape_ffmpeg_text(text):
    """FFmpeg 자막 필터에서 에러를 방지하기 위해 특수문자를 정규화합니다."""
    if not text: return ""
    # 콜론, 따옴표, 백슬래시 등을 FFmpeg이 인식할 수 있게 변환
    text = text.replace('\\', '/').replace("'", "'\\\\\\''").replace(':', '\\:')
    return text

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
        prompt = f"쇼츠 제목 '{title}'에 어울리는 10초 내외의 흥미로운 나레이션 한 문장을 구어체로 써줘."
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return f"오늘 소개할 영상은 {title} 입니다. 함께 보시죠!"

def convert_to_monetizable_format(video_path, title_text):
    """수익화를 위한 가공 (블러 배경 + 9:16 + 자막)"""
    try:
        v_path = Path(video_path)
        output_path = v_path.parent / f"{v_path.stem}_monetized.mp4"
        
        font_file = get_safe_font_path()
        safe_title = escape_ffmpeg_text(title_text)

        # 블러 배경 효과 + 중앙 배치 + 상단 자막 (폰트 설정 보강)
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg];"
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        
        # 폰트가 있을 경우에만 drawtext 추가
        if font_file:
            filter_complex += f",drawtext=fontfile='{font_file}':text='{safe_title}':fontcolor=white:fontsize=75:box=1:boxcolor=black@0.5:boxborderw=25:x=(w-text_w)/2:y=150"

        cmd = [
            'ffmpeg', '-i', str(v_path),
            '-vf', filter_complex,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-c:a', 'aac', '-y', str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except Exception as e:
        logger.error(f"❌ 영상 가공 실패: {e}")
        return None

def main():
    logger.info("🚀 수익화 대응 시스템 가동 (폰트/특수문자 패치 완료)")
    success_count = 0
    try:
        uploader = YouTubeUploader()
        collector = AAGAGCollector()
        videos = collector.collect_and_download(max_videos=5)
        
        for idx, video in enumerate(videos, 1):
            v_path = video.get('video_path')
            if not v_path or get_video_duration(v_path) <= 0: continue

            safe_name = sanitize_filename(os.path.basename(v_path))
            safe_path = os.path.join(os.path.dirname(v_path), safe_name)
            os.rename(v_path, safe_path)
            v_path = safe_path

            logger.info(f"🎬 [{idx}/{len(videos)}] 처리 중: {video.get('title')}")
            temp_files = []
            
            try:
                clean_title = re.sub(r'_\d+$', '', video.get('title')).strip().replace('_', ' ')
                script = generate_ai_script(clean_title)
                
                # 1. 영상 가공 (폰트 경로 에러 해결 지점)
                proc_path = convert_to_monetizable_format(v_path, clean_title)
                if not proc_path: continue
                temp_files.append(proc_path)
                
                # 2. TTS 음성 생성
                tts_file = f"data/videos/voice_{idx}.mp3"
                gTTS(text=script, lang='ko').save(tts_file)
                temp_files.append(tts_file)

                # 3. 오디오 믹싱
                final_output = proc_path.replace('.mp4', '_final.mp4')
                use_bgm = ENABLE_BGM and os.path.exists(BGM_PATH)
                
                if use_bgm:
                    mix = "[0:a]volume=0.8[orig];[1:a]volume=2.5[tts];[2:a]volume=0.1:loop=-1[bgm];[orig][tts][bgm]amix=inputs=3:duration=first[a]"
                    cmd = ['ffmpeg', '-i', proc_path, '-i', tts_file, '-i', BGM_PATH, '-filter_complex', mix, '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-y', final_output]
                else:
                    mix = "[1:a]volume=2.5[tts];[0:a]volume=1.0[orig];[orig][tts]amix=inputs=2:duration=first[a]" if has_audio(proc_path) else "[1:a]volume=2.5[a]"
                    cmd = ['ffmpeg', '-i', proc_path, '-i', tts_file, '-filter_complex', mix, '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-y', final_output]
                
                subprocess.run(cmd, capture_output=True)
                temp_files.append(final_output)

                # 4. 유튜브 업로드
                if uploader.authenticated:
                    uploader.upload_video(video_path=final_output, title=f"{clean_title} #shorts", description=f"{script}\n#유머 #개그", tags=["shorts"])
                    success_count += 1
                
                # 임시 파일 삭제
                for f in temp_files + [v_path]:
                    if os.path.exists(f): os.remove(f)

            except Exception as e:
                logger.error(f"❌ 개별 실패: {e}")

        logger.info(f"🎉 최종 업로드 성공: {success_count}개")
        if success_count == 0 and len(videos) > 0: sys.exit(1)

    except Exception as e:
        logger.error(f"❌ 메인 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
