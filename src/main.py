import os
from video_collector import VideoCollector
from content_processor_gemini import ContentProcessorGemini
from youtube_uploader import YouTubeUploader
from email_notifier import EmailNotifier

def main():
    print("=" * 60)
    print("🎬 개그콘서트 쇼츠 자동 업로드 시작")
    print("=" * 60)
    
    # 1. 영상 수집
    collector = VideoCollector()
    videos = collector.collect_gagconcert_shorts(max_videos=3)
    
    if not videos:
        print("\n⚠️ 수집된 영상이 없습니다. 프로그램 종료.")
        return
    
    # 2. 영상 처리
    processor = ContentProcessorGemini()
    processed_videos = []
    
    for video in videos:
        try:
            # 메타데이터 생성
            metadata = processor.generate_metadata(video)
            
            # 자막 추가
            processed_path = processor.add_subtitles(
                video['path'],
                video,
                metadata
            )
            
            processed_videos.append({
                'path': processed_path,
                'title': metadata['title'],
                'description': metadata['description'],
                'original_title': video['title']
            })
            
        except Exception as e:
            print(f"❌ 영상 처리 실패: {e}")
            continue
    
    if not processed_videos:
        print("\n⚠️ 처리된 영상이 없습니다.")
        return
    
    # 3. YouTube 업로드
    uploader = YouTubeUploader()
    uploaded_count = 0
    
    for video in processed_videos:
        try:
            print(f"\n⬆️ 업로드 중: {video['title']}")
            uploader.upload(
                video_path=video['path'],
                title=video['title'],
                description=video['description']
            )
            uploaded_count += 1
            print(f"✅ 업로드 완료!")
            
        except Exception as e:
            print(f"❌ 업로드 실패: {e}")
            continue
    
    # 4. 이메일 알림
    if uploaded_count > 0:
        notifier = EmailNotifier()
        notifier.send(
            subject=f"✅ 개그콘서트 쇼츠 {uploaded_count}개 업로드 완료",
            body=f"총 {uploaded_count}개의 영상이 YouTube에 업로드되었습니다."
        )
    
    print("\n" + "=" * 60)
    print(f"🎉 작업 완료! (업로드: {uploaded_count}개)")
    print("=" * 60)

if __name__ == "__main__":
    main()
