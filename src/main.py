import os
import sys
from aagag_collector import AagagCollector
from audio_detector import AudioDetector
from background_music import BackgroundMusicAdder
from title_optimizer import TitleOptimizer

def main():
    print("🚀 AAGAG 밈 자동화 시스템 시작\n")
    
    # 환경 변수
    gemini_api_key = os.getenv('GOOGLE_API_KEY')
    
    if not gemini_api_key:
        print("❌ GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다.")
        sys.exit(1)
    
    # 목표 개수
    target_count = 5
    
    # 1. AAGAG 수집기 초기화
    collector = AagagCollector()
    
    # 2. 비디오 게시물 수집
    posts = collector.get_video_posts(limit=30)
    
    if not posts:
        print("❌ 수집된 게시물이 없습니다.")
        return
    
    print(f"📊 수집된 비디오 게시물: {len(posts)}개\n")
    
    # 3. 게시물 처리
    processed_count = 0
    
    for post in posts:
        if processed_count >= target_count:
            break
        
        print(f"\n{'='*70}")
        print(f"📝 처리 중 [{processed_count+1}/{target_count}]: {post['title']}")
        print(f"🔗 URL: {post['url']}")
        
        # 3-1. 미디어 URL 추출
        media_url = collector.extract_media_url(post['url'])
        if not media_url:
            print(f"⚠️ 미디어 URL을 찾을 수 없어 건너뜁니다.")
            continue
        
        # 3-2. 비디오 다운로드
        video_path = collector.download_video(media_url, post['idx'])
        if not video_path:
            print(f"⚠️ 다운로드 실패, 건너뜁니다.")
            continue
        
        # 3-3. 오디오 감지
        audio_detector = AudioDetector()
        has_audio = audio_detector.has_audio(video_path)
        
        final_video_path = video_path
        
        if has_audio:
            has_significant = audio_detector.has_significant_audio(video_path)
            print(f"🔊 오디오: {'있음 (의미있음)' if has_significant else '있음 (무음)'}")
            
            if not has_significant:
                # 무음이면 배경음악 추가
                print("🎵 배경음악 추가 필요")
                music_adder = BackgroundMusicAdder()
                music_path = 'data/music/background.mp3'
                output_path = video_path.replace('.mp4', '_music.mp4')
                final_video_path = music_adder.add_background_music(
                    video_path, music_path, output_path, volume=0.2
                )
        else:
            print("🔇 오디오: 없음 → 배경음악 추가")
            music_adder = BackgroundMusicAdder()
            music_path = 'data/music/background.mp3'
            output_path = video_path.replace('.mp4', '_music.mp4')
            final_video_path = music_adder.add_background_music(
                video_path, music_path, output_path, volume=0.2
            )
        
        # 3-4. 제목 및 설명 생성
        optimizer = TitleOptimizer(gemini_api_key)
        optimized_title = optimizer.generate_engaging_title(post['title'])
        description = optimizer.generate_description(optimized_title)
        
        print(f"\n✨ 최종 제목: {optimized_title}")
        print(f"📄 설명: {description[:100]}...")
        print(f"🎬 최종 영상: {final_video_path}")
        
        # TODO: YouTube 업로드 (다음 단계)
        # uploader.upload(final_video_path, optimized_title, description)
        
        processed_count += 1
        print(f"✅ 처리 완료 ({processed_count}/{target_count})")
    
    print(f"\n🎉 총 {processed_count}개 콘텐츠 처리 완료!")

if __name__ == '__main__':
    main()
