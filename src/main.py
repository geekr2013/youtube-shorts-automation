"""
AAGAG 숏폼 자동화 메인 스크립트 - 자동 정리 버전
- 업로드 성공 후 즉시 영상 파일 삭제
- 저장소 용량 1GB 유지
"""

import os
import sys
import re
import subprocess
from pathlib import Path
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
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


def cleanup_video_files(video_path: str, related_files: list = None):
    """
    업로드 완료된 영상 및 관련 파일 삭제
    
    Args:
        video_path: 원본 영상 경로
        related_files: 관련 파일 경로 리스트 (썸네일, 변환본 등)
    """
    try:
        files_to_delete = [video_path]
        
        # 관련 파일 추가
        if related_files:
            files_to_delete.extend(related_files)
        
        # 파일 삭제
        deleted_count = 0
        for file_path in files_to_delete:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
                logger.debug(f"      🗑️ 삭제: {Path(file_path).name}")
        
        if deleted_count > 0:
            logger.info(f"   🗑️ {deleted_count}개 파일 삭제 완료\n")
        
    except Exception as e:
        logger.warning(f"   ⚠️ 파일 삭제 실패: {e}\n")


def get_folder_size(folder_path: str) -> float:
    """
    폴더 용량 계산 (MB)
    
    Args:
        folder_path: 폴더 경로
        
    Returns:
        용량 (MB)
    """
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size / (1024 * 1024)  # MB
    except:
        return 0


def optimize_title(title: str) -> str:
    """
    제목 최적화 - Shorts 알고리즘 최적화
    - 감정적 호소력 강화
    - 호기심 유발 키워드 추가
    - 클릭률(CTR) 향상 목표
    """
    import random
    
    # 감정 유발 접두어 (클릭률 최적화)
    prefix_keywords = [
        "😂 웃겨서 터졌다", "😱 충격적인", "🔥 요즘 핫한", "😮 진짜 미친",
        "💥 역대급", "🎯 꼭 봐야하는", "👀 보면 후회함", "🚨 난리난"
    ]
    
    # 공감/관심 접미어 (알고리즘 선호)
    suffix_keywords = [
        "#shorts", "#레전드", "#실화냐", "#핵공감",
        "#개웃김", "#꿀잼", "#진짜웃김", "#개그"
    ]
    
    # 이미 이모지가 있으면 스킵
    if any(char in title for char in "😱🔥😮⚡💥🎯👀🚨😂"):
        return title
    
    # 70% 확률로 접두어 추가 (더 눈에 띔)
    if random.random() < 0.7:
        optimized = f"{random.choice(prefix_keywords)} {title}"
    else:
        optimized = f"{title} {random.choice(suffix_keywords)}"
    
    # 제목 길이 제한 (YouTube 권장: 70자 이하)
    if len(optimized) > 70:
        optimized = title[:67] + "..."
    
    return optimized


def extract_keywords_from_title(title: str, max_keywords: int = 15) -> list:
    """
    제목에서 키워드 추출하여 태그 생성
    - Shorts 최적화 태그 추가
    - 한국어 + 영문 태그 혼합 (글로벌 노출 확대)
    """
    # Shorts 필수 태그 (알고리즘 최적화)
    base_tags = [
        'shorts', 'short', '숏츠', '쇼츠',
        '개그', '웃긴영상', '꿀잼', 
        'funny', 'comedy', 'humor',
        '한국', 'korea', 'korean'
    ]
    
    # 제목에서 키워드 추출
    words = re.findall(r'[가-힣a-zA-Z0-9]+', title)
    keywords = [word for word in words if len(word) >= 2 and word.lower() not in ['the', 'and', 'for']]
    keywords = list(dict.fromkeys(keywords))  # 중복 제거
    keywords = keywords[:max_keywords - len(base_tags)]
    
    return base_tags + keywords


