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
            'format': 'best[height<=1920]',
            'noplaylist': False,
            'playlistend': count * 3,  # 여유있게 가져오기
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        
        collected_videos = []
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print("📋 채널에서 최신 Shorts 목록 추출 중...")
                
                channel_info = ydl.extract_info(self.channel_url, download=False)
                
                if not channel_info or 'entries' not in channel_info:
                    print("❌ 채널에서 영상을 찾을 수 없습니다.")
                    return []
                
                # 새로운 영상 필터링
                new_videos = []
                for entry in channel_info['entries']:
                    if entry is None:
                        continue
                    
                    video_id = entry.get('id')
                    if not video_id:
                        continue
                    
                    # 히스토리에 없는 영상만 수집
                    if video_id not in self.downloaded_ids:
                        new_videos.append({
                            'id': video_id,
                            'title': entry.get('title', 'Unknown'),
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'duration': entry.get('duration', 0)
                        })
                        
                        if len(new_videos) >= count:
                            break
                
                if not new_videos:
                    print("⚠️ 새로운 영상이 없습니다. (모두 다운로드 완료)")
                    # ✅ 디버깅: 히스토리 내용 출력
                    print(f"📋 히스토리에 저장된 영상 수: {len(self.downloaded_ids)}")
                    if len(self.downloaded_ids) > 0:
                        print(f"📝 최근 히스토리 샘플 (최대 5개):")
                        for vid_id in list(self.downloaded_ids)[:5]:
                            print(f"   - {vid_id}")
                    return []
                
                print(f"✅ 새로운 영상 {len(new_videos)}개 발견")
            
            # 실제 영상 다운로드
            download_opts = {
                'format': 'best[height<=1920]',
                'outtmpl': 'downloads/%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
            }
            
            os.makedirs('downloads', exist_ok=True)
            
            with yt_dlp.YoutubeDL(download_opts) as ydl:
                for video_data in new_videos:
                    try:
                        print(f"⬇️ 다운로드 중: {video_data['title']} ({video_data['id']})")
                        
                        info = ydl.extract_info(video_data['url'], download=True)
                        video_path = ydl.prepare_filename(info)
                        
                        collected_videos.append({
                            'path': video_path,
                            'id': video_data['id'],
                            'original_title': video_data['title'],
                            'duration': video_data['duration'],
                            'source_url': video_data['url']
                        })
                        
                        # 히스토리에 추가
                        self._save_history(video_data['id'])
                        print(f"✅ 다운로드 완료: {video_path}")
                        
                    except Exception as e:
                        print(f"❌ 다운로드 실패 ({video_data['id']}): {str(e)}")
                        continue
            
            print(f"\n🎉 총 {len(collected_videos)}개 영상 수집 완료!")
            return collected_videos
            
        except Exception as e:
            print(f"❌ 영상 수집 중 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
