import os
import sys
import re
import subprocess
import logging
import textwrap
import shutil
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
BGM_PATH = ROOT_DIR / "data" / "music" / "background.mp3"
LOCAL_FONT_NAME = "font_res.ttf"

def prepare_font():
    """시스템 폰트를 현재 폴더로 복사 (경로 문제 원천 차단)"""
    if os.path.exists(LOCAL_FONT_NAME):
        return LOCAL_FONT_NAME
    fonts = [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]
    for f in fonts:
        if os.path.exists(f):
            shutil.copy(f, LOCAL_FONT_NAME)
            return LOCAL_FONT_NAME
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
        prompt = f"유튜브 쇼츠 제목 '{title}'을 보고 시청자가 흥미를 느낄 수 있게 10초 내외의 구어체 나레이션 대본을 한 문장으로 써줘."
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return f"오늘 영상은 {title} 입니다. 정말 흥미롭네요!"

def convert_to_monetizable_format(video_path, title_text):
    """[핵심 수정] -filter_complex를 사용하여 수익화 포맷 가공"""
    v_path = Path(video_path)
    output_path = v_path.parent / f"{v_path.stem}_monetized.mp4"
    text_file_name = "render_text.txt"
    font_file = prepare_font()
    
    wrapped_text = "\n".join(textwrap.wrap(title_text, width=15))
    
    try:
        with open(text_file_name, "w", encoding="utf-8") as f:
            f.write(wrapped_text)
        
        # [핵심 변경] -vf 대신 -filter_complex를 사용해야 status 234 에러가 발생하지 않습니다.
        filter_complex_str = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg]; "
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg]; "
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[outv]"
        )
        
        if font_file:
            filter_complex_str += (
                f";[outv]drawtext=fontfile='{font_file}':textfile='{text_file_name}':"
                f"fontcolor=white:fontsize=80:line_spacing=20:box=1:boxcolor=black@0.5:"
                f"boxborderw=30:x=(w-text_w)/2:y=150[finalv]"
            )
            map_label = "[finalv]"
        else:
            map_label = "[outv]"

        cmd = [
            'ffmpeg', '-i', str(v_path),
            '-filter_complex', filter_complex_str,
            '-map', map_label,
            '-map', '0:a?', # 오디오가 있으면 가져오고 없으면 무시
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-c:a', 'aac', '-y', str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except Exception as e:
        logger.error(f"❌ 영상 가공 실패: {e}")
        return None
    finally:
        if os.path.exists(text_file_name): os.remove(text_file_name)

def main():
    logger.info("🚀 수익화 대응 시스템 가동 (Final: filter_complex fix)")
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

            logger.info(f"🎬 [{idx}/{len(videos)}] {video.get('title')}")
            temp_files = []
            
            try:
                clean_title = re.sub(r'_\d+$', '', video.get('title')).strip().replace('_', ' ')
                script = generate_ai_script(clean_title)
                
                proc_path = convert_to_monetizable_format(v_path, clean_title)
                if not proc_path: continue
                temp_files.append(proc_path)
                
                tts_file = f"data/videos/voice_{idx}.mp3"
                gTTS(text=script, lang='ko').save(tts_file)
                temp_files.append(tts_file)

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

                if uploader.authenticated:
                    uploader.upload_video(video_path=final_output, title=f"{clean_title} #shorts", description=f"{script}\n#이슈 #유머", tags=["shorts"])
                    success_count += 1
                    logger.info("✅ 업로드 완료")
                
                for f in temp_files + [v_path]:
                    if os.path.exists(f): os.remove(f)

            except Exception as e:
                logger.error(f"❌ 개별 처리 실패: {e}")

        logger.info(f"🎉 최종 업로드 성공: {success_count}개")
        if os.path.exists(LOCAL_FONT_NAME): os.remove(LOCAL_FONT_NAME)
        if success_count == 0 and len(videos) > 0: sys.exit(1)

    except Exception as e:
        logger.error(f"❌ 메인 시스템 에러: {e}")
        if os.path.exists(LOCAL_FONT_NAME): os.remove(LOCAL_FONT_NAME)
        sys.exit(1)

if __name__ == "__main__":
    main()
