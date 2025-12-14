import os
from reddit_collector import RedditCollector
from audio_detector import AudioDetector
from background_music import BackgroundMusicAdder
from title_optimizer import TitleOptimizer
from content_processor_gemini import ContentProcessor
# from youtube_uploader import YouTubeUploader  # 추후 추가

def main():
    print("🚀 밈 자동화 시스템 시작")
    
    # 환경 변수
    reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
    reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
    gemini_api_key = os.getenv('GOOGLE_API_KEY')
    
    # Reddit 수집기
    collector = RedditCollector(
        client_id=reddit_client_id,
        client_secret=reddit_client_secret,
        user_agent='MemeAutomation/1.0'
    )
    
    # 비디오 게시물 수집
    posts = collector.get_video_posts(subreddit_name='funny', limit=10)
    print(f"📊 수집된 게시물: {len(posts)}개")
    
    processed_count = 0
    target_count = 5  # 하루 3~5개
    
    for post in posts:
        if processed_count >= target_count:
            break
        
        print(f"\n{'='*60}")
        print(f"📝 처리 중: {post['title']}")
        
        # 1. 비디오 다운로드
        video_path = collector.download_video(post['media_url'])
        if not video_path:
            continue
        
        # 2. 오디오 감지
        audio_detector = AudioDetector()
        has_audio = audio_detector.has_audio(video_path)
        has_significant = audio_detector.has_significant_audio(video_path) if has_audio else False
        
        # 3. 배경음악 추가 (필요 시)
        final_video_path = video_path
        if not has_significant:
            print("🎵 배경음악 추가 필요")
            music_adder = BackgroundMusicAdder()
            music_path = 'data/music/background.mp3'  # 준비된 배경음악
            output_path = video_path.replace('.mp4', '_with_music.mp4')
            final_video_path = music_adder.add_background_music(
                video_path, music_path, output_path
            )
        
        # 4. 제목 최적화
        optimizer = TitleOptimizer()
        optimized_title = optimizer.optimize_title(post['title'])
        hashtags = optimizer.generate_hashtags(optimized_title)
        
        print(f"✨ 최적화된 제목: {optimized_title}")
        print(f"🏷️ 해시태그: {hashtags}")
        
        # 5. AI 설명 생성 (Gemini)
        # processor = ContentProcessor(gemini_api_key)
        # description = processor.generate_description(optimized_title, final_video_path)
        
        # 6. YouTube 업로드
        # uploader = YouTubeUploader()
        # uploader.upload(final_video_path, optimized_title, description + '\n\n' + hashtags)
        
        processed_count += 1
        print(f"✅ 처리 완료 ({processed_count}/{target_count})")
    
    print(f"\n🎉 총 {processed_count}개 콘텐츠 처리 완료!")

if __name__ == '__main__':
    main()
