"""
AAGAG 숏폼 자동화 메인 스크립트 - 최적화 및 에러 수정 버전
"""

import os
import sys
import re
import subprocess
from pathlib import Path
import logging

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

# 설정: 사용자 폰트 경로 (루트의 font 폴더)
CUSTOM_FONT_PATH = str(Path("font/SeoulAlrim-ExtraBold.otf").absolute())

def cleanup_video_files(video_path: str, related_files: list = None):
    try:
        files_to_delete = [video_path]
        if related_files: files_to_delete.extend(related_files)
        for file_path in files_to_delete:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
    except Exception as e:
        logger.warning(f"   ⚠️ 파일 삭제 실패: {e}")

def get_folder_size(folder_path: str) -> float:
    total_size = 0
    try:
        for dirpath, _, filenames in os.walk(folder_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp): total_size += os.path.getsize(fp)
        return total_size / (1024 * 1024)
    except: return 0

def optimize_title(title: str) -> str:
    import random
    prefix_keywords = ["😂 웃겨서 터졌다", "😱 충격적인", "🔥 요즘 핫한", "👀 보면 후회함", "🚨 난리난"]
    suffix_keywords = ["#shorts", "#레전드", "#핵공감", "#개그"]
    if any(char in title for char in "😱🔥😮⚡💥🎯👀🚨😂"): return title
    optimized = f"{random.choice(prefix_keywords)} {title}" if random.random() < 0.7 else f"{title} {random.choice(suffix_keywords)}"
    return optimized[:70]

def create_metadata_from_title(title: str, source_url: str = "") -> dict:
    clean_title = re.sub(r'_\d+$', '', title).strip()
    if not clean_title: clean_title = "오늘의 핫 이슈 영상"
    optimized_title = optimize_title(clean_title)
    description = f"{clean_title}\n\n😂 웃기면 구독 부탁드려요!\n"
    if source_url: description += f"📌 출처: {source_url}\n"
    description += "\n#shorts #short #숏츠 #개그 #웃긴영상"
    
    base_tags = ['shorts', 'short', '숏츠', '개그', 'funny']
    words = re.findall(r'[가-힣a-zA-Z0-9]+', clean_title)
    tags = base_tags + [w for w in words if len(w) >= 2][:10]
    
    return {'title': optimized_title, 'original_title': clean_title, 'description': description, 'tags': tags}

def add_subtitle_to_video(video_path: str, subtitle_text: str) -> str:
    """사용자 지정 폰트를 사용하여 자막 추가"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_subtitle{video_path.suffix}"
        
        # 폰트 파일 존재 여부 확인
        font_arg = CUSTOM_FONT_PATH.replace('\\', '/') # Windows 경로 대응
        if not os.path.exists(CUSTOM_FONT_PATH):
            logger.warning(f"   ⚠️ 폰트 파일을 찾을 수 없어 기본 설정으로 진행합니다: {CUSTOM_FONT_PATH}")
            # 시스템 기본 폰트 시도 (리눅스 기준)
            font_arg = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"

        logger.info(f"   📝 자막 추가 중: '{subtitle_text[:20]}...'")
        escaped_text = subtitle_text.replace("'", "'\\\\\\''").replace(":", "\\:")
        
        ffmpeg_cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vf', f"drawtext=fontfile='{font_arg}':text='{escaped_text}':fontcolor=white:fontsize=54:box=1:boxcolor=black@0.6:boxborderw=15:x=(w-text_w)/2:y=h-th-80",
            '-c:a', 'copy', '-y', str(output_path)
        ]
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return str(output_path)
        else:
            logger.warning(f"   ⚠️ 자막 추가 실패 (FFmpeg 오류), 원본 사용")
            return str(video_path)
    except Exception as e:
        return str(video_path)

def extract_thumbnail(video_path: str) -> str:
    """0초 영상 에러 방지 로직 포함"""
    try:
        video_path = Path(video_path)
        thumbnail_path = video_path.parent / f"{video_path.stem}_thumb.jpg"
        
        # 영상 길이 확인
        probe_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0
        
        if duration <= 0:
            logger.warning("   ⚠️ 영상 길이가 0초로 인식되어 썸네일을 추출할 수 없습니다.")
            return None

        thumbnail_time = min(2.5, duration * 0.5)
        ffmpeg_cmd = ['ffmpeg', '-ss', str(thumbnail_time), '-i', str(video_path), '-vframes', '1', '-q:v', '2', '-y', str(thumbnail_path)]
        subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
        return str(thumbnail_path)
    except: return None

def convert_to_shorts_format(video_path: str) -> str:
    """비표준 파일명 및 비율 변환 에러 해결"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_shorts.mp4"
        
        # 원본 크기 확인
        probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', str(video_path)]
        res = subprocess.run(probe_cmd, capture_output=True, text=True)
        if not res.stdout.strip(): return None
        
        width, height = map(int, res.stdout.strip().split('x'))
        aspect_ratio = width / height
        
        # 9:16 강제 변환 명령어 (안전한 필터 사용)
        if aspect_ratio > 1: # 가로형
            filter_str = f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black"
        else: # 세로형
            filter_str = f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black"

        ffmpeg_cmd = ['ffmpeg', '-i', str(video_path), '-vf', f"{filter_str},setsar=1", '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-y', str(output_path)]
        
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        return str(output_path)
    except Exception as e:
        logger.error(f"   ❌ 포맷 변환 실패: {e}")
        return None

def main():
    logger.info("\n🚀 AAGAG YouTube Shorts 자동화 시작")
    try:
        uploader = YouTubeUploader()
        collector = AAGAGCollector()
        videos = collector.collect_and_download(max_videos=10)
        
        if not videos:
            logger.warning("❌ 수집된 게시물이 없습니다.")
            return

        for idx, video in enumerate(videos, 1):
            logger.info(f"\n🎬 [{idx}/{len(videos)}] {video.get('title')}")
            v_path = video.get('video_path')
            related = []
            
            try:
                metadata = create_metadata_from_title(video.get('title'), video.get('source_url'))
                
                # 1. 포맷 변환
                shorts_path = convert_to_shorts_format(v_path)
                if not shorts_path: continue
                if shorts_path != v_path: related.append(shorts_path)
                
                # 2. 자막 추가
                sub_path = add_subtitle_to_video(shorts_path, metadata['original_title'])
                if sub_path != shorts_path: related.append(sub_path)
                
                # 3. 썸네일
                thumb_path = extract_thumbnail(sub_path)
                if thumb_path: related.append(thumb_path)
                
                # 4. 업로드
                if uploader.authenticated:
                    res = uploader.upload_video(video_path=sub_path, title=metadata['title'], description=metadata['description'], tags=metadata['tags'], thumbnail_path=thumb_path)
                    if res.get('success'): logger.info(f"✅ 업로드 성공: {res.get('video_url')}")
                
                cleanup_video_files(v_path, related)
            except Exception as e:
                logger.error(f"❌ 처리 에러: {e}")
                cleanup_video_files(v_path, related)
                
        logger.info("\n🎉 모든 작업 완료!")
    except Exception as e:
        logger.error(f"❌ 실행 오류: {e}")

if __name__ == "__main__":
    main()
