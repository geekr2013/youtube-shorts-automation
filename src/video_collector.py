import os
import yt_dlp
from datetime import datetime

class VideoCollector:
    def __init__(self):
        self.channel_url = "https://www.youtube.com/@KBS_Gagconcert/shorts"
        self.history_file = "downloaded_history.txt"
        self.downloaded_ids = self._load_history()
    
    def _load_history(self):
        """다운로드 히스토리 로드"""
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return set(line.strip() for line in f if line.strip())
        return set()
    
    def _save_history(self, video_id):
        """다운로드 히스토리 저장"""
        with open(self.history_file, 'a', encoding='utf-8') as f:
            f.write(f"{video_id}\n")
        self.downloaded_ids.add(video_id)
    
    def collect_videos(self, count=3):
        """개그콘서트 Shorts 최신 영상 수집"""
        print(f"🎬 개그콘서트 Shorts 채널에서 최신 영상 {count}개 수집 시작...")
        
        ydl_opts = {
            'format': 'best[height<=1920]',  # 1080p 이하 (Shorts 최적화)
            'noplaylist': False,
            'extract_flat': True,  # 메타데이터만 먼저 추출
            'quiet': True,
            'no_warnings': True,
        }
        
        collected_videos = []
        
        try:
            # 1단계: 채널에서 최신 Shorts 목록 추출
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print("📋 채널 정보 추출 중...")
                channel_info = ydl.extract_info(self.channel_url, download=False)
                
                if not channel_info or 'entries' not in channel_info:
                    print("❌ 채널에서 영상을 찾을 수 없습니다.")
                    return []
                
                # 2단계: 아직 다운로드하지 않은 영상 필터링
                new_videos = []
                for entry in channel_info['entries']:
                    if entry and 'id' in entry:
                        video_id = entry['id']
                        if video_id not in self.downloaded_ids:
                            new_videos.append(entry)
                            if len(new_videos) >= count:
                                break
                
                if not new_videos:
                    print("⚠️ 새로운 영상이 없습니다. (모두 다운로드 완료)")
                    return []
                
                print(f"✅ 새로운 영상 {len(new_videos)}개 발견")
            
            # 3단계: 실제 영상 다운로드
            download_opts = {
                'format': 'best[height<=1920]',
                'outtmpl': 'downloads/%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
            }
            
            os.makedirs('downloads', exist_ok=True)
            
            with yt_dlp.YoutubeDL(download_opts) as ydl:
                for video_entry in new_videos:
                    try:
                        video_url = f"https://www.youtube.com/watch?v={video_entry['id']}"
                        print(f"⬇️ 다운로드 중: {video_entry.get('title', 'Unknown')} ({video_entry['id']})")
                        
                        info = ydl.extract_info(video_url, download=True)
                        
                        video_path = ydl.prepare_filename(info)
                        
                        # 영상 정보 저장
                        collected_videos.append({
                            'path': video_path,
                            'id': video_entry['id'],
                            'original_title': video_entry.get('title', ''),
                            'duration': info.get('duration', 0),
                            'source_url': video_url
                        })
                        
                        # 히스토리에 추가
                        self._save_history(video_entry['id'])
                        print(f"✅ 다운로드 완료: {video_path}")
                        
                    except Exception as e:
                        print(f"❌ 다운로드 실패 ({video_entry['id']}): {str(e)}")
                        continue
            
            print(f"\n🎉 총 {len(collected_videos)}개 영상 수집 완료!")
            return collected_videos
            
        except Exception as e:
            print(f"❌ 영상 수집 중 오류 발생: {str(e)}")
            return []
