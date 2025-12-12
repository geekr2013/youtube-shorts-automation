import google.generativeai as genai
import os
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from pathlib import Path

class ContentProcessorGemini:
    def __init__(self):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
    def generate_metadata(self, video_info: dict) -> dict:
        """Gemini로 제목/설명 생성"""
        print(f"\n🤖 Gemini로 메타데이터 생성 중...")
        
        original_title = video_info.get('title', '개그콘서트')
        
        prompt = f"""
다음은 KBS '개그콘서트'의 쇼츠 영상입니다.

원본 제목: {original_title}

요청사항:
1. YouTube 쇼츠에 적합한 한국어 제목 생성 (25자 이내, 이모지 포함)
2. 간결한 한국어 설명 생성 (100자 이내)

응답 형식 (JSON):
{{
  "title": "제목",
  "description": "설명"
}}
"""
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            # JSON 파싱
            import json
            if text.startswith('```json'):
                text = text[7:]
            if text.endswith('```'):
                text = text[:-3]
            
            metadata = json.loads(text.strip())
            print(f"✅ 제목: {metadata['title']}")
            print(f"✅ 설명: {metadata['description'][:50]}...")
            
            return metadata
            
        except Exception as e:
            print(f"⚠️ Gemini 생성 실패: {e}, 기본값 사용")
            return {
                'title': f"🎭 {original_title[:20]}",
                'description': "개그콘서트의 재미있는 순간들을 쇼츠로 만나보세요!"
            }
    
    def add_subtitles(self, video_path: str, video_info: dict, metadata: dict) -> str:
        """한국어 자막 추가 (원본 오디오 유지)"""
        print(f"\n🎨 자막 추가 중: {Path(video_path).name}")
        
        output_path = str(Path(video_path).parent / f"processed_{Path(video_path).name}")
        
        try:
            video = VideoFileClip(video_path)
            
            # 자막 텍스트 (제목 활용)
            subtitle_text = metadata['title'].replace('🎭', '').strip()[:30]
            
            # 자막 생성 (하단 중앙)
            txt_clip = TextClip(
                subtitle_text,
                fontsize=40,
                font='NanumGothic-Bold',
                color='white',
                bg_color='black',
                size=(video.w - 40, None),
                method='caption'
            ).set_position(('center', video.h - 100)).set_duration(min(3, video.duration))
            
            # 자막 합성
            final_video = CompositeVideoClip([video, txt_clip])
            
            # 원본 오디오 유지하며 저장
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                fps=video.fps
            )
            
            video.close()
            final_video.close()
            
            print(f"✅ 자막 추가 완료: {Path(output_path).name}")
            return output_path
            
        except Exception as e:
            print(f"⚠️ 자막 추가 실패: {e}, 원본 반환")
            return video_path
