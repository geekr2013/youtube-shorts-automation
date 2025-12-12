import os
import google.generativeai as genai
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip

class GeminiContentProcessor:
    """Gemini API로 컨텐츠 생성 및 배경음악 삽입"""
    
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def generate_title(self, video_info):
        """YouTube Shorts 제목 생성 (한글, 이모지 포함)"""
        
        prompt = f"""
당신은 YouTube Shorts 전문 제목 작성가입니다.

다음 동영상 정보를 보고, 클릭하고 싶은 매력적인 한글 제목을 만들어주세요:
- 동영상 ID: {video_info.get('id')}
- 길이: {video_info.get('duration')}초
- 제작자: {video_info.get('user')}

요구사항:
1. 반드시 한글로 작성
2. 이모지 1-2개 포함 (😂🤣😱🔥💥 등)
3. 70자 이내
4. 클릭을 유도하는 자극적인 표현 사용
5. "이거 진짜", "대박", "레전드", "ㅋㅋㅋ" 같은 한국식 표현 활용
6. 제목만 출력 (설명 없이)

예시:
- 😂 이거 보고 웃음 참기 도전 ㅋㅋㅋ
- 🤣 5초 뒤에 대박 반전 나옴 주의!
- 😱 이런 상황 실화냐고 ㅋㅋ 레전드

제목:
"""
        
        try:
            response = self.model.generate_content(prompt)
            title = response.text.strip()
            
            # 70자 초과 시 자르기
            if len(title) > 70:
                title = title[:67] + "..."
            
            print(f"✅ 생성된 제목: {title}")
            return title
            
        except Exception as e:
            print(f"❌ 제목 생성 실패: {e}")
            # 백업 제목
            backup_titles = [
                "😂 이거 진짜 웃김 ㅋㅋㅋ",
                "🤣 반전 대박 레전드",
                "😱 이거 실화냐 ㅋㅋ",
                "🔥 이거 보고 안 웃으면 인간 아님",
                "💥 5초 뒤에 반전 주의!"
            ]
            import random
            return random.choice(backup_titles)
    
    def generate_description(self, video_info, title):
        """YouTube Shorts 설명 생성"""
        
        prompt = f"""
당신은 YouTube Shorts 설명 작성 전문가입니다.

제목: {title}

다음 요구사항에 맞춰 설명을 작성해주세요:
1. 반드시 한글로 작성
2. 300자 이내
3. 해시태그 5-10개 포함 (#shorts #웃긴영상 등)
4. 구독/좋아요 유도 문구 포함
5. 친근한 말투 사용

설명:
"""
        
        try:
            response = self.model.generate_content(prompt)
            description = response.text.strip()
            
            if len(description) > 300:
                description = description[:297] + "..."
            
            print(f"✅ 생성된 설명: {description[:50]}...")
            return description
            
        except Exception as e:
            print(f"❌ 설명 생성 실패: {e}")
            return f"{title}\n\n#shorts #웃긴영상 #재미 #유머 #funny #viral"
    
    def add_background_music(self, video_path, music_path, output_path):
        """
        동영상에 배경음악 삽입
        
        Args:
            video_path: 원본 동영상 경로
            music_path: 배경음악 경로
            output_path: 출력 동영상 경로
        
        Returns:
            str: 출력 동영상 경로
        """
        
        if not music_path or not os.path.exists(music_path):
            print("⚠️  배경음악 없음, 원본 영상 사용")
            return video_path
        
        try:
            print(f"\n🎬 배경음악 삽입 중...")
            
            # 동영상 로드
            video = VideoFileClip(video_path)
            video_duration = video.duration
            
            # 음악 로드
            music = AudioFileClip(music_path)
            
            # 음악이 영상보다 길면 자르기
            if music.duration > video_duration:
                music = music.subclip(0, video_duration)
            
            # 음악이 영상보다 짧으면 반복 (루프)
            elif music.duration < video_duration:
                repeats = int(video_duration / music.duration) + 1
                music = CompositeAudioClip([music] * repeats).subclip(0, video_duration)
            
            # 배경음악 볼륨 조절 (0.3 = 30%, 영상이 주인공)
            music = music.volumex(0.3)
            
            # 영상에 음악 추가
            final_video = video.set_audio(music)
            
            # 출력
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                fps=video.fps,
                preset='ultrafast',
                threads=4
            )
            
            # 메모리 해제
            video.close()
            music.close()
            final_video.close()
            
            output_size = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ 배경음악 삽입 완료: {output_path} ({output_size:.2f} MB)")
            
            return output_path
            
        except Exception as e:
            print(f"❌ 배경음악 삽입 실패: {e}")
            print("⚠️  원본 영상 사용")
            return video_path
