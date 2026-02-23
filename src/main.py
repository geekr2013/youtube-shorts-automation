"""
AAGAG YouTube Shorts 자동화 - Gemini API 적용 버전
1. Gemini를 사용한 쇼츠 나레이션 대본 자동 생성
2. 무료 gTTS를 통한 음성 합성
3. GitHub Actions 환경 최적화
"""

import os
import sys
import re
import subprocess
import textwrap
import logging
from pathlib import Path

# 필수 라이브러리 임포트
try:
    import google.generativeai as genai
    from gtts import gTTS
    from aagag_collector import AAGAGCollector
    from youtube_uploader import YouTubeUploader
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger.info("✅ Gemini 기반 시스템 로드 완료")
except ImportError as e:
    print(f"❌ 라이브러리 로드 실패: {e}")
    sys.exit(1)

# 설정 정보 (경로 수정: root 기준)
ROOT_DIR = Path(__file__).parent.parent
CUSTOM_FONT_PATH = str((ROOT_DIR / "font/SeoulAlrim-ExtraBold.otf").absolute())
BGM_PATH = str((ROOT_DIR / "data/music/background.mp3").absolute())
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini 초기화
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

def sanitize_filename(filename: str) -> str:
    base, ext = os.path.splitext(filename)
    clean_base = re.sub(r'[^\w\s\d가-힣]', '', base).replace(' ', '_')
    return f"{clean_base[:50]}{ext}"

def get_video_duration(file_path: str) -> float:
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(file_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except: return 0.0

def has_audio(file_path: str) -> bool:
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', str(file_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except: return False

def generate_ai_script(title: str) -> str:
    """Gemini API를 사용하여 쇼츠 대본 생성"""
    if not model: return title
    try:
        prompt = f"유튜브 쇼츠 영상 제목 '{title}'을 보고, 시청자가 흥미를 느낄 수 있게 10초 내외의 구어체 나레이션 대본을 한 문장으로 써줘. 말투는 '~하네요', '~해볼까요?' 처럼 친절하게."
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.warning(f"⚠️ Gemini 대본 생성 실패: {e}")
        return f"오늘 영상은 {title} 입니다. 끝까지 봐주세요!"

def create_metadata(title: str, source_url: str = "") -> dict:
    clean_title = re.sub(r'_\d+$', '', title).strip().replace('_', ' ')
    ai_script = generate_ai_script(clean_title)
    
    youtube_final_title = f"{clean_title} #shorts #이슈 #재미"
    description = f"{ai_script}\n\n😂 영상이 재밌다면 구독과 좋아요 부탁드려요!\n"
    if source_url: description += f"📌 출처: {source_url}\n"
    
    words = re.findall(r'[가-힣a-zA-Z0-9]+', clean_title)
    tags = ['이슈', '숏츠', '개그'] + [w for w in words if len(w) >= 2][:10]
    return {'title': youtube_final_title, 'script': ai_script, 'original_title': clean_title, 'description': description, 'tags': tags}

def convert_to_monetizable_format(video_path: str, title_text: str) -> str:
    """수익화용 시각 가공: 블러 배경 + 9:16 + 자막"""
    try:
        v_path = Path(video_path)
        output_path = v_path.parent / f"{v_path.stem}_monetized.mp4"
        
        # 폰트 경로 체크 (GitHub Actions 환경 대응)
        font_arg = CUSTOM_FONT_PATH.replace('\\', '/')
        if not os.path.exists(CUSTOM_FONT_PATH):
            font_arg = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"

        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg];"
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
            f"drawtext=fontfile='{font_arg}':text='{title_text}':fontcolor=white:fontsize=80:"
            f"box=1:boxcolor=black@0.5:boxborderw=30:x=(w-text_w)/2:y=150"
        )

        cmd = ['ffmpeg', '-i', str(v_path), '-vf', filter_complex, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-y', str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except Exception as e:
        logger.error(f"❌ 영상 가공 에러: {e}")
        return None

def main():
    logger.info("\n🚀 GitHub Actions 자동화 시스템 가동")
    try:
        uploader = YouTubeUploader()
        collector = AAGAGCollector()
        videos = collector.collect_and_download(max_videos=10)
        
        for idx, video in enumerate(videos, 1):
            v_path = video.get('video_path')
            if not v_path or get_video_duration(v_path) <= 0: continue

            # 파일명 정리 및 경로 확보
            safe_name = sanitize_filename(os.path.basename(v_path))
            safe_path = os.path.join(os.path.dirname(v_path), safe_name)
            os.rename(v_path, safe_path)
            v_path = safe_path

            logger.info(f"🎬 [{idx}/{len(videos)}] {video.get('title')}")
            temp_files = []
            
            try:
                metadata = create_metadata(video.get('title'), video.get('source_url'))
                proc_path = convert_to_monetizable_format(v_path, metadata['original_title'])
                if not proc_path: continue
                temp_files.append(proc_path)
                
                # 무료 TTS(gTTS)로 음성 생성
                tts_file = f"data/videos/voice_{idx}.mp3"
                tts = gTTS(text=metadata['script'], lang='ko')
                tts.save(tts_file)
                temp_files.append(tts_file)

                # 오디오 믹싱 (BGM 포함)
                final_output = proc_path.replace('.mp4', '_final.mp4')
                mix_filter = "[1:a]volume=2.5[tts];[2:a]volume=0.2:loop=-1[bgm];[tts][bgm]amix=inputs=2:duration=first[a]"
                if has_audio(proc_path):
                    mix_filter = "[0:a]volume=0.8[orig];[1:a]volume=2.5[tts];[2:a]volume=0.1:loop=-1[bgm];[orig][tts][bgm]amix=inputs=3:duration=first[a]"
                
                mix_cmd = ['ffmpeg', '-i', proc_path, '-i', tts_file, '-i', BGM_PATH, '-filter_complex', mix_filter, '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-y', final_output]
                subprocess.run(mix_cmd, capture_output=True)
                temp_files.append(final_output)

                if uploader.authenticated:
                    uploader.upload_video(video_path=final_output, title=metadata['title'], description=metadata['description'], tags=metadata['tags'])
                
                # 임시 파일 정리
                for f in temp_files + [v_path]:
                    if os.path.exists(f): os.remove(f)
            except Exception as e:
                logger.error(f"❌ 개별 영상 처리 실패: {e}")

    except Exception as e:
        logger.error(f"❌ 메인 시스템 오류: {e}")

if __name__ == "__main__":
    main()
