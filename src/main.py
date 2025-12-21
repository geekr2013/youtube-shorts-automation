"""
AAGAG YouTube Shorts 자동화 - 수익 창출 고도화 버전
개선 사항: AI 나레이션(TTS), 시청 상태 바(Progress Bar), 제목/자막 가독성 최적화
"""

import os
import sys
import re
import subprocess
from pathlib import Path
import logging
import textwrap
from gtts import gTTS # AI 목소리 생성용

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# 모듈 임포트
try:
    from aagag_collector import AAGAGCollector
    from youtube_uploader import YouTubeUploader
    from email_notifier import send_email_notification
    from background_music import add_background_music
    logger.info("✅ 모듈 임포트 완료")
except ImportError as e:
    logger.error(f"❌ 모듈 임포트 실패: {e}")
    sys.exit(1)

# 설정
CUSTOM_FONT_PATH = str(Path("font/SeoulAlrim-ExtraBold.otf").absolute())
BGM_PATH = "data/music/background.mp3"

def cleanup_video_files(video_path: str, related_files: list = None):
    try:
        files_to_delete = [video_path]
        if related_files: files_to_delete.extend(related_files)
        for file_path in files_to_delete:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
    except Exception as e:
        logger.warning(f"   ⚠️ 파일 삭제 실패: {e}")

def create_metadata_from_title(title: str, source_url: str = "") -> dict:
    """제목의 언더바를 제거하고 정제된 메타데이터 생성"""
    clean_title = re.sub(r'_\d+$', '', title).strip()
    clean_title = clean_title.replace('_', ' ') # 언더바 제거
    
    if not clean_title or len(clean_title) < 2:
        clean_title = "오늘의 화제 영상"
    
    youtube_final_title = f"{clean_title} #shorts"
    description = f"{clean_title}\n\n😂 영상이 재밌다면 구독과 좋아요 부탁드려요!\n"
    if source_url:
        description += f"📌 출처: {source_url}\n"
    description += "\n#shorts #숏츠 #개그 #레전드 #꿀잼"
    
    words = re.findall(r'[가-힣a-zA-Z0-9]+', clean_title)
    tags = ['shorts', '숏츠', '개그'] + [w for w in words if len(w) >= 2][:10]
    
    return {
        'title': youtube_final_title, 
        'original_title': clean_title, 
        'description': description, 
        'tags': tags
    }

def generate_tts(text: str, output_path: str):
    """AI 목소리(TTS) 생성"""
    try:
        logger.info(f"🎙️ AI 나레이션 생성 중...")
        # 짧고 강렬한 첫 문장 생성
        intro_text = f"{text}. 끝까지 확인해보세요."
        tts = gTTS(text=intro_text, lang='ko')
        tts.save(output_path)
        return output_path
    except Exception as e:
        logger.error(f"❌ TTS 생성 실패: {e}")
        return None

