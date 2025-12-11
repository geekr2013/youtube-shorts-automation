import requests
import os
import random
from datetime import datetime

class VideoCollector:
    def __init__(self, pexels_api_key):
        """Pexels API 초기화"""
        self.pexels_api_key = pexels_api_key
        self.download_folder = "downloaded_videos"
        
        # 폴더 생성
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)
    
    def get_pexels_videos(self, keyword, per_page=10):
        """Pexels에서 동영상 검색"""
        print(f"🔍 Pexels에서 '{keyword}' 검색 중...")
        
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": self.pexels_api_key}
        params = {
            "query": keyword,
            "per_page": per_page,
            "orientation": "portrait"  # Shorts용 세로 영상
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            videos = data.get('videos', [])
            
            print(f"✅ {len(videos)}개 영상 발견")
            
            # 세로 영상만 필터링
            suitable_videos = []
            for video in videos:
                video_files = video.get('video_files', [])
                portrait_files = [f for f in video_files 
                                if f.get('width', 0) < f.get('height', 0)]
                
                if portrait_files:
                    best_file = max(portrait_files, 
                                  key=lambda x: x.get('width', 0) * x.get('height', 0))
                    
                    suitable_videos.append({
                        'id': video.get('id'),
                        'url': best_file['link'],
                        'duration': video.get('duration', 0),
                        'user': video['user']['name'],
                        'user_url': video['user']['url'],
                        'width': best_file['width'],
                        'height': best_file['height'],
                        'keyword': keyword
                    })
            
            return suitable_videos
            
        except Exception as e:
            print(f"❌ Pexels 검색 실패: {e}")
            return []
    
    def download_video(self, video_info):
        """동영상 다운로드"""
        try:
            filename = f"video_{video_info['id']}.mp4"
            filepath = os.path.join(self.download_folder, filename)
            
            print(f"⬇️ 다운로드 중: {filename}")
            
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
            
            file_size = os.path.getsize(filepath) / (1024*1024)
            print(f"✅ 저장 완료: {file_size:.2f} MB")
            
            return {
                'filepath': filepath,
                'filename': filename,
                'video_info': video_info,
                'size_mb': file_size
            }
            
        except Exception as e:
            print(f"❌ 다운로드 실패: {e}")
            return None
    
    def collect_daily_content(self, count=5):
        """일일 콘텐츠 수집"""
        print("\n" + "="*70)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 콘텐츠 수집 시작")
        print("="*70 + "\n")
        
        # 키워드 목록 (다양성 확보)
        keywords = [
            "funny cats", "cute dogs", "funny animals", "cute pets",
            "funny puppies", "cute kittens", "funny birds",
            "amazing nature", "beautiful sunset", "ocean waves",
            "satisfying videos", "oddly satisfying", "creative art"
        ]
        
        # 랜덤 키워드 선택
        selected_keyword = random.choice(keywords)
        print(f"🎯 선택된 키워드: {selected_keyword}\n")
        
        # 동영상 검색
        all_videos = self.get_pexels_videos(selected_keyword, per_page=15)
        
        if not all_videos:
            print("❌ 검색 결과가 없습니다.")
            return []
        
        # 5-15초 길이의 영상만 선택
        suitable_videos = [v for v in all_videos if 5 <= v['duration'] <= 15]
        
        # 랜덤으로 N개 선택
        selected_videos = random.sample(suitable_videos, 
                                       min(count, len(suitable_videos)))
        
        print(f"\n📌 {len(selected_videos)}개 영상 선택됨\n")
        
        # 다운로드
        downloaded_files = []
        for i, video in enumerate(selected_videos, 1):
            print(f"[{i}/{len(selected_videos)}]")
            result = self.download_video(video)
            if result:
                downloaded_files.append(result)
            print()
        
        print(f"✅ 총 {len(downloaded_files)}개 다운로드 완료\n")
        return downloaded_files
