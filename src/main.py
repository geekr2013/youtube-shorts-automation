import os
from pathlib import Path
from aagag_collector import AAGAGCollector
from audio_detector import has_audio  # ← 변경
from background_music import add_background_music
from title_optimizer import optimize_title, generate_description

def main():
    print("🚀 AAGAG 숏폼 자동화 시작")
    
    # 디렉토리 설정
    video_dir = Path('data/videos')
    music_dir = Path('data/music')
    video_dir.mkdir(parents=True, exist_ok=True)
    music_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. AAGAG 콘텐츠 수집 및 다운로드
    print("\n📥 AAGAG 콘텐츠 수집 중...")
    collector = AAGAGCollector()
    posts = collector.collect_posts(max_posts=20)
    
    if not posts:
        print("❌ 수집된 게시물이 없습니다.")
        return
    
    print(f"✅ {len(posts)}개 게시물 수집 완료")
    
    # 처리할 영상 개수 제한 (1일 3~5개)
    max_videos = min(5, len(posts))
    processed_count = 0
    
    for post in posts[:max_videos]:
        try:
            print(f"\n{'='*50}")
            print(f"📌 처리 중: {post['title']}")
            
            # 영상 다운로드
            video_path = collector.download_video(post)
            if not video_path:
                print(f"⚠️ 다운로드 실패: {post['title']}")
                continue
            
            # 원본 제목에서 확장자 제거
            clean_title = optimize_title(post['title'])
            description = generate_description(post['title'])
            
            # 오디오 확인 (함수로 직접 호출)
            print("\n🔊 오디오 분석 중...")
            video_has_audio = has_audio(video_path)  # ← 변경
            
            # 배경음악 추가 여부 결정
            final_video_path = video_path
            if not video_has_audio:
                music_file = music_dir / 'background.mp3'
                if music_file.exists():
                    print("🎵 배경음악 추가 중...")
                    final_video_path = add_background_music(video_path, music_file)
                else:
                    print("⚠️ 배경음악 파일 없음 - 원본 사용")
            else:
                print("✅ 오디오 있음 - 원본 사용")
            
            print(f"\n✅ 처리 완료: {clean_title}")
            print(f"   파일: {final_video_path}")
            print(f"   설명: {description[:50]}...")
            
            processed_count += 1
            
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            continue
    
    print(f"\n{'='*50}")
    print(f"🎉 총 {processed_count}개 영상 처리 완료!")

if __name__ == '__main__':
    main()