def process_video_effects(video_path: str, subtitle_text: str) -> str:
    """자막 추가 + 상태 바 추가 + FFmpeg 통합 처리"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_processed{video_path.suffix}"
        
        # 자막 정제 및 줄바꿈
        display_text = subtitle_text.replace('_', ' ')
        wrapper = textwrap.TextWrapper(width=12, break_long_words=False)
        wrapped_lines = wrapper.wrap(display_text)
        display_text = "\n".join(wrapped_lines)

        font_arg = CUSTOM_FONT_PATH.replace('\\', '/')
        if not os.path.exists(CUSTOM_FONT_PATH):
            font_arg = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"

        # 영상 길이 추출 (상태 바 계산용)
        probe_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)]
        duration = float(subprocess.run(probe_cmd, capture_output=True, text=True).stdout.strip())

        logger.info(f"📝 자막 및 상태바 합성 중...")
        escaped_text = display_text.replace("'", "'\\\\\\''").replace(":", "\\:")
        
        # [상태바 로직] drawbox 필터 사용: 시간이 흐를수록 가로 길이가 늘어남
        # [자막 로직] 기존 상단 자막 유지
        ffmpeg_cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vf', (
                f"drawtext=fontfile='{font_arg}':text='{escaped_text}':"
                f"fontcolor=white:fontsize=80:line_spacing=15:"
                f"box=1:boxcolor=black@0.4:boxborderw=25:x=(w-text_w)/2:y=120,"
                f"drawbox=y=ih-15:w=iw*t/{duration}:h=15:color=red@0.8:t=fill"
            ),
            '-c:a', 'copy', '-y', str(output_path)
        ]
        
        subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
        return str(output_path)
    except Exception as e:
        logger.warning(f"⚠️ 영상 가공 에러: {e}")
        return str(video_path)

def merge_audio_all(video_path: str, tts_path: str, bgm_path: str) -> str:
    """영상 + 나레이션(TTS) + 배경음악(BGM) 최종 믹싱"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_final.mp4"
        
        # TTS는 시작하자마자 크게, BGM은 잔잔하게 깔리도록 설정
        filter_complex = (
            "[1:a]volume=1.5[tts];" # 나레이션 볼륨 업
            "[2:a]volume=0.2:loop=-1:size=2[bgm];" # BGM 볼륨 다운 및 루프
            "[0:a][tts][bgm]amix=inputs=3:duration=first:dropout_transition=2[a]"
        )
        
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-i', str(tts_path),
            '-i', str(bgm_path),
            '-filter_complex', filter_complex,
            '-map', '0:v', '-map', '[a]',
            '-c:v', 'copy', '-c:a', 'aac', '-y', str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except Exception as e:
        logger.error(f"❌ 오디오 믹싱 실패: {e}")
        return str(video_path)

def convert_to_shorts_format(video_path: str) -> str:
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_shorts.mp4"
        filter_str = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black"
        cmd = ['ffmpeg', '-i', str(video_path), '-vf', f"{filter_str},setsar=1", '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-y', str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except: return None

def main():
    logger.info("\n🚀 수익 창출 고도화 시스템 가동")
    try:
        uploader = YouTubeUploader()
        collector = AAGAGCollector()
        videos = collector.collect_and_download(max_videos=10)
        
        for idx, video in enumerate(videos, 1):
            logger.info(f"\n🎬 [{idx}/{len(videos)}] {video.get('title')}")
            v_path = video.get('video_path')
            related = []
            
            try:
                metadata = create_metadata_from_title(video.get('title'), video.get('source_url'))
                
                # 1. 쇼츠 규격 변환
                proc_path = convert_to_shorts_format(v_path)
                if not proc_path: continue
                related.append(proc_path)
                
                # 2. 자막 및 하단 상태 바 추가
                proc_path = process_video_effects(proc_path, metadata['original_title'])
                related.append(proc_path)
                
                # 3. AI 나레이션(TTS) 파일 생성
                tts_file = f"data/videos/tts_{idx}.mp3"
                if generate_tts(metadata['original_title'], tts_file):
                    related.append(tts_file)
                    # 4. 오디오 최종 믹싱 (영상 + TTS + BGM)
                    if os.path.exists(BGM_PATH):
                        final_path = merge_audio_all(proc_path, tts_file, BGM_PATH)
                        if final_path != proc_path:
                            proc_path = final_path
                            related.append(proc_path)

                # 5. 썸네일 추출 및 업로드
                thumb_path = video.get('video_path').replace('.mp4', '_thumb.jpg') # 간소화
                if uploader.authenticated:
                    uploader.upload_video(video_path=proc_path, title=metadata['title'], 
                                        description=metadata['description'], tags=metadata['tags'])
                
                cleanup_video_files(v_path, related)
            except Exception as e:
                logger.error(f"❌ 처리 실패: {e}")
                cleanup_video_files(v_path, related)
                
    except Exception as e:
        logger.error(f"❌ 실행 오류: {e}")

if __name__ == "__main__":
    main()
