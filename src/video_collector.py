import os
import yt_dlp
from pathlib import Path
from typing import List, Dict
import time
from googleapiclient.discovery import build

class VideoCollector:
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.history_file = Path("downloaded_history.txt")
        
        # YouTube Data API 클라이언트
        api_key = os.getenv('YOUTUBE_DATA_API_KEY')
        if api_key:
            self.youtube = build('youtube', 'v3', developerKey=api_key)
            print("✅ YouTube Data API 초기화 완료")
        else:
            self.youtube = None
            print("⚠️ YOUTUBE_DATA_API_KEY 없음 - RSS 방식 사용")
    
    def load_history(self) -> set:
        """다운로드 이력 로드"""
        if not self.history_file.exists():
            return set()
        with open(self.history_file, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    
    def save_history(self, video_id: str):
        """다운로드 이력 저장"""
        with open(self.history_file, 'a', encoding='utf-8') as f:
            f.write(f"{video_id}\n")
    
    def get_shorts_from_api(self, channel_id: str, max_results: int = 50) -> List[Dict]:
        """YouTube Data API로 Shorts 가져오기"""
        if not self.youtube:
            return []
        
        print(f"📡 YouTube Data API로 영상 검색 중...")
        
        try:
            # 채널의 업로드 재생목록 ID 가져오기
            channel_response = self.youtube.channels().list(
                part='contentDetails',
                id=channel_id
            ).execute()
            
            if not channel_response['items']:
                print("❌ 채널을 찾을 수 없습니다.")
                return []
            
            uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # 최근 업로드 영상 가져오기
            playlist_response = self.youtube.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=uploads_playlist_id,
                maxResults=max_results
            ).execute()
            
            video_ids = [item['contentDetails']['videoId'] for item in playlist_response['items']]
            
            if not video_ids:
                print("⚠️ 영상이 없습니다.")
                return []
            
            # 영상 상세 정보 가져오기 (duration 포함)
            videos_response = self.youtube.videos().list(
                part='snippet,contentDetails',
                id=','.join(video_ids)
            ).execute()
            
            shorts_info = []
            for video in videos_response['items']:
                duration_str = video['contentDetails']['duration']
                
                # ISO 8601 duration을 초로 변환
                duration = self._parse_duration(duration_str)
                
                # 60초 이하만 필터링
                if 0 < duration <= 60:
                    shorts_info.append({
                        'id': video['id'],
                        'title': video['snippet']['title'],
                        'description': video['snippet']['description'],
                        'duration': duration,
                        'url': f"https://www.youtube.com/watch?v={video['id']}"
                    })
            
            print(f"✅ API에서 {len(shorts_info)}개 Shorts 발견")
            return shorts_info
            
        except Exception as e:
            print(f"❌ API 오류: {e}")
            return []
    
    def _parse_duration(self, duration_str: str) -> int:
        """ISO 8601 duration을 초로 변환"""
        import re
        
        # PT1M30S -> 90초
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds
    
    def download_video(self, video_id: str, title: str) -> Optional[str]:
    """비디오 다운로드"""
    try:
        output_path = os.path.join(self.output_dir, f"{video_id}.mp4")
        
        ydl_opts = {
            'format': 'best[ext=mp4]',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 30,
            'cookiefile': os.path.expanduser('~/.config/yt-dlp/cookies.txt'),  # 🔑 쿠키 추가
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"⏬ 다운로드 시작: {title}")
            ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
        
        if os.path.exists(output_path):
            print(f"✅ 다운로드 완료: {output_path}")
            return output_path
        else:
            print(f"❌ 파일 생성 실패: {output_path}")
            return None
            
    except Exception as e:
        print(f"❌ 다운로드 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
    def collect_gagconcert_shorts(self, max_videos: int = 3) -> List[Dict]:
        """개그콘서트 쇼츠 수집 - API 우선, 실패 시 RSS"""
        print(f"\n📥 개그콘서트 쇼츠 수집 시작... (최대 {max_videos}개)")
        
        downloaded_ids = self.load_history()
        print(f"📋 기존 다운로드 이력: {len(downloaded_ids)}개")
        
        channel_id = "UCzT7nHtzVqwiarTH8sqHaJA"
        
        # API로 Shorts 정보 가져오기
        shorts_info = self.get_shorts_from_api(channel_id, max_results=50)
        
        if not shorts_info:
            print("⚠️ API에서 영상을 가져올 수 없습니다.")
            return []
        
        collected_videos = []
        downloaded_count = 0
        
        for short in shorts_info:
            if downloaded_count >= max_videos:
                break
            
            video_id = short['id']
            
            # 이미 다운로드한 영상 스킵
            if video_id in downloaded_ids:
                print(f"⏭️ 이미 다운로드됨: {video_id}")
                continue
            
            print(f"\n[{downloaded_count + 1}/{max_videos}]")
            print(f"  📹 제목: {short['title'][:50]}...")
            print(f"  ⏱️ 길이: {short['duration']}초")
            
            # 다운로드
            video_path = self.download_video_with_cookies(video_id, short['url'])
            
            if video_path:
                video_data = {
                    'id': video_id,
                    'path': video_path,
                    'title': short['title'],
                    'description': short['description'],
                    'duration': short['duration'],
                    'original_url': short['url']
                }
                
                collected_videos.append(video_data)
                self.save_history(video_id)
                downloaded_count += 1
                
                print(f"✅ 다운로드 완료!")
                
                # 서버 부하 방지
                time.sleep(2)
            else:
                print(f"⚠️ 다운로드 실패: {video_id}")
        
        print(f"\n✅ 총 {len(collected_videos)}개 영상 수집 완료")
        return collected_videos
