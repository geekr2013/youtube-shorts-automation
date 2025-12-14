import subprocess
import json

class AudioDetector:
    @staticmethod
    def has_audio(video_path):
        """비디오에 오디오 트랙이 있는지 확인"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            data = json.loads(result.stdout)
            
            # 오디오 스트림 확인
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    return True
            
            return False
        
        except Exception as e:
            print(f"⚠️ 오디오 감지 실패: {str(e)}")
            return False
    
    @staticmethod
    def has_significant_audio(video_path, threshold_db=-50):
        """의미 있는 오디오가 있는지 확인 (무음 제외)"""
        try:
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-af', 'volumedetect',
                '-f', 'null',
                '-',
                '-hide_banner'
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                stderr=subprocess.STDOUT,
                timeout=30
            )
            output = result.stdout
            
            # mean_volume 추출
            for line in output.split('\n'):
                if 'mean_volume' in line:
                    try:
                        volume = float(line.split(':')[1].strip().split()[0])
                        print(f"📊 평균 볼륨: {volume} dB")
                        return volume > threshold_db
                    except:
                        pass
            
            return True  # 감지 실패 시 안전하게 True 반환
        
        except Exception as e:
            print(f"⚠️ 오디오 볼륨 감지 실패: {str(e)}")
            return True
