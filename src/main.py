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

# 경로 설정 - Ubuntu 시스템 폰트 경로로 고정
FONT_PATH = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
ROOT_DIR = Path(__file__).parent.parent
BGM_PATH = str((ROOT_DIR / "data/music/background.mp3").absolute())
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ENABLE_BGM = os.getenv("ENABLE_BGM", "false").lower() == "true"

# Gemini 초기화
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

def escape_ffmpeg_text(text):
    """FFmpeg drawtext 필터에서 에러를 유발하는 특수문자 처리"""
    if not text: return ""
    # 콜론(:)과 작은따옴표(') 처리
    return text.replace(":", "\\:").replace("'", "\\'")

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

def generate_ai_script(title):
    if not model: return title
    try:
        prompt = f"유튜브 쇼츠 제목 '{title}'에 어울리는 10초 내외의 흥미로운 나레이션 한 문장을 구어체로 써줘."
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return f"오늘 준비한 영상은 {title} 입니다. 함께 보시죠!"

def convert_to_monetizable_format(video_path, title_text):
    """수익화용 가공 (블러 배경 + 자막)"""
    try:
        v_path = Path(video_path)
        output_path = v_path.parent / f"{v_path.stem}_monetized.mp4"
        
        # 텍스트 안전하게 변환
        safe_title = escape_ffmpeg_text(title_text)

        # 폰트가 없는 경우를 대비한 방어 로직
        current_font = FONT_PATH
        if not os.path.exists(current_font):
            current_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg];"
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
            f"drawtext=fontfile='{current_font}':text='{safe_title}':fontcolor=white:fontsize=80:"
            f"box=1:boxcolor=black@0.5:boxborderw=30:x=(w-text_w)/2:y=150"
        )

        cmd = ['ffmpeg', '-i', str(v_path), '-vf', filter_complex, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-y', str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except Exception as e:
        logger.error(f"❌ 영상 가공 실패: {e}")
        return None

def main():
    logger.info("🚀 수익화 자동화 시스템 가동 (Fix: Font & Text)")
    success_count = 0
    try:
        uploader = YouTubeUploader()
        collector = AAGAGCollector()
        videos = collector.collect_and_download(max_videos=5) # 테스트를 위해 5개로 조정 권장
        
        for idx, video in enumerate(videos, 1):
            v_path = video.get('video_path')
            if not v_path or get_video_duration(v_path) <= 0: continue

            safe_name = sanitize_filename(os.path.basename(v_path))
            safe_path = os.path.join(os.path.dirname(v_path), safe_name)
            os.rename(v_path, safe_path)
            v_path = safe_path

            logger.info(f"🎬 [{idx}/{len(videos)}] {video.get('title')}")
            temp_files = []
            
            try:
                clean_title = re.sub(r'_\d+$', '', video.get('title')).strip().replace('_', ' ')
                script = generate_ai_script(clean_title)
                
                # 영상 가공
                proc_path = convert_to_monetizable_format(v_path, clean_title)
                if not proc_path: continue
                temp_files.append(proc_path)
                
                # TTS 및 오디오 합성
                tts_file = f"data/videos/voice_{idx}.mp3"
                gTTS(text=script, lang='ko').save(tts_file)
                temp_files.append(tts_file)

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

                # 업로드
                if uploader.authenticated:
                    uploader.upload_video(video_path=final_output, title=f"{clean_title} #shorts", description=f"{script}\n#개그 #이슈", tags=["shorts"])
                    success_count += 1
                
                for f in temp_files + [v_path]:
                    if os.path.exists(f): os.remove(f)

            except Exception as e:
                logger.error(f"❌ 개별 실패: {e}")

        logger.info(f"🎉 작업 완료 (성공: {success_count}개)")
        if success_count == 0 and len(videos) > 0:
            sys.exit(1) # 하나도 성공 못하면 Action을 빨간불로 표시

    except Exception as e:
        logger.error(f"❌ 시스템 종료: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
