import os
import sys
from video_collector import VideoCollector
from content_processor_gemini import ContentProcessor
from youtube_uploader import YouTubeUploader
from email_notifier import EmailNotifier

def main():
    print("="*60)
    print("🚀 개그콘서트 Shorts 자동 업로드 시스템 시작")
    print("="*60)
    
    # 환경 변수 로드
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    sender_email = os.getenv('SENDER_EMAIL')
    receiver_email = os.getenv('RECEIVER_EMAIL')
    gmail_password = os.getenv('GMAIL_PASSWORD')
    youtube_client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')
    youtube_refresh_token = os.getenv('YOUTUBE_REFRESH_TOKEN')
    
    # 필수 환경 변수 확인
    required_vars = {
        'GEMINI_API_KEY': gemini_api_key,
        'SENDER_EMAIL': sender_email,
        'RECEIVER_EMAIL': receiver_email,
        'GMAIL_PASSWORD': gmail_password,
        'YOUTUBE_CLIENT_SECRET': youtube_client_secret,
        'YOUTUBE_REFRESH_TOKEN': youtube_refresh_token
    }
    
    missing_vars = [k for k, v in required_vars.items() if not v]
    if missing_vars:
        print(f"❌ 환경 변수 누락: {', '.join(missing_vars)}")
        sys.exit(1)
    
    try:
        # 1. 영상 수집
        collector = VideoCollector()
        videos = collector.collect_videos(count=3)
        
        if not videos:
            print("⚠️ 수집된 영상이 없습니다. 프로그램 종료.")
            sys.exit(0)
        
        # 2. 영상 처리
        processor = ContentProcessor(gemini_api_key)
        processed_videos = []
        
        for video in videos:
            result = processor.process_video(video)
            if result:
                processed_videos.append(result)
        
        if not processed_videos:
            print("❌ 처리된 영상이 없습니다.")
            sys.exit(1)
        
        # 3. YouTube 업로드
        uploader = YouTubeUploader(youtube_client_secret, youtube_refresh_token)
        upload_results = []
        
        for video in processed_videos:
            upload_result = uploader.upload(
                video_path=video['video_path'],
                title=video['title'],
                description=f"{video['description']}\n\n원본 출처: {video['source_url']}"
            )
            if upload_result:
                upload_results.append({
                    'title': video['title'],
                    'url': upload_result['url'],
                    'status': upload_result['status']
                })
        
        # 4. 이메일 알림
        if upload_results:
            notifier = EmailNotifier(sender_email, gmail_password)
            notifier.send_notification(
                receiver_email,
                upload_results,
                success_count=len(upload_results),
                total_count=len(videos)
            )
        
        print("\n" + "="*60)
        print("✅ 모든 작업 완료!")
        print(f"📊 결과: {len(upload_results)}/{len(videos)} 영상 업로드 성공")
        print("="*60)
        
    except Exception as e:
        print(f"❌ 시스템 오류: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
