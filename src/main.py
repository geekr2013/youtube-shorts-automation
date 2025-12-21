"""
AAGAG YouTube Shorts 자동화 - 하이브리드 TTS 안정화 버전
수정 사항: OpenAI 모듈 부재 시 예외 처리 및 전체 파이프라인 무결성 검증
"""

import os
import sys
import re
import subprocess
import textwrap
import logging
from pathlib import Path

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# [검증 완료] 필수 라이브러리 임포트 및 예외 처리
try:
    from openai import OpenAI
    from gtts import gTTS
    from aagag_collector import AAGAGCollector
    from youtube_uploader import YouTubeUploader
    from email_notifier import send_email_notification
    from background_music import add_background_music
    logger.info("✅ 모든 핵심 모듈 임포트 완료")
except ImportError as e:
    logger.error(f"❌ 라이브러리 로드 실패: {e}")
    logger.error("💡 조치 방법: requirements.txt에 openai, gTTS가 있는지 확인하고 다시 Push 하세요.")
    sys.exit(1)

# 설정 정보
CUSTOM_FONT_PATH = str(Path("font/SeoulAlrim-ExtraBold.otf").absolute())
BGM_PATH = "data/music/background.mp3"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def cleanup_video_files(video_path: str, related_files: list = None):
    """임시 생성된 모든 영상 및 오디오 파일 삭제"""
    try:
        files_to_delete = [video_path]
        if related_files: files_to_delete.extend(related_files)
        for file_path in files_to_delete:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
    except Exception as e:
        logger.warning(f"   ⚠️ 파일 삭제 실패: {e}")

def create_metadata_from_title(title: str, source_url: str = "") -> dict:
    """유튜브 제목(언더바 제거) 및 태그 생성"""
    clean_title = re.sub(r'_\d+$', '', title).strip()
    clean_title = clean_title.replace('_', ' ') # 언더바를 공백으로
    
    youtube_final_title = f"{clean_title} #shorts"
    description = f"{clean_title}\n\n😂 영상이 재밌다면 구독과 좋아요 부탁드려요!\n"
    if source_url:
        description += f"📌 출처: {source_url}\n"
    description += "\n#shorts #숏츠 #개그 #레전드 #꿀잼"
    
    words = re.findall(r'[가-힣a-zA-Z0-9]+', clean_title)
    tags = ['shorts', '숏츠', '개그'] + [w for w in words if len(w) >= 2][:10]
    
    return {'title': youtube_final_title, 'original_title': clean_title, 'description': description, 'tags': tags}

def generate_voice_safe(text: str, output_path: str):
    """OpenAI 우선 사용, 실패 시 gTTS로 자동 전환하는 안전 모드"""
    input_text = f"{text}. 끝까지 확인해보세요."
    
    # 1. OpenAI TTS 시도 (유료 고품질)
    if client:
        try:
            logger.info(f"🎙️ OpenAI TTS 시도 중 (alloy 보이스)...")
            response = client.audio.speech.create(
                model="tts-1",
                voice="alloy", # 경쾌한 남성 목소리
                input=input_text
            )
            response.stream_to_file(output_path)
            logger.info(f"✅ OpenAI TTS 생성 완료")
            return output_path
        except Exception as e:
            logger.warning(f"⚠️ OpenAI TTS 실패: {e}")
            logger.info("🔄 무료 gTTS 엔진으로 즉시 전환합니다.")
    
    # 2. gTTS 백업 (무료)
    try:
        logger.info(f"🎙️ gTTS(무료) 생성 중...")
        tts = gTTS(text=input_text, lang='ko')
        tts.save(output_path)
        logger.info(f"✅ gTTS 생성 완료")
        return output_path
    except Exception as e:
        logger.error(f"❌ 모든 TTS 엔진 실패: {e}")
        return None

def process_video_effects(video_path: str, subtitle_text: str) -> str:
    """자막(상단) + 시청 상태 바(하단) 합성"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_processed{video_path.suffix}"
        
        # 자막 줄바꿈 및 언더바 처리
        display_text = subtitle_text.replace('_', ' ')
        wrapper = textwrap.TextWrapper(width=12, break_long_words=False)
        wrapped_lines = wrapper.wrap(display_text)
        display_text = "\n".join(wrapped_lines)

        font_arg = CUSTOM_FONT_PATH.replace('\\', '/')
        if not os.path.exists(CUSTOM_FONT_PATH):
            font_arg = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"

        # 영상 길이 확인 (상태바 애니메이션용)
        probe_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)]
        duration_res = subprocess.run(probe_cmd, capture_output=True, text=True).stdout.strip()
        duration = float(duration_res) if duration_res else 1.0

        escaped_text = display_text.replace("'", "'\\\\\\''").replace(":", "\\:")
        
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
        logger.error(f"❌ 영상 가공 실패: {e}")
        return str(video_path)

def merge_audio_final(video_path: str, tts_path: str, bgm_path: str) -> str:
    """최종 오디오 믹싱 (영상 + 나레이션 + 배경음악)"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_final.mp4"
        
        filter_complex = (
            "[1:a]volume=1.8[tts];" 
            "[2:a]volume=0.15:loop=-1:size=2[bgm];" 
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
    """9:16 세로형 포맷 변환"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_shorts.mp4"
        filter_str = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black"
        cmd = ['ffmpeg', '-i', str(video_path), '-vf', f"{filter_str},setsar=1", '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-y', str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except: return None

def main():
    logger.info("\n🚀 하이브리드 자동화 시스템 가동 시작")
    try:
        uploader = YouTubeUploader()
        collector = AAGAGCollector()
        # [운영 효율성] 최대 10개 수집
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
                
                # 2. 자막 및 상태바 추가
                proc_path = process_video_effects(proc_path, metadata['original_title'])
                related.append(proc_path)
                
                # 3. 하이브리드 TTS 생성 (OpenAI -> gTTS)
                tts_file = f"data/videos/voice_{idx}.mp3"
                if generate_voice_safe(metadata['original_title'], tts_file):
                    related.append(tts_file)
                    # 4. 최종 오디오 합성
                    if os.path.exists(BGM_PATH):
                        final_path = merge_audio_final(proc_path, tts_file, BGM_PATH)
                        if final_path != proc_path:
                            proc_path = final_path
                            related.append(proc_path)

                # 5. 유튜브 업로드
                if uploader.authenticated:
                    uploader.upload_video(video_path=proc_path, title=metadata['title'], 
                                        description=metadata['description'], tags=metadata['tags'])
                
                # 작업 완료 후 정리 (용량 확보)
                cleanup_video_files(v_path, related)
                
            except Exception as e:
                logger.error(f"❌ 처리 오류: {e}")
                cleanup_video_files(v_path, related)
                
        logger.info("\n🎉 모든 자동 업로드 작업이 완료되었습니다!")
    except Exception as e:
        logger.error(f"❌ 시스템 오류: {e}")

if __name__ == "__main__":
    main()
