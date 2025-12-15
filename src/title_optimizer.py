import re

def optimize_title(original_title):
    """원본 제목에서 확장자만 제거"""
    title = re.sub(r'\.(gif|mp4|webm|jpg|jpeg|png|avi|mov)$', '', original_title, flags=re.IGNORECASE)
    title = title.strip()
    title = re.sub(r'\s+', ' ', title)
    
    if len(title) > 100:
        title = title[:97] + '...'
    
    print(f"📝 원본 제목: {original_title}")
    print(f"✅ 최적화 제목: {title}")
    
    return title

def generate_description(original_title):
    """원본 제목 기반 설명 생성"""
    clean_title = optimize_title(original_title)
    
    description = f"""{clean_title}

출처: AAGAG.com
#Shorts #숏폼 #밈 #짤 #재미"""
    
    return description
