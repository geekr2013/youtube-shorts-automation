import os
from pathlib import Path
from aagag_collector import AAGAGCollector
from audio_detector import has_audio
from background_music import add_background_music
from title_optimizer import optimize_title, generate_description
from youtube_uploader import YouTubeUploader
from email_notifier import EmailNotifier

def main():
    print("🚀 AAGAG 숏폼 자동화 시작")
    
    # 디렉토리 설정
    video_dir = Path('data/videos')
    music_dir = Path('data/music')
    video_dir.mkdir(parents=True, exist_ok=True)
    music_dir.mkdir(parents=True, exist_ok=True)
    
    # YouTube 업로더 초기화
    uploader = YouTubeUploader()
    
    # 이메일 알림 초기화 (현재 Secrets 이름에 맞게 수정)
    email_notifier = None
    if all([os.getenv('SENDER_EMAIL'), os.getenv('GMAIL_PASSWORD'), 
            os.getenv('RECEIVER_EMAIL')]):
        email_notifier = EmailNotifier()
        print("📧 이메일 알림 활성화")
    
    # 1. AAGAG 콘텐츠 수집 및 다운로드
    print("\n📥 AAGAG 콘텐츠 수집 중...")
    collector = AAGAGCollector()
    posts = collector.collect_posts(max_posts=20)
    
    if not posts:
        print("❌ 수집된 게시물이 없습니다.")
        if email_notifier:
            email_notifier.send_notification(
                subject="AAGAG 자동화 - 수집 실패",
                body="수집된 게시물이 없습니다."
            )
        return
    
    print(f"✅ {len(posts)}개 게시물 수집 완료")
    
    # 처리할 영상 개수 제한 (1일 3~5개)
    max_videos = min(5, len(posts))
    processed_videos = []
    failed_videos = []
    
    for post in posts[:max_videos]:
        try:
            print(f"\n{'='*50}")
            print(f"📌 처리 중: {post['title']}")
            
            # 영상 다운로드
            video_path = collector.download_video(post)
            if not video_path:
                print(f"⚠️ 다운로드 실패: {post['title']}")
                failed_videos.append(post['title'])
                continue
            
            # 원본 제목에서 확장자 제거
            clean_title = optimize_title(post['title'])
            description = generate_description(post['title'])
            
            # 오디오 확인
            print("\n🔊 오디오 분석 중...")
            video_has_audio = has_audio(video_path)
            
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
            
            # YouTube Shorts 업로드
            print(f"\n📤 YouTube Shorts 업로드 중...")
            video_url = uploader.upload_short(
                video_path=final_video_path,
                title=clean_title,
                description=description
            )
            
            if video_url:
                print(f"🎉 업로드 성공: {video_url}")
                processed_videos.append({
                    'title': clean_title,
                    'url': video_url
                })
            else:
                print(f"❌ 업로드 실패: {clean_title}")
                failed_videos.append(clean_title)
            
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            failed_videos.append(post.get('title', 'Unknown'))
            continue
    
    # 결과 요약
    print(f"\n{'='*50}")
    print(f"🎉 처리 완료!")
    print(f"✅ 성공: {len(processed_videos)}개")
    print(f"❌ 실패: {len(failed_videos)}개")
    
    # 이메일 알림 전송
    if email_notifier and len(processed_videos) > 0:
        email_body = f"""
AAGAG 숏폼 자동화 결과

✅ 업로드 성공: {len(processed_videos)}개
{''.join([f'- {v["title"]}: {v["url"]}' + chr(10) for v in processed_videos])}

❌ 실패: {len(failed_videos)}개
{''.join([f'- {title}' + chr(10) for title in failed_videos])}
"""
        email_notifier.send_notification(
            subject=f"AAGAG 자동화 완료 - {len(processed_videos)}개 업로드",
            body=email_body
        )

if __name__ == '__main__':
    main()
