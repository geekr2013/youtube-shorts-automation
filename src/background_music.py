from pathlib import Path
import subprocess

def add_background_music(video_path, music_path, output_path=None):
    """비디오에 배경음악 추가"""
    video_path = Path(video_path)
    music_path = Path(music_path)
    
    if output_path is None:
        output_path = video_path.parent / f"{video_path.stem}_with_music{video_path.suffix}"
    else:
        output_path = Path(output_path)
    
    try:
        result = subprocess.run(
            [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(video_path)
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        video_duration = float(result.stdout.strip())
        
        print(f"🎬 비디오 길이: {video_duration:.2f}초")
        
        subprocess.run(
            [
                'ffmpeg', '-y',
                '-i', str(video_path),
                '-stream_loop', '-1',
                '-i', str(music_path),
                '-t', str(video_duration),
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-filter_complex', '[1:a]volume=0.3[a]',
                '-map', '0:v',
                '-map', '[a]',
                '-shortest',
                str(output_path)
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        
        print(f"✅ 배경음악 추가 완료: {output_path.name}")
        return output_path
        
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 오류: {e.stderr.decode('utf-8', errors='ignore')}")
        return video_path
    except Exception as e:
        print(f"❌ 배경음악 추가 실패: {str(e)}")
        return video_path
