import re

def optimize_title(original_title):
    """
    원본 제목에서 확장자만 제거하고 정리
    
    Args:
        original_title: AAGAG 게시물 원본 제목
        
    Returns:
        최적화된 제목 (확장자 제거, 최대 100자)
    """
    # 확장자 제거 (.gif, .mp4, .webm, .jpg, .png 등)
    title = re.sub(r'\.(gif|mp4|webm|jpg|jpeg|png|avi|mov)$', '', original_title, flags=re.IGNORECASE)
    
    # 앞뒤 공백 제거
    title = title.strip()
    
    # 연속된 공백을 하나로
    title = re.sub(r'\s+', ' ', title)
    
    # YouTube 제목 길이 제한 (최대 100자)
    if len(title) > 100:
        title = title[:97] + '...'
    
    print(f"📝 원본 제목: {original_title}")
    print(f"✅ 최적화 제목: {title}")
    
    return title

def generate_description(original_title):
    """
    원본 제목 기반 간단한 설명 생성
    
    Args:
        original_title: AAGAG 게시물 원본 제목
        
    Returns:
        영상 설명
    """
    clean_title = optimize_title(original_title)
    
    description = f"""{clean_title}

출처: AAGAG.com
#Shorts #숏폼 #밈 #짤 #재미"""
    
    return description
