"""
AAGAG 숏폼 자동화 메인 스크립트
- AAGAG 크롤링
- 원본 제목/설명 사용 (Gemini 제거)
- 모든 영상을 세로형(9:16)으로 변환
- YouTube Shorts 업로드
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


def extract_keywords_from_title(title: str, max_keywords: int = 8) -> list:
    """
    제목에서 키워드 추출하여 태그 생성
    
    Args:
        title: 원본 제목
        max_keywords: 최대 키워드 개수
        
    Returns:
        키워드 리스트
    """
    # 기본 태그
    base_tags = ['shorts', '숏츠', '쇼츠']
    
    # 제목을 공백/특수문자로 분리
    words = re.findall(r'[가-힣a-zA-Z0-9]+', title)
    
    # 2글자 이상의 단어만 선택
    keywords = [word for word in words if len(word) >= 2]
    
    # 중복 제거
    keywords = list(dict.fromkeys(keywords))
    
    # 최대 개수 제한
    keywords = keywords[:max_keywords - len(base_tags)]
    
    # 기본 태그와 합치기
    return base_tags + keywords


def create_metadata_from_title(title: str, source_url: str = "") -> dict:
    """
    원본 제목에서 메타데이터 생성 (Gemini 없이)
    
    Args:
        title: 원본 제목
        source_url: 출처 URL
        
    Returns:
        메타데이터 딕셔너리
    """
    # 제목 정리 (파일명에서 추출된 경우 처리)
    clean_title = title
    
    # 파일 확장자 제거
    clean_title = re.sub(r'\.(mp4|gif|webm)$', '', clean_title, flags=re.IGNORECASE)
    
    # 숫자 접미사 제거 (예: _1, _2)
    clean_title = re.sub(r'_\d+$', '', clean_title)
    
    # 앞뒤 공백 제거
    clean_title = clean_title.strip()
    
    # 빈 제목 방지
    if not clean_title or len(clean_title) < 2:
        clean_title = "오늘의 핫 이슈 영상"
    
    # 설명 생성
    description = f"{clean_title}\n\n"
    if source_url:
        description += f"출처: AAGAG\n{source_url}\n\n"
    description += "#shorts #숏츠 #쇼츠"
    
    # 태그 생성
    tags = extract_keywords_from_title(clean_title)
    
    return {
        'title': clean_title,
        'description': description,
        'tags': tags
    }


def convert_to_shorts_format(video_path: str) -> str:
    """
    영상을 YouTube Shorts 세로 포맷(1080x1920)으로 변환
    
    Args:
        video_path: 원본 영상 경로
        
    Returns:
        변환된 영상 경로
    """
    try:
        video_path = Path(video_path)
        output_path = video_path.parent / f"{video_path.stem}_shorts{video_path.suffix}"
        
        logger.info(f"   🎬 Shorts 포맷으로 변환 중...")
        
        # ffprobe로 원본 영상 정보 확인
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
        
        # YouTube Shorts 포맷: 1080x1920 (9:16)
        target_width = 1080
        target_height = 1920
        
        # 이미 세로형인 경우 (9:16 비율)
        if 0.5 <= aspect_ratio <= 0.6:
            logger.info(f"   ✅ 이미 세로형 영상입니다 (스킵)")
            return str(video_path)
        
        # 가로형 영상인 경우: 위아래에 블러 배경 추가
        if aspect_ratio > 1:
            logger.info(f"   🔄 가로형 영상 → 세로형 변환 (블러 배경 추가)")
            
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-filter_complex',
                f'[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
                f'boxblur=20:5,'
                f'setsar=1[bg];'
                f'[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
                f'setsar=1[fg];'
                f'[bg][fg]overlay=(W-w)/2:(H-h)/2',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',
                str(output_path)
            ]
        else:
            # 정사각형 또는 세로에 가까운 경우: 단순 패딩
            logger.info(f"   🔄 영상 크기 조정 중...")
            
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-vf', f'scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
                       f'pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,'
                       f'setsar=1',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',
                str(output_path)
            ]
        
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        
        logger.info(f"   ✅ 변환 완료: {output_path.name}\n")
        return str(output_path)
        
    except Exception as e:
        logger.warning(f"   ⚠️ 포맷 변환 실패: {e}")
        logger.warning(f"   ⚠️ 원본 영상 사용\n")
        return str(video_path)


def main():
    """메인 실행 함수"""
    logger.info("\n" + "="*70)
    logger.info("🚀 AAGAG YouTube Shorts 자동화 시작")
    logger.info("="*70 + "\n")
    
    try:
        # 0. 환경 변수 확인
        gmail_user = os.getenv('GMAIL_USERNAME')
        notification_email = os.getenv('NOTIFICATION_EMAIL')
        enable_bgm = os.getenv('ENABLE_BGM', 'false').lower() == 'true'
        bgm_path = os.getenv('BGM_PATH', 'data/music/background.mp3')
        
        # 1. YouTube 업로더 초기화
        uploader = YouTubeUploader()
        
        if not uploader.authenticated:
            logger.warning("⚠️ YouTube 인증 정보 없음 - 수집만 진행합니다")
        else:
            logger.info("✅ YouTube 업로더 준비 완료\n")
        
        # 2. AAGAG 콘텐츠 수집
        logger.info("📥 AAGAG 콘텐츠 수집 시작...\n")
        collector = AAGAGCollector()
        
        # 수집 및 다운로드 실행 (최대 5개)
        videos = collector.collect_and_download(max_videos=5)
        
        if not videos:
            logger.warning("\n❌ 수집된 게시물이 없습니다.\n")
            
            # 이메일 알림
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
            
            try:
                # 3-1. 원본 제목 기반 메타데이터 생성
                logger.info("📝 메타데이터 생성 중...")
                metadata = create_metadata_from_title(original_title, source_url)
                
                title = metadata['title']
                description = metadata['description']
                tags = metadata['tags']
                
                logger.info(f"   ✅ 제목: {title}")
                logger.info(f"   ✅ 설명: {description[:50]}...")
                logger.info(f"   ✅ 태그: {', '.join(tags[:5])}...\n")
                
                # 3-2. Shorts 포맷 변환 (세로형 1080x1920)
                shorts_video_path = convert_to_shorts_format(video_path)
                
                # 3-3. 배경음악 추가 (선택)
                final_video_path = shorts_video_path
                if enable_bgm and os.path.exists(bgm_path):
                    logger.info("🎵 배경음악 추가 중...")
                    try:
                        final_video_path = add_background_music(
                            video_path=shorts_video_path,
                            music_path=bgm_path
                        )
                        logger.info(f"   ✅ 배경음악 추가 완료\n")
                    except Exception as e:
                        logger.warning(f"   ⚠️ 배경음악 추가 실패: {e}")
                        logger.warning(f"   ⚠️ 원본 영상 사용\n")
                        final_video_path = shorts_video_path
                
                # 3-4. YouTube 업로드
                if uploader.authenticated:
                    logger.info("📤 YouTube 업로드 중...")
                    result = uploader.upload_video(
                        video_path=str(final_video_path),
                        title=title,
                        description=description,
                        tags=tags,
                        privacy="public"
                    )
                    
                    upload_results.append(result)
                    
                    if result.get('success'):
                        logger.info(f"\n✅ 업로드 성공!")
                        logger.info(f"   📺 제목: {title}")
                        logger.info(f"   🔗 URL: {result.get('video_url')}\n")
                    else:
                        logger.error(f"\n❌ 업로드 실패: {result.get('error')}\n")
                else:
                    logger.info("⏭️ YouTube 업로드 스킵 (인증 정보 없음)\n")
                
            except Exception as e:
                logger.error(f"❌ 비디오 처리 오류: {e}\n")
                import traceback
                traceback.print_exc()
                continue
        
        logger.info("="*70 + "\n")
        
        # 4. 결과 이메일 발송
        if gmail_user and notification_email:
            success_count = sum(1 for r in upload_results if r.get('success'))
            
            email_body = f"""
AAGAG YouTube Shorts 자동화 실행 결과

📊 수집 결과:
- 수집된 비디오: {len(videos)}개

📤 업로드 결과:
- 성공: {success_count}개
- 실패: {len(upload_results) - success_count}개

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
        
        # 오류 이메일 발송
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
