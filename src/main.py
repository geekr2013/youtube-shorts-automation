import os
import sys
from video_collector import VideoCollector
from content_processor_gemini import GeminiContentProcessor
from music_collector import MusicCollector
from youtube_uploader import YouTubeUploader
from email_notifier import EmailNotifier

def check_env_variables():
    """필수 환경변수 확인"""
    required_vars = [
        'PEXELS_API_KEY',
        'PIXABAY_API_KEY',  # 추가
        'GEMINI_API_KEY',
        'SENDER_EMAIL',
        'RECEIVER_EMAIL',
        'GMAIL_PASSWORD',
        'YOUTUBE_CLIENT_SECRET',
        'YOUTUBE_REFRESH_TOKEN'
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"❌ 누락된 환경변수: {', '.join(missing)}")
        sys.exit(1)
    
    print("✅ 모든 환경변수 확인 완료\n")

def main():
    print("="*70)
    print("🎬 YouTube Shorts 자동 업로드 시작")
    print("="*70 + "\n")
    
    # 환경변수 확인
    check_env_variables()
    
    # 초기화
    video_collector = VideoCollector(os.getenv('PEXELS_API_KEY'))
    music_collector = MusicCollector(os.getenv('PIXABAY_API_KEY'))
    content_processor = GeminiContentProcessor(os.getenv('GEMINI_API_KEY'))
    youtube_uploader = YouTubeUploader()
    email_notifier = EmailNotifier(
        os.getenv('SENDER_EMAIL'),
        os.getenv('GMAIL_PASSWORD')
    )
    
    try:
        # 1단계: Pexels에서 동영상 수집
        print("📥 STEP 1: Pexels에서 동영상 다운로드 중...\n")
        videos = video_collector.collect_videos(count=3)
        
        if not videos:
            raise Exception("다운로드된 동영상이 없습니다.")
        
        print(f"\n✅ {len(videos)}개 동영상 다운로드 완료\n")
        
        # 2단계: 각 동영상 처리 및 업로드
        upload_results = []
        
        for i, video_info in enumerate(videos, 1):
            print("="*70)
            print(f"🎥 영상 {i}/{len(videos)} 처리 중...")
            print("="*70 + "\n")
            
            video_path = video_info['path']
            
            # 2-1: Gemini로 제목/설명 생성
            print(f"🤖 Gemini AI로 한글 제목/설명 생성 중...")
            title = content_processor.generate_title(video_info)
            description = content_processor.generate_description(video_info, title)
            
            # 2-2: 배경음악 다운로드
            music_path = music_collector.get_random_music(
                duration=int(video_info['duration'])
            )
            
            # 2-3: 배경음악 삽입
            final_video_path = video_path.replace('.mp4', '_final.mp4')
            final_video_path = content_processor.add_background_music(
                video_path, 
                music_path, 
                final_video_path
            )
            
            # 2-4: YouTube 업로드
            print(f"\n📤 YouTube Shorts 업로드 중...")
            video_id = youtube_uploader.upload_video(
                final_video_path,
                title,
                description
            )
            
            if video_id:
                upload_results.append({
                    'title': title,
                    'video_id': video_id,
                    'url': f"https://youtube.com/shorts/{video_id}",
                    'status': 'success'
                })
                print(f"✅ 업로드 성공: https://youtube.com/shorts/{video_id}\n")
            else:
                upload_results.append({
                    'title': title,
                    'status': 'failed'
                })
                print(f"❌ 업로드 실패\n")
        
        # 3단계: 이메일 알림
        print("="*70)
        print("📧 이메일 알림 전송 중...")
        print("="*70 + "\n")
        
        email_notifier.send_notification(
            subject=f"[YouTube Shorts] 오늘 {len(upload_results)}개 영상 업로드 완료",
            message="자동 업로드가 완료되었습니다.",
            video_data=upload_results
        )
        
        print("\n" + "="*70)
        print("🎉 모든 작업 완료!")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        
        # 오류 알림
        email_notifier.send_notification(
            subject="[YouTube Shorts] 자동 업로드 실패",
            message=f"오류가 발생했습니다:\n\n{str(e)}"
        )
        
        sys.exit(1)

if __name__ == "__main__":
    main()
