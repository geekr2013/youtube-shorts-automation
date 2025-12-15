import subprocess
import json
from pathlib import Path

def has_audio(video_path):
    """비디오에 오디오 트랙이 있는지 확인"""
    try:
        # 오디오 스트림 존재 확인
        result = subprocess.run(
            [
                'ffprobe', '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_type',
                '-of', 'json',
                str(video_path)
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        
        data = json.loads(result.stdout)
        has_audio_track = len(data.get('streams', [])) > 0
        
        if not has_audio_track:
            print(f"⚠️ {video_path}: 오디오 트랙 없음")
            return False
            
        # 볼륨 레벨 확인
        result = subprocess.run(
            [
                'ffmpeg', '-i', str(video_path),
                '-af', 'volumedetect',
                '-f', 'null', '-'
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        max_volume = -100.0
        for line in result.stderr.split('\n'):
            if 'max_volume:' in line:
                max_volume = float(line.split(':')[1].strip().split()[0])
                break
        
        print(f"🔊 {video_path}: 최대 볼륨 {max_volume} dB")
        
        # 볼륨이 -60dB 이하면 무음으로 간주
        is_silent = max_volume < -60.0
        if is_silent:
            print(f"🔇 {video_path}: 무음 영상으로 판단")
        
        return not is_silent
        
    except Exception as e:
        print(f"❌ 오디오 감지 오류 ({video_path}): {str(e)}")
        return True  # 에러 시 안전하게 오디오 있다고 가정
