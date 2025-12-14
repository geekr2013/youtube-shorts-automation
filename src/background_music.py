import subprocess
import os

class BackgroundMusicAdder:
    def __init__(self, music_library_dir='data/music'):
        """배경음악 라이브러리 디렉토리"""
        self.music_library_dir = music_library_dir
        os.makedirs(music_library_dir, exist_ok=True)
    
    def add_background_music(self, video_path, music_path, output_path, volume=0.3):
        """비디오에 배경음악 추가"""
        try:
            print(f"🎵 배경음악 추가 중: {video_path}")
            
            # 비디오 길이 확인
            duration = self._get_video_duration(video_path)
            
            # ffmpeg 명령어
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-stream_loop', '-1',  # 음악 반복
                '-i', music_path,
                '-filter_complex',
                f'[1:a]volume={volume},atrim=0:{duration}[bg];[bg]apad[out]',
                '-map', '0:v',
                '-map', '[out]',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',
                '-y',
                output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ 배경음악 추가 완료: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ 배경음악 추가 실패: {str(e)}")
            return video_path
    
    def _get_video_duration(self, video_path):
        """비디오 길이(초) 반환"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            import json
            data = json.loads(result.stdout)
            return float(data['format']['duration'])
            
        except:
            return 60  # 기본값
