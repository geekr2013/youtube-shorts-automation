from pathlib import Path
import subprocess

def add_background_music(video_path, music_path, output_path=None):
    """
    비디오에 배경음악 추가
    
    Args:
        video_path: 원본 비디오 파일 경로
        music_path: 배경음악 파일 경로
        output_path: 출력 파일 경로 (기본값: 원본_with_music.mp4)
        
    Returns:
        출력 파일 경로
    """
    video_path = Path(video_path)
    music_path = Path(music_path)
    
    if output_path is None:
        output_path = video_path.parent / f"{video_path.stem}_with_music{video_path.suffix}"
    else:
        output_path = Path(output_path)
    
    try:
        # 비디오 길이 확인
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
        
        # 배경음악 추가 (비디오 길이만큼 반복/자르기)
        subprocess.run(
            [
                'ffmpeg', '-y',
                '-i', str(video_path),
                '-stream_loop', '-1',  # 음악 무한 반복
                '-i', str(music_path),
                '-t', str(video_duration),  # 비디오 길이만큼만
                '-c:v', 'copy',  # 비디오 코덱 복사 (재인코딩 안함)
                '-c:a', 'aac',  # 오디오 AAC 코덱
                '-b:a', '128k',  # 오디오 비트레이트
                '-filter_complex', '[1:a]volume=0.3[a]',  # 배경음악 볼륨 30%
                '-map', '0:v',  # 비디오 스트림
                '-map', '[a]',  # 오디오 스트림
                '-shortest',  # 짧은 쪽에 맞춤
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
        return video_path  # 실패 시 원본 반환
    except Exception as e:
        print(f"❌ 배경음악 추가 실패: {str(e)}")
        return video_path  # 실패 시 원본 반환
