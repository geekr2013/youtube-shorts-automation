import requests
import os
import random
from datetime import datetime

class VideoCollector:
    """Pexels/Pixabay에서 다양한 동영상 수집"""
    
    def __init__(self, pexels_api_key, pixabay_api_key=None):
        self.pexels_api_key = pexels_api_key
        self.pixabay_api_key = pixabay_api_key
        self.pexels_base_url = "https://api.pexels.com/videos/search"
        self.pixabay_base_url = "https://pixabay.com/api/videos/"
        
        # 50+ 다양한 키워드 (카테고리별 분류)
        self.keyword_categories = {
            'animals': [
                "funny cats", "funny dogs", "funny animals", "cute puppies",
                "cat fails", "dog pranks", "pet reactions", "animal surprise",
                "cats vs dogs", "funny birds", "animal jumping", "pets playing",
                "kitten fails", "puppy videos", "wild animals funny"
            ],
            'fails_pranks': [
                "funny fails", "epic fails", "fail compilation", "people falling",
                "silly mistakes", "prank reactions", "unexpected moments", "funny accidents",
                "clumsy people", "embarrassing moments", "sport fails", "gym fails",
                "wedding fails", "cooking disasters", "dance fails"
            ],
            'babies_kids': [
                "funny babies", "baby laughing", "cute babies", "toddler fails",
                "kids reactions", "children playing", "baby surprised", "kids dancing",
                "baby eating", "funny toddlers"
            ],
            'sports_action': [
                "skateboard fails", "bike tricks", "parkour fails", "extreme sports",
                "surfing wipeout", "basketball tricks", "soccer fails", "skiing funny",
                "snowboard tricks", "sports bloopers"
            ],
            'magic_illusions': [
                "magic tricks", "illusions", "mind blowing", "optical illusion",
                "card tricks", "street magic", "amazing tricks", "visual effects",
                "creative videos", "unexpected tricks"
            ]
        }
        
        # 중복 방지용 히스토리 파일
        self.history_file = "downloaded_history.txt"
        self.downloaded_ids = self._load_history()
    
    def _load_history(self):
        """이전에 다운로드한 영상 ID 로드"""
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()
    
    def _save_to_history(self, video_id):
        """다운로드한 영상 ID 저장"""
        self.downloaded_ids.add(str(video_id))
        with open(self.history_file, 'a') as f:
            f.write(f"{video_id}\n")
    
    def get_daily_keywords(self, count=3):
        """
        매일 다른 키워드 선택 (요일별 로테이션)
        
        Args:
            count: 선택할 키워드 개수
        
        Returns:
            list: 선택된 키워드 리스트
        """
        # 요일별 카테고리 매핑 (0=월요일, 6=일요일)
        today = datetime.now().weekday()
        
        category_schedule = {
            0: 'animals',           # 월요일
            1: 'fails_pranks',      # 화요일
            2: 'babies_kids',       # 수요일
            3: 'sports_action',     # 목요일
            4: 'magic_illusions',   # 금요일
            5: 'random',            # 토요일 (전체 랜덤)
            6: 'random'             # 일요일 (전체 랜덤)
        }
        
        selected_category = category_schedule[today]
        
        if selected_category == 'random':
            # 주말: 모든 카테고리에서 랜덤 선택
            all_keywords = []
            for keywords in self.keyword_categories.values():
                all_keywords.extend(keywords)
            keywords = random.sample(all_keywords, min(count, len(all_keywords)))
        else:
            # 평일: 해당 카테고리에서 선택
            category_keywords = self.keyword_categories[selected_category]
            keywords = random.sample(category_keywords, min(count, len(category_keywords)))
        
        print(f"📅 오늘은 {['월','화','수','목','금','토','일'][today]}요일")
        print(f"🎯 선택된 카테고리: {selected_category}")
        print(f"🔑 사용할 키워드: {keywords}\n")
        
        return keywords
    
    def search_pexels_videos(self, keyword, max_results=10):
        """Pexels에서 동영상 검색"""
        
        headers = {"Authorization": self.pexels_api_key}
        params = {
            "query": keyword,
            "per_page": max_results,
            "orientation": "portrait"
        }
        
        try:
            response = requests.get(
                self.pexels_base_url, 
                headers=headers, 
                params=params, 
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            videos = data.get('videos', [])
            
            # 세로 영상만 필터링 + 중복 제외
            suitable_videos = []
            for video in videos:
                video_id = video.get('id')
                
                # 이미 다운로드한 영상 제외
                if str(video_id) in self.downloaded_ids:
                    continue
                
                duration = video.get('duration', 0)
                
                # 5~30초 영상만 선택
                if 5 <= duration <= 30:
                    video_files = video.get('video_files', [])
                    portrait_files = [
                        f for f in video_files 
                        if f.get('width', 0) < f.get('height', 0)
                    ]
                    
                    if portrait_files:
                        best_file = max(
                            portrait_files, 
                            key=lambda x: x.get('width', 0) * x.get('height', 0)
                        )
                        
                        suitable_videos.append({
                            'id': video_id,
                            'url': best_file['link'],
                            'duration': duration,
                            'width': best_file['width'],
                            'height': best_file['height'],
                            'user': video['user']['name'],
                            'keyword': keyword,
                            'source': 'pexels'
                        })
            
            return suitable_videos
            
        except Exception as e:
            print(f"❌ Pexels 검색 실패 ({keyword}): {e}")
            return []
    
    def download_video(self, video_info, folder="downloaded_videos"):
        """동영상 다운로드"""
        
        os.makedirs(folder, exist_ok=True)
        
        video_id = video_info['id']
        source = video_info['source']
        filename = f"{source}_{video_id}.mp4"
        filepath = os.path.join(folder, filename)
        
        # 이미 다운로드된 파일이면 스킵
        if os.path.exists(filepath):
            print(f"⏭️  이미 존재함: {filename}")
            video_info['path'] = filepath
            return video_info
        
        try:
            print(f"⬇️  다운로드 중: {filename}")
            print(f"   키워드: {video_info['keyword']}")
            print(f"   길이: {video_info['duration']}초")
            
            response = requests.get(video_info['url'], stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"   진행률: {percent:.1f}%", end='\r')
            
            print()  # 줄바꿈
            
            file_size = os.path.getsize(filepath) / (1024 * 1024)
            print(f"✅ 다운로드 완료: {file_size:.2f} MB\n")
            
            video_info['path'] = filepath
            
            # 히스토리에 저장
            self._save_to_history(video_id)
            
            return video_info
            
        except Exception as e:
            print(f"❌ 다운로드 실패: {e}\n")
            return None
    
    def collect_videos(self, count=3):
        """
        다양한 키워드로 동영상 수집
        
        Args:
            count: 수집할 동영상 개수
        
        Returns:
            list: 다운로드된 동영상 정보 리스트
        """
        
        print("="*70)
        print(f"🎬 동영상 수집 시작 (목표: {count}개)")
        print("="*70 + "\n")
        
        # 매일 다른 키워드 선택
        keywords = self.get_daily_keywords(count=count * 2)  # 여유있게 2배
        
        collected_videos = []
        
        for keyword in keywords:
            if len(collected_videos) >= count:
                break
            
            print(f"🔍 '{keyword}' 검색 중...")
            
            # Pexels 검색
            videos = self.search_pexels_videos(keyword, max_results=10)
            
            if videos:
                print(f"✅ {len(videos)}개 발견\n")
                
                # 랜덤하게 1개 선택
                selected = random.choice(videos)
                
                # 다운로드
                downloaded = self.download_video(selected)
                
                if downloaded:
                    collected_videos.append(downloaded)
            else:
                print(f"⚠️  영상을 찾을 수 없음\n")
        
        print("="*70)
        print(f"✅ 총 {len(collected_videos)}개 동영상 수집 완료")
        print("="*70 + "\n")
        
        return collected_videos
