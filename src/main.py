"""
AAGAG YouTube Shorts 자동화 - 수익화 최적화 버전
1. GPT 기반 나레이션 대본 자동 생성
2. 시각적 차별화를 위한 블러 배경 효과 추가
3. 파일명 정규화 및 0초 영상 에러 방지 로직 포함
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
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger.info("✅ 수익화 대응 모듈 로드 완료")
except ImportError as e:
    print(f"❌ 라이브러리 로드 실패: {e}. pip install openai gtts 등을 확인하세요.")
    sys.exit(1)

# 설정 정보
CUSTOM_FONT_PATH = str(Path("font/SeoulAlrim-ExtraBold.otf").absolute())
BGM_PATH = "data/music/background.mp3"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def sanitize_filename(filename: str) -> str:
    """파일명 에러 방지를 위한 정규화"""
    base, ext = os.path.splitext(filename)
    clean_base = re.sub(r'[^\w\s\d가-힣]', '', base).replace(' ', '_')
    return f"{clean_base[:50]}{ext}"

def get_video_duration(file_path: str) -> float:
    """영상의 실제 길이를 측정"""
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

def cleanup_video_files(video_path: str, related_files: list = None):
    try:
        files_to_delete = [video_path]
        if related_files: files_to_delete.extend(related_files)
        for f in files_to_delete:
            if f and os.path.exists(f): os.remove(f)
    except: pass

def generate_ai_script(title: str) -> str:
    """GPT를 사용하여 수익화용 나레이션 대본 생성"""
    if not client: return title
    try:
        prompt = f"이 유튜브 쇼츠 영상 제목을 바탕으로 시청자의 호기심을 자극하는 10초 내외의 짧은 나레이션 대본을 써줘. 문장은 ~네요, ~일까요? 처럼 친근하게. 제목: {title}"
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except:
        return f"오늘 소개할 내용은 {title} 입니다. 정말 흥미롭지 않나요?"

def create_metadata(title: str, source_url: str = "") -> dict:
    clean_title = re.sub(r'_\d+$', '', title).strip().replace('_', ' ')
    ai_script = generate_ai_script(clean_title)
    
    youtube_final_title = f"{clean_title} #shorts #이슈 #재미"
    description = f"{ai_script}\n\n😂 영상이 재밌다면 구독과 좋아요 부탁드려요!\n"
    if source_url: description += f"📌 출처: {source_url}\n"
    
    words = re.findall(r'[가-힣a-zA-Z0-9]+', clean_title)
    tags = ['이슈', '숏츠', '개그'] + [w for w in words if len(w) >= 2][:10]
    return {'title': youtube_final_title, 'script': ai_script, 'original_title': clean_title, 'description': description, 'tags': tags}

def generate_voice_safe(text: str, output_path: str):
    """나레이션 생성"""
    if client:
        try:
            response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
            response.stream_to_file(output_path)
            return output_path
        except: pass
    try:
        tts = gTTS(text=text, lang='ko')
        tts.save(output_path)
        return output_path
    except: return None

def convert_to_monetizable_format(video_path: str, title_text: str) -> str:
    """수익화를 위한 시각적 가공: 블러 배경 + 9:16 + 자막"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_final_prod.mp4"
        
        font_arg = CUSTOM_FONT_PATH.replace('\\', '/')
        if not os.path.exists(CUSTOM_FONT_PATH):
            font_arg = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"

        # 블러 배경 효과 + 중앙 영상 배치 + 상단 자막 필터
        # 1. 배경을 크게 키워 블러 처리, 2. 원본을 비율에 맞게 중앙 배치, 3. 자막 추가
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg];"
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
            f"drawtext=fontfile='{font_arg}':text='{title_text}':fontcolor=white:fontsize=80:"
            f"box=1:boxcolor=black@0.5:boxborderw=30:x=(w-text_w)/2:y=150"
        )

        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vf', filter_complex,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-c:a', 'aac', '-y', str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except Exception as e:
        logger.error(f"❌ 영상 가공 에러: {e}")
        return None

def merge_audio_final(video_path: str, tts_path: str, bgm_path: str) -> str:
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"final_upload_{video_path.name}"
        has_v_audio = has_audio(str(video_path))
        
        if has_v_audio:
            filter_audio = "[0:a]volume=0.8[orig];[1:a]volume=2.0[tts];[2:a]volume=0.1:loop=-1:size=2[bgm];[orig][tts][bgm]amix=inputs=3:duration=first[a]"
        else:
            filter_audio = "[1:a]volume=2.0[tts];[2:a]volume=0.3:loop=-1:size=2[bgm];[tts][bgm]amix=inputs=2:duration=first[a]"
            
        cmd = [
            'ffmpeg', '-i', str(video_path), '-i', str(tts_path), '-i', str(bgm_path),
            '-filter_complex', filter_audio, '-map', '0:v', '-map', '[a]',
            '-c:v', 'copy', '-c:a', 'aac', '-y', str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
    except: return str(video_path)

def main():
    logger.info("\n🚀 수익화 대응 자동화 시스템 시작")
    try:
        uploader = YouTubeUploader()
        collector = AAGAGCollector()
        videos = collector.collect_and_download(max_videos=10)
        
        for idx, video in enumerate(videos, 1):
            v_path = video.get('video_path')
            if not v_path or get_video_duration(v_path) <= 0:
                logger.warning(f"⚠️ 건너뜀 (파일 없음 혹은 0초): {video.get('title')}")
                continue

            # 파일명 안전하게 변경
            safe_v_path = os.path.join(os.path.dirname(v_path), sanitize_filename(os.path.basename(v_path)))
            os.rename(v_path, safe_v_path)
            v_path = safe_v_path

            logger.info(f"\n🎬 [{idx}/{len(videos)}] 처리 중: {video.get('title')}")
            related = []
            
            try:
                # 1. 메타데이터 및 AI 대본 생성
                metadata = create_metadata(video.get('title'), video.get('source_url'))
                
                # 2. 영상 포맷 변환 (블러 배경 + 자막)
                proc_path = convert_to_monetizable_format(v_path, metadata['original_title'])
                if not proc_path: continue
                related.append(proc_path)
                
                # 3. AI 나레이션 생성
                tts_file = f"data/videos/voice_{idx}.mp3"
                if generate_voice_safe(metadata['script'], tts_file):
                    related.append(tts_file)
                    # 4. 오디오 믹싱
                    if os.path.exists(BGM_PATH):
                        final_path = merge_audio_final(proc_path, tts_file, BGM_PATH)
                        if final_path != proc_path:
                            proc_path = final_path
                            related.append(proc_path)

                # 5. 업로드
                if uploader.authenticated:
                    uploader.upload_video(video_path=proc_path, title=metadata['title'], 
                                        description=metadata['description'], tags=metadata['tags'])
                
                cleanup_video_files(v_path, related)
                logger.info(f"✅ 처리 및 업로드 완료")
            except Exception as e:
                logger.error(f"❌ 개별 영상 처리 오류: {e}")
                cleanup_video_files(v_path, related)

        logger.info("\n🎉 모든 작업이 완료되었습니다!")
    except Exception as e:
        logger.error(f"❌ 시스템 오류: {e}")

if __name__ == "__main__":
    main()
