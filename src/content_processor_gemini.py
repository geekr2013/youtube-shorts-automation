import os
import google.generativeai as genai
from datetime import datetime

class GeminiContentProcessor:
    def __init__(self):
        """Gemini API 초기화"""
        # GitHub Secrets 또는 환경 변수에서 API 키 가져오기
        api_key = os.environ.get('GEMINI_API_KEY')
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        # Gemini API 설정
        genai.configure(api_key=api_key)
        
        # Gemini 2.5 Flash 모델 사용 (무료 티어)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        print("✅ Gemini API 초기화 완료")
    
    def generate_korean_title(self, video_keywords, duration):
        """Gemini로 한글 제목 생성"""
        try:
            prompt = f"""
당신은 YouTube Shorts 제목 전문가입니다.

영상 정보:
- 키워드: {video_keywords}
- 길이: {duration}초

다음 조건을 만족하는 YouTube Shorts 제목을 만들어주세요:
1. 70자 이내의 한글 제목
2. 이모지 2-3개 포함
3. 클릭을 유도하는 호기심 자극
4. 자연스러운 한국어
5. 트렌디하고 재미있는 표현 사용
6. "이거", "ㄷㄷㄷ", "레전드" 같은 인터넷 용어 활용

제목만 출력하세요. 다른 설명은 필요 없습니다.
"""
            
            response = self.model.generate_content(prompt)
            title = response.text.strip()
            
            # 길이 제한 (YouTube Shorts 제목 최대 100자)
            if len(title) > 70:
                title = title[:67] + "..."
            
            print(f"✅ Gemini 제목 생성: {title}")
            return title
            
        except Exception as e:
            print(f"⚠️ Gemini 제목 생성 실패: {e}")
            # 백업 템플릿 (Gemini 실패 시)
            backup_titles = [
                "😂 이거 보고 웃음 참기 도전!",
                "🤣 이 영상 보고 안 웃으면 신기한 거임",
                "😱 예상 못한 반전! 끝까지 봐야 함",
                "🔥 이 영상 지금 난리남 ㄷㄷㄷ",
                "💯 이건 진짜 레전드급이에요"
            ]
            import random
            return random.choice(backup_titles)
    
    def generate_korean_script(self, video_title, duration):
        """Gemini로 한글 나레이션 스크립트 생성"""
        try:
            max_words = int(duration * 2)  # 한국어는 초당 약 2단어
            
            prompt = f"""
YouTube Shorts용 한국어 나레이션 스크립트를 작성하세요.

제목: {video_title}
영상 길이: {duration}초
스크립트 길이: {max_words}단어 이내

다음 조건을 만족하는 나레이션을 작성하세요:
1. 짧고 임팩트 있게
2. 친근하고 재미있는 톤
3. 시청자 참여 유도
4. 자연스러운 한국어 구어체
5. "여러분", "오늘은" 같은 인사말 포함

스크립트만 출력하세요. 다른 설명은 필요 없습니다.
"""
            
            response = self.model.generate_content(prompt)
            script = response.text.strip()
            
            # 길이 조정 (너무 길면 잘라내기)
            words = script.split()
            if len(words) > max_words:
                script = ' '.join(words[:max_words])
            
            print(f"✅ Gemini 스크립트 생성: {script[:50]}...")
            return script
            
        except Exception as e:
            print(f"⚠️ Gemini 스크립트 생성 실패: {e}")
            # 백업 스크립트
            return f"여러분 안녕하세요! 오늘 준비한 영상 정말 재미있어요. 끝까지 시청해주세요!"
    
    def generate_video_description(self, title, keywords):
        """Gemini로 동영상 설명 생성"""
        try:
            prompt = f"""
YouTube Shorts 설명란을 작성하세요.

제목: {title}
키워드: {keywords}

다음 조건을 만족하는 설명을 작성하세요:
1. 300자 이내
2. 해시태그 5-10개 포함
3. 시청자 행동 유도 (좋아요, 구독, 댓글)
4. 친근한 톤
5. 이모지 활용

설명만 출력하세요. 다른 내용은 필요 없습니다.
"""
            
            response = self.model.generate_content(prompt)
            description = response.text.strip()
            
            # 길이 제한
            if len(description) > 500:
                description = description[:497] + "..."
            
            print(f"✅ Gemini 설명 생성 완료")
            return description
            
        except Exception as e:
            print(f"⚠️ Gemini 설명 생성 실패: {e}")
            # 백업 설명
            return f"""
{title}

오늘도 재미있는 영상으로 찾아왔어요! 😊
끝까지 시청해주시고, 좋아요와 구독 부탁드립니다! 💖

#Shorts #재미 #힐링 #웃긴영상 #일상 #꿀잼
"""

# 테스트 코드 (로컬 테스트용)
if __name__ == "__main__":
    # 로컬에서 테스트하려면 환경 변수 설정 필요
    # 예: export GEMINI_API_KEY="your_api_key"
    
    try:
        processor = GeminiContentProcessor()
        
        # 제목 생성 테스트
        print("\n" + "="*70)
        print("📝 제목 생성 테스트")
        print("="*70)
        title = processor.generate_korean_title("funny cats", 10)
        print(f"제목: {title}\n")
        
        # 스크립트 생성 테스트
        print("="*70)
        print("💬 스크립트 생성 테스트")
        print("="*70)
        script = processor.generate_korean_script(title, 10)
        print(f"스크립트: {script}\n")
        
        # 설명 생성 테스트
        print("="*70)
        print("📋 설명 생성 테스트")
        print("="*70)
        description = processor.generate_video_description(title, "funny cats")
        print(f"설명:\n{description}\n")
        
    except ValueError as e:
        print(f"\n❌ 오류: {e}")
        print("\n💡 해결 방법:")
        print("   1. Gemini API 키를 발급받으세요")
        print("   2. 환경 변수로 설정하세요:")
        print("      Windows: set GEMINI_API_KEY=your_api_key")
        print("      Mac/Linux: export GEMINI_API_KEY=your_api_key")
