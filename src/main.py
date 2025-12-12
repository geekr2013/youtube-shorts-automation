import os
from video_collector import VideoCollector
from content_processor_gemini import ContentProcessor
from youtube_uploader import YouTubeUploader
from email_notifier import EmailNotifier

def main():
    print("=" * 60)
    print("🎬 개그콘서트 쇼츠 자동 업로드 시작")
    print("=" * 60)
    
    # 환경 변수 확인
    youtube_api_key = os.getenv('YOUTUBE_DATA_API_KEY')
    gemini_api_key = os.getenv('GOOGLE_API_KEY')
    
    if not youtube_api_key:
        print("❌ YOUTUBE_DATA_API_KEY 환경 변수가 설정되지 않았습니다.")
        return
    
    if not gemini_api_key:
        print("❌ GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다.")
        return
    
    try:
        # 1. 비디오 수집
        print("\n[1/4] 📥 비디오 수집 중...")
        collector = VideoCollector(
            api_key=youtube_api_key,
            channel_id="UCzT7nHtzVqwiarTH8sqHaJA",  # 개그콘서트 채널
            max_videos=3
        )
        video_paths = collector.collect_videos()
        
        if not video_paths:
            print("❌ 수집된 비디오가 없습니다. 프로그램을 종료합니다.")
            return
        
        print(f"✅ {len(video_paths)}개 비디오 수집 완료")
        
        # 2. 콘텐츠 처리 (메타데이터 생성 + 자막 추가)
        print("\n[2/4] 🎨 콘텐츠 처리 중...")
        processor = ContentProcessor(api_key=gemini_api_key)
        processed_videos = []
        
        for video_path in video_paths:
            try:
                result = processor.process_video(video_path)
                if result:
                    processed_videos.append(result)
                    print(f"✅ 처리 완료: {result['title']}")
            except Exception as e:
                print(f"❌ 비디오 처리 실패 ({video_path}): {str(e)}")
                continue
        
        if not processed_videos:
            print("❌ 처리된 비디오가 없습니다. 프로그램을 종료합니다.")
            return
        
        print(f"✅ {len(processed_videos)}개 비디오 처리 완료")
        
        # 3. YouTube 업로드
        print("\n[3/4] 📤 YouTube 업로드 중...")
        uploader = YouTubeUploader()
        upload_results = []
        
        for video_data in processed_videos:
            try:
                video_id = uploader.upload_video(
                    video_path=video_data['output_path'],
                    title=video_data['title'],
                    description=video_data['description'],
                    tags=video_data['tags']
                )
                
                if video_id:
                    upload_results.append({
                        'title': video_data['title'],
                        'video_id': video_id,
                        'url': f"https://www.youtube.com/watch?v={video_id}"
                    })
                    print(f"✅ 업로드 완료: {video_data['title']}")
            except Exception as e:
                print(f"❌ 업로드 실패 ({video_data['title']}): {str(e)}")
                continue
        
        if not upload_results:
            print("❌ 업로드된 비디오가 없습니다.")
            return
        
        print(f"✅ {len(upload_results)}개 비디오 업로드 완료")
        
        # 4. 이메일 알림
        print("\n[4/4] 📧 이메일 알림 발송 중...")
        notifier = EmailNotifier()
        
        if notifier.send_notification(upload_results):
            print("✅ 이메일 알림 발송 완료")
        else:
            print("⚠️ 이메일 알림 발송 실패 (업로드는 성공)")
        
        print("\n" + "=" * 60)
        print(f"🎉 모든 작업 완료! 총 {len(upload_results)}개 비디오 업로드됨")
        print("=" * 60)
        
        # 업로드 결과 출력
        for i, result in enumerate(upload_results, 1):
            print(f"{i}. {result['title']}")
            print(f"   🔗 {result['url']}")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
