import os
import time
import google.generativeai as genai
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from moviepy.video.fx.all import resize

class ContentProcessor:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        # ✅ gemini-1.5-flash로 변경 (안정적 무료 tier)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.request_count = 0
        self.max_retries = 3
    
    def _rate_limit_wait(self):
        """API Rate Limit 방지: 요청 간 3초 대기"""
        if self.request_count > 0:
            print("⏳ API Rate Limit 방지: 3초 대기...")
            time.sleep(3)
        self.request_count += 1
    
    def generate_title_and_description(self, video_info):
        """Gemini API로 한글 제목 및 설명 생성"""
        original_title = video_info.get('original_title', '개그콘서트 명장면')
        
        # Rate Limit 대기
        self._rate_limit_wait()
        
        prompt = f"""
당신은 유튜브 쇼츠 콘텐츠 전문가입니다.

원본 영상 제목: "{original_title}"

위 개그콘서트 영상을 기반으로 아래 형식에 맞춰 **한글로만** 작성해주세요:

1. 제목 (50자 이내, 이모지 포함, 클릭 유도)
2. 설명 (100자 이내, 해시태그 3개 포함)

형식:
제목: [여기에 제목]
설명: [여기에 설명]

**중요:**
- 반드시 한글로만 작성
- 제목에는 숫자나 "반전" 같은 클릭 유도 요소 포함
- 설명에는 #개그콘서트 #코미디 관련 해시태그 필수
"""
        
        for attempt in range(self.max_retries):
            try:
                print(f"🤖 Gemini API 호출 중... (시도 {attempt + 1}/{self.max_retries})")
                response = self.model.generate_content(prompt)
                
                if not response or not response.text:
                    raise Exception("API 응답이 비어있습니다.")
                
                # 응답 파싱
                lines = response.text.strip().split('\n')
                title = "개그콘서트 명장면 🎭"
                description = "웃음이 끊이지 않는 개그콘서트! #개그콘서트 #코미디 #KBS"
                
                for line in lines:
                    if line.startswith('제목:'):
                        title = line.replace('제목:', '').strip()
                    elif line.startswith('설명:'):
                        description = line.replace('설명:', '').strip()
                
                print(f"✅ 제목 생성 완료: {title}")
                print(f"✅ 설명 생성 완료: {description[:50]}...")
                
                return {
                    'title': title,
                    'description': description
                }
                
            except Exception as e:
                print(f"❌ Gemini API 오류 (시도 {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"⏳ {wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    print("⚠️ 최대 재시도 횟수 초과. 기본 제목/설명 사용.")
                    return {
                        'title': f"{original_title} 🎭",
                        'description': "개그콘서트의 명장면을 만나보세요! #개그콘서트 #코미디 #KBS"
                    }
    
    def add_subtitles(self, video_path, title_text):
        """영상에 새로운 한글 자막 추가 (원본 오디오 보존)"""
        print(f"📝 자막 추가 중: {title_text}")
        
        try:
            video = VideoFileClip(video_path)
            
            # 자막 텍스트 클립 생성 (하단 중앙 배치)
            txt_clip = TextClip(
                title_text,
                fontsize=40,
                color='white',
                bg_color='black',
                font='NanumGothic-Bold',  # 한글 폰트 (GitHub Actions에 설치 필요)
                size=(video.w - 40, None),
                method='caption'
            ).set_position(('center', video.h - 150)).set_duration(video.duration)
            
            # 원본 영상 + 자막 합성
            final_video = CompositeVideoClip([video, txt_clip])
            
            # 출력 파일 경로
            output_path = video_path.replace('.mp4', '_subtitled.mp4')
            
            # ✅ 원본 오디오 그대로 사용
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                fps=30
            )
            
            # 리소스 해제
            video.close()
            final_video.close()
            txt_clip.close()
            
            print(f"✅ 자막 추가 완료: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ 자막 추가 실패: {str(e)}")
            print("⚠️ 원본 영상 그대로 사용합니다.")
            return video_path
    
    def process_video(self, video_info):
        """영상 처리 메인 함수"""
        print(f"\n{'='*50}")
        print(f"🎬 영상 처리 시작: {video_info['id']}")
        print(f"{'='*50}")
        
        try:
            # 1. Gemini로 제목/설명 생성
            content = self.generate_title_and_description(video_info)
            
            # 2. 자막 추가 (원본 오디오 보존)
            final_video_path = self.add_subtitles(
                video_info['path'],
                content['title']
            )
            
            return {
                'video_path': final_video_path,
                'title': content['title'],
                'description': content['description'],
                'source_url': video_info['source_url']
            }
            
        except Exception as e:
            print(f"❌ 영상 처리 중 오류: {str(e)}")
            return None
