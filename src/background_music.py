import subprocess
import os
import json

class BackgroundMusicAdder:
    def __init__(self, music_dir='data/music'):
        """배경음악 디렉토리"""
        self.music_dir = music_dir
        os.makedirs(music_dir, exist_ok=True)
    
    def add_background_music(self, video_path, music_path, output_path, volume=0.2):
        """비디오에 배경음악 추가"""
        try:
            if not os.path.exists(music_path):
                print(f"⚠️ 배경음악 파일 없음: {music_path}")
                return video_path
            
            print(f"🎵 배경음악 추가 중...")
            
            # 비디오 길이 확인
            duration = self._get_video_duration(video_path)
            
            # ffmpeg 명령어: 배경음악을 비디오 길이에 맞춰 반복하고 볼륨 조절
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-stream_loop', '-1',  # 음악 무한 반복
                '-i', music_path,
                '-filter_complex',
                f'[1:a]volume={volume},atrim=0:{duration},asetpts=PTS-STARTPTS[bg]',
                '-map', '0:v',
                '-map', '[bg]',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-shortest',
                '-y',
                output_path
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                timeout=120
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                print(f"✅ 배경음악 추가 완료: {output_path}")
                return output_path
            else:
                print(f"⚠️ 배경음악 추가 실패, 원본 사용")
                return video_path
        
        except Exception as e:
            print(f"❌ 배경음악 추가 오류: {str(e)}")
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
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            print(f"⏱️ 비디오 길이: {duration:.1f}초")
            return duration
        
        except:
            print(f"⚠️ 비디오 길이 감지 실패, 기본값 60초 사용")
            return 60
