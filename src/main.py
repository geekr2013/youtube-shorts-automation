"""
AAGAG 숏폼 자동화 메인 스크립트
- AAGAG 크롤링
- Gemini AI 제목/설명 생성
- 배경음악 추가 (선택)
- YouTube Shorts 업로드
"""

import os
import sys
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
    from content_processor_gemini import ContentProcessor
    from email_notifier import send_email_notification
    from background_music import add_background_music
    logger.info("✅ 모듈 임포트 완료")
except ImportError as e:
    logger.error(f"❌ 모듈 임포트 실패: {e}")
    sys.exit(1)


def main():
    """메인 실행 함수"""
    logger.info("\n" + "="*70)
    logger.info("🚀 AAGAG YouTube Shorts 자동화 시작")
    logger.info("="*70 + "\n")
    
    try:
        # 0. 환경 변수 확인
        gemini_api_key = os.getenv('GEMINI_API_KEY')
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
        
        # 2. Gemini AI 프로세서 초기화
        processor = None
        if gemini_api_key:
            try:
                processor = ContentProcessor(api_key=gemini_api_key)
                logger.info("✅ Gemini AI 프로세서 준비 완료\n")
            except Exception as e:
                logger.warning(f"⚠️ Gemini 초기화 실패: {e}")
                logger.warning("⚠️ 기본 제목/설명 사용\n")
        else:
            logger.warning("⚠️ GEMINI_API_KEY 없음 - 기본 제목/설명 사용\n")
        
        # 3. AAGAG 콘텐츠 수집
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
        
        # 4. 각 비디오 처리 및 업로드
        upload_results = []
        
        for idx, video in enumerate(videos, 1):
            logger.info(f"{'='*70}")
            logger.info(f"🎬 [{idx}/{len(videos)}] 비디오 처리 중")
            logger.info(f"{'='*70}\n")
            
            video_path = video.get('video_path')
            original_title = video.get('title', '무제')
            
            if not video_path or not os.path.exists(video_path):
                logger.warning(f"⚠️ 비디오 파일 없음: {video_path}\n")
                continue
            
            try:
                # 4-1. Gemini AI로 메타데이터 생성
                if processor:
                    logger.info("🤖 Gemini AI로 제목/설명 생성 중...")
                    try:
                        metadata = processor.generate_metadata(video_path)
                        title = metadata.get('title', original_title)
                        description = metadata.get('description', f'AAGAG에서 가져온 재미있는 영상입니다.\n\n{original_title}')
                        tags = metadata.get('tags', ['shorts', '재미', 'aagag', '한국', '개그'])
                        logger.info(f"   ✅ 제목: {title}")
                        logger.info(f"   ✅ 설명: {description[:50]}...")
                        logger.info(f"   ✅ 태그: {', '.join(tags)}\n")
                    except Exception as e:
                        logger.warning(f"   ⚠️ Gemini 생성 실패: {e}")
                        logger.warning(f"   ⚠️ 기본 메타데이터 사용\n")
                        title = original_title
                        description = f'AAGAG에서 가져온 재미있는 영상입니다.\n\n원제: {original_title}\n출처: {video.get("source_url", "")}'
                        tags = ['shorts', '재미', 'aagag', '한국']
                else:
                    title = original_title
                    description = f'AAGAG에서 가져온 재미있는 영상입니다.\n\n원제: {original_title}\n출처: {video.get("source_url", "")}'
                    tags = ['shorts', '재미', 'aagag', '한국']
                
                # 4-2. 배경음악 추가 (선택)
                final_video_path = video_path
                if enable_bgm and os.path.exists(bgm_path):
                    logger.info("🎵 배경음악 추가 중...")
                    try:
                        final_video_path = add_background_music(
                            video_path=video_path,
                            music_path=bgm_path
                        )
                        logger.info(f"   ✅ 배경음악 추가 완료\n")
                    except Exception as e:
                        logger.warning(f"   ⚠️ 배경음악 추가 실패: {e}")
                        logger.warning(f"   ⚠️ 원본 영상 사용\n")
                        final_video_path = video_path
                
                # 4-3. YouTube 업로드
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
        
        # 5. 결과 이메일 발송
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
