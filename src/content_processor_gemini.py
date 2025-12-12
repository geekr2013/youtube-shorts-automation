import os
import re
from pathlib import Path
from typing import Dict, Optional
import google.generativeai as genai

# MoviePy 임포트 (버전 호환성 처리)
try:
    from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
except ImportError:
    try:
        from moviepy import VideoFileClip, TextClip, CompositeVideoClip
    except ImportError:
        print("⚠️ MoviePy 임포트 실패. 대체 방법을 사용합니다.")
        VideoFileClip = None
        TextClip = None
        CompositeVideoClip = None

class ContentProcessorGemini:
    def __init__(self, api_key: str):
        """Gemini API 초기화"""
        if not api_key:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # MoviePy 사용 가능 여부 확인
        self.moviepy_available = VideoFileClip is not None
        if not self.moviepy_available:
            print("⚠️ MoviePy를 사용할 수 없습니다. 자막 추가가 비활성화됩니다.")
        
        # 폰트 경로 설정
        self.font_path = Path(__file__).parent.parent / "fonts" / "SeoulAlrim-ExtraBold.otf"
        
        if not self.font_path.exists():
            print(f"⚠️ 폰트 파일을 찾을 수 없습니다: {self.font_path}")
            print(f"   기본 폰트로 대체됩니다.")
            self.font_path = None
    
    def generate_metadata(self, video_path: str, original_title: str = "") -> Dict[str, str]:
        """Gemini로 YouTube 메타데이터 생성"""
        print(f"\n🤖 Gemini로 메타데이터 생성 중...")
        
        prompt = f"""
당신은 YouTube Shorts 전문 마케터입니다.
아래 개그콘서트 영상의 원제목을 바탕으로 YouTube에 최적화된 메타데이터를 생성해주세요.

원제목: {original_title}

다음 형식으로 응답해주세요:
TITLE: (25자 이내, 이모지 포함, 클릭을 유도하는 제목)
DESCRIPTION: (100자 이내, 해시태그 3-5개 포함, SEO 최적화)

제약사항:
- TITLE은 반드시 25자 이내
- DESCRIPTION은 100자 이내
- 원제목의 핵심 키워드 유지
- 이모지 적극 활용
- 해시태그 필수 포함 (#개그콘서트 #코미디 등)
"""
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text
            
            # TITLE, DESCRIPTION 추출
            title_match = re.search(r'TITLE:\s*(.+)', text)
            desc_match = re.search(r'DESCRIPTION:\s*(.+)', text, re.DOTALL)
            
            title = title_match.group(1).strip() if title_match else original_title[:25]
            description = desc_match.group(1).strip() if desc_match else f"{original_title} #개그콘서트"
            
            # 길이 제한 강제
            title = title[:25]
            description = description[:100]
            
            print(f"✅ 생성된 제목: {title}")
            print(f"✅ 생성된 설명: {description[:50]}...")
            
            return {
                'title': title,
                'description': description
            }
            
        except Exception as e:
            print(f"⚠️ Gemini API 오류: {e}")
            print(f"   기본 메타데이터를 사용합니다.")
            
            return {
                'title': original_title[:25] if original_title else "개그콘서트 쇼츠 🎭",
                'description': f"{original_title[:50]} #개그콘서트 #코미디 #KBS"
            }
    
    def add_subtitle_to_video(
        self, 
        video_path: str, 
        subtitle_text: str, 
        output_path: Optional[str] = None
    ) -> str:
        """영상에 자막 추가 (서울알림 폰트 사용)"""
        
        # MoviePy 사용 불가능하면 원본 반환
        if not self.moviepy_available:
            print(f"⚠️ MoviePy를 사용할 수 없어 자막을 추가하지 않습니다.")
            return video_path
        
        print(f"\n🎬 자막 추가 중...")
        print(f"   자막 내용: {subtitle_text}")
        
        if not output_path:
            video_name = Path(video_path).stem
            output_path = str(Path(video_path).parent / f"{video_name}_subtitled.mp4")
        
        try:
            # 원본 영상 로드
            video = VideoFileClip(video_path)
            width, height = video.size
            duration = video.duration
            
            print(f"   영상 크기: {width}x{height}")
            print(f"   영상 길이: {duration:.1f}초")
            
            # 폰트 설정
            if self.font_path and self.font_path.exists():
                font_to_use = str(self.font_path)
                print(f"   ✅ 서울알림 폰트 사용: {self.font_path.name}")
            else:
                font_to_use = "NanumGothic-Bold"
                print(f"   ⚠️ 기본 폰트 사용: {font_to_use}")
            
            # 자막 텍스트 생성
            txt_clip = TextClip(
                subtitle_text,
                fontsize=int(height * 0.08),  # 화면 높이의 8%
                font=font_to_use,
                color='white',
                stroke_color='black',
                stroke_width=3,
                method='caption',
                size=(int(width * 0.9), None)  # 화면 너비의 90%
            )
            
            # 자막 위치 설정 (하단에서 15% 위)
            txt_clip = txt_clip.set_position(('center', height * 0.75))
            txt_clip = txt_clip.set_duration(duration)
            
            # 영상과 자막 합성
            final_video = CompositeVideoClip([video, txt_clip])
            
            # 출력 (원본 오디오 유지)
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                fps=video.fps,
                preset='medium',
                threads=4
            )
            
            # 메모리 정리
            video.close()
            txt_clip.close()
            final_video.close()
            
            print(f"✅ 자막 추가 완료: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ 자막 추가 실패: {e}")
            print(f"   원본 영상을 사용합니다: {video_path}")
            return video_path
    
    def process_video(self, video_data: Dict) -> Dict:
        """영상 전체 처리 (메타데이터 생성 + 자막 추가)"""
        print(f"\n{'='*60}")
        print(f"🎥 영상 처리 시작: {video_data.get('title', 'Unknown')[:40]}...")
        print(f"{'='*60}")
        
        # 1. Gemini로 메타데이터 생성
        metadata = self.generate_metadata(
            video_data['path'],
            video_data.get('title', '')
        )
        
        # 2. 생성된 제목으로 자막 추가
        processed_path = self.add_subtitle_to_video(
            video_data['path'],
            metadata['title']
        )
        
        # 3. 결과 반환
        result = video_data.copy()
        result.update({
            'processed_path': processed_path,
            'youtube_title': metadata['title'],
            'youtube_description': metadata['description']
        })
        
        print(f"\n✅ 영상 처리 완료!")
        print(f"   최종 제목: {result['youtube_title']}")
        print(f"   자막 파일: {processed_path}")
        
        return result
