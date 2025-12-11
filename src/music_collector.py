import requests
import os
import random

class MusicCollector:
    """Pixabay에서 배경음악 수집 (키워드 확대)"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://pixabay.com/api/"
        
        # 음악 키워드 대폭 확대 (20개)
        self.music_keywords = [
            "funny", "upbeat", "comedy", "happy", "energetic",
            "fun", "playful", "cheerful", "positive", "exciting",
            "groovy", "bouncy", "silly", "quirky", "lighthearted",
            "uplifting", "joyful", "bright", "carefree", "optimistic"
        ]
        
        self.history_file = "music_history.txt"
        self.used_music_ids = self._load_history()
    
    def _load_history(self):
        """사용한 음악 ID 로드"""
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()
    
    def _save_to_history(self, music_id):
        """사용한 음악 ID 저장"""
        self.used_music_ids.add(str(music_id))
        with open(self.history_file, 'a') as f:
            f.write(f"{music_id}\n")
    
    def get_random_music(self, duration=15):
        """
        랜덤 배경음악 다운로드 (중복 방지)
        
        Args:
            duration: 최소 음악 길이 (초)
        
        Returns:
            str: 다운로드된 음악 파일 경로
        """
        # 랜덤 키워드 3개 시도
        attempted_keywords = random.sample(self.music_keywords, min(3, len(self.music_keywords)))
        
        for keyword in attempted_keywords:
            print(f"\n🎵 배경음악 검색 중... (키워드: {keyword})")
            
            params = {
                'key': self.api_key,
                'q': keyword,
                'per_page': 30,  # 더 많이 가져오기
                'audio_type': 'music'
            }
            
            try:
                response = requests.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                hits = data.get('hits', [])
                
                if not hits:
                    print(f"⚠️  '{keyword}' 음악 없음, 다음 키워드 시도...")
                    continue
                
                # duration 이상이고 아직 사용하지 않은 음악 필터링
                suitable_music = [
                    m for m in hits 
                    if m.get('duration', 0) >= duration 
                    and str(m['id']) not in self.used_music_ids
                ]
                
                if not suitable_music:
                    print(f"⚠️  새로운 음악 없음, 다음 키워드 시도...")
                    continue
                
                # 랜덤 선택
                selected = random.choice(suitable_music)
                
                music_id = selected['id']
                music_url = selected['previewURL']
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
                
                # 이미 다운로드된 파일이면 스킵
                if not os.path.exists(music_path):
                    print(f"⬇️  음악 다운로드 중...")
                    
                    music_response = requests.get(music_url, timeout=30)
                    music_response.raise_for_status()
                    
                    with open(music_path, 'wb') as f:
                        f.write(music_response.content)
                    
                    file_size = os.path.getsize(music_path) / (1024 * 1024)
                    print(f"✅ 다운로드 완료: {music_path} ({file_size:.2f} MB)")
                
                # 히스토리에 저장
                self._save_to_history(music_id)
                
                return music_path
                
            except Exception as e:
                print(f"❌ 음악 다운로드 실패 ({keyword}): {e}")
                continue
        
        print("\n⚠️  모든 키워드 시도 실패, 음악 없이 진행")
        return None
