import os
import yt_dlp
from pathlib import Path
from typing import List, Dict
import json
import re
import time
import feedparser

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
    
    def get_videos_from_rss(self, channel_id: str, max_entries: int = 50) -> List[str]:
        """RSS 피드에서 최신 영상 ID 추출"""
        print(f"📡 RSS 피드에서 영상 ID 수집 중...")
        
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        video_ids = []
        
        try:
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                print(f"⚠️ RSS 피드가 비어 있습니다.")
                return []
            
            print(f"✅ RSS에서 {len(feed.entries)}개 항목 발견")
            
            for entry in feed.entries[:max_entries]:
                # YouTube RSS 형식: yt:video:VIDEO_ID
                video_id = entry.id.split(':')[-1] if hasattr(entry, 'id') else None
                if video_id:
                    video_ids.append(video_id)
            
            print(f"📋 추출된 영상 ID: {len(video_ids)}개")
            
        except Exception as e:
            print(f"❌ RSS 피드 파싱 실패: {e}")
        
        return video_ids
    
    def collect_gagconcert_shorts(self, max_videos: int = 3) -> List[Dict]:
        """개그콘서트 쇼츠 수집 - RSS 기반 접근"""
        print(f"\n📥 개그콘서트 쇼츠 수집 시작... (최대 {max_videos}개)")
        
        downloaded_ids = self.load_history()
        print(f"📋 기존 다운로드 이력: {len(downloaded_ids)}개")
        
        # KBS 개그콘서트 채널 ID
        channel_id = "UCzT7nHtzVqwiarTH8sqHaJA"
        
        # ✅ 1단계: RSS에서 최신 영상 ID 수집
        video_ids = self.get_videos_from_rss(channel_id, max_entries=30)
        
        if not video_ids:
            print("❌ RSS에서 영상을 찾을 수 없습니다.")
            return []
        
        # ✅ 2단계: 각 영상의 메타데이터 확인 및 Shorts 필터링
        ydl_opts = {
            'format': 'best[ext=mp4][height<=1080]/best[ext=mp4]/best',
            'outtmpl': str(self.download_dir / '%(id)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': True,
            'writeinfojson': True,
            'skip_download': False,
            'socket_timeout': 30,
            'retries': 3,
        }
        
        collected_videos = []
        downloaded_count = 0
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for idx, video_id in enumerate(video_ids, 1):
                    if downloaded_count >= max_videos:
                        break
                    
                    print(f"\n[{idx}/{len(video_ids)}] 확인 중: {video_id}")
                    
                    # 이미 다운로드한 영상 스킵
                    if video_id in downloaded_ids:
                        print(f"⏭️ 이미 다운로드됨")
                        continue
                    
                    try:
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        
                        # 영상 메타데이터만 먼저 가져오기
                        info = ydl.extract_info(video_url, download=False)
                        
                        if not info:
                            print(f"⚠️ 메타데이터 없음")
                            continue
                        
                        duration = info.get('duration', 0)
                        title = info.get('title', '')
                        
                        print(f"  📹 제목: {title[:50]}...")
                        print(f"  ⏱️ 길이: {duration}초")
                        
                        # Shorts 필터링 (60초 이하만)
                        if duration > 60 or duration == 0:
                            print(f"  ⏭️ Shorts 아님 (길이: {duration}초)")
                            continue
                        
                        # ✅ 실제 다운로드
                        print(f"  📥 다운로드 시작...")
                        ydl.download([video_url])
                        
                        video_path = self.download_dir / f"{video_id}.mp4"
                        
                        if not video_path.exists():
                            print(f"  ⚠️ 파일 생성 실패")
                            continue
                        
                        video_data = {
                            'id': video_id,
                            'path': str(video_path),
                            'title': title,
                            'description': info.get('description', ''),
                            'duration': duration,
                            'original_url': video_url
                        }
                        
                        collected_videos.append(video_data)
                        self.save_history(video_id)
                        downloaded_count += 1
                        
                        print(f"  ✅ 다운로드 완료!")
                        
                        # 서버 부하 방지를 위한 대기
                        time.sleep(2)
                        
                    except Exception as e:
                        print(f"  ⚠️ 영상 처리 실패: {e}")
                        continue
                
        except Exception as e:
            print(f"❌ 수집 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n✅ 총 {len(collected_videos)}개 영상 수집 완료")
        return collected_videos
