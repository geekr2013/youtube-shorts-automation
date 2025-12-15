import os
import sys
from aagag_collector import AAGAGCollector
from audio_detector import has_audio
from background_music import add_background_music
from title_optimizer import optimize_title
from youtube_uploader import upload_to_youtube
from email_notifier import send_email


def main():
    print("🚀 AAGAG 숏폼 자동화 시작")
    
    # YouTube 인증
    if not upload_to_youtube("", "", dry_run=True):
        print("❌ YouTube API 인증 실패")
        sys.exit(1)
    print("✅ YouTube API 인증 완료")
    
    # 이메일 설정 확인
    sender_email = os.getenv("SENDER_EMAIL")
    gmail_password = os.getenv("GMAIL_PASSWORD")
    receiver_email = os.getenv("RECEIVER_EMAIL")
    
    email_enabled = all([sender_email, gmail_password, receiver_email])
    if email_enabled:
        print("📧 이메일 알림 활성화")
    
    # AAGAG 콘텐츠 수집
    print("\n📥 AAGAG 콘텐츠 수집 중...")
    collector = AAGAGCollector(
        download_dir="downloads",
        history_file="data/download_history.json"
    )
    
    # 비디오 다운로드 (최대 5개)
    videos = collector.collect_and_download(max_videos=5)
    
    if not videos:
        print("⚠️ 다운로드된 비디오가 없습니다.")
        if email_enabled:
            send_email(
                subject="[AAGAG 자동화] 콘텐츠 없음",
                body="오늘 수집된 새로운 비디오가 없습니다.",
                sender_email=sender_email,
                sender_password=gmail_password,
                receiver_email=receiver_email
            )
        return
    
    print(f"✅ {len(videos)}개 비디오 다운로드 완료\n")
    
    # 각 비디오 처리
    success_count = 0
    fail_count = 0
    results = []
    
    for idx, video in enumerate(videos, 1):
        print("=" * 50)
        print(f"📌 처리 중 [{idx}/{len(videos)}]: {video['title']}")
        
        try:
            video_path = video['path']
            original_title = video['title']
            
            # 1. 오디오 감지
            print("  🔊 오디오 확인 중...")
            video_has_audio = has_audio(video_path)
            
            if not video_has_audio:
                print("  ⚠️ 오디오 없음 - 배경음악 추가 중...")
                music_path = "data/music/background.mp3"
                
                if os.path.exists(music_path):
                    result = add_background_music(video_path, music_path)
                    if result:
                        video_path = result
                        print(f"  ✅ 배경음악 추가 완료")
                    else:
                        print(f"  ⚠️ 배경음악 추가 실패 (원본 사용)")
                else:
                    print(f"  ⚠️ 배경음악 파일 없음: {music_path}")
            else:
                print("  ✅ 오디오 있음")
            
            # 2. 제목 최적화
            print("  📝 제목 최적화 중...")
            optimized_data = optimize_title(original_title)
            title = optimized_data["title"]
            description = optimized_data["description"]
            print(f"  ✅ 최적화된 제목: {title}")
            
            # 3. YouTube 업로드
            print("  📤 YouTube 업로드 중...")
            upload_success = upload_to_youtube(
                video_path=video_path,
                title=title,
                description=description
            )
            
            if upload_success:
                print(f"  ✅ YouTube 업로드 성공!")
                success_count += 1
                results.append(f"✅ {title}")
            else:
                print(f"  ❌ YouTube 업로드 실패")
                fail_count += 1
                results.append(f"❌ {title}")
        
        except Exception as e:
            print(f"  ❌ 오류 발생: {e}")
            fail_count += 1
            results.append(f"❌ {original_title} (오류: {str(e)})")
        
        print()
    
    # 최종 결과
    print("=" * 50)
    print("🎉 처리 완료!")
    print(f"✅ 성공: {success_count}개")
    print(f"❌ 실패: {fail_count}개")
    
    # 이메일 전송
    if email_enabled:
        result_text = "\n".join(results)
        send_email(
            subject=f"[AAGAG 자동화] 처리 완료 ({success_count}개 성공)",
            body=f"처리 결과:\n\n{result_text}\n\n성공: {success_count}개\n실패: {fail_count}개",
            sender_email=sender_email,
            sender_password=gmail_password,
            receiver_email=receiver_email
        )
        print("📧 이메일 전송 완료")


if __name__ == "__main__":
    main()
