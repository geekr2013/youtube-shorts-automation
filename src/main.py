"""
AAGAG YouTube Shorts 자동화 - 최종 최적화 버전 (오디오 감지 및 UI 정돈)
1. 무음 영상 시 배경음악 자동 적용
2. 하단 진행바 제거 (가독성 증대)
3. OpenAI TTS 우선 -> gTTS 백업 (하이브리드 유지)
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
    from openai import OpenAI
    from gtts import gTTS
    from aagag_collector import AAGAGCollector
    from youtube_uploader import YouTubeUploader
    from email_notifier import send_email_notification
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger.info("✅ 모든 핵심 모듈 임포트 완료")
except ImportError as e:
    print(f"❌ 라이브러리 로드 실패: {e}")
    sys.exit(1)

# 설정 정보
CUSTOM_FONT_PATH = str(Path("font/SeoulAlrim-ExtraBold.otf").absolute())
BGM_PATH = "data/music/background.mp3"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def has_audio(file_path: str) -> bool:
    """영상에 오디오 스트림이 존재하는지 확인"""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'a',
            '-show_entries', 'stream=index', '-of', 'csv=p=0', str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except:
        return False

def cleanup_video_files(video_path: str, related_files: list = None):
    """임시 파일 삭제"""
    try:
        files_to_delete = [video_path]
        if related_files: files_to_delete.extend(related_files)
        for file_path in files_to_delete:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
    except Exception as e:
        logger.warning(f"   ⚠️ 파일 삭제 실패: {e}")

def create_metadata_from_title(title: str, source_url: str = "") -> dict:
    """유튜브 메타데이터 생성"""
    clean_title = re.sub(r'_\d+$', '', title).strip().replace('_', ' ')
    youtube_final_title = f"{clean_title} #shorts"
    description = f"{clean_title}\n\n😂 영상이 재밌다면 구독과 좋아요 부탁드려요!\n"
    if source_url: description += f"📌 출처: {source_url}\n"
    description += "\n#핫이슈 #숏츠 #개그 #레전드"
    
    words = re.findall(r'[가-힣a-zA-Z0-9]+', clean_title)
    tags = ['이슈', '숏츠', '개그'] + [w for w in words if len(w) >= 2][:10]
    return {'title': youtube_final_title, 'original_title': clean_title, 'description': description, 'tags': tags}

def generate_voice_safe(text: str, output_path: str):
    """하이브리드 TTS 생성"""
    input_text = f"{text}. 끝까지 확인해보세요."
    if client:
        try:
            response = client.audio.speech.create(model="tts-1", voice="alloy", input=input_text)
            response.stream_to_file(output_path)
            return output_path
        except:
            logger.warning("⚠️ OpenAI TTS 실패, gTTS로 전환합니다.")
    try:
        tts = gTTS(text=input_text, lang='ko')
        tts.save(output_path)
        return output_path
    except:
        return None

def process_video_effects(video_path: str, subtitle_text: str) -> str:
    """자막(상단) 추가 - 진행바 로직 제거됨"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_processed{video_path.suffix}"
        
        display_text = subtitle_text.replace('_', ' ')
        wrapper = textwrap.TextWrapper(width=12, break_long_words=False)
        display_text = "\n".join(wrapper.wrap(display_text))

        font_arg = CUSTOM_FONT_PATH.replace('\\', '/')
        if not os.path.exists(CUSTOM_FONT_PATH):
            font_arg = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"

        logger.info(f"📝 상단 타이틀 자막 합성 중...")
        escaped_text = display_text.replace("'", "'\\\\\\''").replace(":", "\\:")
        
        ffmpeg_cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vf', (
                f"drawtext=fontfile='{font_arg}':text='{escaped_text}':"
                f"fontcolor=white:fontsize=80:line_spacing=15:"
                f"box=1:boxcolor=black@0.4:boxborderw=25:x=(w-text_w)/2:y=120"
            ),
            '-c:a', 'copy', '-y', str(output_path)
        ]
        
        subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
        return str(output_path)
    except Exception as e:
        logger.error(f"❌ 영상 가공 실패: {e}")
        return str(video_path)

def merge_audio_final(video_path: str, tts_path: str, bgm_path: str) -> str:
    """최종 오디오 믹싱 (원본 소리 유무에 따른 가변 믹싱)"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_final.mp4"
        
        video_has_audio = has_audio(video_path)
        
        if video_has_audio:
            logger.info("🔊 원본 소리 감지: 원본+나레이션+배경음(약하게) 믹싱")
            filter_complex = (
                "[0:a]volume=1.0[orig];"
                "[1:a]volume=1.8[tts];"
                "[2:a]volume=0.12:loop=-1:size=2[bgm];" # 원본 소리가 있으면 BGM은 아주 작게
                "[orig][tts][bgm]amix=inputs=3:duration=first:dropout_transition=2[a]"
            )
        else:
            logger.info("🔇 원본 소리 없음: 나레이션+배경음(정상) 믹싱")
            filter_complex = (
                "[1:a]volume=1.8[tts];"
                "[2:a]volume=0.3:loop=-1:size=2[bgm];" # 원본 소리가 없으면 BGM을 적절히 높임
                "[tts][bgm]amix=inputs=2:duration=first:dropout_transition=2[a]"
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
    """9:16 포맷 변환"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_shorts.mp4"
        filter_str = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black"
        cmd = ['ffmpeg', '-i', str(video_path), '-vf', f"{filter_str},setsar=1", '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-y', str(output_path)]
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except: return None

def main():
    logger.info("\n🚀 최적화 자동화 시스템 가동 시작")
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
                proc_path = convert_to_shorts_format(v_path)
                if not proc_path: continue
                related.append(proc_path)
                
                proc_path = process_video_effects(proc_path, metadata['original_title'])
                related.append(proc_path)
                
                tts_file = f"data/videos/voice_{idx}.mp3"
                if generate_voice_safe(metadata['original_title'], tts_file):
                    related.append(tts_file)
                    if os.path.exists(BGM_PATH):
                        final_path = merge_audio_final(proc_path, tts_file, BGM_PATH)
                        if final_path != proc_path:
                            proc_path = final_path
                            related.append(proc_path)

                if uploader.authenticated:
                    uploader.upload_video(video_path=proc_path, title=metadata['title'], 
                                        description=metadata['description'], tags=metadata['tags'])
                cleanup_video_files(v_path, related)
            except Exception as e:
                logger.error(f"❌ 처리 오류: {e}")
                cleanup_video_files(v_path, related)
        logger.info("\n🎉 모든 자동 업로드 작업 완료!")
    except Exception as e:
        logger.error(f"❌ 시스템 오류: {e}")

if __name__ == "__main__":
    main()
