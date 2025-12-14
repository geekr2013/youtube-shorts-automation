import re

class TitleOptimizer:
    @staticmethod
    def optimize_title(title):
        """제목 최적화 (확장자 제거, 한글 보정)"""
        # 확장자 제거 (.gif, .mp4, .webm 등)
        title = re.sub(r'\.(gif|mp4|webm|avi|mov|gifv)(\s|$)', ' ', title, flags=re.IGNORECASE)
        
        # [OC], [VIDEO], 태그 제거
        title = re.sub(r'\[.*?\]', '', title)
        
        # 특수문자 정리
        title = re.sub(r'[_\-]+', ' ', title)
        
        # 연속 공백 제거
        title = re.sub(r'\s+', ' ', title)
        
        # 앞뒤 공백 제거
        title = title.strip()
        
        # 길이 제한 (YouTube Shorts 제목은 100자까지)
        if len(title) > 90:
            title = title[:90] + '...'
        
        return title
    
    @staticmethod
    def generate_hashtags(title):
        """제목에서 해시태그 생성"""
        hashtags = ['#Shorts', '#밈', '#웃긴영상']
        
        # 키워드 추출 (간단한 방법)
        keywords = title.split()
        for keyword in keywords[:3]:
            if len(keyword) > 2:
                hashtags.append(f'#{keyword}')
        
        return ' '.join(hashtags)
