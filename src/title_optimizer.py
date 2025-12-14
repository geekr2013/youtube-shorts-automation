import re
import os
import google.generativeai as genai

class TitleOptimizer:
    def __init__(self, gemini_api_key=None):
        """Gemini API 초기화"""
        self.gemini_api_key = gemini_api_key
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    def optimize_title(self, original_title):
        """제목 최적화 (확장자 제거, 정리)"""
        # 확장자 제거
        title = re.sub(r'\.(gif|mp4|webm|avi|mov|gifv|jpg|jpeg|png)(\s|$)', ' ', original_title, flags=re.IGNORECASE)
        
        # 특수 기호 정리
        title = re.sub(r'[_\-]+', ' ', title)
        title = re.sub(r'\s+', ' ', title)
        title = title.strip()
        
        # 혐 표시 제거
        title = re.sub(r'^혐\)\s*', '', title)
        
        return title
    
    def generate_engaging_title(self, original_title, video_path=None):
        """AI로 매력적인 제목 생성"""
        if not self.gemini_api_key:
            return self.optimize_title(original_title)
        
        try:
            print(f"🤖 AI로 제목 생성 중...")
            
            cleaned_title = self.optimize_title(original_title)
            
            prompt = f"""다음은 YouTube Shorts용 짧은 영상의 원본 제목입니다:
"{cleaned_title}"

이 제목을 바탕으로 더 클릭하고 싶고 매력적인 한글 제목을 만들어주세요.

조건:
1. 50자 이내
2. 호기심을 자극하는 표현 사용
3. 이모지 1~2개 포함 (선택사항)
4. 자연스러운 한글
5. 원본 의미 유지

제목만 출력하고 다른 설명은 하지 마세요."""

            response = self.model.generate_content(prompt)
            ai_title = response.text.strip()
            
            # 따옴표 제거
            ai_title = ai_title.strip('"\'')
            
            print(f"✨ AI 생성 제목: {ai_title}")
            return ai_title
        
        except Exception as e:
            print(f"⚠️ AI 제목 생성 실패, 기본 제목 사용: {str(e)}")
            return self.optimize_title(original_title)
    
    def generate_description(self, title, video_path=None):
        """AI로 설명 생성"""
        if not self.gemini_api_key:
            return f"{title}\n\n#Shorts #밈 #웃긴영상 #재미"
        
        try:
            print(f"🤖 AI로 설명 생성 중...")
            
            prompt = f"""다음은 YouTube Shorts 영상의 제목입니다:
"{title}"

이 영상에 어울리는 간단한 설명을 작성해주세요.

조건:
1. 2~3줄 분량
2. 자연스러운 한글
3. 해시태그 3~5개 포함 (#Shorts는 필수)
4. 시청자의 관심을 끌 수 있는 내용

설명만 출력하세요."""

            response = self.model.generate_content(prompt)
            description = response.text.strip()
            
            print(f"✨ AI 생성 설명: {description[:50]}...")
            return description
        
        except Exception as e:
            print(f"⚠️ AI 설명 생성 실패: {str(e)}")
            return f"{title}\n\n#Shorts #밈 #웃긴영상 #재미"
