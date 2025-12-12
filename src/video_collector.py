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
        """개그콘서트 쇼츠 수집 - 직접 다운로드 방식"""
        print(f"\n📥 개그콘서트 쇼츠 수집 시작... (최대 {max_videos}개)")
        
        downloaded_ids = self.load_history()
        print(f"📋 기존 다운로드 이력: {len(downloaded_ids)}개")
        
        channel_url = "https://www.youtube.com/@KBS_Gagconcert/shorts"
        
        # 직접 다운로드 시도 (플레이리스트에서 최신 영상만)
        ydl_opts = {
            'format': 'best[ext=mp4][height<=1080]/best[ext=mp4]/best',
            'outtmpl': str(self.download_dir / '%(id)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': True,
            'noplaylist': False,  # 플레이리스트 허용
            'playlistend': 10,    # 최신 10개만 확인
            'writeinfojson': True,
            'skip_download': False,
        }
        
        collected_videos = []
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"🔍 채널에서 영상 다운로드 시작: {channel_url}")
                
                # 플레이리스트 정보 추출
                info = ydl.extract_info(channel_url, download=False)
                
                if not info or 'entries' not in info:
                    print("❌ 채널에서 영상을 찾을 수 없습니다.")
                    return []
                
                entries = [e for e in info['entries'] if e is not None]
                print(f"✅ 총 {len(entries)}개 영상 발견")
                
                downloaded_count = 0
                
                for entry in entries:
                    if downloaded_count >= max_videos:
                        break
                    
                    video_id = entry.get('id')
                    if not video_id:
                        continue
                    
                    # 이미 다운로드한 영상 스킵
                    if video_id in downloaded_ids:
                        print(f"⏭️ 이미 다운로드됨: {video_id}")
                        continue
                    
                    try:
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        print(f"\n📥 [{downloaded_count + 1}/{max_videos}] 다운로드: {video_id}")
                        
                        # 개별 영상 다운로드
                        video_info = ydl.extract_info(video_url, download=True)
                        
                        video_path = self.download_dir / f"{video_id}.mp4"
                        
                        if not video_path.exists():
                            print(f"⚠️ 파일이 생성되지 않음: {video_path}")
                            continue
                        
                        video_data = {
                            'id': video_id,
                            'path': str(video_path),
                            'title': video_info.get('title', '개그콘서트'),
                            'description': video_info.get('description', ''),
                            'duration': video_info.get('duration', 0),
                            'original_url': video_url
                        }
                        
                        collected_videos.append(video_data)
                        self.save_history(video_id)
                        downloaded_count += 1
                        
                        print(f"✅ 다운로드 완료: {video_data['title'][:40]}...")
                        
                    except Exception as e:
                        print(f"⚠️ 영상 다운로드 실패 ({video_id}): {e}")
                        continue
                
        except Exception as e:
            print(f"❌ 채널 접근 실패: {e}")
            return []
        
        print(f"\n✅ 총 {len(collected_videos)}개 영상 수집 완료")
        return collected_videos
