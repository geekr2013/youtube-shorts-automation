import os
import json
from typing import List, Dict, Optional
import yt_dlp
from googleapiclient.discovery import build
from datetime import datetime

class VideoCollector:
    def __init__(self, api_key: str, channel_id: str = "UCzT7nHtzVqwiarTH8sqHaJA", max_videos: int = 3):
        """
        YouTube Data API를 사용한 비디오 수집기
        
        Args:
            api_key: YouTube Data API 키
            channel_id: 개그콘서트 채널 ID
            max_videos: 수집할 최대 비디오 수
        """
        self.api_key = api_key
        self.channel_id = channel_id
        self.max_videos = max_videos
        self.output_dir = "downloads"
        self.history_file = "data/download_history.json"
        
        # 출력 디렉토리 생성
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs("data", exist_ok=True)
        
        # YouTube API 클라이언트 초기화
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        print(f"✅ YouTube Data API 초기화 완료")
    
    def load_history(self) -> set:
        """다운로드 이력 로드"""
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get('downloaded_ids', []))
        return set()
    
    def save_history(self, video_ids: set):
        """다운로드 이력 저장"""
        data = {
            'downloaded_ids': list(video_ids),
            'last_updated': datetime.now().isoformat()
        }
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 다운로드 이력 저장 완료: {len(video_ids)}개")
    
    def search_shorts(self) -> List[Dict]:
        """YouTube Data API로 Shorts 검색"""
        try:
            print(f"🔍 YouTube Data API로 채널 검색 시작...")
            
            # 채널의 최신 업로드 가져오기
            request = self.youtube.search().list(
                part="id,snippet",
                channelId=self.channel_id,
                maxResults=50,  # API 쿼터: 100 units
                order="date",
                type="video"
            )
            response = request.execute()
            
            videos = []
            for item in response.get('items', []):
                video_id = item['id']['videoId']
                title = item['snippet']['title']
                
                # 비디오 세부정보 가져오기 (duration 확인)
                video_request = self.youtube.videos().list(
                    part="contentDetails,snippet",
                    id=video_id
                )
                video_response = video_request.execute()
                
                if video_response['items']:
                    video_data = video_response['items'][0]
                    duration = video_data['contentDetails']['duration']
                    
                    # ISO 8601 duration을 초로 변환 (PT1M30S -> 90초)
                    duration_seconds = self._parse_duration(duration)
                    
                    # Shorts는 60초 이하
                    if duration_seconds <= 60:
                        videos.append({
                            'id': video_id,
                            'title': title,
                            'duration': duration_seconds,
                            'published_at': item['snippet']['publishedAt']
                        })
                        print(f"  ✅ Shorts 발견: {title} ({duration_seconds}초)")
            
            print(f"✅ 총 {len(videos)}개의 Shorts 발견")
            return videos
            
        except Exception as e:
            print(f"❌ YouTube API 검색 실패: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _parse_duration(self, duration: str) -> int:
        """ISO 8601 duration을 초로 변환"""
        import re
        
        # PT1M30S 형식 파싱
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration)
        
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
                'cookiefile': os.path.expanduser('~/.config/yt-dlp/cookies.txt'),  # 쿠키 파일 사용
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Referer': 'https://www.youtube.com/'
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
    
    def collect_videos(self) -> List[str]:
        """비디오 수집 메인 함수"""
        print("="*50)
        print("🎬 개그콘서트 Shorts 수집 시작")
        print("="*50)
        
        # 다운로드 이력 로드
        downloaded_ids = self.load_history()
        print(f"📋 기존 다운로드 이력: {len(downloaded_ids)}개")
        
        # Shorts 검색
        videos = self.search_shorts()
        
        if not videos:
            print("❌ 수집할 비디오가 없습니다.")
            return []
        
        # 새로운 비디오만 필터링
        new_videos = [v for v in videos if v['id'] not in downloaded_ids]
        print(f"📥 새로운 비디오: {len(new_videos)}개")
        
        if not new_videos:
            print("✅ 모든 비디오가 이미 다운로드되었습니다.")
            return []
        
        # 최대 개수만큼만 다운로드
        videos_to_download = new_videos[:self.max_videos]
        print(f"⏬ 다운로드 대상: {len(videos_to_download)}개")
        
        downloaded_paths = []
        for video in videos_to_download:
            video_id = video['id']
            title = video['title']
            
            path = self.download_video(video_id, title)
            if path:
                downloaded_paths.append(path)
                downloaded_ids.add(video_id)
        
        # 이력 저장
        if downloaded_paths:
            self.save_history(downloaded_ids)
        
        print("="*50)
        print(f"✅ 수집 완료: {len(downloaded_paths)}개 비디오")
        print("="*50)
        
        return downloaded_paths
