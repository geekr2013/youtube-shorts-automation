"""
Gemini AI 콘텐츠 프로세서 - 한글 인코딩 강화 버전
비디오 분석 및 메타데이터 생성
"""

import os
import json
import unicodedata
import google.generativeai as genai
from typing import Dict, Optional

# MoviePy 임포트 (여러 경로 시도)
try:
    from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
    MOVIEPY_AVAILABLE = True
    print("✅ MoviePy 임포트 성공")
except ImportError:
    try:
        from moviepy import VideoFileClip, TextClip, CompositeVideoClip
        MOVIEPY_AVAILABLE = True
        print("✅ MoviePy 임포트 성공 (대체 경로)")
    except ImportError:
        MOVIEPY_AVAILABLE = False
        print("⚠️ MoviePy를 사용할 수 없습니다. 자막 기능이 비활성화됩니다.")


class ContentProcessor:
    def __init__(self, api_key: str):
        """
        Gemini API를 사용한 콘텐츠 프로세서
        
        Args:
            api_key: Google Gemini API 키
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash-latest')  # 수정: 최신 모델명
        print("✅ Gemini API 초기화 완료")
        
        # 폰트 경로 찾기
        self.font_path = self._find_font()
    
    def _normalize_korean_text(self, text: str) -> str:
        """
        한글 텍스트 정규화 (NFC 정규화)
        
        Args:
            text: 원본 텍스트
            
        Returns:
            정규화된 텍스트
        """
        if not text:
            return ""
        
        # NFC 정규화 (한글 조합형 통일)
        normalized = unicodedata.normalize('NFC', text)
        
        # 제어 문자 제거
        normalized = ''.join(char for char in normalized if unicodedata.category(char)[0] != 'C')
        
        return normalized.strip()
    
    def _find_font(self) -> str:
        """사용 가능한 한글 폰트 찾기"""
        # 여러 경로에서 한글 폰트 찾기
        font_paths = [
            # 프로젝트 폰트
            "fonts/SeoulAlrim-ExtraBold.otf",
            "../fonts/SeoulAlrim-ExtraBold.otf",
            "/home/runner/work/youtube-shorts-automation/youtube-shorts-automation/fonts/SeoulAlrim-ExtraBold.otf",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts", "SeoulAlrim-ExtraBold.otf"),
            # 시스템 한글 폰트
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf",
            "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf"
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                print(f"✅ 한글 폰트 사용: {path}")
                return path
        
        print("⚠️ 사용 가능한 한글 폰트를 찾을 수 없습니다.")
        return None
    
    def generate_metadata(self, video_path: str) -> Dict:
        """
        비디오 분석 후 메타데이터 생성 (한글 안전 처리)
        
        Args:
            video_path: 비디오 파일 경로
            
        Returns:
            title, description, tags를 포함한 딕셔너리
        """
        try:
            print(f"   🤖 Gemini로 메타데이터 생성 중: {os.path.basename(video_path)}")
            
            # 비디오 파일 업로드
            video_file = genai.upload_file(path=video_path)
            print(f"   ✅ 비디오 업로드 완료")
            
            # 프롬프트 생성 (한글 명시)
            prompt = """
이 짧은 개그 영상을 분석하고 다음 정보를 **반드시 한글로** JSON 형식으로 생성해주세요:

1. title: 15자 이내의 흥미로운 제목 (이모지 1-2개 포함, 클릭을 유도하는 제목)
2. description: 3-5줄의 상세 설명 (영상의 재미 포인트와 핵심 내용 설명)
3. tags: 관련 해시태그 7-10개 (한글 태그 위주, 일부 영어 가능)
4. subtitle: 영상의 핵심 대사나 상황을 요약한 한 줄 자막 (10자 이내, 임팩트 있게)

**중요**: 모든 텍스트는 반드시 UTF-8 인코딩 가능한 한글로 작성하세요.