def create_metadata_from_title(title: str, source_url: str = "") -> dict:
    """원본 제목에서 메타데이터 생성"""
    clean_title = title
    clean_title = re.sub(r'\.(mp4|gif|webm)$', '', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'_\d+$', '', clean_title)
    clean_title = clean_title.strip()
    
    if not clean_title or len(clean_title) < 2:
        clean_title = "오늘의 핫 이슈 영상"
    
    optimized_title = optimize_title(clean_title)
    
    # Shorts 최적화 설명 작성
    description = f"{clean_title}\n\n"
    description += "😂 웃기면 구독 부탁드려요!\n"
    description += "👍 좋아요와 댓글은 큰 힘이 됩니다\n\n"
    
    if source_url:
        description += f"📌 출처: AAGAG\n{source_url}\n\n"
    
    # SEO 최적화 해시태그 (알고리즘 선호)
    description += "#shorts #short #숏츠 #쇼츠 #개그 #웃긴영상 #꿀잼 "
    description += "#funny #comedy #humor #핫이슈 #화제의영상 #레전드 "
    description += "#한국 #korea #korean"
    
    tags = extract_keywords_from_title(clean_title)
    
    return {
        'title': optimized_title,
        'original_title': clean_title,
        'description': description,
        'tags': tags
    }


def add_subtitle_to_video(video_path: str, subtitle_text: str) -> str:
    """영상에 자막 추가 (ffmpeg 사용)"""
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_subtitle{video_path.suffix}"
        
        logger.info(f"   📝 자막 추가 중: '{subtitle_text[:30]}...'")
        
        escaped_text = subtitle_text.replace("'", "'\\\\\\''").replace(":", "\\:")
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vf',
            f"drawtext=fontfile=/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf:"
            f"text='{escaped_text}':"
            f"fontcolor=white:"
            f"fontsize=48:"
            f"box=1:"
            f"boxcolor=black@0.6:"
            f"boxborderw=10:"
            f"x=(w-text_w)/2:"
            f"y=h-th-50",
            '-c:a', 'copy',
            '-y',
            str(output_path)
        ]
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"   ✅ 자막 추가 완료\n")
            return str(output_path)
        else:
            logger.warning(f"   ⚠️ 자막 추가 실패, 원본 사용\n")
            return str(video_path)
            
    except Exception as e:
        logger.warning(f"   ⚠️ 자막 추가 오류: {e}")
        return str(video_path)


def extract_thumbnail(video_path: str) -> str:
    """
    영상에서 최적의 썸네일 추출
    - 시작 후 2~3초 구간에서 선명한 프레임 추출 (클릭률 최적화)
    - 고품질 JPEG 생성 (YouTube 썸네일 최적화)
    """
    try:
        video_path = Path(video_path)
        thumbnail_path = video_path.parent / f"{video_path.stem}_thumb.jpg"
        
        logger.info(f"   🖼️ 고품질 썸네일 추출 중...")
        
        probe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path)
        ]
        
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        
        # 썸네일 추출 위치 최적화: 시작 후 2~3초 (가장 중요한 구간)
        # 너무 처음은 로딩 화면일 수 있고, 중간은 덜 중요함
        thumbnail_time = min(2.5, duration * 0.3)  # 2.5초 또는 영상의 30% 지점
        
        logger.info(f"   ⏱️ 추출 위치: {thumbnail_time:.1f}초 (총 {duration:.1f}초)")
        
        # 고품질 썸네일 생성
        ffmpeg_cmd = [
            'ffmpeg',
            '-ss', str(thumbnail_time),
            '-i', str(video_path),
            '-vframes', '1',
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease',  # Shorts 비율 유지
            '-q:v', '1',  # 최고 품질 (2 → 1)
            '-y',
            str(thumbnail_path)
        ]
        
        subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
        
        # 썸네일 파일 크기 확인
        thumb_size = os.path.getsize(thumbnail_path) / 1024  # KB
        logger.info(f"   ✅ 썸네일 추출 완료 ({thumb_size:.1f} KB)\n")
        return str(thumbnail_path)
        
    except Exception as e:
        logger.warning(f"   ⚠️ 썸네일 추출 실패: {e}\n")
        return None


