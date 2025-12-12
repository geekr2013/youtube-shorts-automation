import os
import yt_dlp
from pathlib import Path
from typing import List, Dict
import json

class VideoCollector:
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.history_file = Path("downloaded_history.txt")
        
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
    
    def collect_gagconcert_shorts(self, max_videos: int = 3) -> List[Dict]:
        """개그콘서트 쇼츠 수집"""
        print(f"\n📥 개그콘서트 쇼츠 수집 시작... (최대 {max_videos}개)")
        
        downloaded_ids = self.load_history()
        print(f"📋 기존 다운로드 이력: {len(downloaded_ids)}개")
        
        channel_url = "https://www.youtube.com/@KBS_Gagconcert/shorts"
        
        # 1단계: 플레이리스트 정보 수집
        ydl_opts_info = {
            'quiet': True,
            'extract_flat': True,
            'playlistend': 10,  # 최신 10개 확인
        }
        
        video_urls = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                print(f"🔍 채널 확인 중: {channel_url}")
                playlist_info = ydl.extract_info(channel_url, download=False)
                
                if not playlist_info or 'entries' not in playlist_info:
                    print("❌ 채널에서 영상을 찾을 수 없습니다.")
                    return []
                
                entries = playlist_info['entries']
                print(f"✅ 총 {len(entries)}개 영상 발견")
                
                # 새로운 영상만 필터링
                for entry in entries:
                    if entry and 'id' in entry:
                        video_id = entry['id']
                        if video_id not in downloaded_ids:
                            video_urls.append(f"https://www.youtube.com/watch?v={video_id}")
                            print(f"  ➕ 새 영상 발견: {video_id}")
                            if len(video_urls) >= max_videos:
                                break
                
                if not video_urls:
                    print("⚠️ 새로운 영상이 없습니다. (모두 다운로드 완료)")
                    return []
                
        except Exception as e:
            print(f"❌ 플레이리스트 정보 수집 실패: {e}")
            return []
        
        # 2단계: 실제 영상 다운로드
        ydl_opts_download = {
            'format': 'best[ext=mp4][height<=1080]/best[ext=mp4]/best',
            'outtmpl': str(self.download_dir / '%(id)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'writeinfojson': True,  # 메타데이터 저장
        }
        
        collected_videos = []
        
        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
            for idx, video_url in enumerate(video_urls, 1):
                try:
                    print(f"\n📥 [{idx}/{len(video_urls)}] 다운로드 중: {video_url}")
                    info = ydl.extract_info(video_url, download=True)
                    
                    video_id = info['id']
                    video_path = self.download_dir / f"{video_id}.mp4"
                    
                    if not video_path.exists():
                        print(f"⚠️ 다운로드 실패: {video_path}")
                        continue
                    
                    video_data = {
                        'id': video_id,
                        'path': str(video_path),
                        'title': info.get('title', '개그콘서트'),
                        'description': info.get('description', ''),
                        'duration': info.get('duration', 0),
                        'original_url': video_url
                    }
                    
                    collected_videos.append(video_data)
                    self.save_history(video_id)
                    print(f"✅ 다운로드 완료: {video_data['title'][:30]}...")
                    
                except Exception as e:
                    print(f"⚠️ 영상 다운로드 실패: {e}")
                    continue
        
        print(f"\n✅ 총 {len(collected_videos)}개 영상 수집 완료")
        return collected_videos
