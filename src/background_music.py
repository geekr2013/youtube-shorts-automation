from pathlib import Path
import subprocess

def add_background_music(video_path, music_path, output_path=None):
    """비디오에 배경음악 추가 (에러 내성 강화)"""
    video_path = Path(video_path)
    music_path = Path(music_path)
    
    if not video_path.exists() or not music_path.exists():
        return video_path
        
    if output_path is None:
        output_path = video_path.parent / f"{video_path.stem}_with_music{video_path.suffix}"
    else:
        output_path = Path(output_path)
    
    try:
        # 비디오 길이 추출
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        duration_str = result.stdout.strip()
        video_duration = float(duration_str) if duration_str else 0
        
        if video_duration <= 0:
            return video_path
        
        # 배경음악 합성
        subprocess.run(
            [
                'ffmpeg', '-y', '-i', str(video_path), 
                '-stream_loop', '-1', '-i', str(music_path),
                '-t', str(video_duration),
                '-filter_complex', '[1:a]volume=0.2[bgm];[0:a][bgm]amix=inputs=2:duration=first[a]',
                '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-shortest', str(output_path)
            ],
            capture_output=True, check=True
        )
        return output_path
    except:
        return video_path