def convert_to_shorts_format(video_path: str) -> str:
    """
    영상을 YouTube Shorts 세로 포맷(1080x1920)으로 강제 변환
    - 모든 영상을 정확히 9:16 비율로 변환
    - 수익화 최적화를 위한 품질 개선
    """
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_shorts{video_path.suffix}"
        
        logger.info(f"   🎬 Shorts 포맷(9:16)으로 변환 중...")
        
        # 원본 영상 크기 확인
        probe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=s=x:p=0',
            str(video_path)
        ]
        
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split('x'))
        
        aspect_ratio = width / height
        logger.info(f"   📐 원본 크기: {width}x{height} (비율: {aspect_ratio:.2f})")
        
        target_width = 1080
        target_height = 1920
        target_ratio = target_width / target_height  # 0.5625 (정확히 9:16)
        
        # 이미 9:16 비율인지 엄격하게 체크 (오차 ±2% 이내)
        ratio_diff = abs(aspect_ratio - target_ratio)
        if ratio_diff < 0.01 and width >= 1080 and height >= 1920:
            logger.info(f"   ✅ 이미 완벽한 Shorts 포맷입니다 (스킵)\n")
            return str(video_path)
        
        # 변환 필요: 모든 영상을 9:16으로 강제 변환
        logger.info(f"   🔄 {'가로형' if aspect_ratio > 1 else '비표준 비율'} → Shorts 세로형(9:16) 변환")
        
        if aspect_ratio > 1:
            # 가로형 영상: 블러 배경 + 중앙 배치 (시네마틱 효과)
            logger.info(f"   ✨ 블러 배경 추가 (수익화 최적화)")
            
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-filter_complex',
                # 배경: 블러 처리 + 약간 어둡게
                f'[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,'
                f'crop={target_width}:{target_height},'
                f'boxblur=30:5,'
                f'eq=brightness=-0.15:saturation=1.2,'
                f'setsar=1[bg];'
                # 전경: 원본 영상을 적절한 크기로
                f'[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
                f'setsar=1[fg];'
                # 배경 위에 전경 오버레이
                f'[bg][fg]overlay=(W-w)/2:(H-h)/2',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '20',  # 품질 향상 (23 → 20)
                '-profile:v', 'high',
                '-level', '4.2',
                '-c:a', 'aac',
                '-b:a', '192k',  # 오디오 품질 향상 (128k → 192k)
                '-ar', '48000',
                '-movflags', '+faststart',
                '-y',
                str(output_path)
            ]
        else:
            # 세로형이지만 비율이 맞지 않는 경우: 패딩 추가
            logger.info(f"   📏 정확한 9:16 비율로 조정")
            
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-vf', f'scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
                       f'pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black,'
                       f'setsar=1',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '20',  # 품질 향상
                '-profile:v', 'high',
                '-level', '4.2',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '48000',
                '-movflags', '+faststart',
                '-y',
                str(output_path)
            ]
        
        # 변환 실행
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        
        # 변환 결과 확인
        verify_result = subprocess.run(probe_cmd[:-1] + [str(output_path)], 
                                       capture_output=True, text=True, check=True)
        new_width, new_height = map(int, verify_result.stdout.strip().split('x'))
        logger.info(f"   ✅ 변환 완료: {new_width}x{new_height} (9:16 비율)")
        logger.info(f"   📁 파일: {output_path.name}\n")
        
        return str(output_path)
        
    except Exception as e:
        logger.error(f"   ❌ 포맷 변환 실패: {e}")
        logger.error(f"   ⚠️ 이 영상은 업로드를 스킵합니다\n")
        # 변환 실패 시 None 반환 (업로드 스킵)
        return None


