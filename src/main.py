import os
import sys
import re
import subprocess
import logging
import textwrap
import shutil
from pathlib import Path
from aagag_collector import AAGAGCollector
from youtube_uploader import YouTubeUploader

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# 환경 변수 및 경로 설정
# GEMINI_API_KEY는 이제 필요 없지만, 다른 용도를 위해 남겨둘 수 있습니다.
ENABLE_BGM = os.getenv("ENABLE_BGM", "false").lower() == "true"
ROOT_DIR = Path.cwd()
BGM_PATH = ROOT_DIR / "data" / "music" / "background.mp3"
LOCAL_FONT_NAME = "font_res.ttf"

def prepare_font():
    """시스템 폰트를 현재 작업 폴더로 복사해옵니다."""
    if os.path.exists(LOCAL_FONT_NAME):
        return os.path.abspath(LOCAL_FONT_NAME)
    fonts = [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]
    for f in fonts:
        if os.path.exists(f):
            shutil.copy(f, LOCAL_FONT_NAME)
            return os.path.abspath(LOCAL_FONT_NAME)
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

def is_valid_file(file_path):
    return os.path.exists(file_path) and os.path.getsize(file_path) > 0

def convert_to_visual_optimized_format(video_path, title_text):
    """
    [핵심 변경] AI 음성은 빼고, 시각적 가공(블러 배경)과 원본 오디오만 살립니다.
    """
    v_path = os.path.abspath(video_path)
    output_path = v_path.replace('.mp4', '_final.mp4')
    text_file_name = os.path.abspath("render_text.txt")
    font_file = prepare_font()
    
    # 제목 줄바꿈 처리
    wrapped_text = "\n".join(textwrap.wrap(title_text, width=15))
    
    try:
        with open(text_file_name, "w", encoding="utf-8") as f:
            f.write(wrapped_text)
        
        # 1. 텍스트 파일 경로 이스케이프
        safe_text_path = text_file_name.replace('\\', '/').replace(':', '\\:')
        safe_font_path = font_file.replace('\\', '/').replace(':', '\\:') if font_file else ""

        # 2. 비디오 필터: 배경 블러 + 중앙 배치 + 자막
        # (이 부분은 유지하여 '재사용 콘텐츠' 탐지를 방어합니다)
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg]; "
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg]; "
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[outv]"
        )
        
        if safe_font_path:
            filter_complex += (
                f";[outv]drawtext=fontfile='{safe_font_path}':textfile='{safe_text_path}':"
                f"fontcolor=white:fontsize=80:line_spacing=20:box=1:boxcolor=black@0.5:"
                f"boxborderw=30:x=(w-text_w)/2:y=150[finalv]"
            )
            map_v = "[finalv]"
        else:
            map_v = "[outv]"

        # 3. 오디오 처리: 원본 오디오(0:a) + 배경음악(BGM) 믹싱
        # 나레이션(TTS) 입력은 완전히 제거되었습니다.
        inputs = ['ffmpeg', '-i', v_path]
        audio_filter = ""
        map_a = ""
        
        use_bgm = ENABLE_BGM and os.path.exists(BGM_PATH)
        if use_bgm:
            inputs.extend(['-stream_loop', '-1', '-i', str(BGM_PATH)])
            # 원본 소리(1.0) + 배경음악(0.1 ~ 0.2) 섞기
            audio_filter = f";[0:a]volume=1.0[orig];[1:a]volume=0.1[bgm];[orig][bgm]amix=inputs=2:duration=first[finala]"
            map_a = "-map [finala]"
        else:
            # BGM 없으면 원본 소리만 사용
            map_a = "-map 0:a?" 

        # 최종 명령어 조립
        cmd = inputs + [
            '-filter_complex', filter_complex + audio_filter,
            '-map', map_v,
        ]
        
        if map_a:
            cmd.extend(map_a.split())
            
        cmd.extend([
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-c:a', 'aac', '-y', output_path
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0 or not is_valid_file(output_path):
            logger.error(f"❌ 가공 실패 (FFmpeg 에러): {result.stderr}")
            return None
            
        return output_path

    except Exception as e:
        logger.error(f"❌ 시스템 예외 발생: {e}")
        return None
    finally:
        if os.path.exists(text_file_name): os.remove(text_file_name)

def main():
    logger.info("🚀 수익화 대응 시스템 가동 (Visual Only Mode)")
    success_count = 0
    try:
        uploader = YouTubeUploader()
        collector = AAGAGCollector()
        # 하루 제한을 고려해 3개 정도로 조정 추천
        videos = collector.collect_and_download(max_videos=3)
        
        for idx, video in enumerate(videos, 1):
            v_path = video.get('video_path')
            if not v_path or get_video_duration(v_path) <= 0: continue

            safe_name = sanitize_filename(os.path.basename(v_path))
            safe_path = os.path.join(os.path.dirname(v_path), safe_name)
            os.rename(v_path, safe_path)
            v_path = safe_path

            logger.info(f"\n🎬 [{idx}/{len(videos)}] 처리 중: {video.get('title')}")
            
            try:
                # 불필요한 _\d 접미사 제거
                clean_title = re.sub(r'_\d+$', '', video.get('title')).strip().replace('_', ' ')
                
                # [변경] AI 대본 생성 및 TTS 과정 생략 -> 바로 영상 가공
                final_output = convert_to_visual_optimized_format(v_path, clean_title)
                
                if not final_output:
                    logger.warning("⚠️ 영상 가공 실패. 건너뜁니다.")
                    if os.path.exists(v_path): os.remove(v_path)
                    continue

                # 유튜브 업로드
                if uploader.authenticated:
                    # 설명란도 심플하게 변경
                    desc = f"{clean_title}\n\n재밌게 보셨다면 구독과 좋아요 부탁드립니다!\n#이슈 #유머 #영상"
                    uploader.upload_video(video_path=final_output, title=f"{clean_title} #shorts", description=desc, tags=["shorts", "이슈"])
                    success_count += 1
                    logger.info("✅ 업로드 완료")
                
                # 파일 정리
                if os.path.exists(v_path): os.remove(v_path)
                if os.path.exists(final_output): os.remove(final_output)

            except Exception as e:
                logger.error(f"❌ 개별 처리 중 에러: {e}")
                # 에러 나도 다음 영상으로 진행

        logger.info(f"\n🎉 최종 업로드 성공: {success_count}개")
        if os.path.exists(LOCAL_FONT_NAME): os.remove(LOCAL_FONT_NAME)
        # 하나도 성공 못하면 실패 처리 (로그 확인용)
        if success_count == 0 and len(videos) > 0: sys.exit(1)

    except Exception as e:
        logger.error(f"❌ 메인 시스템 에러: {e}")
        if os.path.exists(LOCAL_FONT_NAME): os.remove(LOCAL_FONT_NAME)
        sys.exit(1)

if __name__ == "__main__":
    main()
