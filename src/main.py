import os
import sys
from datetime import datetime
from video_collector import VideoCollector
from content_processor_gemini import GeminiContentProcessor
from youtube_uploader import YouTubeUploader
from email_notifier import EmailNotifier
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip

class VideoProcessor:
    def __init__(self):
        """동영상 처리기 초기화"""
        self.audio_folder = "audio_files"
        self.processed_folder = "processed_videos"
        
        for folder in [self.audio_folder, self.processed_folder]:
            if not os.path.exists(folder):
                os.makedirs(folder)
    
    def add_tts_to_video(self, video_path, script, output_path):
        """동영상에 TTS 추가"""
        try:
            # TTS 생성
            tts_path = os.path.join(self.audio_folder, "temp_tts.mp3")
            tts = gTTS(text=script, lang='ko', slow=False)
            tts.save(tts_path)
            
            # 동영상 로드
            video = VideoFileClip(video_path)
            
            # TTS 오디오 로드
            tts_audio = AudioFileClip(tts_path)
            
            # 오디오 합성
            if video.audio:
                # 원본 오디오 볼륨 낮추고 TTS 추가
                original_audio = video.audio.volumex(0.3)
                final_audio = CompositeAudioClip([original_audio, tts_audio.volumex(1.0)])
            else:
                final_audio = tts_audio
            
            # 최종 동영상 생성
            final_video = video.set_audio(final_audio)
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                fps=24,
                logger=None  # 로그 출력 최소화
            )
            
            # 리소스 정리
            video.close()
            tts_audio.close()
            
            # 임시 파일 삭제
            if os.path.exists(tts_path):
                os.remove(tts_path)
            
            return True
            
        except Exception as e:
            print(f"❌ TTS 추가 실패: {e}")
            return False

def main():
    """메인 실행 함수"""
    print("\n" + "="*70)
    print("🚀 YouTube Shorts 자동화 시작 (GitHub Actions)")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    try:
        # 환경 변수 확인
        required_vars = [
            'PEXELS_API_KEY', 'GEMINI_API_KEY', 
            'SENDER_EMAIL', 'GMAIL_PASSWORD', 'RECEIVER_EMAIL'
        ]
        
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        if missing_vars:
            raise ValueError(f"필수 환경 변수 누락: {', '.join(missing_vars)}")
        
        # 1단계: 동영상 수집
        print("📥 STEP 1: Pexels에서 동영상 수집")
        print("-"*70)
        collector = VideoCollector(os.environ.get('PEXELS_API_KEY'))
        downloaded_videos = collector.collect_daily_content(count=5)
        
        if not downloaded_videos:
            print("❌ 수집된 동영상이 없어 종료합니다.")
            sys.exit(1)
        
        # 2단계: Gemini로 콘텐츠 생성 및 TTS 추가
        print("\n🎨 STEP 2: Gemini로 제목/스크립트 생성 + TTS 추가")
        print("-"*70)
        gemini_processor = GeminiContentProcessor()
        video_processor = VideoProcessor()
        
        processed_videos = []
        
        for i, video in enumerate(downloaded_videos, 1):
            print(f"\n[{i}/{len(downloaded_videos)}] 처리 중...")
            
            video_info = video['video_info']
            
            # Gemini로 제목 생성
            korean_title = gemini_processor.generate_korean_title(
                video_keywords=video_info['keyword'],
                duration=video_info['duration']
            )
            
            # Gemini로 스크립트 생성
            script = gemini_processor.generate_korean_script(
                video_title=korean_title,
                duration=video_info['duration']
            )
            
            # Gemini로 설명 생성
            description = gemini_processor.generate_video_description(
                title=korean_title,
                keywords=video_info['keyword']
            )
            
            # TTS 추가
            output_filename = f"processed_{video['filename']}"
            output_path = os.path.join(video_processor.processed_folder, output_filename)
            
            print(f"🔊 TTS 추가 중...")
            success = video_processor.add_tts_to_video(
                video_path=video['filepath'],
                script=script,
                output_path=output_path
            )
            
            if success:
                processed_videos.append({
                    'filepath': output_path,
                    'korean_title': korean_title,
                    'description': description,
                    'original_video': video_info
                })
                print(f"✅ 처리 완료")
            else:
                print(f"⚠️ 처리 실패, 건너뜀")
        
        if not processed_videos:
            print("❌ 처리된 동영상이 없어 종료합니다.")
            sys.exit(1)
        
        # 3단계: YouTube 업로드
        print("\n📤 STEP 3: YouTube Shorts 업로드")
        print("-"*70)
        uploader = YouTubeUploader()
        upload_results = uploader.upload_multiple_videos(processed_videos)
        
        # 4단계: 이메일 발송
        print("\n📧 STEP 4: 결과 이메일 발송")
        print("-"*70)
        notifier = EmailNotifier()
        notifier.send_report(upload_results)
        
        # 최종 요약
        print("\n" + "="*70)
        print("✅ 모든 작업 완료!")
        success_count = sum(1 for r in upload_results if r['success'])
        print(f"📊 성공: {success_count}/{len(upload_results)}개")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
