import os
import yt_dlp
from pathlib import Path
from typing import List, Dict
import json
import re

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
    
    def get_shorts_video_ids(self, channel_url: str, max_videos: int = 10) -> List[str]:
        """Shorts 탭에서 영상 ID 추출 (yt-dlp 내부 파서 활용)"""
        print(f"🔍 Shorts 탭에서 영상 ID 추출 중...")
        
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',  # 플레이리스트 항목만 추출
            'skip_download': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        
        video_ids = []
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Shorts 탭 URL 변형 시도
                shorts_urls = [
                    channel_url,  # 기본 /shorts
                    channel_url.replace('/shorts', '/streams'),  # 대체 시도
                ]
                
                for url in shorts_urls:
                    try:
                        print(f"  시도 중: {url}")
                        result = ydl.extract_info(url, download=False)
                        
                        if result and 'entries' in result:
                            entries = list(result['entries'])
                            print(f"  ✅ {len(entries)}개 항목 발견")
                            
                            for entry in entries[:max_videos]:
                                if entry and 'id' in entry:
                                    video_ids.append(entry['id'])
                            
                            if video_ids:
                                break  # 성공하면 중단
                    except Exception as e:
                        print(f"  ⚠️ 실패: {e}")
                        continue
                        
        except Exception as e:
            print(f"❌ ID 추출 실패: {e}")
        
        return video_ids
    
    def collect_gagconcert_shorts(self, max_videos: int = 3) -> List[Dict]:
        """개그콘서트 쇼츠 수집 - 검색 기반 접근"""
        print(f"\n📥 개그콘서트 쇼츠 수집 시작... (최대 {max_videos}개)")
        
        downloaded_ids = self.load_history()
        print(f"📋 기존 다운로드 이력: {len(downloaded_ids)}개")
        
        # ✅ 전략 변경: YouTube 검색으로 Shorts 찾기
        search_query = "개그콘서트 #shorts"
        channel_id = "UCzT7nHtzVqwiarTH8sqHaJA"
        
        ydl_opts = {
            'format': 'best[ext=mp4][height<=1080]/best[ext=mp4]/best',
            'outtmpl': str(self.download_dir / '%(id)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': True,
            'writeinfojson': True,
            'skip_download': False,
            'match_filter': lambda info: (
                info.get('duration', 0) <= 60 and 
                info.get('duration', 0) > 0 and
                info.get('channel_id') == channel_id  # KBS 개그콘서트 채널만
            ),
        }
        
        collected_videos = []
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # YouTube 검색 URL
                search_url = f"ytsearch{max_videos * 3}:{search_query}"
                print(f"🔍 YouTube 검색: {search_query}")
                
                # 검색 실행
                search_result = ydl.extract_info(search_url, download=False)
                
                if not search_result or 'entries' not in search_result:
                    print("❌ 검색 결과가 없습니다.")
                    return []
                
                entries = [e for e in search_result['entries'] if e is not None]
                print(f"✅ 검색 결과: {len(entries)}개 발견")
                
                downloaded_count = 0
                
                for entry in entries:
                    if downloaded_count >= max_videos:
                        break
                    
                    video_id = entry.get('id')
                    duration = entry.get('duration', 0)
                    channel_id_check = entry.get('channel_id', '')
                    
                    if not video_id:
                        continue
                    
                    # KBS 개그콘서트 채널 확인
                    if channel_id_check != channel_id:
                        print(f"⏭️ 다른 채널: {entry.get('channel', '')} ({video_id})")
                        continue
                    
                    # 60초 이하만 처리
                    if duration > 60 or duration == 0:
                        print(f"⏭️ Shorts 아님 (길이: {duration}초): {video_id}")
                        continue
                    
                    # 이미 다운로드한 영상 스킵
                    if video_id in downloaded_ids:
                        print(f"⏭️ 이미 다운로드됨: {video_id}")
                        continue
                    
                    try:
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        print(f"\n📥 [{downloaded_count + 1}/{max_videos}] 다운로드: {video_id} ({duration}초)")
                        
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
            print(f"❌ 검색 실패: {e}")
            return []
        
        print(f"\n✅ 총 {len(collected_videos)}개 영상 수집 완료")
        return collected_videos