응답 형식 (정확히 이 형식으로):
{
  "title": "제목",
  "description": "설명",
  "tags": ["태그1", "태그2", "태그3"],
  "subtitle": "자막"
}
"""
            
            # Gemini API 호출
            response = self.model.generate_content([video_file, prompt])
            
            # JSON 파싱
            response_text = response.text.strip()
            
            # 마크다운 코드 블록 제거
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            result = json.loads(response_text.strip())
            
            # 한글 정규화 적용
            result['title'] = self._normalize_korean_text(result.get('title', ''))
            result['description'] = self._normalize_korean_text(result.get('description', ''))
            result['tags'] = [self._normalize_korean_text(tag) for tag in result.get('tags', [])]
            result['subtitle'] = self._normalize_korean_text(result.get('subtitle', ''))
            
            print(f"   ✅ 메타데이터 생성 완료")
            print(f"      제목: {result['title']}")
            print(f"      자막: {result.get('subtitle', 'N/A')}")
            
            return result
            
        except Exception as e:
            print(f"   ❌ 메타데이터 생성 실패: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # 기본값 반환 (한글 안전)
            return {
                'title': '🎬 재미있는 개그 영상',
                'description': 'AAGAG에서 가져온 재미있는 영상입니다.\n\n#개그 #재미 #웃음',
                'tags': ['개그', '재미', '웃음', 'aagag', '한국', 'shorts', '숏츠'],
                'subtitle': '웃음 폭탄!'
            }
    
    def add_subtitle_to_video(self, video_path: str, subtitle_text: str) -> Optional[str]:
        """
        비디오에 자막 추가 (한글 안전 처리)
        
        Args:
            video_path: 원본 비디오 경로
            subtitle_text: 자막 텍스트
            
        Returns:
            자막이 추가된 비디오 경로 (실패 시 원본 경로)
        """
        if not MOVIEPY_AVAILABLE:
            print("   ⚠️ MoviePy를 사용할 수 없어 자막을 추가하지 못했습니다.")
            return video_path
        
        if not self.font_path:
            print("   ⚠️ 한글 폰트를 찾을 수 없어 자막을 추가하지 못했습니다.")
            return video_path
        
        try:
            print(f"   📝 자막 추가 중: '{subtitle_text}'")
            
            # 자막 텍스트 정규화
            subtitle_text = self._normalize_korean_text(subtitle_text)
            
            # 비디오 로드
            video = VideoFileClip(video_path)
            
            # 자막 생성 (한글 안전)
            txt_clip = TextClip(
                subtitle_text,
                fontsize=60,
                color='white',
                font=self.font_path,
                stroke_color='black',
                stroke_width=3,
                method='caption',
                size=(video.w * 0.9, None),
                align='center'
            ).set_position(('center', 0.85), relative=True).set_duration(video.duration)
            
            # 자막 합성
            final_video = CompositeVideoClip([video, txt_clip])
            
            # 출력 경로
            output_path = video_path.replace('.mp4', '_subtitled.mp4')
            
            # 저장 (오디오 보존)
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            # 리소스 해제
            video.close()
            final_video.close()
            
            print(f"   ✅ 자막 추가 완료: {os.path.basename(output_path)}")
            return output_path
            
        except Exception as e:
            print(f"   ❌ 자막 추가 실패: {str(e)}")
            import traceback
            traceback.print_exc()
            return video_path
    
    def process_video(self, video_path: str) -> Optional[Dict]:
        """
        비디오 처리 메인 함수
        
        Args:
            video_path: 비디오 파일 경로
            
        Returns:
            처리 결과 딕셔너리
        """
        try:
            print(f"\n{'='*60}")
            print(f"🎬 비디오 처리 시작: {os.path.basename(video_path)}")
            print(f"{'='*60}")
            
            # 1. 메타데이터 생성
            metadata = self.generate_metadata(video_path)
            
            # 2. 자막 추가 (선택사항)
            output_path = self.add_subtitle_to_video(
                video_path,
                metadata.get('subtitle', '재미있는 영상')
            )
            
            result = {
                'original_path': video_path,
                'output_path': output_path,
                'title': metadata['title'],
                'description': metadata['description'],
                'tags': metadata['tags']
            }
            
            print(f"{'='*60}")
            print(f"✅ 비디오 처리 완료")
            print(f"{'='*60}\n")
            
            return result
            
        except Exception as e:
            print(f"❌ 비디오 처리 실패: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