def main():
    """메인 실행 함수"""
    logger.info("\n" + "="*70)
    logger.info("🚀 AAGAG YouTube Shorts 자동화 시작 (자동 정리 버전)")
    logger.info("="*70 + "\n")
    
    try:
        # 0. 환경 변수 확인
        gmail_user = os.getenv('GMAIL_USERNAME')
        notification_email = os.getenv('NOTIFICATION_EMAIL')
        enable_bgm = os.getenv('ENABLE_BGM', 'false').lower() == 'true'
        bgm_path = os.getenv('BGM_PATH', 'data/music/background.mp3')
        
        # 시작 전 용량 확인
        videos_folder = Path("data/videos")
        initial_size = get_folder_size(str(videos_folder))
        logger.info(f"📦 시작 전 저장소 용량: {initial_size:.2f} MB\n")
        
        # 1. YouTube 업로더 초기화
        uploader = YouTubeUploader()
        
        if not uploader.authenticated:
            logger.warning("⚠️ YouTube 인증 정보 없음 - 수집만 진행합니다")
        else:
            logger.info("✅ YouTube 업로더 준비 완료\n")
        
        # 2. AAGAG 콘텐츠 수집
        logger.info("📥 AAGAG 콘텐츠 수집 시작...\n")
        collector = AAGAGCollector()
        
        # 수집 및 다운로드 실행 (최대 10개)
        videos = collector.collect_and_download(max_videos=10)
        
        if not videos:
            logger.warning("\n❌ 수집된 게시물이 없습니다.\n")
            
            if gmail_user and notification_email:
                send_email_notification(
                    subject="⚠️ AAGAG 자동화 - 수집 실패",
                    body="수집된 게시물이 없습니다. AAGAG 사이트를 확인해주세요."
                )
            
            return
        
        logger.info(f"\n✅ {len(videos)}개 비디오 수집 완료\n")
        logger.info("="*70 + "\n")
        
        # 3. 각 비디오 처리 및 업로드
        upload_results = []
        
        for idx, video in enumerate(videos, 1):
            logger.info(f"{'='*70}")
            logger.info(f"🎬 [{idx}/{len(videos)}] 비디오 처리 중")
            logger.info(f"{'='*70}\n")
            
            video_path = video.get('video_path')
            original_title = video.get('title', '오늘의 핫 이슈 영상')
            source_url = video.get('source_url', '')
            
            if not video_path or not os.path.exists(video_path):
                logger.warning(f"⚠️ 비디오 파일 없음: {video_path}\n")
                continue
            
            # 처리 과정에서 생성된 파일들을 추적
            related_files = []
            
            try:
                # 3-1. 메타데이터 생성
                logger.info("📝 메타데이터 생성 중...")
                metadata = create_metadata_from_title(original_title, source_url)
                
                title = metadata['title']
                original_clean_title = metadata['original_title']
                description = metadata['description']
                tags = metadata['tags']
                
                logger.info(f"   ✅ 원본 제목: {original_clean_title}")
                logger.info(f"   ✅ 최적화 제목: {title}")
                logger.info(f"   ✅ 태그: {', '.join(tags[:5])}...\n")
                
                # 3-2. Shorts 포맷 변환 (필수)
                shorts_video_path = convert_to_shorts_format(video_path)
                if shorts_video_path is None:
                    logger.error(f"⚠️ Shorts 포맷 변환 실패 - 이 영상은 스킵합니다\n")
                    cleanup_video_files(video_path, related_files)
                    continue
                
                if shorts_video_path != video_path:
                    related_files.append(shorts_video_path)
                
                # 3-3. 자막 추가
                subtitled_video_path = add_subtitle_to_video(shorts_video_path, original_clean_title)
                if subtitled_video_path != shorts_video_path:
                    related_files.append(subtitled_video_path)
                
                # 3-4. 썸네일 추출
                thumbnail_path = extract_thumbnail(subtitled_video_path)
                if thumbnail_path:
                    related_files.append(thumbnail_path)
                
                # 3-5. 배경음악 추가 (선택)
                final_video_path = subtitled_video_path
                if enable_bgm and os.path.exists(bgm_path):
                    logger.info("🎵 배경음악 추가 중...")
                    try:
                        final_video_path = add_background_music(
                            video_path=subtitled_video_path,
                            music_path=bgm_path
                        )
                        if final_video_path != subtitled_video_path:
                            related_files.append(final_video_path)
                        logger.info(f"   ✅ 배경음악 추가 완료\n")
                    except Exception as e:
                        logger.warning(f"   ⚠️ 배경음악 추가 실패: {e}")
                        logger.warning(f"   ⚠️ 원본 영상 사용\n")
                        final_video_path = subtitled_video_path
                
                # 3-6. YouTube 업로드
                if uploader.authenticated:
                    logger.info("📤 YouTube 업로드 중...")
                    result = uploader.upload_video(
                        video_path=str(final_video_path),
                        title=title,
                        description=description,
                        tags=tags,
                        thumbnail_path=thumbnail_path,
                        privacy="public"
                    )
                    
                    upload_results.append(result)
                    
                    if result.get('success'):
                        logger.info(f"\n✅ 업로드 성공!")
                        logger.info(f"   📺 제목: {title}")
                        logger.info(f"   🔗 URL: {result.get('video_url')}\n")
                        
                        # ✅ 업로드 성공 시 즉시 파일 삭제
                        cleanup_video_files(video_path, related_files)
                    else:
                        logger.error(f"\n❌ 업로드 실패: {result.get('error')}\n")
                        # 업로드 실패 시에도 파일 삭제 (저장소 용량 절약)
                        cleanup_video_files(video_path, related_files)
                else:
                    logger.info("⏭️ YouTube 업로드 스킵 (인증 정보 없음)\n")
                    # 인증 없어도 파일 삭제 (테스트 환경)
                    cleanup_video_files(video_path, related_files)
                
            except Exception as e:
                logger.error(f"❌ 비디오 처리 오류: {e}\n")
                import traceback
                traceback.print_exc()
                # 에러 발생 시에도 파일 정리
                cleanup_video_files(video_path, related_files)
                continue
        
        logger.info("="*70 + "\n")
        
        # 종료 후 용량 확인
        final_size = get_folder_size(str(videos_folder))
        logger.info(f"📦 종료 후 저장소 용량: {final_size:.2f} MB")
        logger.info(f"📊 절약된 용량: {initial_size - final_size:.2f} MB\n")
        
        # 4. 결과 이메일 발송
        if gmail_user and notification_email:
            success_count = sum(1 for r in upload_results if r.get('success'))
            
            email_body = f"""
AAGAG YouTube Shorts 자동화 실행 결과 (자동 정리 버전)

📊 수집 결과:
- 수집된 비디오: {len(videos)}개

📤 업로드 결과:
- 성공: {success_count}개
- 실패: {len(upload_results) - success_count}개

📦 저장소 관리:
- 시작 전 용량: {initial_size:.2f} MB
- 종료 후 용량: {final_size:.2f} MB
- 절약된 용량: {initial_size - final_size:.2f} MB

📹 업로드된 비디오:
"""
            for result in upload_results:
                if result.get('success'):
                    email_body += f"\n✅ {result.get('title')}\n   🔗 {result.get('video_url')}\n"
                else:
                    email_body += f"\n❌ {result.get('title', '알 수 없음')}\n   오류: {result.get('error', '알 수 없음')}\n"
            
            try:
                send_email_notification(
                    subject=f"✅ AAGAG 자동화 완료 - {success_count}/{len(videos)} 업로드",
                    body=email_body
                )
                logger.info(f"📧 이메일 전송 완료: {notification_email}\n")
            except Exception as e:
                logger.warning(f"⚠️ 이메일 전송 실패: {e}\n")
        
        logger.info("="*70)
        logger.info("🎉 모든 작업 완료!")
        logger.info("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"\n❌ 실행 오류: {e}\n")
        import traceback
        traceback.print_exc()
        
        if gmail_user and notification_email:
            try:
                send_email_notification(
                    subject="❌ AAGAG 자동화 오류",
                    body=f"실행 중 오류 발생:\n\n{str(e)}"
                )
            except:
                pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()
