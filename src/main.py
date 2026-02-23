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

# 로깅 설정 (진행 상황 출력)
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# 경로 설정
ROOT_DIR = Path(__file__).parent.parent
# Ubuntu(GitHub Actions) 환경의 나눔고딕 폰트 경로
FONT_PATH = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
BGM_PATH = str((ROOT_DIR / "data/music/background.mp3").absolute())
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ENABLE_BGM = os.getenv("ENABLE_BGM", "false").lower() == "true"

# Gemini 초기화
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

def sanitize_filename(filename):
    """파일명 특수문자 제거 및 정규화"""
    base, ext = os.path.splitext(filename)
    clean_base = re.sub(r'[^\w\s\d가-힣]', '', base).replace(' ', '_')
    return f"{clean_base[:50]}{ext}"

def get_video_duration(file_path):
    """영상 길이 측정"""
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(file_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except: return 0.0

def has_audio(file_path):
    """소리 존재 여부 확인"""
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', str(file_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except: return False

def generate_ai_script(title):
    """Gemini API로 쇼츠 나레이션 생성"""
    if not model: return title
    try:
        prompt = f"쇼츠 영상 제목 '{title}'을 보고 시청자가 끝까지 보게 만드는 10초 내외의 흥미로운 나레이션 한 문장을 써줘. 친근한 구어체로."
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return f"오늘 영상은 {title} 입니다. 정말 흥미롭네요!"

def convert_to_monetizable_format(video_path, title_text):
    """블러 배경 + 중앙 영상 + 상단 자막 합성"""
    try:
        v_path = Path(video_path)
        output_path = v_path.parent / f"{v_path.stem}_monetized.mp4"
        
        # FFmpeg 필터: 배경 블러 처리 후 원본을 중앙에 배치
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg];"
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
            f"drawtext=fontfile='{FONT_PATH}':text='{title_text}':fontcolor=white:fontsize=80:"
            f"box=1:boxcolor=black@0.5:boxborderw=30:x=(w-text_w)/2:y=150"
        )

        cmd = ['ffmpeg', '-i', str(v_path), '-vf', filter_complex, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-y', str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except Exception as e:
        logger.error(f"❌ 영상 가공 실패: {e}")
        return None

def main():
    logger.info("🚀 수익화 대응 자동화 시스템 가동 시작")
    try:
        uploader = YouTubeUploader()
        collector = AAGAGCollector()
        videos = collector.collect_and_download(max_videos=10)
        
        for idx, video in enumerate(videos, 1):
            v_path = video.get('video_path')
            # 0초 영상 에러 방지
            if not v_path or get_video_duration(v_path) <= 0:
                logger.warning(f"⚠️ {idx}번 영상 건너뜀 (파일 에러)")
                continue

            # 파일명 정규화
            safe_name = sanitize_filename(os.path.basename(v_path))
            safe_path = os.path.join(os.path.dirname(v_path), safe_name)
            os.rename(v_path, safe_path)
            v_path = safe_path

            logger.info(f"🎬 [{idx}/{len(videos)}] {video.get('title')}")
            temp_files = []
            
            try:
                # 1. 대본 생성 및 영상 가공
                clean_title = re.sub(r'_\d+$', '', video.get('title')).strip().replace('_', ' ')
                script = generate_ai_script(clean_title)
                proc_path = convert_to_monetizable_format(v_path, clean_title)
                if not proc_path: continue
                temp_files.append(proc_path)
                
                # 2. TTS 음성 생성
                tts_file = f"data/videos/voice_{idx}.mp3"
                gTTS(text=script, lang='ko').save(tts_file)
                temp_files.append(tts_file)

                # 3. 오디오 믹싱 (BGM 포함 여부 체크)
                final_output = proc_path.replace('.mp4', '_final.mp4')
                use_bgm = ENABLE_BGM and os.path.exists(BGM_PATH)
                
                if use_bgm:
                    logger.info("🎵 배경음악 믹싱 중...")
                    if has_audio(proc_path):
                        mix = "[0:a]volume=0.8[orig];[1:a]volume=2.5[tts];[2:a]volume=0.1:loop=-1[bgm];[orig][tts][bgm]amix=inputs=3:duration=first[a]"
                    else:
                        mix = "[1:a]volume=2.5[tts];[2:a]volume=0.2:loop=-1[bgm];[tts][bgm]amix=inputs=2:duration=first[a]"
                    cmd = ['ffmpeg', '-i', proc_path, '-i', tts_file, '-i', BGM_PATH, '-filter_complex', mix, '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-y', final_output]
                else:
                    logger.info("🔇 배경음악 없이 믹싱 중...")
                    mix = "[1:a]volume=2.5[tts];[0:a]volume=1.0[orig];[orig][tts]amix=inputs=2:duration=first[a]" if has_audio(proc_path) else "[1:a]volume=2.5[a]"
                    cmd = ['ffmpeg', '-i', proc_path, '-i', tts_file, '-filter_complex', mix, '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-y', final_output]
                
                subprocess.run(cmd, capture_output=True)
                temp_files.append(final_output)

                # 4. 유튜브 업로드
                if uploader.authenticated:
                    uploader.upload_video(
                        video_path=final_output, 
                        title=f"{clean_title} #shorts", 
                        description=f"{script}\n\n#재미 #이슈 #유머", 
                        tags=["shorts", "이슈", "개그"]
                    )
                    logger.info("✅ 업로드 완료")
                
                # 작업 완료 후 임시 파일 정리
                for f in temp_files + [v_path]:
                    if os.path.exists(f): os.remove(f)

            except Exception as e:
                logger.error(f"❌ 처리 중 오류 발생: {e}")

    except Exception as e:
        logger.error(f"❌ 시스템 종료 에러: {e}")

if __name__ == "__main__":
    main()
