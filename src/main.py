"""
AAGAG 숏폼 자동화 메인 스크립트 - OAuth 오류 방지 버전
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
    from email_notifier import send_email_notification
    logger.info("✅ 모듈 임포트 완료")
except ImportError as e:
    logger.error(f"❌ 모듈 임포트 실패: {e}")
    sys.exit(1)


def main():
    """메인 실행 함수"""
    logger.info("🚀 AAGAG 숏폼 자동화 시작")
    
    try:
        # 1. YouTube 업로더 초기화 (인증 스킵)
        uploader = YouTubeUploader()
        
        if not uploader.authenticated:
            logger.warning("⚠️ YouTube 인증 정보 없음 - 수집만 진행합니다")
        else:
            logger.info("✅ YouTube Uploader 준비 완료")
        
        # 2. 이메일 알림 확인
        gmail_user = os.getenv('GMAIL_USERNAME')
        notification_email = os.getenv('NOTIFICATION_EMAIL')
        
        if gmail_user and notification_email:
            logger.info("📧 이메일 알림 활성화")
        else:
            logger.warning("⚠️ 이메일 설정 없음")
        
        # 3. AAGAG 콘텐츠 수집
        logger.info("📥 AAGAG 콘텐츠 수집 중...")
        collector = AAGAGCollector()
        
        # 수집 및 다운로드 실행
        videos = collector.collect_and_download(max_videos=5)
        
        if not videos:
            logger.warning("❌ 수집된 게시물이 없습니다.")
            
            # 이메일 알림
            if gmail_user and notification_email:
                send_email_notification(
                    subject="⚠️ AAGAG 자동화 - 수집 실패",
                    body="수집된 게시물이 없습니다. AAGAG 사이트를 확인해주세요."
                )
            
            return
        
        logger.info(f"✅ {len(videos)}개 비디오 수집 완료")
        
        # 4. 업로드 (인증 있을 경우에만)
        upload_results = []
        
        if uploader.authenticated:
            logger.info("📤 YouTube 업로드 시작...")
            
            for video in videos:
                video_path = video.get('video_path')
                title = video.get('title', '무제')
                
                if not video_path or not os.path.exists(video_path):
                    logger.warning(f"⚠️ 비디오 파일 없음: {video_path}")
                    continue
                
                # 업로드
                result = uploader.upload_video(
                    video_path=video_path,
                    title=title,
                    description=f"AAGAG에서 가져온 재미있는 영상입니다.\n\n{title}",
                    tags=["shorts", "재미", "aagag", "한국"],
                    privacy="public"
                )
                
                upload_results.append(result)
                
                if result.get('success'):
                    logger.info(f"✅ 업로드 성공: {title}")
                else:
                    logger.error(f"❌ 업로드 실패: {title}")
        else:
            logger.info("⏭️ YouTube 업로드 스킵 (인증 정보 없음)")
        
        # 5. 결과 이메일 발송
        if gmail_user and notification_email:
            success_count = sum(1 for r in upload_results if r.get('success'))
            
            email_body = f"""
AAGAG 숏폼 자동화 실행 결과

📊 수집 결과:
- 수집된 비디오: {len(videos)}개

📤 업로드 결과:
- 성공: {success_count}개
- 실패: {len(upload_results) - success_count}개

📹 업로드된 비디오:
"""
            for result in upload_results:
                if result.get('success'):
                    email_body += f"\n✅ {result.get('title')}\n   {result.get('video_url')}\n"
            
            send_email_notification(
                subject=f"✅ AAGAG 자동화 완료 - {success_count}/{len(videos)}",
                body=email_body
            )
            logger.info(f"📧 이메일 전송 완료: {notification_email}")
        
        logger.info("🎉 모든 작업 완료!")
        
    except Exception as e:
        logger.error(f"❌ 실행 오류: {e}")
        
        # 오류 이메일 발송
        if gmail_user and notification_email:
            send_email_notification(
                subject="❌ AAGAG 자동화 오류",
                body=f"실행 중 오류 발생:\n\n{str(e)}"
            )
        
        sys.exit(1)


if __name__ == "__main__":
    main()
