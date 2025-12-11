import requests
import os
import random

class MusicCollector:
    """Pixabay에서 배경음악 수집"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://pixabay.com/api/"
        
        # 쇼츠에 어울리는 음악 장르
        self.music_keywords = [
            "funny", "upbeat", "comedy", "happy", "energetic",
            "fun", "playful", "cheerful", "positive", "exciting"
        ]
    
    def get_random_music(self, duration=15):
        """
        랜덤 배경음악 다운로드
        
        Args:
            duration: 최소 음악 길이 (초)
        
        Returns:
            str: 다운로드된 음악 파일 경로
        """
        keyword = random.choice(self.music_keywords)
        
        print(f"\n🎵 배경음악 검색 중... (키워드: {keyword})")
        
        params = {
            'key': self.api_key,
            'q': keyword,
            'per_page': 20,
            'audio_type': 'music'
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            hits = data.get('hits', [])
            
            if not hits:
                print(f"❌ '{keyword}' 음악을 찾을 수 없습니다.")
                return None
            
            # duration 이상인 음악만 필터링
            suitable_music = [
                m for m in hits 
                if m.get('duration', 0) >= duration
            ]
            
            if not suitable_music:
                # duration이 부족하면 가장 긴 음악 선택
                suitable_music = sorted(hits, key=lambda x: x.get('duration', 0), reverse=True)[:5]
            
            # 랜덤 선택
            selected = random.choice(suitable_music)
            
            music_id = selected['id']
            music_url = selected['previewURL']  # MP3 128kbps
            music_duration = selected['duration']
            tags = selected.get('tags', 'unknown')
            
            print(f"✅ 선택된 음악:")
            print(f"   ID: {music_id}")
            print(f"   길이: {music_duration}초")
            print(f"   태그: {tags}")
            
            # 음악 다운로드
            music_folder = "downloaded_music"
            os.makedirs(music_folder, exist_ok=True)
            
            music_path = os.path.join(music_folder, f"music_{music_id}.mp3")
            
            print(f"⬇️  음악 다운로드 중...")
            
            music_response = requests.get(music_url, timeout=30)
            music_response.raise_for_status()
            
            with open(music_path, 'wb') as f:
                f.write(music_response.content)
            
            file_size = os.path.getsize(music_path) / (1024 * 1024)
            print(f"✅ 다운로드 완료: {music_path} ({file_size:.2f} MB)")
            
            return music_path
            
        except Exception as e:
            print(f"❌ 음악 다운로드 실패: {e}")
            return None
